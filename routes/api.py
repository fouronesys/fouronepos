from flask import Blueprint, request, jsonify, session
import models
from main import db
from datetime import datetime

bp = Blueprint('api', __name__, url_prefix='/api')


def require_login():
    if 'user_id' not in session:
        return jsonify({'error': 'No autorizado'}), 401
    
    user = models.User.query.get(session['user_id'])
    if not user:
        return jsonify({'error': 'Usuario no encontrado'}), 401
    
    return user


@bp.route('/products')
def get_products():
    user = require_login()
    if not isinstance(user, models.User):
        return user
    
    category_id = request.args.get('category_id')
    query = models.Product.query.filter_by(active=True)
    
    if category_id:
        query = query.filter_by(category_id=category_id)
    
    products = query.all()
    
    return jsonify([{
        'id': p.id,
        'name': p.name,
        'price': p.price,
        'stock': p.stock,
        'category_id': p.category_id
    } for p in products])


@bp.route('/categories')
def get_categories():
    user = require_login()
    if not isinstance(user, models.User):
        return user
    
    categories = models.Category.query.filter_by(active=True).all()
    
    return jsonify([{
        'id': c.id,
        'name': c.name,
        'description': c.description
    } for c in categories])


@bp.route('/tables/<int:table_id>/status', methods=['PUT'])
def update_table_status(table_id):
    user = require_login()
    if not isinstance(user, models.User):
        return user
    
    table = models.Table.query.get_or_404(table_id)
    data = request.get_json()
    
    if 'status' in data:
        table.status = models.TableStatus(data['status'])
        db.session.commit()
    
    return jsonify({'success': True})


@bp.route('/sales', methods=['POST'])
def create_sale():
    user = require_login()
    if not isinstance(user, models.User):
        return user
    
    data = request.get_json()
    
    # Get cash register for this user
    cash_register = models.CashRegister.query.filter_by(user_id=user.id, active=True).first()
    if not cash_register:
        return jsonify({'error': 'No tienes una caja asignada. Contacta al administrador.'}), 400
    
    # Create new sale
    sale = models.Sale()
    sale.user_id = user.id
    sale.cash_register_id = cash_register.id
    sale.table_id = data.get('table_id')
    sale.subtotal = 0
    sale.tax_amount = 0
    sale.total = 0
    sale.status = 'pending'
    
    db.session.add(sale)
    db.session.commit()
    
    return jsonify({
        'id': sale.id,
        'status': sale.status,
        'cash_register_id': cash_register.id,
        'created_at': sale.created_at.isoformat()
    })


@bp.route('/sales/<int:sale_id>/items', methods=['POST'])
def add_sale_item(sale_id):
    user = require_login()
    if not isinstance(user, models.User):
        return user
    
    sale = models.Sale.query.get_or_404(sale_id)
    data = request.get_json()
    
    product = models.Product.query.get(data['product_id'])
    if not product:
        return jsonify({'error': 'Producto no encontrado'}), 404
    
    # Create sale item
    sale_item = models.SaleItem()
    sale_item.sale_id = sale_id
    sale_item.product_id = product.id
    sale_item.quantity = data['quantity']
    sale_item.unit_price = product.price
    sale_item.total_price = product.price * data['quantity']
    
    db.session.add(sale_item)
    
    # Update sale totals
    sale.subtotal += sale_item.total_price
    sale.tax_amount = sale.subtotal * 0.18  # 18% ITBIS
    sale.total = sale.subtotal + sale.tax_amount
    
    db.session.commit()
    
    return jsonify({
        'id': sale_item.id,
        'product_name': product.name,
        'quantity': sale_item.quantity,
        'unit_price': sale_item.unit_price,
        'total_price': sale_item.total_price
    })


@bp.route('/sales/<int:sale_id>/finalize', methods=['POST'])
def finalize_sale(sale_id):
    user = require_login()
    if not isinstance(user, models.User):
        return user
    
    sale = models.Sale.query.get_or_404(sale_id)
    data = request.get_json()
    
    # Check if sale is already finalized
    if sale.status == 'completed':
        return jsonify({'error': 'La venta ya está finalizada'}), 400
    
    # Get NCF type from request (default to consumo)
    ncf_type = data.get('ncf_type', 'consumo')
    payment_method = data.get('payment_method', 'efectivo')
    
    # Get appropriate NCF sequence for this cash register and type
    cash_register = models.CashRegister.query.get(sale.cash_register_id)
    ncf_sequence = models.NCFSequence.query.filter_by(
        cash_register_id=cash_register.id,
        ncf_type=models.NCFType(ncf_type),
        active=True
    ).first()
    
    if not ncf_sequence:
        return jsonify({'error': f'No hay secuencia NCF activa para tipo {ncf_type} en esta caja'}), 400
    
    # Check if sequence has available numbers
    if ncf_sequence.current_number >= ncf_sequence.end_number:
        return jsonify({'error': 'Secuencia NCF agotada. Contacta al administrador.'}), 400
    
    # Generate NCF number
    ncf_number = f"{ncf_sequence.serie}{ncf_sequence.current_number:08d}"
    
    # Update sale with NCF and finalize
    sale.ncf_sequence_id = ncf_sequence.id
    sale.ncf = ncf_number
    sale.payment_method = payment_method
    sale.status = 'completed'
    
    # Increment NCF sequence counter
    ncf_sequence.current_number += 1
    
    # Reduce stock for all sale items
    for sale_item in sale.sale_items:
        product = sale_item.product
        if product.stock >= sale_item.quantity:
            product.stock -= sale_item.quantity
        else:
            return jsonify({'error': f'Stock insuficiente para {product.name}'}), 400
    
    db.session.commit()
    
    return jsonify({
        'id': sale.id,
        'ncf': sale.ncf,
        'total': sale.total,
        'status': sale.status,
        'payment_method': sale.payment_method,
        'created_at': sale.created_at.isoformat()
    })


@bp.route('/sales/<int:sale_id>/cancel', methods=['POST'])
def cancel_sale(sale_id):
    user = require_login()
    if not isinstance(user, models.User):
        return user
    
    sale = models.Sale.query.get_or_404(sale_id)
    data = request.get_json()
    
    if sale.status == 'completed' and sale.ncf:
        # If sale was completed and has NCF, we need to register the cancelled NCF
        cancelled_ncf = models.CancelledNCF()
        cancelled_ncf.ncf = sale.ncf
        cancelled_ncf.ncf_type = sale.ncf_sequence.ncf_type
        cancelled_ncf.reason = data.get('reason', 'Cancelación de venta')
        cancelled_ncf.cancelled_by = user.id
        
        db.session.add(cancelled_ncf)
    
    # Update sale status
    sale.status = 'cancelled'
    
    db.session.commit()
    
    return jsonify({
        'id': sale.id,
        'status': sale.status,
        'message': 'Venta cancelada exitosamente'
    })