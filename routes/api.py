from flask import Blueprint, request, jsonify, session, render_template, send_file, abort, flash
import models
from models import db
from datetime import datetime
from sqlalchemy.exc import IntegrityError
from sqlalchemy import text
import time
import random
import os
import logging
from receipt_generator import generate_pdf_receipt, generate_thermal_receipt_text
from utils import get_company_info_for_receipt, validate_ncf
from flask_wtf.csrf import validate_csrf
from werkzeug.exceptions import BadRequest

# Configure logging
logger = logging.getLogger(__name__)

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


def validate_csrf_token():
    """Validate CSRF token for API requests"""
    try:
        # Support CSRF token from JSON body or header
        csrf_token = None
        
        # Try JSON body first (for API calls)
        if request.is_json and request.get_json() and request.get_json().get('csrf_token'):
            csrf_token = request.get_json().get('csrf_token')
        # Try header (for API calls)
        elif request.headers.get('X-CSRFToken'):
            csrf_token = request.headers.get('X-CSRFToken')
        
        if not csrf_token:
            return jsonify({'error': 'Token de seguridad requerido (csrf_token)'}), 400
            
        validate_csrf(csrf_token)
    except BadRequest:
        return jsonify({'error': 'Token de seguridad inválido'}), 400
    return None  # Success


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
        'category_id': p.category_id,
        'tax_types': [{
            'id': pt.tax_type.id,
            'name': pt.tax_type.name,
            'rate': pt.tax_type.rate,
            'is_inclusive': pt.tax_type.is_inclusive
        } for pt in p.product_taxes] if p.product_taxes else []
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


# REMOVED: GLOBAL_TAX_TYPES hardcoded list - now using database queries

def get_tax_type_by_id(tax_type_id):
    """Helper function to get tax type from database by ID"""
    if not tax_type_id:
        return None
    
    tax_type = models.TaxType.query.filter_by(id=int(tax_type_id), active=True).first()
    if not tax_type:
        return None
    
    return {
        'id': tax_type.id,
        'name': tax_type.name,
        'rate': tax_type.rate,
        'is_inclusive': tax_type.is_inclusive,
        'description': getattr(tax_type, 'description', ''),
        'is_percentage': True,
        'display_order': tax_type.id
    }

@bp.route('/tax-types')
def get_tax_types():
    """Get all active tax types from database (excluding non-product types)"""
    # Get all active tax types, excluding 'Propina Legal' which is not a product tax
    tax_types = models.TaxType.query.filter(
        models.TaxType.active == True,
        models.TaxType.name != 'Propina Legal'
    ).all()
    
    return jsonify([{
        'id': tax_type.id,
        'name': tax_type.name,
        'rate': tax_type.rate,
        'is_inclusive': tax_type.is_inclusive,
        'description': getattr(tax_type, 'description', ''),
        'is_percentage': True,
        'display_order': tax_type.id
    } for tax_type in tax_types])


@bp.route('/tables/<int:table_id>/status', methods=['PUT'])
def update_table_status(table_id):
    user = require_login()
    if not isinstance(user, models.User):
        return user
    
    # Validate CSRF token
    csrf_error = validate_csrf_token()
    if csrf_error:
        return csrf_error
    
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
        
        # Validate CSRF token
        csrf_error = validate_csrf_token()
        if csrf_error:
            return csrf_error
        
        data = request.get_json() or {}  # Default to empty dict if no JSON
        
        # Table assignment is optional for POS sales (direct sales, carry-out, delivery)
        table_id = data.get('table_id')
        if table_id:
            # If table_id is provided, validate that the table exists
            table = models.Table.query.get(int(table_id))
            if not table:
                return jsonify({'error': f'Mesa {table_id} no encontrada'}), 400
        
        # Create new sale (waiters don't need cash registers initially)
        sale = models.Sale()
        sale.user_id = user.id
        
        # DEBUG: Detailed table_id handling
        print(f"[DEBUG CREATE_SALE] Raw table_id: {table_id}, type: {type(table_id)}")
        if table_id and str(table_id).strip():
            try:
                sale.table_id = int(table_id)
                print(f"[DEBUG CREATE_SALE] Set table_id to: {sale.table_id}")
            except (ValueError, TypeError) as e:
                print(f"[DEBUG CREATE_SALE] Error converting table_id: {e}")
                # Leave table_id unassigned (None) for optional field
        else:
            print(f"[DEBUG CREATE_SALE] No table_id provided")
            
        sale.description = data.get('description', '')
        sale.subtotal = 0
        sale.tax_amount = 0
        sale.total = 0
        sale.status = 'pending'
        sale.tax_mode = models.TaxMode.PRODUCT_BASED
        print(f"[DEBUG CREATE_SALE] tax_mode set to: {sale.tax_mode}, value: {sale.tax_mode.value}")
        
        # Store customer information if provided (for table orders)
        customer_name = data.get('customer_name')
        customer_rnc = data.get('customer_rnc')
        if customer_name:
            sale.customer_name = customer_name.strip()
            print(f"[DEBUG CREATE_SALE] Customer name set to: {sale.customer_name}")
        if customer_rnc:
            sale.customer_rnc = customer_rnc.strip()
            print(f"[DEBUG CREATE_SALE] Customer RNC set to: {sale.customer_rnc}")
        
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
    
    # Validate CSRF token
    csrf_error = validate_csrf_token()
    if csrf_error:
        return csrf_error
    
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

        # Check for existing sale items of the same product in this sale (always needed)
        existing_quantity = db.session.query(db.func.sum(models.SaleItem.quantity)).filter_by(
            sale_id=sale_id, 
            product_id=product.id
        ).scalar() or 0
        
        # Calculate total quantity (existing + new) - needed for all products
        total_quantity = existing_quantity + quantity
        
        # Only validate stock for inventariable products, not consumables
        if product.product_type == 'inventariable':
            # Check stock availability against total quantity
            if product.stock < total_quantity:
                return jsonify({
                    'error': f'Stock insuficiente para {product.name}. Disponible: {product.stock}, ya en venta: {existing_quantity}, solicitado: {quantity}'
                }), 400
        # For consumable products, skip stock validation entirely

        # Check if product already exists in this sale - merge quantities instead of creating duplicate lines
        existing_item = models.SaleItem.query.filter_by(sale_id=sale_id, product_id=product.id).first()
        
        # ENHANCED TAX CALCULATION LOGIC with proper fallback hierarchy
        # 1. Use tax_type_id and is_inclusive from frontend payload (if provided)
        # 2. Fallback to product.product_taxes (if configured)
        # 3. Final fallback to default ITBIS 18% included for fiscal compliance
        
        # Get product's tax types for NEW TAX SYSTEM (always initialize)
        product_tax_types = []
        for product_tax in product.product_taxes:
            if product_tax.tax_type.active:
                product_tax_types.append({
                    'name': product_tax.tax_type.name,
                    'rate': product_tax.tax_type.rate,
                    'is_inclusive': product_tax.tax_type.is_inclusive
                })
        
        # Check if frontend provided specific tax information
        frontend_tax_type_id = data.get('tax_type_id')
        frontend_is_inclusive = data.get('is_inclusive')
        
        if frontend_tax_type_id:
            # Use tax information explicitly provided by frontend from global variable
            tax_type = get_tax_type_by_id(frontend_tax_type_id)
            if tax_type:
                total_tax_rate = tax_type['rate']
                has_inclusive_tax = frontend_is_inclusive if frontend_is_inclusive is not None else tax_type['is_inclusive']
            else:
                # Invalid tax_type_id provided, use default fallback
                total_tax_rate = 0.18  # Default ITBIS 18%
                has_inclusive_tax = True
        else:
            if product_tax_types:
                # Use product-specific tax configuration
                total_tax_rate = sum(tax['rate'] for tax in product_tax_types)
                has_inclusive_tax = any(tax['is_inclusive'] for tax in product_tax_types)
            else:
                # CRITICAL FIX: Default fallback for fiscal compliance (level 3)
                # If no product_taxes configured, use default ITBIS 18% included
                # This ensures products aren't saved with 0% tax rate
                total_tax_rate = 0.18  # Default ITBIS 18%
                has_inclusive_tax = True  # ITBIS is typically included in Dominican Republic
        
        if existing_item:
            # Update existing item quantity
            existing_item.quantity = total_quantity
            existing_item.total_price = product.price * total_quantity
            # Use 0.0 instead of None for tax_rate field  
            existing_item.tax_rate = float(total_tax_rate) if total_tax_rate and total_tax_rate > 0 else 0.0
            existing_item.is_tax_included = has_inclusive_tax
            sale_item = existing_item
        else:
            # Create new sale item
            sale_item = models.SaleItem()
            sale_item.sale_id = sale_id
            sale_item.product_id = product.id
            sale_item.quantity = quantity
            sale_item.unit_price = product.price
            sale_item.total_price = product.price * quantity
            # Use 0.0 instead of None for tax_rate field
            sale_item.tax_rate = float(total_tax_rate) if total_tax_rate and total_tax_rate > 0 else 0.0
            sale_item.is_tax_included = has_inclusive_tax
            
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
            'is_tax_included': sale_item.is_tax_included,
            'tax_types': product_tax_types if 'product_tax_types' in locals() else []  # NEW: Include detailed tax types for receipt generation
        })
        
    except Exception as e:
        # Handle any unexpected errors
        return jsonify({'error': 'Error interno del servidor'}), 500


