from flask import Blueprint, request, jsonify, session, render_template, send_file, abort
import models
from models import db
from datetime import datetime
from sqlalchemy.exc import IntegrityError
from sqlalchemy import text
import time
import random
import os
from receipt_generator import generate_pdf_receipt, generate_thermal_receipt_text
from utils import get_company_info_for_receipt

bp = Blueprint('api', __name__, url_prefix='/api')

# HEAD handlers to prevent log spam from monitoring services
@bp.route('', methods=['HEAD'])
@bp.route('/', methods=['HEAD'])
def api_head():
    """Handle HEAD requests to /api and /api/ - likely from monitoring service"""
    return '', 200


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
    
    # Create new sale (waiters don't need cash registers initially)
    sale = models.Sale()
    sale.user_id = user.id
    sale.table_id = data.get('table_id')
    sale.subtotal = 0
    sale.tax_amount = 0
    sale.total = 0
    sale.status = 'pending'
    
    # Only assign cash register if user has one (cashiers/admins)
    cash_register = models.CashRegister.query.filter_by(user_id=user.id, active=True).first()
    if cash_register:
        sale.cash_register_id = cash_register.id
    
    db.session.add(sale)
    db.session.commit()
    
    return jsonify({
        'id': sale.id,
        'status': sale.status,
        'cash_register_id': sale.cash_register_id,
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
    
    data = request.get_json()
    
    # Get NCF type from request (default to consumo)
    ncf_type = data.get('ncf_type', 'consumo')
    payment_method = data.get('payment_method', 'efectivo')
    
    # CRITICAL FIX: Idempotent sale finalization with proper locking to prevent NCF race conditions
    # This ensures exactly one NCF per sale even under concurrent finalization requests
    try:
        with db.session.begin():
            # Get sale with row-level lock to prevent concurrent modifications
            sale = db.session.query(models.Sale).filter_by(id=sale_id).with_for_update().first()
            
            if not sale:
                raise ValueError('Venta no encontrada')
            
            # IDEMPOTENCY CHECK: If sale is already completed, return existing data
            # This prevents duplicate NCF allocation for the same sale
            if sale.status == 'completed':
                return jsonify({
                    'id': sale.id,
                    'ncf': sale.ncf,
                    'total': sale.total,
                    'status': sale.status,
                    'payment_method': sale.payment_method,
                    'created_at': sale.created_at.isoformat(),
                    'message': 'Venta ya estaba finalizada'
                })
            
            # Validate that sale is in pending status (only pending sales can be finalized)
            if sale.status != 'pending':
                raise ValueError(f'No se puede finalizar una venta con estado {sale.status}')
            
            # Validate stock availability before proceeding with NCF allocation
            # Load sale items with their products for stock validation
            sale_items = db.session.query(models.SaleItem).filter_by(sale_id=sale_id).all()
            for sale_item in sale_items:
                product = sale_item.product
                if product.stock < sale_item.quantity:
                    raise ValueError(f'Stock insuficiente para {product.name}')
            
            # SALE REASSIGNMENT: If sale doesn't have cash register (waiter-created), assign finalizing user's cash register
            if not sale.cash_register_id:
                # Get cash register for the finalizing user (must be cashier/admin)
                user_cash_register = db.session.query(models.CashRegister).filter_by(
                    user_id=user.id, 
                    active=True
                ).first()
                
                if not user_cash_register:
                    raise ValueError('Solo usuarios con caja asignada pueden finalizar ventas. Contacta al administrador.')
                
                # Assign the cash register to the sale for NCF generation
                sale.cash_register_id = user_cash_register.id
            
            # Get NCF sequence with row-level lock to prevent concurrent access
            ncf_sequence = db.session.query(models.NCFSequence).filter_by(
                cash_register_id=sale.cash_register_id,
                ncf_type=models.NCFType(ncf_type),
                active=True
            ).with_for_update().first()
            
            if not ncf_sequence:
                raise ValueError(f'No hay secuencia NCF activa para tipo {ncf_type} en esta caja')
            
            # Check if sequence is exhausted (treat end_number as inclusive)
            if ncf_sequence.current_number > ncf_sequence.end_number:
                raise ValueError('Secuencia NCF agotada. Contacta al administrador.')
            
            # Generate NCF number using current number
            ncf_number = f"{ncf_sequence.serie}{ncf_sequence.current_number:08d}"
            
            # Increment counter for next use
            ncf_sequence.current_number += 1
            
            # Update sale with NCF and finalize (atomic state transition from pending to completed)
            sale.ncf_sequence_id = ncf_sequence.id
            sale.ncf = ncf_number
            sale.payment_method = payment_method
            sale.status = 'completed'
            
            # Reduce stock for all sale items
            for sale_item in sale_items:
                product = sale_item.product
                product.stock -= sale_item.quantity
            
            # Transaction commits automatically at the end of this block
            # If ANY part fails, everything rolls back and no NCF is consumed
        
        # Return success response
        return jsonify({
            'id': sale.id,
            'ncf': sale.ncf,
            'total': sale.total,
            'status': sale.status,
            'payment_method': sale.payment_method,
            'created_at': sale.created_at.isoformat()
        })
        
    except ValueError as e:
        # Handle business logic errors (no sale, wrong status, no NCF sequence, exhausted sequence, stock issues)
        return jsonify({'error': str(e)}), 400
        
    except IntegrityError as e:
        # Handle database constraint violations
        if 'unique constraint' in str(e).lower() and 'ncf' in str(e).lower():
            return jsonify({'error': 'Error de concurrencia al generar NCF. Intente nuevamente.'}), 500
        else:
            return jsonify({'error': f'Error de integridad de datos: {str(e)}'}), 500
            
    except Exception as e:
        # Handle other unexpected errors
        return jsonify({'error': f'Error interno: {str(e)}'}), 500


@bp.route('/sales/<int:sale_id>/cancel', methods=['POST'])
def cancel_sale(sale_id):
    user = require_login()
    if not isinstance(user, models.User):
        return user
    
    data = request.get_json() or {}
    reason = data.get('reason', 'Cancelación de venta')
    
    # CRITICAL FIX: Atomic cancellation with proper locking to prevent race conditions with finalize_sale
    # This ensures DGII fiscal audit compliance by preventing NCF state inconsistencies
    try:
        with db.session.begin():
            # Get sale with row-level lock to prevent concurrent modifications
            sale = db.session.query(models.Sale).filter_by(id=sale_id).with_for_update().first()
            
            if not sale:
                raise ValueError('Venta no encontrada')
            
            # IDEMPOTENCY CHECK: If sale is already cancelled, return existing state
            # This prevents duplicate CancelledNCF records and ensures safe retry behavior
            if sale.status == 'cancelled':
                # Check if CancelledNCF record exists for this sale's NCF
                cancelled_ncf_exists = False
                if sale.ncf:
                    existing_cancelled = db.session.query(models.CancelledNCF).filter_by(ncf=sale.ncf).first()
                    cancelled_ncf_exists = existing_cancelled is not None
                
                return jsonify({
                    'id': sale.id,
                    'status': sale.status,
                    'ncf': sale.ncf,
                    'cancelled_ncf_exists': cancelled_ncf_exists,
                    'message': 'Venta ya estaba cancelada'
                })
            
            # Validate that sale can be cancelled (only pending or completed sales)
            if sale.status not in ['pending', 'completed']:
                raise ValueError(f'No se puede cancelar una venta con estado {sale.status}')
            
            # FISCAL AUDIT COMPLIANCE: Create CancelledNCF record if sale has NCF
            # This is CRITICAL for DGII compliance - every NCF cancellation must be recorded
            cancelled_ncf_created = False
            if sale.status == 'completed' and sale.ncf:
                # Check if CancelledNCF already exists (handle edge cases)
                existing_cancelled = db.session.query(models.CancelledNCF).filter_by(ncf=sale.ncf).first()
                
                if not existing_cancelled:
                    # Create new CancelledNCF record for fiscal audit trail
                    cancelled_ncf = models.CancelledNCF()
                    cancelled_ncf.ncf = sale.ncf
                    cancelled_ncf.ncf_type = sale.ncf_sequence.ncf_type
                    cancelled_ncf.reason = reason
                    cancelled_ncf.cancelled_by = user.id
                    
                    db.session.add(cancelled_ncf)
                    cancelled_ncf_created = True
            
            # Atomic state transition to cancelled
            sale.status = 'cancelled'
            
            # Transaction commits automatically at the end of this block
            # If ANY part fails, everything rolls back and no inconsistent state occurs
        
        # Return success response with fiscal audit information
        return jsonify({
            'id': sale.id,
            'status': sale.status,
            'ncf': sale.ncf,
            'cancelled_ncf_created': cancelled_ncf_created,
            'message': 'Venta cancelada exitosamente'
        })
        
    except ValueError as e:
        # Handle business logic errors (no sale, wrong status)
        return jsonify({'error': str(e)}), 400
        
    except IntegrityError as e:
        # Handle database constraint violations (e.g., duplicate CancelledNCF)
        if 'unique constraint' in str(e).lower() and 'cancelled_ncfs' in str(e).lower():
            return jsonify({'error': 'NCF ya fue cancelado previamente. Operación duplicada detectada.'}), 409
        else:
            return jsonify({'error': f'Error de integridad de datos: {str(e)}'}), 500
            
    except Exception as e:
        # Handle other unexpected errors
        return jsonify({'error': f'Error interno: {str(e)}'}), 500


@bp.route('/sales/<int:sale_id>/items/<int:item_id>', methods=['DELETE'])
def remove_sale_item(sale_id, item_id):
    user = require_login()
    if not isinstance(user, models.User):
        return user
    
    try:
        with db.session.begin():
            # Get sale and item with locks
            sale = db.session.query(models.Sale).filter_by(id=sale_id).with_for_update().first()
            sale_item = db.session.query(models.SaleItem).filter_by(id=item_id, sale_id=sale_id).with_for_update().first()
            
            if not sale:
                raise ValueError('Venta no encontrada')
            
            if not sale_item:
                raise ValueError('Producto no encontrado en la venta')
            
            # Only allow removing items from pending sales
            if sale.status != 'pending':
                raise ValueError('Solo se pueden modificar ventas pendientes')
            
            # Remove item and update totals
            item_total = sale_item.total_price
            db.session.delete(sale_item)
            
            # Recalculate sale totals
            sale.subtotal -= item_total
            sale.tax_amount = sale.subtotal * 0.18
            sale.total = sale.subtotal + sale.tax_amount
            
            # Ensure totals don't go negative
            if sale.subtotal < 0:
                sale.subtotal = 0
                sale.tax_amount = 0
                sale.total = 0
        
        return jsonify({'success': True, 'new_total': sale.total})
    
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        return jsonify({'error': f'Error interno: {str(e)}'}), 500


@bp.route('/sales/<int:sale_id>/items/<int:item_id>/quantity', methods=['PUT'])
def update_item_quantity(sale_id, item_id):
    user = require_login()
    if not isinstance(user, models.User):
        return user
    
    data = request.get_json()
    new_quantity = data.get('quantity', 1)
    
    if new_quantity <= 0:
        return jsonify({'error': 'La cantidad debe ser mayor a 0'}), 400
    
    try:
        with db.session.begin():
            # Get sale and item with locks
            sale = db.session.query(models.Sale).filter_by(id=sale_id).with_for_update().first()
            sale_item = db.session.query(models.SaleItem).filter_by(id=item_id, sale_id=sale_id).with_for_update().first()
            
            if not sale:
                raise ValueError('Venta no encontrada')
            
            if not sale_item:
                raise ValueError('Producto no encontrado en la venta')
            
            # Only allow modifying pending sales
            if sale.status != 'pending':
                raise ValueError('Solo se pueden modificar ventas pendientes')
            
            # Check stock availability
            product = sale_item.product
            if product.stock < new_quantity:
                raise ValueError(f'Stock insuficiente para {product.name}. Disponible: {product.stock}')
            
            # Update quantity and totals
            old_total = sale_item.total_price
            sale_item.quantity = new_quantity
            sale_item.total_price = sale_item.unit_price * new_quantity
            
            # Update sale totals
            sale.subtotal = sale.subtotal - old_total + sale_item.total_price
            sale.tax_amount = sale.subtotal * 0.18
            sale.total = sale.subtotal + sale.tax_amount
        
        return jsonify({
            'success': True,
            'new_quantity': sale_item.quantity,
            'new_item_total': sale_item.total_price,
            'new_sale_total': sale.total
        })
    
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        return jsonify({'error': f'Error interno: {str(e)}'}), 500


@bp.route('/tables/<int:table_id>/close', methods=['POST'])
def close_table_properly(table_id):
    """Properly close a table by finalizing or cancelling its pending sale"""
    user = require_login()
    if not isinstance(user, models.User):
        return user
    
    data = request.get_json() or {}
    action = data.get('action', 'finalize')  # 'finalize' or 'cancel'
    
    try:
        with db.session.begin():
            # Get table and any pending sale
            table = db.session.query(models.Table).filter_by(id=table_id).with_for_update().first()
            pending_sale = db.session.query(models.Sale).filter_by(
                table_id=table_id, 
                status='pending'
            ).with_for_update().first()
            
            if not table:
                raise ValueError('Mesa no encontrada')
            
            if not pending_sale:
                # No pending sale, just mark table as available
                table.status = models.TableStatus.AVAILABLE
                return jsonify({
                    'success': True,
                    'message': 'Mesa liberada (no había venta pendiente)',
                    'table_status': 'available'
                })
            
            # Handle based on action
            if action == 'cancel':
                # Cancel the sale
                pending_sale.status = 'cancelled'
                table.status = models.TableStatus.AVAILABLE
                return jsonify({
                    'success': True,
                    'message': 'Venta cancelada y mesa liberada',
                    'table_status': 'available',
                    'sale_status': 'cancelled'
                })
            else:
                # For finalization, only cashiers/admins can do this
                # Waiters must hand over to cashier for finalization
                if user.role.value == 'mesero':
                    raise ValueError('Los meseros deben entregar la mesa al cajero para finalizar. Use "Enviar a Caja" en su lugar.')
                
                # This is just the table closing part - actual sale finalization happens via /sales/{id}/finalize
                # Just mark the table as ready for finalization
                return jsonify({
                    'success': True,
                    'message': 'Mesa lista para finalización por cajero',
                    'sale_id': pending_sale.id,
                    'requires_finalization': True
                })
        
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        return jsonify({'error': f'Error interno: {str(e)}'}), 500


@bp.route('/sales/<int:sale_id>/kitchen-status', methods=['PUT'])
def update_kitchen_status(sale_id):
    """Update the kitchen/order status of a sale"""
    user = require_login()
    if not isinstance(user, models.User):
        return user
    
    data = request.get_json()
    new_status = data.get('order_status')
    
    if not new_status:
        return jsonify({'error': 'order_status es requerido'}), 400
    
    # Validate order status
    valid_statuses = [status.value for status in models.OrderStatus]
    if new_status not in valid_statuses:
        return jsonify({'error': f'Estado inválido. Debe ser uno de: {valid_statuses}'}), 400
    
    try:
        with db.session.begin():
            sale = db.session.query(models.Sale).filter_by(id=sale_id).with_for_update().first()
            
            if not sale:
                raise ValueError('Venta no encontrada')
            
            # Only allow updating order status for pending sales
            if sale.status != 'pending':
                raise ValueError('Solo se puede actualizar el estado de pedidos pendientes')
            
            # Update order status
            sale.order_status = models.OrderStatus(new_status)
            
        return jsonify({
            'success': True,
            'sale_id': sale.id,
            'order_status': sale.order_status.value,
            'message': f'Estado del pedido actualizado a: {sale.order_status.value}'
        })
        
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        return jsonify({'error': f'Error interno: {str(e)}'}), 500


@bp.route('/sales/<int:sale_id>/send-to-kitchen', methods=['POST'])
def send_to_kitchen(sale_id):
    """Send sale to kitchen - updates order status to sent_to_kitchen"""
    user = require_login()
    if not isinstance(user, models.User):
        return user
    
    try:
        with db.session.begin():
            sale = db.session.query(models.Sale).filter_by(id=sale_id).with_for_update().first()
            
            if not sale:
                raise ValueError('Venta no encontrada')
            
            # Only allow sending pending sales to kitchen
            if sale.status != 'pending':
                raise ValueError('Solo se pueden enviar a cocina pedidos pendientes')
            
            # Check if sale has items
            if not sale.sale_items:
                raise ValueError('No se puede enviar un pedido vacío a cocina')
            
            # Update order status to sent_to_kitchen
            sale.order_status = models.OrderStatus.SENT_TO_KITCHEN
            
        return jsonify({
            'success': True,
            'sale_id': sale.id,
            'order_status': sale.order_status.value,
            'table_id': sale.table_id,
            'total': sale.total,
            'message': 'Pedido enviado a cocina exitosamente'
        })
        
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        return jsonify({'error': f'Error interno: {str(e)}'}), 500


@bp.route('/tables')
def get_tables():
    """Get tables filtered by status"""
    user = require_login()
    if not isinstance(user, models.User):
        return user
    
    # Get status filter from query params
    status_filter = request.args.get('status')
    
    query = models.Table.query
    
    if status_filter:
        if status_filter == 'available':
            query = query.filter_by(status=models.TableStatus.AVAILABLE)
        elif status_filter == 'occupied':
            query = query.filter_by(status=models.TableStatus.OCCUPIED)
        elif status_filter == 'reserved':
            query = query.filter_by(status=models.TableStatus.RESERVED)
    
    tables = query.order_by(models.Table.number).all()
    
    return jsonify([{
        'id': table.id,
        'number': table.number,
        'name': table.name,
        'capacity': table.capacity,
        'status': table.status.value
    } for table in tables])


# Receipt Generation Routes
@bp.route('/receipts/<int:sale_id>/view')
def view_receipt(sale_id):
    """Show receipt in HTML format for viewing/printing"""
    user = require_login()
    if not isinstance(user, models.User):
        return user
    
    # Get sale data
    sale = models.Sale.query.get_or_404(sale_id)
    
    # FISCAL COMPLIANCE: Only allow receipts for completed sales with NCF
    if sale.status != 'completed':
        return jsonify({'error': 'Solo se pueden generar recibos para ventas completadas'}), 400
    
    if not sale.ncf:
        return jsonify({'error': 'Esta venta no tiene NCF válido para generar recibo fiscal'}), 400
    
    # SECURITY: Verify user has access to this sale
    if user.role.value not in ['administrador', 'cajero']:
        return jsonify({'error': 'No tienes permisos para ver recibos'}), 403
    
    if user.role.value == 'cajero':
        # For cashiers, verify cash register ownership and it exists
        if not sale.cash_register:
            return jsonify({'error': 'Esta venta no tiene caja registradora asignada'}), 400
        if sale.cash_register.user_id != user.id:
            return jsonify({'error': 'No tienes acceso a esta venta'}), 403
    
    # Get sale items
    sale_items = models.SaleItem.query.filter_by(sale_id=sale_id).all()
    
    # Prepare sale data
    sale_data = _prepare_sale_data_for_receipt(sale, sale_items)
    
    # Get company info
    company_info = get_company_info_for_receipt()
    
    return render_template('receipt_view.html', 
                         sale_data=sale_data, 
                         company_info=company_info)


@bp.route('/receipts/<int:sale_id>/pdf')
def generate_receipt_pdf(sale_id):
    """Generate and download PDF receipt"""
    user = require_login()
    if not isinstance(user, models.User):
        return user
    
    # Get sale data
    sale = models.Sale.query.get_or_404(sale_id)
    
    # FISCAL COMPLIANCE: Only allow receipts for completed sales with NCF
    if sale.status != 'completed':
        return jsonify({'error': 'Solo se pueden generar recibos para ventas completadas'}), 400
    
    if not sale.ncf:
        return jsonify({'error': 'Esta venta no tiene NCF válido para generar recibo fiscal'}), 400
    
    # SECURITY: Verify user has access to this sale
    if user.role.value not in ['administrador', 'cajero']:
        return jsonify({'error': 'No tienes permisos para generar recibos'}), 403
    
    if user.role.value == 'cajero':
        # For cashiers, verify cash register ownership and it exists
        if not sale.cash_register:
            return jsonify({'error': 'Esta venta no tiene caja registradora asignada'}), 400
        if sale.cash_register.user_id != user.id:
            return jsonify({'error': 'No tienes acceso a esta venta'}), 403
    
    # Get sale items
    sale_items = models.SaleItem.query.filter_by(sale_id=sale_id).all()
    
    # Prepare sale data for PDF generation
    sale_data = _prepare_sale_data_for_receipt(sale, sale_items)
    
    try:
        # Generate PDF
        pdf_path = generate_pdf_receipt(sale_data)
        
        # Send file
        return send_file(
            pdf_path,
            as_attachment=True,
            download_name=f'recibo_fiscal_{sale_id}_{datetime.now().strftime("%Y%m%d_%H%M%S")}.pdf',
            mimetype='application/pdf'
        )
        
    except Exception as e:
        return jsonify({'error': f'Error generando PDF: {str(e)}'}), 500


@bp.route('/receipts/<int:sale_id>/thermal')
def generate_receipt_thermal(sale_id):
    """Generate thermal receipt text for ESC/POS printers"""
    user = require_login()
    if not isinstance(user, models.User):
        return user
    
    # Get sale data
    sale = models.Sale.query.get_or_404(sale_id)
    
    # FISCAL COMPLIANCE: Only allow receipts for completed sales with NCF
    if sale.status != 'completed':
        return jsonify({'error': 'Solo se pueden generar recibos para ventas completadas'}), 400
    
    if not sale.ncf:
        return jsonify({'error': 'Esta venta no tiene NCF válido para generar recibo fiscal'}), 400
    
    # SECURITY: Verify user has access to this sale
    if user.role.value not in ['administrador', 'cajero']:
        return jsonify({'error': 'No tienes permisos para generar recibos'}), 403
    
    if user.role.value == 'cajero':
        # For cashiers, verify cash register ownership and it exists  
        if not sale.cash_register:
            return jsonify({'error': 'Esta venta no tiene caja registradora asignada'}), 400
        if sale.cash_register.user_id != user.id:
            return jsonify({'error': 'No tienes acceso a esta venta'}), 403
    
    # Get sale items
    sale_items = models.SaleItem.query.filter_by(sale_id=sale_id).all()
    
    # Prepare sale data
    sale_data = _prepare_sale_data_for_receipt(sale, sale_items)
    
    try:
        # Generate thermal receipt text
        receipt_text = generate_thermal_receipt_text(sale_data)
        
        return jsonify({
            'success': True,
            'receipt_text': receipt_text,
            'sale_id': sale_id
        })
        
    except Exception as e:
        return jsonify({'error': f'Error generando recibo térmico: {str(e)}'}), 500


def _prepare_sale_data_for_receipt(sale, sale_items):
    """Helper function to prepare sale data for receipt generation"""
    
    # Calculate totals
    subtotal = sum(item.quantity * item.price for item in sale_items)
    tax_amount = subtotal * 0.18  # 18% ITBIS
    total = subtotal + tax_amount
    
    # Prepare sale data
    sale_data = {
        'id': sale.id,
        'created_at': sale.created_at,
        'ncf': sale.ncf,
        'total': total,
        'subtotal': subtotal,
        'tax_amount': tax_amount,
        'payment_method': sale.payment_method,
        'payment_method_display': {
            'efectivo': 'Efectivo',
            'tarjeta': 'Tarjeta',
            'transferencia': 'Transferencia'
        }.get(sale.payment_method, sale.payment_method.title()),
        'cashier_name': sale.user.name if sale.user else None,
        'ncf_type_display': _get_ncf_type_display(sale.ncf) if sale.ncf else None,
        'items': []
    }
    
    # Add items
    for item in sale_items:
        sale_data['items'].append({
            'quantity': item.quantity,
            'product_name': item.product.name,
            'name': item.product.name,  # Alternative name field
            'price': item.price
        })
    
    return sale_data


def _get_ncf_type_display(ncf):
    """Helper function to get NCF type display name"""
    if not ncf:
        return None
    
    if ncf.startswith('B'):
        return 'Crédito Fiscal'
    elif ncf.startswith('E'):
        return 'Consumidor Final'
    elif ncf.startswith('P'):
        return 'Pagos al Exterior'
    elif ncf.startswith('A'):
        return 'Comprobante de Ingreso'
    elif ncf.startswith('F'):
        return 'Facturas de Consumo'
    elif ncf.startswith('G'):
        return 'Gastos Menores'
    elif ncf.startswith('K'):
        return 'Único de Ingresos'
    elif ncf.startswith('L'):
        return 'Liquidación'
    else:
        return 'Comprobante Fiscal'