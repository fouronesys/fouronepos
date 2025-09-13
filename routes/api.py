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
from utils import get_company_info_for_receipt, validate_ncf
# CSRF exempt decorator will be applied at app level

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
    try:
        user = require_login()
        if not isinstance(user, models.User):
            return user
        
        data = request.get_json() or {}  # Default to empty dict if no JSON
        
        # Create new sale (waiters don't need cash registers initially)
        sale = models.Sale()
        sale.user_id = user.id
        table_id = data.get('table_id')
        if table_id is not None:
            sale.table_id = int(table_id)
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
        
    except Exception as e:
        db.session.rollback()
        print(f"Error creating sale: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': 'Error al crear la venta', 'details': str(e)}), 500


@bp.route('/sales/<int:sale_id>/items', methods=['POST'])
def add_sale_item(sale_id):
    user = require_login()
    if not isinstance(user, models.User):
        return user
    
    data = request.get_json()
    
    if not data:
        return jsonify({'error': 'No data provided'}), 400
        
    if 'product_id' not in data or 'quantity' not in data:
        return jsonify({'error': 'Faltan campos requeridos: product_id y quantity'}), 400
    
    # Validate quantity is positive integer
    try:
        quantity = int(data['quantity'])
        if quantity <= 0:
            return jsonify({'error': 'La cantidad debe ser mayor a 0'}), 400
    except (ValueError, TypeError):
        return jsonify({'error': 'La cantidad debe ser un número válido'}), 400
    
    # CRITICAL: Use transactional locking to prevent post-finalization mutations
    try:
        # Lock the sale to prevent concurrent finalization
        sale = db.session.query(models.Sale).filter_by(id=sale_id).with_for_update().first()
        if not sale:
            return jsonify({'error': 'Venta no encontrada'}), 404
        
        # CRITICAL: Re-check sale status after acquiring lock (prevents post-finalization mutations)
        if sale.status != 'pending':
            return jsonify({'error': 'Solo se pueden modificar ventas pendientes'}), 400
        
        # Lock product to ensure consistent stock validation
        product = db.session.query(models.Product).filter_by(id=data['product_id']).with_for_update().first()
        if not product:
            return jsonify({'error': 'Producto no encontrado'}), 404

        # Check for existing sale items of the same product in this sale
        existing_quantity = db.session.query(db.func.sum(models.SaleItem.quantity)).filter_by(
            sale_id=sale_id, 
            product_id=product.id
        ).scalar() or 0
        
        # Calculate total quantity (existing + new)
        total_quantity = existing_quantity + quantity
        
        # Check stock availability against total quantity
        if product.stock < total_quantity:
            return jsonify({
                'error': f'Stock insuficiente para {product.name}. Disponible: {product.stock}, ya en venta: {existing_quantity}, solicitado: {quantity}'
            }), 400

        # Check if product already exists in this sale - merge quantities instead of creating duplicate lines
        existing_item = models.SaleItem.query.filter_by(sale_id=sale_id, product_id=product.id).first()
        
        if existing_item:
            # Update existing item quantity
            existing_item.quantity = total_quantity
            existing_item.total_price = product.price * total_quantity
            existing_item.tax_rate = product.tax_rate  # Actualizar tasa de impuesto desde producto
            existing_item.is_tax_included = product.is_tax_included  # Actualizar si impuesto está incluido
            sale_item = existing_item
        else:
            # Create new sale item
            sale_item = models.SaleItem()
            sale_item.sale_id = sale_id
            sale_item.product_id = product.id
            sale_item.quantity = quantity
            sale_item.unit_price = product.price
            sale_item.total_price = product.price * quantity
            sale_item.tax_rate = product.tax_rate  # Capturar tasa de impuesto desde producto
            sale_item.is_tax_included = product.is_tax_included  # Capturar si impuesto está incluido
            
            db.session.add(sale_item)
        
        # Recalculate sale totals from all items using proper per-item tax calculation
        # Calculate totals by tax rate categories with support for included taxes
        subtotal_by_rate = {}
        total_subtotal = 0
        total_tax_included = 0  # Tax that was already included in prices
        total_tax_added = 0     # Tax that gets added to prices
        
        # Group items by tax rate and calculate totals per category
        for item in sale.sale_items:
            # Defensive fallback: if fields are NULL, use product's current values
            rate = item.tax_rate if item.tax_rate is not None else item.product.tax_rate
            is_included = item.is_tax_included if hasattr(item, 'is_tax_included') else item.product.is_tax_included
            
            if rate not in subtotal_by_rate:
                subtotal_by_rate[rate] = 0
            
            if is_included and rate > 0:
                # Tax is included in the price - calculate base amount and included tax
                # Formula: base = total / (1 + rate), tax = total - base
                base_amount = item.total_price / (1 + rate)
                tax_amount = item.total_price - base_amount
                subtotal_by_rate[rate] += base_amount
                total_subtotal += base_amount
                total_tax_included += round(tax_amount, 2)
            else:
                # Tax is added to price (normal behavior) or no tax
                subtotal_by_rate[rate] += item.total_price
                total_subtotal += item.total_price
                if rate > 0:
                    tax_amount = round(item.total_price * rate, 2)
                    total_tax_added += tax_amount
        
        # Set sale totals
        sale.subtotal = round(total_subtotal, 2)
        sale.tax_amount = round(total_tax_included + total_tax_added, 2)
        sale.total = round(total_subtotal + total_tax_added, 2)  # Only add non-included taxes
        
        # Commit the transaction
        db.session.commit()
        
        return jsonify({
            'id': sale_item.id,
            'product_name': product.name,
            'quantity': sale_item.quantity,
            'unit_price': sale_item.unit_price,
            'total_price': sale_item.total_price,
            'tax_rate': sale_item.tax_rate,
            'is_tax_included': sale_item.is_tax_included
        })
        
    except Exception as e:
        # Handle any unexpected errors
        return jsonify({'error': 'Error interno del servidor'}), 500


@bp.route('/sales/<int:sale_id>/finalize', methods=['POST'])
def finalize_sale(sale_id):
    user = require_login()
    if not isinstance(user, models.User):
        return user
    
    # ROLE RESTRICTION: Only cashiers and administrators can finalize sales
    if user.role.value not in ['administrador', 'cajero']:
        return jsonify({'error': 'Solo cajeros y administradores pueden finalizar ventas'}), 403
    
    data = request.get_json()
    
    # Get NCF type from request (default to consumo)
    ncf_type = data.get('ncf_type', 'consumo')
    payment_method = data.get('payment_method', 'efectivo')
    
    # NOTE: Tax rates are now calculated automatically from individual products
    # No need to validate user-provided tax_rate as we calculate from sale items
    
    # Get client info for fiscal/government invoices
    customer_name = data.get('client_name')
    customer_rnc = data.get('client_rnc')
    
    # CRITICAL FIX: Idempotent sale finalization with proper locking to prevent NCF race conditions
    # This ensures exactly one NCF per sale even under concurrent finalization requests
    try:
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
        
        # PREVENT EMPTY SALES: Validate that sale has items before proceeding with NCF allocation
        if not sale.sale_items:
            raise ValueError('No se puede finalizar una venta sin productos')
        
        # Validate stock availability before proceeding with NCF allocation with concurrent safety
        # Load sale items and group by product for aggregate validation
        sale_items = db.session.query(models.SaleItem).filter_by(sale_id=sale_id).all()
        
        # Group sale items by product ID and calculate total quantity per product
        product_quantities = {}
        product_ids = []
        
        for sale_item in sale_items:
            product_id = sale_item.product_id
            if product_id not in product_quantities:
                product_quantities[product_id] = 0
                product_ids.append(product_id)
            product_quantities[product_id] += sale_item.quantity
        
        # Lock all involved products to prevent concurrent modifications (CRITICAL for fiscal compliance)
        locked_products = db.session.query(models.Product).filter(
            models.Product.id.in_(product_ids)
        ).with_for_update().all()
        
        # Validate stock availability per product (aggregated quantities)
        for product in locked_products:
            required_quantity = product_quantities[product.id]
            if product.stock < required_quantity:
                raise ValueError(f'Stock insuficiente para {product.name}. Disponible: {product.stock}, requerido: {required_quantity}')
        
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
        
        # Get shared NCF sequence with row-level lock to prevent concurrent access
        # Uses global shared sequences for fiscal compliance across all registers
        shared_cash_register = db.session.query(models.CashRegister).filter_by(
            name="Secuencias NCF Compartidas",
            active=True
        ).first()
        
        if not shared_cash_register:
            raise ValueError('Configuración de secuencias NCF compartidas no encontrada. Contacta al administrador.')
            
        ncf_sequence = db.session.query(models.NCFSequence).filter_by(
            cash_register_id=shared_cash_register.id,
            ncf_type=models.NCFType(ncf_type),
            active=True
        ).with_for_update().first()
        
        if not ncf_sequence:
            raise ValueError(f'No hay secuencia NCF compartida activa para tipo {ncf_type}. Contacta al administrador.')
        
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
        
        # Calculate totals by tax rate categories with support for included taxes
        subtotal_by_rate = {}
        total_subtotal = 0
        total_tax_included = 0  # Tax that was already included in prices
        total_tax_added = 0     # Tax that gets added to prices
        
        # Group items by tax rate and calculate totals per category
        for item in sale.sale_items:
            # Defensive fallback: if fields are NULL, use product's current values
            rate = item.tax_rate if item.tax_rate is not None else item.product.tax_rate
            is_included = item.is_tax_included if hasattr(item, 'is_tax_included') else item.product.is_tax_included
            
            if rate not in subtotal_by_rate:
                subtotal_by_rate[rate] = 0
            
            if is_included and rate > 0:
                # Tax is included in the price - calculate base amount and included tax
                # Formula: base = total / (1 + rate), tax = total - base
                base_amount = item.total_price / (1 + rate)
                tax_amount = item.total_price - base_amount
                subtotal_by_rate[rate] += base_amount
                total_subtotal += base_amount
                total_tax_included += round(tax_amount, 2)
            else:
                # Tax is added to price (normal behavior) or no tax
                subtotal_by_rate[rate] += item.total_price
                total_subtotal += item.total_price
                if rate > 0:
                    tax_amount = round(item.total_price * rate, 2)
                    total_tax_added += tax_amount
        
        # Set sale totals
        sale.subtotal = round(total_subtotal, 2)
        sale.tax_amount = round(total_tax_included + total_tax_added, 2)
        sale.total = round(total_subtotal + total_tax_added, 2)  # Only add non-included taxes
        
        # Add client info for fiscal/government invoices (NCF compliance)
        if customer_name and customer_rnc and ncf_type in ['credito_fiscal', 'gubernamental']:
            sale.customer_name = customer_name
            sale.customer_rnc = customer_rnc
        
        # Reduce stock for all products (using already locked products to prevent race conditions)
        for product in locked_products:
            required_quantity = product_quantities[product.id]
            product.stock -= required_quantity
            
        # Commit the transaction
        db.session.commit()
        
        # If ANY part fails, everything rolls back and no NCF is consumed
        
        # Success response data
        response_data = {
            'id': sale.id,
            'ncf': sale.ncf,
            'total': sale.total,
            'status': sale.status,
            'payment_method': sale.payment_method,
            'created_at': sale.created_at.isoformat(),
            'receipt_printed': False  # Will be updated if printing succeeds
        }
        
        # AUTOMATIC RECEIPT PRINTING: Generate thermal receipt immediately after successful finalization
        try:
            # Prepare sale data for receipt generation
            sale_data = {
                'id': sale.id,
                'ncf': sale.ncf,
                'created_at': sale.created_at.isoformat(),
                'payment_method': sale.payment_method,
                'subtotal': sale.subtotal,
                'tax_amount': sale.tax_amount,
                'total': sale.total,
                'items': [{
                    'product_name': item.product.name,
                    'quantity': item.quantity,
                    'price': item.unit_price,
                    'total_price': item.total_price,
                    'tax_rate': item.tax_rate,
                    'is_tax_included': item.is_tax_included
                } for item in sale.sale_items]
            }
            
            # Import and use thermal receipt generator
            from receipt_generator import generate_thermal_receipt_text
            receipt_text = generate_thermal_receipt_text(sale_data)
            
            if receipt_text:
                response_data['receipt_printed'] = True
                response_data['receipt_text'] = receipt_text
                response_data['message'] = 'Venta finalizada exitosamente. Recibo generado automáticamente.'
            else:
                response_data['message'] = 'Venta finalizada exitosamente. Error generando recibo automático.'
        except Exception as print_error:
            # Don't fail the entire sale if receipt printing fails
            print(f"[Receipt] Error generando recibo automático para venta {sale.id}: {print_error}")
            response_data['message'] = 'Venta finalizada exitosamente. Error en impresión automática de recibo.'
        
        # Return success response
        return jsonify(response_data)
        
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


@bp.route('/pending-orders')
def get_pending_orders():
    """Get pending orders that need to be finalized by cashiers/admins"""
    user = require_login()
    if not isinstance(user, models.User):
        return user
    
    # Only cashiers and admins can view pending orders for billing
    if user.role.value not in ['administrador', 'cajero']:
        return jsonify({'error': 'Solo cajeros y administradores pueden ver órdenes pendientes de facturación'}), 403
    
    try:
        # Get pending sales with table and user information
        pending_sales = models.Sale.query.filter_by(status='pending').options(
            db.joinedload(models.Sale.table),
            db.joinedload(models.Sale.user),
            db.joinedload(models.Sale.sale_items).joinedload(models.SaleItem.product)
        ).order_by(models.Sale.created_at.desc()).all()
        
        orders_data = []
        for sale in pending_sales:
            # Skip orders with no items
            if not sale.sale_items:
                continue
                
            order_data = {
                'id': sale.id,
                'table_number': sale.table.number if sale.table else None,
                'table_name': sale.table.name if sale.table else None,
                'waiter_name': sale.user.name if sale.user else 'Desconocido',
                'created_at': sale.created_at.isoformat(),
                'total': sale.total,
                'order_status': sale.order_status.value if sale.order_status else 'not_sent',
                'items_count': len(sale.sale_items),
                'items': [{
                    'id': item.id,
                    'product_name': item.product.name,
                    'quantity': item.quantity,
                    'unit_price': item.unit_price,
                    'total_price': item.total_price
                } for item in sale.sale_items]
            }
            orders_data.append(order_data)
        
        return jsonify({
            'success': True,
            'orders': orders_data,
            'total_orders': len(orders_data)
        })
        
    except Exception as e:
        return jsonify({'error': f'Error obteniendo órdenes pendientes: {str(e)}'}), 500


# Receipt Generation Routes
@bp.route('/receipts/<int:sale_id>/view')
def view_receipt(sale_id):
    """Show receipt in HTML format for viewing/printing"""
    user = require_login()
    if not isinstance(user, models.User):
        return user
    
    # Get format parameter for device-appropriate sizing
    receipt_format = request.args.get('format', '80mm')
    if receipt_format not in ['58mm', '80mm']:
        receipt_format = '80mm'  # Default to 80mm if invalid format
    
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
    
    # Check for auto_print parameter to add print trigger JavaScript
    auto_print = request.args.get('auto_print', 'false').lower() == 'true'
    
    return render_template('receipt_view.html', 
                         sale_data=sale_data, 
                         company_info=company_info,
                         receipt_format=receipt_format,
                         auto_print=auto_print)


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
    
    # CRITICAL FIX: Use already calculated totals from sale object instead of recalculating
    # The finalize_sale function already computed these correctly with per-item tax rates
    
    # Prepare sale data with correct totals from sale object
    sale_data = {
        'id': sale.id,
        'created_at': sale.created_at,
        'ncf': sale.ncf,
        'total': sale.total,        # Use calculated total from sale
        'subtotal': sale.subtotal,  # Use calculated subtotal from sale  
        'tax_amount': sale.tax_amount,  # Use calculated tax from sale
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
    
    # Add items with CRITICAL tax fields needed for line-by-line tax display
    for item in sale_items:
        # Defensive fallback: if fields are NULL, use product's current values
        tax_rate = item.tax_rate if hasattr(item, 'tax_rate') and item.tax_rate is not None else item.product.tax_rate
        is_tax_included = item.is_tax_included if hasattr(item, 'is_tax_included') and item.is_tax_included is not None else item.product.is_tax_included
        
        sale_data['items'].append({
            'quantity': item.quantity,
            'product_name': item.product.name,
            'name': item.product.name,  # Alternative name field
            'price': item.unit_price,
            'tax_rate': tax_rate,  # CRITICAL: Add tax rate for line-by-line display
            'is_tax_included': is_tax_included  # CRITICAL: Add tax inclusion flag
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


@bp.route('/sales/<int:sale_id>/details')
def get_sale_details(sale_id):
    """Get detailed information about a specific sale"""
    user = require_login()
    if not isinstance(user, models.User):
        return user
    
    # Get sale data
    sale = models.Sale.query.get_or_404(sale_id)
    
    # SECURITY: Verify user has access to this sale
    if user.role.value not in ['administrador', 'cajero']:
        return jsonify({'error': 'No tienes permisos para ver esta venta'}), 403
    
    if user.role.value == 'cajero':
        # For cashiers, verify cash register ownership and it exists
        if not sale.cash_register:
            return jsonify({'error': 'Esta venta no tiene caja registradora asignada'}), 400
        if sale.cash_register.user_id != user.id:
            return jsonify({'error': 'No tienes acceso a esta venta'}), 403
    
    # Get sale items with product information
    sale_items = models.SaleItem.query.filter_by(sale_id=sale_id).all()
    
    # Prepare sale data
    sale_data = {
        'id': sale.id,
        'ncf': sale.ncf,
        'created_at': sale.created_at.isoformat(),
        'customer_name': sale.customer_name,
        'customer_rnc': sale.customer_rnc,
        'payment_method': sale.payment_method,
        'status': sale.status,
        'order_status': sale.order_status.value if sale.order_status else None,
        'subtotal': float(sale.subtotal),
        'tax_amount': float(sale.tax_amount),
        'total': float(sale.total),
        'user_name': sale.user.name if sale.user else None,
        'cash_register_name': sale.cash_register.name if sale.cash_register else None,
        'items': []
    }
    
    # Add items with product details
    for item in sale_items:
        sale_data['items'].append({
            'id': item.id,
            'product_id': item.product_id,
            'product_name': item.product.name if item.product else 'Producto eliminado',
            'quantity': item.quantity,
            'unit_price': float(item.unit_price),
            'total_price': float(item.total_price)
        })
    
    return jsonify({
        'success': True,
        'sale': sale_data
    })


# Credit/Debit Note Routes
@bp.route('/sales/<int:sale_id>/credit-note', methods=['POST'])
def create_credit_note(sale_id):
    """Create a credit note for a completed sale"""
    user = require_login()
    if not isinstance(user, models.User):
        return user
    
    # Only administrators and cashiers can create credit notes
    if user.role.value not in ['administrador', 'cajero']:
        return jsonify({'error': 'No tienes permisos para crear notas de crédito'}), 403
    
    data = request.get_json()
    if not data:
        return jsonify({'error': 'Datos no proporcionados'}), 400
    
    reason = data.get('reason')
    items = data.get('items', [])
    note_type = data.get('note_type', 'nota_credito')  # nota_credito or nota_debito
    
    if not reason:
        return jsonify({'error': 'La razón es requerida'}), 400
    
    if not items:
        return jsonify({'error': 'Debe especificar al menos un producto'}), 400
    
    try:
        with db.session.begin():
            # Get original sale with lock
            sale = db.session.query(models.Sale).filter_by(id=sale_id).with_for_update().first()
            
            if not sale:
                raise ValueError('Venta no encontrada')
            
            # Validate that sale is completed
            if sale.status != 'completed':
                raise ValueError('Solo se pueden crear notas para ventas completadas')
            
            if not sale.ncf:
                raise ValueError('La venta debe tener un NCF válido')
            
            # Validate NCF type
            if note_type not in ['nota_credito', 'nota_debito']:
                raise ValueError('Tipo de nota inválido')
            
            # Use CREDITO_FISCAL sequence but generate appropriate NCF type
            # Since credit/debit note sequences may not exist, use existing CREDITO_FISCAL sequence
            cash_register = sale.cash_register
            if not cash_register:
                raise ValueError('La venta no tiene caja registradora asignada')
            
            # Lock NCF sequence for atomic operation to prevent race conditions
            # Use CREDITO_FISCAL sequence and replace B with A or C as needed
            ncf_sequence = db.session.query(models.NCFSequence).filter_by(
                cash_register_id=cash_register.id,
                ncf_type=models.NCFType.CREDITO_FISCAL,
                active=True
            ).with_for_update().first()
            
            if not ncf_sequence:
                raise ValueError('No hay secuencia de NCF de crédito fiscal activa')
            
            # Check if sequence has available numbers
            if ncf_sequence.current_number >= ncf_sequence.end_number:
                raise ValueError(f'Secuencia de NCF agotada')
            
            # Generate next NCF number atomically
            next_number = ncf_sequence.current_number + 1
            
            # Generate appropriate NCF: replace B in serie with A (credit) or C (debit)
            ncf_type_code = 'A' if note_type == 'nota_credito' else 'C'
            # Replace the B in serie (e.g., "B01") with appropriate letter (e.g., "A01" or "C01")
            note_serie = ncf_sequence.serie.replace('B', ncf_type_code, 1)
            ncf = f"{note_serie}{next_number:08d}"
            
            # Validate generated NCF
            if not validate_ncf(ncf):
                raise ValueError(f'NCF generado inválido: {ncf}')
            
            # Validate items and calculate totals using SERVER-SIDE pricing only
            note_subtotal = 0
            note_tax_amount = 0
            valid_items = []
            
            for item_data in items:
                product_id = item_data.get('product_id')
                quantity = item_data.get('quantity', 1)
                original_sale_item_id = item_data.get('original_sale_item_id')
                
                if not product_id or quantity <= 0:
                    raise ValueError('Datos de producto inválidos')
                
                # SECURITY: Always derive pricing from original sale items - NEVER trust client prices
                original_item = models.SaleItem.query.filter_by(
                    sale_id=sale_id, 
                    product_id=product_id
                ).first()
                
                if not original_item:
                    raise ValueError(f'Producto {product_id} no está en la venta original')
                
                # Validate quantity doesn't exceed original quantity sold
                if quantity > original_item.quantity:
                    raise ValueError(f'La cantidad para {original_item.product.name} no puede exceder la cantidad original vendida ({original_item.quantity})')
                
                # Use original sale item pricing - never client-provided prices
                unit_price = original_item.unit_price
                tax_rate = original_item.tax_rate
                is_tax_included = original_item.is_tax_included
                
                # Calculate item totals
                line_total = unit_price * quantity
                
                if is_tax_included:
                    line_tax = line_total * (tax_rate / (1 + tax_rate))
                    line_subtotal = line_total - line_tax
                else:
                    line_subtotal = line_total
                    line_tax = line_subtotal * tax_rate
                
                note_subtotal += line_subtotal
                note_tax_amount += line_tax
                
                valid_items.append({
                    'product_id': product_id,
                    'product': original_item.product,
                    'quantity': quantity,
                    'unit_price': unit_price,
                    'total_price': line_total,
                    'tax_rate': tax_rate,
                    'is_tax_included': is_tax_included,
                    'original_sale_item_id': original_item.id
                })
            
            note_total = note_subtotal + note_tax_amount
            
            # Create credit note
            credit_note = models.CreditNote()
            credit_note.original_sale_id = sale_id
            credit_note.ncf_sequence_id = ncf_sequence.id
            credit_note.ncf = ncf
            credit_note.note_type = ncf_enum_type
            credit_note.amount = note_subtotal
            credit_note.tax_amount = note_tax_amount
            credit_note.total = note_total
            credit_note.reason = reason
            credit_note.customer_name = sale.customer_name
            credit_note.customer_rnc = sale.customer_rnc
            credit_note.created_by = user.id
            
            db.session.add(credit_note)
            db.session.flush()  # Get the credit note ID
            
            # Create credit note items
            for item_data in valid_items:
                note_item = models.CreditNoteItem()
                note_item.credit_note_id = credit_note.id
                note_item.original_sale_item_id = item_data.get('original_sale_item_id')
                note_item.product_id = item_data['product_id']
                note_item.quantity = item_data['quantity']
                note_item.unit_price = item_data['unit_price']
                note_item.total_price = item_data['total_price']
                note_item.tax_rate = item_data['tax_rate']
                note_item.is_tax_included = item_data['is_tax_included']
                
                db.session.add(note_item)
            
            # Update NCF sequence
            ncf_sequence.current_number = next_number
            
            # For credit notes, increase inventory (returned goods)
            # For debit notes, no stock adjustment typically needed
            if note_type == 'nota_credito':
                for item_data in valid_items:
                    product = item_data['product']
                    if product and product.product_type == 'inventariable':
                        old_stock = product.stock
                        product.stock += item_data['quantity']
                        
                        # Create stock adjustment record for audit trail
                        stock_adjustment = models.StockAdjustment()
                        stock_adjustment.product_id = product.id
                        stock_adjustment.user_id = user.id
                        stock_adjustment.adjustment_type = 'credit_note'
                        stock_adjustment.old_stock = old_stock
                        stock_adjustment.adjustment = item_data['quantity']
                        stock_adjustment.new_stock = product.stock
                        stock_adjustment.reason = f'Nota de crédito NCF {ncf}: {reason}'
                        stock_adjustment.reference_id = credit_note.id
                        stock_adjustment.reference_type = 'credit_note'
                        
                        db.session.add(stock_adjustment)
            
            # Commit transaction
            db.session.commit()
            
            return jsonify({
                'success': True,
                'credit_note': {
                    'id': credit_note.id,
                    'ncf': credit_note.ncf,
                    'note_type': credit_note.note_type.value,
                    'total': float(credit_note.total),
                    'reason': credit_note.reason,
                    'created_at': credit_note.created_at.isoformat()
                },
                'message': f'{"Nota de crédito" if note_type == "nota_credito" else "Nota de débito"} creada exitosamente'
            })
            
    except ValueError as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': f'Error interno: {str(e)}'}), 500


@bp.route('/credit-notes')
def get_credit_notes():
    """Get list of credit/debit notes"""
    user = require_login()
    if not isinstance(user, models.User):
        return user
    
    # Only administrators and cashiers can view credit notes
    if user.role.value not in ['administrador', 'cajero']:
        return jsonify({'error': 'No tienes permisos para ver notas de crédito'}), 403
    
    # Get query parameters
    page = request.args.get('page', 1, type=int)
    per_page = min(request.args.get('per_page', 20, type=int), 100)
    note_type = request.args.get('note_type')  # nota_credito, nota_debito
    
    # Build query
    query = models.CreditNote.query
    
    if note_type:
        if note_type == 'nota_credito':
            query = query.filter_by(note_type=models.NCFType.NOTA_CREDITO)
        elif note_type == 'nota_debito':
            query = query.filter_by(note_type=models.NCFType.NOTA_DEBITO)
    
    # Order by creation date (newest first)
    query = query.order_by(models.CreditNote.created_at.desc())
    
    # Paginate
    credit_notes = query.paginate(
        page=page, 
        per_page=per_page, 
        error_out=False
    )
    
    # Format response
    notes_data = []
    for note in credit_notes.items:
        notes_data.append({
            'id': note.id,
            'ncf': note.ncf,
            'note_type': note.note_type.value,
            'original_sale_id': note.original_sale_id,
            'original_sale_ncf': note.original_sale.ncf if note.original_sale else None,
            'total': float(note.total),
            'tax_amount': float(note.tax_amount),
            'reason': note.reason,
            'customer_name': note.customer_name,
            'customer_rnc': note.customer_rnc,
            'status': note.status,
            'created_at': note.created_at.isoformat(),
            'created_by_name': note.created_by_user.name if note.created_by_user else None
        })
    
    return jsonify({
        'success': True,
        'credit_notes': notes_data,
        'pagination': {
            'page': credit_notes.page,
            'pages': credit_notes.pages,
            'per_page': credit_notes.per_page,
            'total': credit_notes.total,
            'has_next': credit_notes.has_next,
            'has_prev': credit_notes.has_prev
        }
    })


@bp.route('/credit-notes/<int:note_id>')
def get_credit_note_detail(note_id):
    """Get detailed information about a credit/debit note"""
    user = require_login()
    if not isinstance(user, models.User):
        return user
    
    # Only administrators and cashiers can view credit notes
    if user.role.value not in ['administrador', 'cajero']:
        return jsonify({'error': 'No tienes permisos para ver notas de crédito'}), 403
    
    # Get credit note
    credit_note = models.CreditNote.query.get_or_404(note_id)
    
    # Get credit note items
    note_items = models.CreditNoteItem.query.filter_by(credit_note_id=note_id).all()
    
    # Format response
    items_data = []
    for item in note_items:
        items_data.append({
            'id': item.id,
            'product_id': item.product_id,
            'product_name': item.product.name if item.product else 'Producto eliminado',
            'quantity': item.quantity,
            'unit_price': float(item.unit_price),
            'total_price': float(item.total_price),
            'tax_rate': float(item.tax_rate),
            'is_tax_included': item.is_tax_included
        })
    
    note_data = {
        'id': credit_note.id,
        'ncf': credit_note.ncf,
        'note_type': credit_note.note_type.value,
        'original_sale_id': credit_note.original_sale_id,
        'original_sale_ncf': credit_note.original_sale.ncf if credit_note.original_sale else None,
        'amount': float(credit_note.amount),
        'tax_amount': float(credit_note.tax_amount),
        'total': float(credit_note.total),
        'reason': credit_note.reason,
        'customer_name': credit_note.customer_name,
        'customer_rnc': credit_note.customer_rnc,
        'status': credit_note.status,
        'created_at': credit_note.created_at.isoformat(),
        'created_by_name': credit_note.created_by_user.name if credit_note.created_by_user else None,
        'items': items_data
    }
    
    return jsonify({
        'success': True,
        'credit_note': note_data
    })


@bp.route('/sales/<int:sale_id>/cancel', methods=['POST'])
def cancel_sale(sale_id):
    """Cancel a completed sale and mark NCF as cancelled"""
    user = require_login()
    if not isinstance(user, models.User):
        return user
    
    # Only administrators and cashiers can cancel sales
    if user.role.value not in ['administrador', 'cajero']:
        return jsonify({'error': 'No tienes permisos para cancelar facturas'}), 403
    
    data = request.get_json()
    if not data:
        return jsonify({'error': 'Datos no proporcionados'}), 400
    
    reason = data.get('reason')
    
    if not reason:
        return jsonify({'error': 'La razón de cancelación es requerida'}), 400
    
    try:
        with db.session.begin():
            # Get sale with lock
            sale = db.session.query(models.Sale).filter_by(id=sale_id).with_for_update().first()
            
            if not sale:
                raise ValueError('Venta no encontrada')
            
            # Validate that sale can be cancelled
            if sale.status == 'cancelled':
                raise ValueError('La venta ya está cancelada')
            
            if sale.status != 'completed':
                raise ValueError('Solo se pueden cancelar ventas completadas')
            
            if not sale.ncf:
                raise ValueError('La venta debe tener un NCF válido para cancelar')
            
            # Update sale status
            sale.status = 'cancelled'
            sale.cancellation_reason = reason
            sale.cancelled_at = datetime.utcnow()
            sale.cancelled_by = user.id
            
            # Register cancelled NCF for DGII compliance
            if sale.ncf_sequence_id:
                cancelled_ncf = models.CancelledNCF()
                cancelled_ncf.ncf_sequence_id = sale.ncf_sequence_id
                cancelled_ncf.ncf = sale.ncf
                cancelled_ncf.original_sale_id = sale.id
                cancelled_ncf.reason = reason
                cancelled_ncf.cancelled_by = user.id
                
                db.session.add(cancelled_ncf)
            
            # For inventoriable products, restore stock
            sale_items = models.SaleItem.query.filter_by(sale_id=sale_id).all()
            for item in sale_items:
                product = item.product
                if product and product.product_type == 'inventariable':
                    old_stock = product.stock
                    product.stock += item.quantity
                    
                    # Create stock adjustment record
                    stock_adjustment = models.StockAdjustment()
                    stock_adjustment.product_id = product.id
                    stock_adjustment.user_id = user.id
                    stock_adjustment.adjustment_type = 'sale_cancellation'
                    stock_adjustment.old_stock = old_stock
                    stock_adjustment.adjustment = item.quantity
                    stock_adjustment.new_stock = product.stock
                    stock_adjustment.reason = f'Cancelación de venta: {reason}'
                    stock_adjustment.reference_id = sale.id
                    stock_adjustment.reference_type = 'sale_cancellation'
                    
                    db.session.add(stock_adjustment)
            
            # Commit transaction
            db.session.commit()
            
            return jsonify({
                'success': True,
                'message': 'Venta cancelada exitosamente',
                'sale': {
                    'id': sale.id,
                    'ncf': sale.ncf,
                    'status': sale.status,
                    'cancelled_at': sale.cancelled_at.isoformat() if sale.cancelled_at else None
                }
            })
            
    except ValueError as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': f'Error interno: {str(e)}'}), 500