@bp.route('/sales/<int:sale_id>/finalize', methods=['POST'])
def finalize_sale(sale_id):
    print(f"[DEBUG FINALIZE START] Finalize sale {sale_id} called")
    
    user = require_login()
    if not isinstance(user, models.User):
        print(f"[DEBUG FINALIZE] User login failed")
        return user
    
    print(f"[DEBUG FINALIZE] User logged in: {user.username}, role: {user.role.value}")
    
    # Validate CSRF token  
    csrf_error = validate_csrf_token()
    if csrf_error:
        print(f"[DEBUG FINALIZE] CSRF validation failed")
        return csrf_error
    
    print(f"[DEBUG FINALIZE] CSRF validation passed")
    
    # ROLE RESTRICTION: Only cashiers and administrators can finalize sales
    if user.role.value not in ['ADMINISTRADOR', 'CAJERO']:
        print(f"[DEBUG FINALIZE] Role check failed: {user.role.value}")
        return jsonify({'error': 'Solo cajeros y administradores pueden finalizar ventas'}), 403
    
    data = request.get_json()
    
    # Get NCF type from request (default to consumo)
    ncf_type_raw = data.get('ncf_type', 'consumo')
    payment_method = data.get('payment_method', 'cash')
    
    # Handle cash payment details
    cash_received = data.get('cash_received')
    change_amount = data.get('change_amount')
    
    # Handle "sin_comprobante" case - treat as consumo type
    if ncf_type_raw == 'sin_comprobante':
        ncf_type = 'consumo'
    else:
        ncf_type = ncf_type_raw
    
    # NOTE: Tax rates are now calculated automatically from individual products
    # No need to validate user-provided tax_rate as we calculate from sale items
    
    # Get client info for fiscal/government invoices
    customer_name = data.get('client_name')
    customer_rnc = data.get('client_rnc')
    
    # NEW: Get service charge (propina) option
    apply_service_charge = data.get('apply_service_charge', False)
    service_charge_rate = 0.10  # 10% standard tip rate in Dominican Republic
    
    # CRITICAL FIX: Idempotent sale finalization with proper locking to prevent NCF race conditions
    # This ensures exactly one NCF per sale even under concurrent finalization requests
    try:
        print(f"[DEBUG FINALIZE] Attempting to finalize sale {sale_id} with NCF type {ncf_type}")
        print(f"[DEBUG FINALIZE] Payment method: {payment_method}")
        print(f"[DEBUG FINALIZE] Customer info: name={customer_name}, rnc={customer_rnc}")
        
        # Get sale with row-level lock to prevent concurrent modifications
        sale = db.session.query(models.Sale).filter_by(id=sale_id).with_for_update().first()
        
        if not sale:
            error_msg = f'Venta {sale_id} no encontrada'
            print(f"[ERROR FINALIZE] {error_msg}")
            raise ValueError(error_msg)
        
        print(f"[DEBUG FINALIZE] Sale found: ID={sale.id}, status={sale.status}, cash_register_id={sale.cash_register_id}")
        
        # IDEMPOTENCY CHECK: If sale is already completed, return existing data
        # This prevents duplicate NCF allocation for the same sale
        if sale.status == 'completed':
            print(f"[DEBUG FINALIZE] Sale {sale_id} already completed with NCF {sale.ncf}")
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
            error_msg = f'No se puede finalizar una venta con estado {sale.status}'
            print(f"[ERROR FINALIZE] {error_msg}")
            raise ValueError(error_msg)
        
        print(f"[DEBUG FINALIZE] Sale status validation passed")
        
        # PREVENT EMPTY SALES: Validate that sale has items before proceeding with NCF allocation
        if not sale.sale_items:
            error_msg = 'No se puede finalizar una venta sin productos'
            print(f"[ERROR FINALIZE] {error_msg}")
            raise ValueError(error_msg)
        
        print(f"[DEBUG FINALIZE] Sale has {len(sale.sale_items)} items")
        
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
        # Only validate stock for inventariable products, not consumible ones
        for product in locked_products:
            required_quantity = product_quantities[product.id]
            # Skip stock validation for consumible products (food, drinks, services)
            if product.product_type == 'consumible':
                continue
            # Only validate stock for inventariable products
            if product.stock < required_quantity:
                raise ValueError(f'Stock insuficiente para {product.name}. Disponible: {product.stock}, requerido: {required_quantity}')
        
        # SALE REASSIGNMENT: If sale doesn't have cash register (waiter-created), assign finalizing user's cash register
        if not sale.cash_register_id:
            print(f"[DEBUG FINALIZE] Sale has no cash register, searching for user's cash register")
            # Get cash register for the finalizing user (must be cashier/admin)
            user_cash_register = db.session.query(models.CashRegister).filter_by(
                user_id=user.id, 
                active=True
            ).first()
            
            if not user_cash_register:
                error_msg = 'Solo usuarios con caja asignada pueden finalizar ventas. Contacta al administrador.'
                print(f"[ERROR FINALIZE] {error_msg}")
                raise ValueError(error_msg)
            
            # Assign the cash register to the sale for NCF generation
            sale.cash_register_id = user_cash_register.id
            print(f"[DEBUG FINALIZE] Assigned cash register {user_cash_register.id} ({user_cash_register.name}) to sale")
        else:
            print(f"[DEBUG FINALIZE] Sale already has cash register: {sale.cash_register_id}")
        
        # Get NCF sequence - now global and independent of cash registers
        print(f"[DEBUG FINALIZE] Looking for active global NCF sequences for type {ncf_type}")
        
        # Search for active NCF sequence of the required type (with row-level lock for thread safety)
        # Order by ID for deterministic selection and validate uniqueness
        active_sequences = db.session.query(models.NCFSequence).filter_by(
            ncf_type=models.NCFType(ncf_type.upper()),
            active=True
        ).order_by(models.NCFSequence.id).with_for_update().all()
        
        if len(active_sequences) > 1:
            sequence_ids = [str(seq.id) for seq in active_sequences]
            error_msg = f'Error de configuración: múltiples secuencias NCF activas para tipo {ncf_type} (IDs: {", ".join(sequence_ids)}). Solo debe haber una secuencia activa por tipo. Contacte al administrador.'
            print(f"[ERROR FINALIZE] {error_msg}")
            raise ValueError(error_msg)
        
        ncf_sequence = active_sequences[0] if active_sequences else None
        
        if ncf_sequence:
            print(f"[DEBUG FINALIZE] Found global NCF sequence: {ncf_sequence.id} (serie: {ncf_sequence.serie})")
        else:
            print(f"[DEBUG FINALIZE] No active NCF sequence found for type {ncf_type}")
            
            # Get all available sequences for debugging
            all_sequences = db.session.query(models.NCFSequence).filter_by(active=True).all()
            print(f"[DEBUG FINALIZE] Available NCF sequences:")
            for seq in all_sequences:
                print(f"  - ID: {seq.id}, Type: {seq.ncf_type}, Serie: {seq.serie}, Active: {seq.active}")
            
            available_types = [str(s.ncf_type.value) for s in all_sequences]
            if available_types:
                error_msg = f'No hay secuencia NCF activa para tipo {ncf_type}. Tipos disponibles: {", ".join(set(available_types))}'
            else:
                error_msg = 'Sistema de facturación no configurado: no hay secuencias NCF activas. Contacte al administrador para configurar las secuencias fiscales.'
            
            print(f"[ERROR FINALIZE] {error_msg}")
            raise ValueError(error_msg)
        
        # Check if sequence is exhausted (treat end_number as inclusive)
        print(f"[DEBUG FINALIZE] NCF sequence status: current={ncf_sequence.current_number}, end={ncf_sequence.end_number}")
        if ncf_sequence.current_number > ncf_sequence.end_number:
            error_msg = f'Secuencia NCF agotada. Actual: {ncf_sequence.current_number}, Límite: {ncf_sequence.end_number}'
            print(f"[ERROR FINALIZE] {error_msg}")
            raise ValueError(error_msg)
        
        # Enforce cash session requirement BEFORE NCF generation
        if payment_method == 'cash':
            # Check if user has an open cash session for cash payments
            if not sale.cash_register_id:
                error_msg = 'No tienes una caja registradora asignada para procesar pagos en efectivo'
                print(f"[ERROR FINALIZE] {error_msg}")
                raise ValueError(error_msg)
            
            # Verify the cash register has an open session
            open_session = models.CashSession.query.filter_by(
                cash_register_id=sale.cash_register_id,
                status='open'
            ).order_by(models.CashSession.opened_at.desc()).first()
            
            if not open_session:
                error_msg = 'Debes abrir la caja registradora antes de procesar pagos en efectivo'
                print(f"[ERROR FINALIZE] {error_msg}")
                raise ValueError(error_msg)
            
            print(f"[DEBUG FINALIZE] Cash payment validated with open session: {open_session.id}")
        
        # Generate NCF number using current number
        ncf_number = f"{ncf_sequence.serie}{ncf_sequence.current_number:08d}"
        print(f"[DEBUG FINALIZE] Generated NCF: {ncf_number}")
        
        # Increment counter for next use
        ncf_sequence.current_number += 1
        print(f"[DEBUG FINALIZE] NCF sequence incremented to: {ncf_sequence.current_number}")
        
        # Update sale with NCF and finalize (atomic state transition from pending to completed)
        sale.ncf_sequence_id = ncf_sequence.id
        sale.ncf = ncf_number
        sale.payment_method = payment_method
        sale.status = 'completed'
        
        # Store cash payment details if provided
        if cash_received is not None:
            sale.cash_received = cash_received
        if change_amount is not None:
            sale.change_amount = change_amount
        
        # Calculate totals with DR fiscal compliance (ITBIS over subtotal + service charge)
        subtotal_by_rate = {}
        exclusive_tax_by_rate = {}  # Track exclusive tax rates for base calculation
        total_subtotal = 0
        total_tax_included = 0  # Tax that was already included in prices
        
        # First pass: Calculate subtotal and identify tax rates
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
                # Tax is exclusive (added to price) or no tax
                subtotal_by_rate[rate] += item.total_price
                total_subtotal += item.total_price
                if rate > 0:
                    # Track exclusive tax rates and their subtotal amounts for later calculation
                    if rate not in exclusive_tax_by_rate:
                        exclusive_tax_by_rate[rate] = 0
                    exclusive_tax_by_rate[rate] += item.total_price
        
        # Calculate service charge (propina) BEFORE exclusive taxes per DR law
        service_charge_amount = 0
        if apply_service_charge:
            service_charge_amount = round(total_subtotal * service_charge_rate, 2)
        
        # Calculate exclusive taxes on tax base (subtotal + service charge for DR compliance)
        tax_base = total_subtotal + service_charge_amount
        total_tax_added = 0
        
        for rate, rate_subtotal in exclusive_tax_by_rate.items():
            # Apply tax proportionally to items that have this rate
            proportion = rate_subtotal / total_subtotal if total_subtotal > 0 else 0
            tax_on_base = tax_base * proportion * rate
            total_tax_added += round(tax_on_base, 2)
        
        # Set sale totals
        sale.subtotal = round(total_subtotal, 2)
        sale.tax_amount = round(total_tax_included + total_tax_added, 2)  # Only taxes, not service charge
        sale.service_charge_amount = service_charge_amount  # Store service charge separately
        sale.total = round(total_subtotal + total_tax_included + total_tax_added + service_charge_amount, 2)  # Include both included and added taxes
        
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
            
            # Import receipt generators
            from receipt_generator import generate_thermal_receipt_text, generate_pdf_receipt
            receipt_text = generate_thermal_receipt_text(sale_data)
            
            if receipt_text:
                response_data['receipt_printed'] = True
                response_data['receipt_text'] = receipt_text
                response_data['message'] = 'Venta finalizada exitosamente. Recibo generado automáticamente.'
                
                # Generate PDF receipt for download
                try:
                    pdf_path = generate_pdf_receipt(sale_data)
                    if pdf_path:
                        # Convert absolute path to web-accessible relative path
                        web_path = pdf_path.replace(os.getcwd() + '/', '')
                        response_data['pdf_receipt_path'] = web_path
                        response_data['pdf_generated'] = True
                        logger.info(f"Recibo PDF generado para venta {sale.id}: {web_path}")
                    else:
                        response_data['pdf_generated'] = False
                except Exception as pdf_error:
                    logger.error(f"Error generando PDF para venta {sale.id}: {str(pdf_error)}")
                    response_data['pdf_generated'] = False
                
                # Attempt automatic thermal printing
                try:
                    from thermal_printer import print_receipt_auto
                    print_success = print_receipt_auto(sale_data)
                    response_data['thermal_print_success'] = print_success
                    if print_success:
                        logger.info(f"Recibo térmico impreso automáticamente para venta {sale.id}")
                    else:
                        logger.warning(f"Fallo en impresión térmica automática para venta {sale.id}")
                except Exception as thermal_error:
                    logger.error(f"Error en impresión térmica: {str(thermal_error)}")
                    response_data['thermal_print_success'] = False
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
        error_msg = str(e)
        print(f"[ERROR FINALIZE] ValueError: {error_msg}")
        db.session.rollback()
        return jsonify({'error': error_msg}), 400
        
    except IntegrityError as e:
        # Handle database constraint violations
        error_msg = str(e)
        print(f"[ERROR FINALIZE] IntegrityError: {error_msg}")
        db.session.rollback()
        if 'unique constraint' in error_msg.lower() and 'ncf' in error_msg.lower():
            return jsonify({'error': 'Error de concurrencia al generar NCF. Intente nuevamente.'}), 500
        else:
            return jsonify({'error': f'Error de integridad de datos: {error_msg}'}), 500
            
    except Exception as e:
        # Handle other unexpected errors
        error_msg = str(e)
        print(f"[ERROR FINALIZE] Unexpected error: {error_msg}")
        print(f"[ERROR FINALIZE] Error type: {type(e).__name__}")
        import traceback
        print(f"[ERROR FINALIZE] Traceback: {traceback.format_exc()}")
        db.session.rollback()
        return jsonify({'error': f'Error interno: {error_msg}'}), 500



