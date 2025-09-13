from flask import Blueprint, render_template, request, redirect, url_for, session, flash, jsonify
import models
from models import db
from datetime import datetime
import utils

bp = Blueprint('inventory', __name__, url_prefix='/inventory')


def require_admin():
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))
    
    user = models.User.query.get(session['user_id'])
    if not user or user.role.value != 'ADMINISTRADOR':
        flash('Solo los administradores pueden acceder al inventario', 'error')
        return redirect(url_for('admin.dashboard'))
    
    return user


def require_admin_or_manager():
    """Allow admin or manager access to inventory"""
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))
    
    user = models.User.query.get(session['user_id'])
    if not user or user.role.value not in ['ADMINISTRADOR', 'GERENTE']:
        flash('Solo administradores y gerentes pueden acceder al inventario', 'error')
        return redirect(url_for('admin.dashboard'))
    
    return user


@bp.route('/products')
def products():
    user = require_admin_or_manager()
    if not isinstance(user, models.User):
        return user
    
    # Get all products with their categories
    products = models.Product.query.join(models.Category).filter(
        models.Product.active == True
    ).order_by(models.Category.name, models.Product.name).all()
    
    categories = models.Category.query.filter_by(active=True).order_by(models.Category.name).all()
    
    # Calculate low stock count for inventoriable products
    low_stock_count = sum(1 for product in products 
                         if product.product_type == 'inventariable' and product.stock <= product.min_stock)
    
    return render_template('inventory/products.html', 
                         products=products, 
                         categories=categories,
                         low_stock_count=low_stock_count)


@bp.route('/suppliers')
def suppliers():
    user = require_admin_or_manager()
    if not isinstance(user, models.User):
        return user
    
    suppliers = models.Supplier.query.filter_by(active=True).all()
    return render_template('inventory/suppliers.html', suppliers=suppliers)


@bp.route('/suppliers/<int:supplier_id>')
def supplier_detail(supplier_id):
    user = require_admin_or_manager()
    if not isinstance(user, models.User):
        return user
    
    supplier = models.Supplier.query.get_or_404(supplier_id)
    purchases = models.Purchase.query.filter_by(supplier_id=supplier_id).order_by(models.Purchase.created_at.desc()).all()
    
    return render_template('inventory/supplier_detail.html', supplier=supplier, purchases=purchases)


@bp.route('/purchases')
def purchases():
    user = require_admin_or_manager()
    if not isinstance(user, models.User):
        return user
    
    purchases = models.Purchase.query.order_by(models.Purchase.created_at.desc()).all()
    suppliers = models.Supplier.query.filter_by(active=True).all()
    
    return render_template('inventory/purchases.html', purchases=purchases, suppliers=suppliers)


@bp.route('/purchases/<int:purchase_id>')
def purchase_detail(purchase_id):
    user = require_admin_or_manager()
    if not isinstance(user, models.User):
        return user
    
    purchase = models.Purchase.query.get_or_404(purchase_id)
    return render_template('inventory/purchase_detail.html', purchase=purchase)


@bp.route('/stock-alerts')
def stock_alerts():
    user = require_admin_or_manager()
    if not isinstance(user, models.User):
        return user
    
    # Get products with low stock (only inventariables)
    low_stock_products = models.Product.query.filter(
        models.Product.stock <= models.Product.min_stock,
        models.Product.active == True,
        models.Product.product_type == 'inventariable'
    ).all()
    
    # Get products with very low stock (less than half of minimum, only inventariables)
    critical_stock_products = models.Product.query.filter(
        models.Product.stock <= (models.Product.min_stock / 2),
        models.Product.active == True,
        models.Product.product_type == 'inventariable'
    ).all()
    
    return render_template('inventory/stock_alerts.html', 
                         low_stock_products=low_stock_products,
                         critical_stock_products=critical_stock_products)