@bp.route('/sales/<int:sale_id>/items/<int:item_id>', methods=['DELETE'])
def remove_sale_item(sale_id, item_id):
    user = require_login()
    if not isinstance(user, models.User):
        return user
    
    # Validate CSRF token
    csrf_error = validate_csrf_token()
    if csrf_error:
        return csrf_error
    
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
    
    # Validate CSRF token
    csrf_error = validate_csrf_token()
    if csrf_error:
        return csrf_error
    
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
                if user.role.value == 'MESERO':
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
    
    # Validate CSRF token
    csrf_error = validate_csrf_token()
    if csrf_error:
        return csrf_error
    
    data = request.get_json()
    new_status = data.get('order_status')
    
    if not new_status:
        return jsonify({'error': 'order_status es requerido'}), 400
    
    # Validate order status
    valid_statuses = [status.value for status in models.OrderStatus]
    if new_status not in valid_statuses:
        return jsonify({'error': f'Estado inválido. Debe ser uno de: {valid_statuses}'}), 400
    
    try:
        sale = db.session.query(models.Sale).filter_by(id=sale_id).with_for_update().first()
        
        if not sale:
            return jsonify({'error': 'Venta no encontrada'}), 404
        
        # Only allow updating order status for pending sales
        if sale.status != 'pending':
            return jsonify({'error': 'Solo se puede actualizar el estado de pedidos pendientes'}), 400
        
        # Update order status
        sale.order_status = models.OrderStatus(new_status)
        db.session.commit()
            
        return jsonify({
            'success': True,
            'sale_id': sale.id,
            'order_status': sale.order_status.value,
            'message': f'Estado del pedido actualizado a: {sale.order_status.value}'
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': f'Error interno: {str(e)}'}), 500


@bp.route('/sales/<int:sale_id>/send-to-kitchen', methods=['POST'])
def send_to_kitchen(sale_id):
    """Send sale to kitchen - updates order status to sent_to_kitchen"""
    user = require_login()
    if not isinstance(user, models.User):
        return user
    
    # Validate CSRF token
    csrf_error = validate_csrf_token()
    if csrf_error:
        return csrf_error
    
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
    if user.role.value not in ['ADMINISTRADOR', 'CAJERO']:
        return jsonify({'error': 'Solo cajeros y administradores pueden ver órdenes pendientes de facturación'}), 403
    
    try:
        # Get pending sales with table and user information
        # Only show orders that are pending and not yet being processed (not_sent or sent_to_kitchen)
        pending_sales = models.Sale.query.filter(
            models.Sale.status == 'pending',
            models.Sale.order_status.in_([models.OrderStatus.NOT_SENT, models.OrderStatus.SENT_TO_KITCHEN])
        ).options(
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
    if user.role.value not in ['ADMINISTRADOR', 'CAJERO']:
        return jsonify({'error': 'No tienes permisos para ver recibos'}), 403
    
    if user.role.value == 'CAJERO':
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
    if user.role.value not in ['ADMINISTRADOR', 'CAJERO']:
        return jsonify({'error': 'No tienes permisos para generar recibos'}), 403
    
    if user.role.value == 'CAJERO':
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
    if user.role.value not in ['ADMINISTRADOR', 'CAJERO']:
        return jsonify({'error': 'No tienes permisos para generar recibos'}), 403
    
    if user.role.value == 'CAJERO':
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
        'tax_amount': sale.tax_amount,  # Use calculated tax from sale (taxes only)
        'service_charge_amount': getattr(sale, 'service_charge_amount', 0),  # Service charge/propina
        'payment_method': sale.payment_method,
        'payment_method_display': {
            'efectivo': 'Efectivo',
            'tarjeta': 'Tarjeta',
            'transferencia': 'Transferencia'
        }.get(sale.payment_method, sale.payment_method.title()),
        'cashier_name': sale.user.name if sale.user else None,
        'ncf_type_display': _get_ncf_type_display(sale.ncf) if sale.ncf else None,
        'customer_name': sale.customer_name,
        'customer_rnc': sale.customer_rnc,
        'cash_received': getattr(sale, 'cash_received', None),
        'change_amount': getattr(sale, 'change_amount', None),
        'items': []
    }
    
    # Add items with CRITICAL tax fields needed for line-by-line tax display
    for item in sale_items:
        # Defensive fallback: if fields are NULL, use product's current values
        tax_rate = item.tax_rate if hasattr(item, 'tax_rate') and item.tax_rate is not None else item.product.tax_rate
        is_tax_included = item.is_tax_included if hasattr(item, 'is_tax_included') and item.is_tax_included is not None else item.product.is_tax_included
        
        # NEW TAX SYSTEM: Get product's tax types for receipt generation
        product_tax_types = []
        if hasattr(item, 'product') and item.product and hasattr(item.product, 'product_taxes'):
            for product_tax in item.product.product_taxes:
                if product_tax.tax_type and product_tax.tax_type.active:
                    product_tax_types.append({
                        'name': product_tax.tax_type.name,
                        'rate': product_tax.tax_type.rate,
                        'is_inclusive': product_tax.tax_type.is_inclusive
                    })
        
        sale_data['items'].append({
            'quantity': item.quantity,
            'product_name': item.product.name,
            'name': item.product.name,  # Alternative name field
            'price': item.unit_price,
            'tax_rate': tax_rate,  # LEGACY: Backward compatibility
            'is_tax_included': is_tax_included,  # LEGACY: Backward compatibility
            'tax_types': product_tax_types  # NEW: Detailed tax types for receipt
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
    if user.role.value not in ['ADMINISTRADOR', 'CAJERO']:
        return jsonify({'error': 'No tienes permisos para ver esta venta'}), 403
    
    if user.role.value == 'CAJERO':
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
        'table_id': sale.table_id,
        'table_number': sale.table.number if sale.table else None,
        'table_name': sale.table.name if sale.table else None,
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
    
    # Validate CSRF token
    csrf_error = validate_csrf_token()
    if csrf_error:
        return csrf_error
    
    # Only administrators and cashiers can create credit notes
    if user.role.value not in ['ADMINISTRADOR', 'CAJERO']:
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
            credit_note.note_type = models.NCFType.NOTA_CREDITO if note_type == 'nota_credito' else models.NCFType.NOTA_DEBITO
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
    if user.role.value not in ['ADMINISTRADOR', 'CAJERO']:
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
    if user.role.value not in ['ADMINISTRADOR', 'CAJERO']:
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
    
    # Validate CSRF token
    csrf_error = validate_csrf_token()
    if csrf_error:
        return csrf_error
    
    # Only administrators and cashiers can cancel sales
    if user.role.value not in ['ADMINISTRADOR', 'CAJERO']:
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


def require_admin_or_cashier_api():
    """API-specific authorization check for admin/cashier - returns JSON response"""
    if 'user_id' not in session:
        return None
    
    user = models.User.query.get(session['user_id'])
    if not user or user.role.value not in ['ADMINISTRADOR', 'CAJERO']:
        return None
    
    return user


def require_admin_or_manager_api():
    """API-specific authorization check for admin/manager - returns JSON response"""
    if 'user_id' not in session:
        return None
    
    user = models.User.query.get(session['user_id'])
    if not user or user.role.value not in ['ADMINISTRADOR', 'GERENTE']:
        return None
    
    return user


def require_manager_api():
    """API-specific authorization check for manager only - returns JSON response"""
    if 'user_id' not in session:
        return None
    
    user = models.User.query.get(session['user_id'])
    if not user or user.role.value != 'GERENTE':
        return None
    
    return user


def require_admin_or_manager_or_cashier_api():
    """API-specific authorization check for admin/manager/cashier - returns JSON response"""
    if 'user_id' not in session:
        return None
    
    user = models.User.query.get(session['user_id'])
    if not user or user.role.value not in ['ADMINISTRADOR', 'GERENTE', 'CAJERO']:
        return None
    
    return user

@bp.route('/sales/<int:sale_id>/table-details', methods=['GET'])
def get_table_sale_details(sale_id):
    """Get detailed information about a sale for table management - Admin/Manager/Cashier only"""
    user = require_admin_or_manager_or_cashier_api()
    if not user:
        return jsonify({'error': 'Solo administradores, gerentes y cajeros pueden ver detalles de ventas'}), 403
    
    sale = models.Sale.query.get_or_404(sale_id)
    sale_items = models.SaleItem.query.filter_by(sale_id=sale_id).all()
    
    # Prepare sale details
    sale_details = {
        'id': sale.id,
        'created_at': sale.created_at.isoformat(),
        'table_number': sale.table.number if sale.table else None,
        'table_name': sale.table.name if sale.table else None,
        'status': sale.status,
        'total': sale.total,
        'subtotal': sale.subtotal,
        'tax_amount': sale.tax_amount,
        'description': sale.description,
        'items': []
    }
    
    # Add sale items
    for item in sale_items:
        sale_details['items'].append({
            'product_name': item.product.name,
            'quantity': item.quantity,
            'unit_price': item.unit_price,
            'total_price': item.total_price
        })
    
    return jsonify(sale_details)


@bp.route('/sales/<int:sale_id>/table-finalize', methods=['POST'])
def finalize_table_sale(sale_id):
    """Finalize a table sale with NCF generation - Admin/Manager/Cashier only"""
    user = require_admin_or_manager_or_cashier_api()
    if not user:
        return jsonify({'error': 'Solo administradores, gerentes y cajeros pueden facturar órdenes'}), 403
    
    # Validate CSRF token
    try:
        data = request.get_json() or {}
        csrf_token = request.headers.get('X-CSRFToken') or data.get('csrf_token')
        if not csrf_token:
            return jsonify({'error': 'Token CSRF requerido'}), 400
        validate_csrf(csrf_token)
    except BadRequest:
        return jsonify({'error': 'Token CSRF inválido'}), 400
    
    # Get cash register for admin/cashier
    cash_register = models.CashRegister.query.filter_by(user_id=user.id, active=True).first()
    if not cash_register:
        return jsonify({'error': 'No tienes una caja registradora asignada'}), 400
    
    try:
        # data already available from CSRF validation above
        
        # Validate required fields - only payment_method is required now
        payment_method = data.get('payment_method')
        
        if not payment_method:
            return jsonify({'error': 'Método de pago es requerido'}), 400
        
        sale = models.Sale.query.get_or_404(sale_id)
        
        # Ensure sale is pending
        if sale.status != 'pending':
            return jsonify({'error': f'Esta venta ya está {sale.status}'}), 400
        
        # Determine NCF type automatically based on customer info already in the sale
        # If customer_rnc exists in sale, it's credito_fiscal, otherwise consumo
        if sale.customer_rnc and sale.customer_rnc.strip():
            ncf_type = models.NCFType.CREDITO_FISCAL
            ncf_type_str = 'credito_fiscal'
        else:
            ncf_type = models.NCFType.CONSUMO
            ncf_type_str = 'consumo'
        
        # Update sale with billing information
        sale.payment_method = payment_method
        # Keep existing customer info - don't override from request
        # sale.customer_name and sale.customer_rnc remain as they were set when creating the order
        
        # Store cash payment details if provided
        cash_received = data.get('cash_received')
        change_amount = data.get('change_amount')
        if cash_received is not None:
            sale.cash_received = cash_received
        if change_amount is not None:
            sale.change_amount = change_amount
        sale.cash_register_id = cash_register.id
        sale.user_id = user.id
        
        # Use existing atomic NCF allocation logic (reuse from existing finalize_sale)
        with db.session.begin_nested():  # Atomic transaction
            ncf_sequence = db.session.query(models.NCFSequence).filter_by(
                ncf_type=ncf_type,
                active=True
            ).filter(
                models.NCFSequence.current_number < models.NCFSequence.end_number
            ).with_for_update().first()  # Lock the row
            
            if not ncf_sequence:
                return jsonify({'error': f'No hay NCF disponibles del tipo {ncf_type_str}'}), 400
            
            # Generate NCF using the existing system format
            sale.ncf_sequence_id = ncf_sequence.id
            next_number = ncf_sequence.current_number + 1
            
            # Use existing NCF format (B01 prefix + series + number)
            prefix = ncf_sequence.serie  # B01, B02, B14 etc
            sale.ncf = f"{prefix}{next_number:08d}"
            
            # Mark NCF as used atomically
            ncf_sequence.current_number = next_number
        
        # Complete the sale
        sale.status = 'completed'
        sale.completed_at = datetime.utcnow()
        
        # Update table status to available
        if sale.table:
            sale.table.status = models.TableStatus.AVAILABLE
        
        # Commit changes
        db.session.commit()
        
        # Prepare response data
        response_data = {
            'success': True,
            'message': 'Venta facturada exitosamente',
            'sale_id': sale.id,
            'ncf': sale.ncf,
            'total': sale.total,
            'payment_method': sale.payment_method
        }
        
        # Automatic receipt printing (same as POS finalization)
        try:
            # Check user device info to determine format preference
            user_agent = request.headers.get('User-Agent', '').lower()
            receipt_format = '58mm' if any(mobile in user_agent for mobile in ['mobile', 'android', 'iphone']) else '80mm'
            
            # Generate thermal receipt for automatic printing
            sale_items = models.SaleItem.query.filter_by(sale_id=sale.id).all()
            sale_data = _prepare_sale_data_for_receipt(sale, sale_items)
            
            from receipt_generator import generate_thermal_receipt_text
            receipt_text = generate_thermal_receipt_text(sale_data)
            
            # Add receipt data to response for automatic display
            response_data['receipt_text'] = receipt_text
            response_data['auto_print'] = True
            
            # Attempt automatic thermal printing
            try:
                from thermal_printer import print_receipt_auto
                print_success = print_receipt_auto(sale_data)
                response_data['thermal_print_success'] = print_success
                if print_success:
                    logger.info(f"Recibo térmico impreso automáticamente para venta {sale.id}")
                else:
                    logger.warning(f"Fallo en impresión térmica automática para venta {sale.id}")
            except Exception as thermal_error:
                logger.error(f"Error en impresión térmica: {str(thermal_error)}")
                response_data['thermal_print_success'] = False
            
        except Exception as e:
            print(f"[ERROR PRINT] Auto receipt error for sale {sale.id}: {str(e)}")
            # Don't fail the sale, just notify about printing issue
            response_data['message'] = 'Venta facturada exitosamente. Error en impresión automática de recibo.'
        
        return jsonify(response_data)
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': f'Error finalizando venta: {str(e)}'}), 500


@bp.route('/sales/cash-summary', methods=['GET'])
def get_cash_summary():
    """Get cash summary for the current day broken down by payment method"""
    user = require_login()
    if not isinstance(user, models.User):
        return user
    
    # Get today's date
    today = datetime.now().date()
    
    try:
        # Get sales grouped by payment method for today
        from sqlalchemy import func
        
        sales_summary = db.session.query(
            models.Sale.payment_method,
            func.sum(models.Sale.total).label('total'),
            func.count(models.Sale.id).label('count')
        ).filter(
            func.date(models.Sale.created_at) == today,
            models.Sale.status == 'completed'
        ).group_by(models.Sale.payment_method).all()
        
        # Initialize totals
        cash_total = 0.0
        card_total = 0.0
        transfer_total = 0.0
        total_sales = 0.0
        
        # Process results (handle both 'cash' and 'efectivo' for backwards compatibility)
        for payment_method, total, count in sales_summary:
            if payment_method in ['cash', 'efectivo']:
                cash_total += float(total or 0)
            elif payment_method == 'card':
                card_total = float(total or 0)
            elif payment_method == 'transfer':
                transfer_total = float(total or 0)
            
            total_sales += float(total or 0)
        
        return jsonify({
            'cash_total': cash_total,
            'card_total': card_total,
            'transfer_total': transfer_total,
            'total_sales': total_sales,
            'date': today.isoformat()
        })
        
    except Exception as e:
        print(f"[ERROR] Failed to get cash summary: {str(e)}")
        return jsonify({'error': f'Error al obtener resumen de caja: {str(e)}'}), 500


@bp.route('/cash-register/status', methods=['GET'])
def get_cash_register_status():
    """Get current user's cash register session status"""
    user = require_login()
    if not isinstance(user, models.User):
        return user
    
    # Check if user has permission (admin or cashier)
    if user.role.value not in ['ADMINISTRADOR', 'CAJERO']:
        return jsonify({'error': 'No tienes permisos para acceder al estado de caja'}), 403
    
    try:
        # Find user's active cash register
        cash_register = models.CashRegister.query.filter_by(user_id=user.id, active=True).first()
        
        if not cash_register:
            return jsonify({
                'has_register': False,
                'message': 'No tienes una caja registradora asignada'
            })
        
        # Find current open cash session
        current_session = models.CashSession.query.filter_by(
            cash_register_id=cash_register.id,
            status='open'
        ).order_by(models.CashSession.opened_at.desc()).first()
        
        if current_session:
            return jsonify({
                'has_register': True,
                'register_name': cash_register.name,
                'register_id': cash_register.id,
                'has_open_session': True,
                'session_id': current_session.id,
                'opened_at': current_session.opened_at.isoformat(),
                'opening_amount': current_session.opening_amount,
                'session_status': 'open'
            })
        else:
            return jsonify({
                'has_register': True,
                'register_name': cash_register.name,
                'register_id': cash_register.id,
                'has_open_session': False,
                'session_status': 'closed'
            })
            
    except Exception as e:
        print(f"[ERROR] Failed to get cash register status: {str(e)}")
        return jsonify({'error': 'Error obteniendo estado de caja'}), 500


@bp.route('/cash-register/open', methods=['POST'])
def open_cash_register():
    """Open cash register session"""
    user = require_login()
    if not isinstance(user, models.User):
        return user
        
    # Check if user has permission (admin or cashier)
    if user.role.value not in ['ADMINISTRADOR', 'CAJERO']:
        return jsonify({'error': 'No tienes permisos para abrir caja'}), 403
    
    # Validate CSRF token
    csrf_error = validate_csrf_token()
    if csrf_error:
        return csrf_error
    
    try:
        data = request.get_json()
        opening_amount = float(data.get('opening_amount', 0))
        opening_notes = data.get('opening_notes', '')
        
        # Validate opening amount
        if opening_amount < 0:
            return jsonify({'error': 'El monto de apertura no puede ser negativo'}), 400
        
        # Find user's active cash register
        cash_register = models.CashRegister.query.filter_by(user_id=user.id, active=True).first()
        
        if not cash_register:
            return jsonify({'error': 'No tienes una caja registradora asignada'}), 400
        
        # Check if there's already an open session
        existing_session = models.CashSession.query.filter_by(
            cash_register_id=cash_register.id,
            status='open'
        ).first()
        
        if existing_session:
            return jsonify({'error': 'Ya tienes una sesión de caja abierta'}), 400
        
        # Create new cash session
        new_session = models.CashSession()
        new_session.cash_register_id = cash_register.id
        new_session.user_id = user.id
        new_session.opening_amount = opening_amount
        new_session.opening_notes = opening_notes
        new_session.status = 'open'
        
        db.session.add(new_session)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': f'Caja {cash_register.name} abierta exitosamente',
            'session_id': new_session.id,
            'opening_amount': opening_amount
        })
        
    except ValueError:
        return jsonify({'error': 'El monto de apertura debe ser un número válido'}), 400
    except Exception as e:
        db.session.rollback()
        print(f"[ERROR] Failed to open cash register: {str(e)}")
        return jsonify({'error': 'Error abriendo caja registradora'}), 500


@bp.route('/cash-register/close', methods=['POST'])
def close_cash_register():
    """Close cash register session with detailed summary"""
    user = require_login()
    if not isinstance(user, models.User):
        return user
        
    # Check if user has permission (admin or cashier)
    if user.role.value not in ['ADMINISTRADOR', 'CAJERO']:
        return jsonify({'error': 'No tienes permisos para cerrar caja'}), 403
    
    # Validate CSRF token
    csrf_error = validate_csrf_token()
    if csrf_error:
        return csrf_error
    
    try:
        data = request.get_json()
        closing_amount = float(data.get('closing_amount', 0))
        closing_notes = data.get('closing_notes', '')
        
        # Validate closing amount
        if closing_amount < 0:
            return jsonify({'error': 'El monto de cierre no puede ser negativo'}), 400
        
        # Find user's active cash register
        cash_register = models.CashRegister.query.filter_by(user_id=user.id, active=True).first()
        
        if not cash_register:
            return jsonify({'error': 'No tienes una caja registradora asignada'}), 400
        
        # Find current open session
        current_session = models.CashSession.query.filter_by(
            cash_register_id=cash_register.id,
            status='open'
        ).order_by(models.CashSession.opened_at.desc()).first()
        
        if not current_session:
            return jsonify({'error': 'No hay una sesión de caja abierta para cerrar'}), 400
        
        # Get sales summary for the session period
        from sqlalchemy import func
        session_sales = db.session.query(
            models.Sale.payment_method,
            func.sum(models.Sale.total).label('total'),
            func.count(models.Sale.id).label('count')
        ).filter(
            models.Sale.cash_register_id == cash_register.id,
            models.Sale.created_at >= current_session.opened_at,
            models.Sale.status == 'completed'
        ).group_by(models.Sale.payment_method).all()
        
        # Calculate session totals
        cash_sales = 0.0
        card_sales = 0.0
        transfer_sales = 0.0
        total_transactions = 0
        
        for payment_method, total, count in session_sales:
            if payment_method in ['cash', 'efectivo']:
                cash_sales += float(total or 0)
            elif payment_method == 'card':
                card_sales += float(total or 0)
            elif payment_method == 'transfer':
                transfer_sales += float(total or 0)
            total_transactions += count
        
        expected_cash = current_session.opening_amount + cash_sales
        cash_difference = closing_amount - expected_cash
        
        # Close the session
        current_session.closing_amount = closing_amount
        current_session.closing_notes = closing_notes
        current_session.closed_at = datetime.utcnow()
        current_session.status = 'closed'
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': f'Caja {cash_register.name} cerrada exitosamente',
            'session_summary': {
                'session_id': current_session.id,
                'opened_at': current_session.opened_at.isoformat(),
                'closed_at': current_session.closed_at.isoformat(),
                'opening_amount': current_session.opening_amount,
                'closing_amount': closing_amount,
                'cash_sales': cash_sales,
                'card_sales': card_sales,
                'transfer_sales': transfer_sales,
                'total_sales': cash_sales + card_sales + transfer_sales,
                'total_transactions': total_transactions,
                'expected_cash': expected_cash,
                'cash_difference': cash_difference,
                'opening_notes': current_session.opening_notes,
                'closing_notes': closing_notes
            }
        })
        
    except ValueError:
        return jsonify({'error': 'El monto de cierre debe ser un número válido'}), 400
    except Exception as e:
        db.session.rollback()
        print(f"[ERROR] Failed to close cash register: {str(e)}")
        return jsonify({'error': 'Error cerrando caja registradora'}), 500