# API Routes for AJAX operations
@bp.route('/api/products', methods=['POST'])
def create_product():
    user = require_admin()
    if not isinstance(user, models.User):
        return jsonify({'error': 'No autorizado'}), 401
    
    # Validar CSRF
    from routes.admin import validate_csrf_token
    if not validate_csrf_token():
        return jsonify({'error': 'Token de seguridad inválido'}), 400
    
    data = request.get_json()
    
    try:
        product = models.Product()
        product.name = data['name']
        product.description = data.get('description', '')
        product.category_id = data['category_id']
        product.cost = float(data['cost'])
        product.price = float(data['price'])
        product.tax_rate = float(data.get('tax_rate', 0.18))
        product.product_type = data.get('product_type', 'inventariable')
        
        # Solo manejar stock para productos inventariables
        if product.product_type == 'inventariable':
            product.stock = int(data.get('stock', 0))
            product.min_stock = int(data.get('min_stock', 5))
        else:  # consumible
            product.stock = 0
            product.min_stock = 0
            
        product.active = data.get('active', True)
        
        db.session.add(product)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'product': {
                'id': product.id,
                'name': product.name,
                'description': product.description,
                'price': product.price,
                'stock': product.stock
            }
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 400


@bp.route('/api/products/<int:product_id>', methods=['PUT'])
def update_product(product_id):
    user = require_admin()
    if not isinstance(user, models.User):
        return jsonify({'error': 'No autorizado'}), 401
    
    # Validar CSRF
    from routes.admin import validate_csrf_token
    if not validate_csrf_token():
        return jsonify({'error': 'Token de seguridad inválido'}), 400
    
    product = models.Product.query.get_or_404(product_id)
    data = request.get_json()
    
    try:
        product.name = data['name']
        product.description = data.get('description', '')
        product.category_id = data['category_id']
        product.cost = float(data['cost'])
        product.price = float(data['price'])
        product.tax_rate = float(data.get('tax_rate', 0.18))
        product.product_type = data.get('product_type', 'inventariable')
        
        # Solo manejar stock para productos inventariables
        if product.product_type == 'inventariable':
            product.stock = int(data.get('stock', 0))
            product.min_stock = int(data.get('min_stock', 5))
        else:  # consumible
            product.stock = 0
            product.min_stock = 0
            
        product.active = data.get('active', True)
        
        db.session.commit()
        
        return jsonify({'success': True})
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 400


@bp.route('/api/suppliers', methods=['POST'])
def create_supplier():
    user = require_admin()
    if not isinstance(user, models.User):
        return jsonify({'error': 'No autorizado'}), 401
    
    data = request.get_json()
    
    # Validate required fields
    if not data or not data.get('name'):
        return jsonify({'error': 'El nombre del proveedor es requerido'}), 400
    
    # Validate RNC if provided
    rnc = data.get('rnc', '').strip()
    if rnc:
        rnc_validation = utils.validate_rnc(rnc)
        if not rnc_validation['valid']:
            return jsonify({'error': rnc_validation['message']}), 400
        rnc = rnc_validation['formatted']
    
    # Validate phone if provided
    phone = data.get('phone', '').strip()
    if phone:
        phone_validation = utils.validate_phone_rd(phone)
        if not phone_validation['valid']:
            return jsonify({'error': phone_validation['message']}), 400
        phone = phone_validation['formatted']
    
    # Validate email if provided
    email = data.get('email', '').strip()
    if email:
        email_validation = utils.validate_email(email)
        if not email_validation['valid']:
            return jsonify({'error': email_validation['message']}), 400
        email = email_validation['formatted']
    
    try:
        # Check if RNC already exists (if provided)
        if rnc:
            existing_supplier = models.Supplier.query.filter_by(rnc=rnc, active=True).first()
            if existing_supplier:
                return jsonify({'error': f'Ya existe un proveedor activo con RNC {rnc}'}), 400
        
        supplier = models.Supplier()
        supplier.name = utils.sanitize_input(data['name'], 100)
        supplier.rnc = rnc
        supplier.contact_person = utils.sanitize_input(data.get('contact_person', ''), 100)
        supplier.phone = phone
        supplier.email = email
        supplier.address = utils.sanitize_input(data.get('address', ''), 500)
        supplier.active = data.get('active', True)
        
        db.session.add(supplier)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'supplier_id': supplier.id,
            'message': 'Proveedor creado exitosamente'
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 400