@bp.route('/customers')
def get_customers():
    """Get all active customers for POS customer selection dropdown"""
    user = require_login()
    if not isinstance(user, models.User):
        return user
    
    # Get all active customers ordered by name
    customers = models.Customer.query.filter_by(active=True).order_by(models.Customer.name.asc()).all()
    
    # Return customer data with id, name, and rnc
    customers_data = []
    for customer in customers:
        customers_data.append({
            'id': customer.id,
            'name': customer.name,
            'rnc': customer.rnc,
            'phone': customer.phone,
            'email': customer.email,
            'address': customer.address
        })
    
    return jsonify(customers_data)


# PWA Authentication Endpoints

@bp.route('/auth/login', methods=['POST'])
def api_login():
    """JSON login endpoint for PWA authentication"""
    try:
        if not request.is_json:
            return jsonify({'error': 'Content-Type must be application/json'}), 400
        
        data = request.get_json()
        username = data.get('username')
        password = data.get('password')
        
        if not username or not password:
            return jsonify({'error': 'Usuario y contraseña son requeridos'}), 400
        
        user = models.User.query.filter_by(username=username, active=True).first()
        
        # Check password using appropriate method based on hash format
        password_valid = False
        if user:
            if user.password_hash.startswith('$2b$') or user.password_hash.startswith('$2a$'):
                # bcrypt hash
                try:
                    import bcrypt
                    password_valid = bcrypt.checkpw(password.encode('utf-8'), user.password_hash.encode('utf-8'))
                except ValueError:
                    password_valid = False
            else:
                # werkzeug/scrypt hash
                from werkzeug.security import check_password_hash
                password_valid = check_password_hash(user.password_hash, password)
        
        if user and password_valid:
            # Update last_login timestamp
            user.last_login = datetime.utcnow()
            db.session.commit()
            
            # Set session for the user
            session['user_id'] = user.id
            session['username'] = user.username
            session['role'] = user.role.value
            
            # Return user data JSON response
            return jsonify({
                'success': True,
                'message': 'Inicio de sesión exitoso',
                'user': {
                    'id': user.id,
                    'username': user.username,
                    'name': user.name,
                    'role': user.role.value,
                    'must_change_password': user.must_change_password
                }
            })
        else:
            return jsonify({'error': 'Usuario o contraseña incorrectos'}), 401
    
    except Exception as e:
        print(f"[ERROR] API login failed: {str(e)}")
        return jsonify({'error': 'Error interno del servidor'}), 500