@bp.route('/api/suppliers/<int:supplier_id>', methods=['PUT'])
def update_supplier(supplier_id):
    user = require_admin()
    if not isinstance(user, models.User):
        return jsonify({'error': 'No autorizado'}), 401
    
    supplier = models.Supplier.query.get_or_404(supplier_id)
    data = request.get_json()
    
    # Validate required fields
    if not data or not data.get('name'):
        return jsonify({'error': 'El nombre del proveedor es requerido'}), 400
    
    # Validate RNC if provided
    rnc = data.get('rnc', '').strip()
    if rnc:
        rnc_validation = utils.validate_rnc(rnc)
        if not rnc_validation['valid']:
            return jsonify({'error': rnc_validation['message']}), 400
        rnc = rnc_validation['formatted']
        
        # Check if RNC already exists in another active supplier
        existing_supplier = models.Supplier.query.filter(
            models.Supplier.rnc == rnc,
            models.Supplier.active == True,
            models.Supplier.id != supplier_id
        ).first()
        if existing_supplier:
            return jsonify({'error': f'Ya existe otro proveedor activo con RNC {rnc}'}), 400
    
    # Validate phone if provided
    phone = data.get('phone', '').strip()
    if phone:
        phone_validation = utils.validate_phone_rd(phone)
        if not phone_validation['valid']:
            return jsonify({'error': phone_validation['message']}), 400
        phone = phone_validation['formatted']
    
    # Validate email if provided
    email = data.get('email', '').strip()
    if email:
        email_validation = utils.validate_email(email)
        if not email_validation['valid']:
            return jsonify({'error': email_validation['message']}), 400
        email = email_validation['formatted']
    
    try:
        supplier.name = utils.sanitize_input(data['name'], 100)
        supplier.rnc = rnc
        supplier.contact_person = utils.sanitize_input(data.get('contact_person', ''), 100)
        supplier.phone = phone
        supplier.email = email
        supplier.address = utils.sanitize_input(data.get('address', ''), 500)
        supplier.active = data.get('active', True)
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'Proveedor actualizado exitosamente'
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 400


@bp.route('/api/suppliers/<int:supplier_id>', methods=['GET'])
def get_supplier(supplier_id):
    user = require_admin()
    if not isinstance(user, models.User):
        return jsonify({'error': 'No autorizado'}), 401
    
    supplier = models.Supplier.query.get_or_404(supplier_id)
    
    return jsonify({
        'id': supplier.id,
        'name': supplier.name,
        'rnc': supplier.rnc,
        'contact_person': supplier.contact_person,
        'phone': supplier.phone,
        'email': supplier.email,
        'address': supplier.address,
        'active': supplier.active,
        'created_at': supplier.created_at.isoformat() if supplier.created_at else None
    })


@bp.route('/api/suppliers/<int:supplier_id>', methods=['DELETE'])
def delete_supplier(supplier_id):
    user = require_admin()
    if not isinstance(user, models.User):
        return jsonify({'error': 'No autorizado'}), 401
    
    supplier = models.Supplier.query.get_or_404(supplier_id)
    
    try:
        # Check if supplier has purchases
        purchase_count = models.Purchase.query.filter_by(supplier_id=supplier_id).count()
        
        if purchase_count > 0:
            # Don't delete, just deactivate if has purchases
            supplier.active = False
            db.session.commit()
            return jsonify({
                'success': True,
                'message': f'Proveedor desactivado (tiene {purchase_count} compras registradas)'
            })
        else:
            # Safe to delete if no purchases
            db.session.delete(supplier)
            db.session.commit()
            return jsonify({
                'success': True,
                'message': 'Proveedor eliminado exitosamente'
            })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 400


@bp.route('/api/purchases', methods=['POST'])
def create_purchase():
    user = require_admin()
    if not isinstance(user, models.User):
        return jsonify({'error': 'No autorizado'}), 401
    
    data = request.get_json()
    
    # Comprehensive input validation
    if not data:
        return jsonify({'error': 'Datos no proporcionados'}), 400
    
    # Validate required fields
    if not data.get('supplier_id'):
        return jsonify({'error': 'ID del proveedor es requerido'}), 400
    
    if not data.get('items') or not isinstance(data['items'], list):
        return jsonify({'error': 'Lista de productos es requerida'}), 400
    
    if len(data['items']) == 0:
        return jsonify({'error': 'Debe incluir al menos un producto'}), 400
    
    # Validate supplier exists
    supplier = models.Supplier.query.filter_by(id=data['supplier_id'], active=True).first()
    if not supplier:
        return jsonify({'error': 'Proveedor no encontrado o inactivo'}), 400
    
    # Validate NCF if provided
    ncf_supplier = data.get('ncf_supplier', '').strip()
    ncf_type = data.get('ncf_type', '').strip()
    
    if ncf_supplier:
        # If NCF is provided but type is missing, require type selection
        if not ncf_type:
            return jsonify({'error': 'Debe seleccionar el tipo de comprobante antes de ingresar el NCF'}), 400
        
        # Validate NCF format and type
        ncf_validation = utils.validate_ncf(ncf_supplier, ncf_type)
        if not ncf_validation['valid']:
            return jsonify({'error': f'NCF inválido: {ncf_validation["message"]}'}), 400
        ncf_supplier = ncf_validation['formatted']
    elif ncf_type:
        # If type is provided but NCF is missing
        return jsonify({'error': 'Debe ingresar el NCF del proveedor para el tipo de comprobante seleccionado'}), 400
    
    # Validate and calculate items
    items_to_process = []
    calculated_subtotal = 0.0
    
    for i, item_data in enumerate(data['items']):
        try:
            # Validate item fields
            if not item_data.get('product_id'):
                return jsonify({'error': f'ID del producto es requerido en item {i+1}'}), 400
            
            if not item_data.get('quantity') or int(item_data['quantity']) <= 0:
                return jsonify({'error': f'Cantidad debe ser mayor a 0 en item {i+1}'}), 400
            
            if not item_data.get('unit_cost') or float(item_data['unit_cost']) <= 0:
                return jsonify({'error': f'Costo unitario debe ser mayor a 0 en item {i+1}'}), 400
            
            # Validate product exists
            product = models.Product.query.filter_by(id=item_data['product_id'], active=True).first()
            if not product:
                return jsonify({'error': f'Producto {item_data["product_id"]} no encontrado o inactivo'}), 400
            
            quantity = int(item_data['quantity'])
            unit_cost = float(item_data['unit_cost'])
            total_cost = quantity * unit_cost
            
            calculated_subtotal += total_cost
            
            items_to_process.append({
                'product': product,
                'quantity': quantity,
                'unit_cost': unit_cost,
                'total_cost': total_cost
            })
            
        except (ValueError, TypeError) as e:
            return jsonify({'error': f'Error en item {i+1}: {str(e)}'}), 400
    
    # SECURITY: Validate tax rate to prevent compliance violations
    tax_rate = data.get('tax_rate', 0.18)
    try:
        tax_rate = float(tax_rate)
        # Allow Dominican Republic ITBIS rates: 0% (exento), 16% (reducido), 18% (estándar)
        if tax_rate not in [0.0, 0.16, 0.18]:
            return jsonify({'error': 'Tasa de impuesto inválida. Solo se permite 0% (exento), 16% (reducido), o 18% (estándar) ITBIS'}), 400
    except (ValueError, TypeError):
        return jsonify({'error': 'Tasa de impuesto debe ser un número válido'}), 400
    
    calculated_tax = utils.calculate_itbis(calculated_subtotal, tax_rate)
    calculated_total = calculated_subtotal + calculated_tax
    
    # Validate provided totals against calculated (allow small rounding differences)
    provided_total = float(data.get('total_amount', calculated_total))
    if abs(provided_total - calculated_total) > 0.01:
        return jsonify({
            'error': f'Total incorrecto. Calculado: RD$ {calculated_total:.2f}, Proporcionado: RD$ {provided_total:.2f}'
        }), 400
    
    try:
        with db.session.begin():
            # Create purchase record
            purchase = models.Purchase()
            purchase.supplier_id = data['supplier_id']
            purchase.ncf_supplier = ncf_supplier
            purchase.total_amount = calculated_total
            purchase.tax_amount = calculated_tax
            purchase.notes = utils.sanitize_input(data.get('notes', ''), 500)
            
            db.session.add(purchase)
            db.session.flush()  # Get purchase ID
            
            # Process each item
            for item_info in items_to_process:
                product = item_info['product']
                quantity = item_info['quantity']
                unit_cost = item_info['unit_cost']
                total_cost = item_info['total_cost']
                
                # Create purchase item
                purchase_item = models.PurchaseItem()
                purchase_item.purchase_id = purchase.id
                purchase_item.product_id = product.id
                purchase_item.quantity = quantity
                purchase_item.unit_cost = unit_cost
                purchase_item.total_cost = total_cost
                
                db.session.add(purchase_item)
                
                # Update product stock and cost
                old_stock = product.stock
                new_stock = old_stock + quantity
                product.stock = new_stock
                product.cost = unit_cost  # Update cost to latest purchase price
                
                # Create stock adjustment record for audit trail
                stock_adjustment = models.StockAdjustment()
                stock_adjustment.product_id = product.id
                stock_adjustment.user_id = user.id
                stock_adjustment.adjustment_type = 'purchase'
                stock_adjustment.old_stock = old_stock
                stock_adjustment.adjustment = quantity
                stock_adjustment.new_stock = new_stock
                stock_adjustment.reason = f'Compra #{purchase.id} - {supplier.name}'
                stock_adjustment.reference_id = purchase.id
                stock_adjustment.reference_type = 'purchase'
                
                db.session.add(stock_adjustment)
            
            # Final commit of all changes
            db.session.commit()
        
        return jsonify({
            'success': True,
            'purchase_id': purchase.id,
            'subtotal': calculated_subtotal,
            'tax_amount': calculated_tax,
            'total_amount': calculated_total,
            'items_count': len(items_to_process),
            'message': f'Compra creada exitosamente. Total: {utils.format_currency_rd(calculated_total)}'
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': f'Error al crear la compra: {str(e)}'}), 400


@bp.route('/api/stock/<int:product_id>/adjust', methods=['POST'])
def adjust_stock(product_id):
    user = require_admin()
    if not isinstance(user, models.User):
        return jsonify({'error': 'No autorizado'}), 401
    
    product = models.Product.query.get_or_404(product_id)
    data = request.get_json()
    
    # Validate input
    if not data:
        return jsonify({'error': 'Datos no proporcionados'}), 400
    
    try:
        adjustment = int(data['adjustment'])
        reason = utils.sanitize_input(data.get('reason', 'Ajuste manual'), 255)
        adjustment_type = data.get('adjustment_type', 'manual')
        reference_id = data.get('reference_id')
        reference_type = data.get('reference_type')
        
        if adjustment == 0:
            return jsonify({'error': 'El ajuste debe ser diferente de cero'}), 400
        
        if not reason.strip():
            return jsonify({'error': 'La razón del ajuste es requerida'}), 400
        
        old_stock = product.stock
        new_stock = old_stock + adjustment
        
        if new_stock < 0:
            return jsonify({'error': f'El stock no puede ser negativo. Stock actual: {old_stock}, Ajuste: {adjustment}'}), 400
        
        # Use transaction to ensure atomicity
        with db.session.begin():
            # Update product stock
            product.stock = new_stock
            
            # Create stock adjustment record for audit trail
            stock_adjustment = models.StockAdjustment()
            stock_adjustment.product_id = product_id
            stock_adjustment.user_id = user.id
            stock_adjustment.adjustment_type = adjustment_type
            stock_adjustment.old_stock = old_stock
            stock_adjustment.adjustment = adjustment
            stock_adjustment.new_stock = new_stock
            stock_adjustment.reason = reason
            stock_adjustment.reference_id = reference_id
            stock_adjustment.reference_type = reference_type
            
            db.session.add(stock_adjustment)
            
            # Update product minimum stock alert if stock was very low and now restored
            if old_stock <= product.min_stock and new_stock > product.min_stock:
                flash(f'Stock de {product.name} restaurado por encima del mínimo', 'success')
            elif new_stock <= product.min_stock and old_stock > product.min_stock:
                flash(f'¡Alerta! Stock de {product.name} está por debajo del mínimo ({product.min_stock})', 'warning')
        
        return jsonify({
            'success': True,
            'old_stock': old_stock,
            'new_stock': new_stock,
            'adjustment': adjustment,
            'reason': reason,
            'adjustment_id': stock_adjustment.id,
            'message': f'Stock ajustado exitosamente. {product.name}: {old_stock} → {new_stock}'
        })
        
    except ValueError:
        return jsonify({'error': 'El ajuste debe ser un número entero'}), 400
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 400


@bp.route('/api/stock/<int:product_id>/history', methods=['GET'])
def stock_history(product_id):
    user = require_admin()
    if not isinstance(user, models.User):
        return jsonify({'error': 'No autorizado'}), 401
    
    product = models.Product.query.get_or_404(product_id)
    
    # Get stock adjustment history
    adjustments = models.StockAdjustment.query.filter_by(product_id=product_id)\
        .order_by(models.StockAdjustment.created_at.desc()).all()
    
    history = []
    for adjustment in adjustments:
        history.append({
            'id': adjustment.id,
            'date': adjustment.created_at.strftime('%d/%m/%Y %I:%M %p'),
            'user': adjustment.user.name,
            'type': adjustment.adjustment_type,
            'old_stock': adjustment.old_stock,
            'adjustment': adjustment.adjustment,
            'new_stock': adjustment.new_stock,
            'reason': adjustment.reason,
            'reference_id': adjustment.reference_id,
            'reference_type': adjustment.reference_type
        })
    
    return jsonify({
        'success': True,
        'product': {
            'id': product.id,
            'name': product.name,
            'current_stock': product.stock,
            'min_stock': product.min_stock
        },
        'history': history
    })


@bp.route('/api/stock/alerts', methods=['GET'])
def stock_alerts_api():
    user = require_admin()
    if not isinstance(user, models.User):
        return jsonify({'error': 'No autorizado'}), 401
    
    # Get products with low stock (only inventariables)
    low_stock_products = models.Product.query.filter(
        models.Product.stock <= models.Product.min_stock,
        models.Product.active == True,
        models.Product.product_type == 'inventariable'
    ).all()
    
    # Get products with critical stock (less than half of minimum, only inventariables)
    critical_stock_products = models.Product.query.filter(
        models.Product.stock <= (models.Product.min_stock / 2),
        models.Product.active == True,
        models.Product.product_type == 'inventariable'
    ).all()
    
    low_stock_list = []
    for product in low_stock_products:
        low_stock_list.append({
            'id': product.id,
            'name': product.name,
            'current_stock': product.stock,
            'min_stock': product.min_stock,
            'category': product.category.name if product.category else None,
            'status': 'critical' if product.stock <= (product.min_stock / 2) else 'low'
        })
    
    return jsonify({
        'success': True,
        'total_alerts': len(low_stock_list),
        'critical_count': len(critical_stock_products),
        'low_count': len(low_stock_products) - len(critical_stock_products),
        'products': low_stock_list
    })