@bp.route('/auth/user')
def api_get_current_user():
    """Get current logged in user info"""
    user = require_login()
    if not isinstance(user, models.User):
        return user
    
    return jsonify({
        'id': user.id,
        'username': user.username,
        'name': user.name,
        'role': user.role.value,
        'must_change_password': user.must_change_password
    })


@bp.route('/auth/logout', methods=['POST'])
def api_logout():
    """JSON logout endpoint for PWA"""
    session.clear()
    return jsonify({
        'success': True,
        'message': 'Sesión cerrada exitosamente'
    })


@bp.route('/csrf')
def get_csrf_token():
    """Get CSRF token for API requests"""
    from flask_wtf.csrf import generate_csrf
    try:
        csrf_token = generate_csrf()
        return jsonify({
            'csrf_token': csrf_token
        })
    except Exception as e:
        print(f"[ERROR] Failed to generate CSRF token: {str(e)}")
        return jsonify({'error': 'Error generando token CSRF'}), 500


@bp.route('/sales/preview', methods=['POST'])
def preview_sale_calculation():
    """Preview sale tax calculations without creating records - server-side totals as source of truth"""
    user = require_login()
    if not isinstance(user, models.User):
        return user
    
    # Validate CSRF token
    csrf_error = validate_csrf_token()
    if csrf_error:
        return csrf_error
    
    data = request.get_json()
    if not data:
        return jsonify({'error': 'No se proporcionaron datos'}), 400
    
    items = data.get('items', [])
    apply_service_charge = data.get('apply_service_charge', False)
    service_charge_rate = 0.10  # 10% standard tip rate in Dominican Republic
    
    if not items:
        return jsonify({'error': 'Se requiere al menos un producto'}), 400
    
    try:
        # Calculate totals using same logic as finalize_sale
        subtotal_by_rate = {}
        exclusive_tax_by_rate = {}
        total_subtotal = 0
        total_tax_included = 0
        item_details = []
        
        # Process each item
        for item_data in items:
            product_id = item_data.get('product_id')
            quantity = item_data.get('quantity', 1)
            
            if not product_id:
                return jsonify({'error': 'product_id es requerido para cada item'}), 400
            
            try:
                quantity = int(quantity)
                if quantity <= 0:
                    return jsonify({'error': 'La cantidad debe ser mayor a 0'}), 400
            except (ValueError, TypeError):
                return jsonify({'error': 'La cantidad debe ser un número válido'}), 400
            
            # Get product
            product = models.Product.query.get(product_id)
            if not product:
                return jsonify({'error': f'Producto {product_id} no encontrado'}), 404
            
            # Determine tax rate and inclusivity (same logic as add_sale_item)
            frontend_tax_type_id = item_data.get('tax_type_id')
            frontend_is_inclusive = item_data.get('is_inclusive')
            
            if frontend_tax_type_id:
                # Use tax information explicitly provided by frontend
                tax_type = None
                for tt in models.TaxType.query.filter_by(active=True).all():
                    if tt.id == frontend_tax_type_id:
                        tax_type = {'rate': tt.rate, 'is_inclusive': tt.is_inclusive}
                        break
                
                if tax_type:
                    total_tax_rate = tax_type['rate']
                    has_inclusive_tax = frontend_is_inclusive if frontend_is_inclusive is not None else tax_type['is_inclusive']
                else:
                    total_tax_rate = 0.18  # Default ITBIS 18%
                    has_inclusive_tax = True
            else:
                # Get product's tax types for NEW TAX SYSTEM
                product_tax_types = []
                for product_tax in product.product_taxes:
                    if product_tax.tax_type.active:
                        product_tax_types.append({
                            'rate': product_tax.tax_type.rate,
                            'is_inclusive': product_tax.tax_type.is_inclusive
                        })
                
                if product_tax_types:
                    total_tax_rate = sum(tax['rate'] for tax in product_tax_types)
                    has_inclusive_tax = any(tax['is_inclusive'] for tax in product_tax_types)
                else:
                    # Default fallback for fiscal compliance
                    total_tax_rate = 0.18  # Default ITBIS 18%
                    has_inclusive_tax = True
            
            # Calculate item totals
            item_total = product.price * quantity
            
            if total_tax_rate not in subtotal_by_rate:
                subtotal_by_rate[total_tax_rate] = 0
            
            item_subtotal = 0
            item_tax_amount = 0
            
            if has_inclusive_tax and total_tax_rate > 0:
                # Tax is included in the price
                base_amount = item_total / (1 + total_tax_rate)
                tax_amount = item_total - base_amount
                subtotal_by_rate[total_tax_rate] += base_amount
                total_subtotal += base_amount
                total_tax_included += round(tax_amount, 2)
                item_subtotal = base_amount
                item_tax_amount = tax_amount
            else:
                # Tax is exclusive or no tax
                subtotal_by_rate[total_tax_rate] += item_total
                total_subtotal += item_total
                item_subtotal = item_total
                if total_tax_rate > 0:
                    if total_tax_rate not in exclusive_tax_by_rate:
                        exclusive_tax_by_rate[total_tax_rate] = 0
                    exclusive_tax_by_rate[total_tax_rate] += item_total
            
            # Add item details for response
            item_details.append({
                'product_id': product_id,
                'product_name': product.name,
                'quantity': quantity,
                'unit_price': product.price,
                'total_price': item_total,
                'tax_rate': total_tax_rate,
                'is_tax_included': has_inclusive_tax,
                'item_subtotal': round(item_subtotal, 2),
                'item_tax_amount': round(item_tax_amount, 2)
            })
        
        # Calculate service charge BEFORE exclusive taxes
        service_charge_amount = 0
        if apply_service_charge:
            service_charge_amount = round(total_subtotal * service_charge_rate, 2)
        
        # Calculate exclusive taxes on tax base (subtotal + service charge)
        tax_base = total_subtotal + service_charge_amount
        total_tax_added = 0
        
        for rate, rate_subtotal in exclusive_tax_by_rate.items():
            # Apply tax proportionally to items that have this rate
            proportion = rate_subtotal / total_subtotal if total_subtotal > 0 else 0
            tax_on_base = tax_base * proportion * rate
            total_tax_added += round(tax_on_base, 2)
            
            # Update item details with exclusive tax amounts
            for item in item_details:
                if item['tax_rate'] == rate and not item['is_tax_included']:
                    item_proportion = (item['total_price']) / rate_subtotal if rate_subtotal > 0 else 0
                    item['item_tax_amount'] = round(tax_on_base * item_proportion, 2)
        
        # Final totals
        final_subtotal = round(total_subtotal, 2)
        final_tax_amount = round(total_tax_included + total_tax_added, 2)
        final_service_charge = service_charge_amount
        final_total = round(total_subtotal + total_tax_added + service_charge_amount, 2)
        
        return jsonify({
            'success': True,
            'preview': True,
            'items': item_details,
            'totals': {
                'subtotal': final_subtotal,
                'tax_amount': final_tax_amount,
                'service_charge_amount': final_service_charge,
                'total': final_total
            },
            'tax_breakdown': {
                'included_taxes': round(total_tax_included, 2),
                'exclusive_taxes': round(total_tax_added, 2),
                'service_charge_rate': service_charge_rate if apply_service_charge else 0,
                'tax_base': round(tax_base, 2) if exclusive_tax_by_rate else final_subtotal
            }
        })
        
    except Exception as e:
        print(f"[ERROR] Sales preview calculation failed: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': 'Error en cálculo de preview', 'details': str(e)}), 500