from flask import Blueprint, render_template, request, redirect, url_for, session, flash, jsonify, make_response
import models
from models import db
from datetime import datetime, date
from sqlalchemy import func, and_
import bcrypt
import secrets
from flask_wtf.csrf import validate_csrf
from werkzeug.exceptions import BadRequest
from utils import (
    initialize_company_settings, 
    get_company_settings, 
    update_company_setting,
    get_company_info_for_receipt
)

bp = Blueprint('admin', __name__, url_prefix='/admin')


def validate_csrf_token():
    """Validate CSRF token for POST requests"""
    try:
        # Support CSRF token from form, JSON body, or header
        csrf_token = None
        
        # Try form data first (for HTML forms)
        if request.form.get('csrf_token'):
            csrf_token = request.form.get('csrf_token')
        # Try JSON body (for API calls)
        elif request.is_json and request.get_json() and request.get_json().get('csrf_token'):
            csrf_token = request.get_json().get('csrf_token')
        # Try header (for API calls)
        elif request.headers.get('X-CSRFToken'):
            csrf_token = request.headers.get('X-CSRFToken')
        
        if not csrf_token:
            flash('Token de seguridad requerido.', 'error')
            return False
            
        validate_csrf(csrf_token)
    except BadRequest:
        flash('Token de seguridad inválido. Inténtalo de nuevo.', 'error')
        return False
    return True


def require_admin_or_cashier():
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))
    
    user = models.User.query.get(session['user_id'])
    if not user or user.role.value not in ['ADMINISTRADOR', 'CAJERO']:
        flash('Acceso denegado', 'error')
        return redirect(url_for('auth.login'))
    
    return user


def require_admin():
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))
    
    user = models.User.query.get(session['user_id'])
    if not user or user.role.value != 'ADMINISTRADOR':
        flash('Solo los administradores pueden acceder a esta sección', 'error')
        return redirect(url_for('admin.dashboard'))
    
    return user


def require_pos_access():
    """Allow admin, manager, cashier, or waiter access to POS system"""
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))
    
    user = models.User.query.get(session['user_id'])
    if not user or user.role.value not in ['ADMINISTRADOR', 'GERENTE', 'CAJERO', 'MESERO']:
        flash('No tienes permisos para acceder al punto de venta.', 'error')
        return redirect(url_for('auth.login'))
    
    return user


def require_manager():
    """Only manager access"""
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))
    
    user = models.User.query.get(session['user_id'])
    if not user or user.role.value != 'GERENTE':
        flash('Solo los gerentes pueden acceder a esta sección', 'error')
        return redirect(url_for('admin.dashboard'))
    
    return user


def require_admin_or_manager():
    """Allow admin or manager access"""
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))
    
    user = models.User.query.get(session['user_id'])
    if not user or user.role.value not in ['ADMINISTRADOR', 'GERENTE']:
        flash('Solo administradores y gerentes pueden acceder a esta sección', 'error')
        return redirect(url_for('admin.dashboard'))
    
    return user


def require_admin_or_manager_or_cashier():
    """Allow admin, manager, or cashier access"""
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))
    
    user = models.User.query.get(session['user_id'])
    if not user or user.role.value not in ['ADMINISTRADOR', 'GERENTE', 'CAJERO']:
        flash('Acceso denegado', 'error')
        return redirect(url_for('auth.login'))
    
    return user


@bp.route('/dashboard')
def dashboard():
    user = require_admin_or_manager_or_cashier()
    if not isinstance(user, models.User):
        return user
    
    # Get today's statistics
    today = date.today()
    daily_sales = db.session.query(func.sum(models.Sale.total)).filter(
        func.date(models.Sale.created_at) == today,
        models.Sale.status == 'completed'
    ).scalar() or 0
    
    daily_transactions = models.Sale.query.filter(
        func.date(models.Sale.created_at) == today,
        models.Sale.status == 'completed'
    ).count()
    
    # Get yesterday's sales for comparison
    from datetime import timedelta
    yesterday = today - timedelta(days=1)
    yesterday_sales = db.session.query(func.sum(models.Sale.total)).filter(
        func.date(models.Sale.created_at) == yesterday,
        models.Sale.status == 'completed'
    ).scalar() or 0
    
    # Calculate percentage change
    if yesterday_sales > 0:
        sales_change_percent = ((daily_sales - yesterday_sales) / yesterday_sales) * 100
    else:
        sales_change_percent = 100 if daily_sales > 0 else 0
    
    low_stock_products = models.Product.query.filter(
        models.Product.stock <= models.Product.min_stock,
        models.Product.active == True,
        models.Product.product_type == 'inventariable'
    ).all()
    
    # Most sold product today
    top_product = db.session.query(
        models.Product.name,
        func.sum(models.SaleItem.quantity).label('total_quantity'),
        func.sum(models.SaleItem.total_price).label('total_revenue')
    ).join(
        models.SaleItem, models.Product.id == models.SaleItem.product_id
    ).join(
        models.Sale, models.SaleItem.sale_id == models.Sale.id
    ).filter(
        func.date(models.Sale.created_at) == today,
        models.Sale.status == 'completed'
    ).group_by(
        models.Product.id, models.Product.name
    ).order_by(
        func.sum(models.SaleItem.quantity).desc()
    ).first()
    
    # Most sold category today
    top_category = db.session.query(
        models.Category.name,
        func.sum(models.SaleItem.quantity).label('total_quantity'),
        func.sum(models.SaleItem.total_price).label('total_revenue')
    ).join(
        models.Product, models.Category.id == models.Product.category_id
    ).join(
        models.SaleItem, models.Product.id == models.SaleItem.product_id
    ).join(
        models.Sale, models.SaleItem.sale_id == models.Sale.id
    ).filter(
        func.date(models.Sale.created_at) == today,
        models.Sale.status == 'completed'
    ).group_by(
        models.Category.id, models.Category.name
    ).order_by(
        func.sum(models.SaleItem.total_price).desc()
    ).first()
    
    # Payment methods breakdown
    payment_methods = db.session.query(
        models.Sale.payment_method,
        func.count(models.Sale.id).label('count'),
        func.sum(models.Sale.total).label('total')
    ).filter(
        func.date(models.Sale.created_at) == today,
        models.Sale.status == 'completed'
    ).group_by(
        models.Sale.payment_method
    ).all()
    
    # Recent sales (last 10)
    recent_sales = models.Sale.query.filter(
        models.Sale.status == 'completed'
    ).order_by(
        models.Sale.created_at.desc()
    ).limit(10).all()
    
    # Active tables count
    from models import TableStatus
    active_tables = models.Table.query.filter(
        models.Table.status == TableStatus.OCCUPIED
    ).count()
    
    return render_template('admin/dashboard.html', 
                         daily_sales=daily_sales,
                         daily_transactions=daily_transactions,
                         low_stock_products=low_stock_products,
                         sales_change_percent=sales_change_percent,
                         top_product=top_product,
                         top_category=top_category,
                         payment_methods=payment_methods,
                         recent_sales=recent_sales,
                         active_tables=active_tables)


@bp.route('/tables-management')
def tables_management():
    """View for admin/manager/cashier to manage table orders and billing"""
    user = require_admin_or_manager_or_cashier()
    if not isinstance(user, models.User):
        return user
    
    # Get all tables with their current sales information
    tables = models.Table.query.all()
    
    # Enrich tables with sale information for admin/cashier view
    enriched_tables = []
    for table in tables:
        # Get current pending sale for this table
        current_sale = models.Sale.query.filter_by(
            table_id=table.id, 
            status='pending'
        ).first()
        
        table_data = {
            'table': table,
            'current_sale': current_sale,
            'has_order': current_sale is not None,
            'order_total': current_sale.total if current_sale else 0,
            'order_items_count': len(current_sale.sale_items) if current_sale else 0,
            'can_bill': current_sale is not None  # Only tables with orders can be billed
        }
        enriched_tables.append(table_data)
    
    # Filter to show only tables with orders first, then all tables
    tables_with_orders = [t for t in enriched_tables if t['has_order']]
    tables_available = [t for t in enriched_tables if not t['has_order']]
    
    return render_template('admin/tables_management.html', 
                         tables_with_orders=tables_with_orders,
                         tables_available=tables_available,
                         user_role=user.role.value)


@bp.route('/pos')
def pos():
    user = require_pos_access()
    if not isinstance(user, models.User):
        return user
    
    # Get cash register for this user (only required for admin and cashiers)
    cash_register = None
    if user.role.value in ['ADMINISTRADOR', 'CAJERO']:
        cash_register = models.CashRegister.query.filter_by(user_id=user.id, active=True).first()
        if not cash_register:
            flash('No tienes una caja asignada. Contacta al administrador.', 'error')
            return redirect(url_for('admin.dashboard'))
        
        # Check if cash register has an open session
        current_session = models.CashSession.query.filter_by(
            cash_register_id=cash_register.id,
            status='open'
        ).order_by(models.CashSession.opened_at.desc()).first()
        
        if not current_session:
            flash('Debes abrir la caja registradora antes de usar el POS.', 'warning')
            # Pass flag to template to show cash opening modal automatically
            return render_template('admin/pos.html', 
                                 cash_register=cash_register,
                                 categories=models.Category.query.filter_by(active=True).all(),
                                 edit_sale_data=None,
                                 show_cash_opening_modal=True)
    
    # Check if we're editing an existing sale
    edit_sale_id = request.args.get('edit_sale')
    edit_sale_data = None
    
    if edit_sale_id:
        try:
            # Get sale to edit
            sale = models.Sale.query.get(int(edit_sale_id))
            if sale and sale.status == 'pending':
                # Get sale items
                sale_items = models.SaleItem.query.filter_by(sale_id=sale.id).all()
                
                edit_sale_data = {
                    'id': sale.id,
                    'table_id': sale.table_id,
                    'description': sale.description or '',
                    'items': [
                        {
                            'product_id': item.product_id,
                            'product_name': item.product.name,
                            'price': float(item.unit_price),
                            'quantity': item.quantity
                        }
                        for item in sale_items
                    ]
                }
            else:
                flash('La orden no existe o ya fue procesada.', 'error')
        except (ValueError, TypeError):
            flash('ID de orden inválido.', 'error')
    
    # Get products by category
    categories = models.Category.query.filter_by(active=True).all()
    
    response = make_response(render_template('admin/pos.html', 
                         cash_register=cash_register,
                         categories=categories,
                         edit_sale_data=edit_sale_data))
    
    # Force browser to reload this page - prevents caching issues during development
    response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'
    
    return response


@bp.route('/products')
def products():
    """Redirect to inventory products to avoid duplication"""
    return redirect(url_for('inventory.products'))


@bp.route('/categories/create', methods=['POST'])
def create_category():
    user = require_admin_or_manager()
    if not isinstance(user, models.User):
        return jsonify({'error': 'No autorizado'}), 401
    
    # Validate CSRF token
    if not validate_csrf_token():
        return redirect(url_for('admin.products'))
    
    try:
        name = request.form['name'].strip()
        description = request.form.get('description', '').strip()
        
        if not name:
            flash('El nombre de la categoría es obligatorio', 'error')
            return redirect(url_for('admin.products'))
        
        # Check if name already exists
        existing_category = models.Category.query.filter_by(name=name, active=True).first()
        if existing_category:
            flash('Ya existe una categoría con ese nombre', 'error')
            return redirect(url_for('admin.products'))
        
        new_category = models.Category()
        new_category.name = name
        new_category.description = description
        new_category.active = True
        
        db.session.add(new_category)
        db.session.commit()
        
        flash(f'Categoría {name} creada exitosamente', 'success')
        
    except Exception as e:
        db.session.rollback()
        flash(f'Error al crear categoría: {str(e)}', 'error')
    
    return redirect(url_for('admin.products'))

@bp.route('/categories/<int:category_id>/edit', methods=['POST'])
def edit_category(category_id):
    user = require_admin_or_manager()
    if not isinstance(user, models.User):
        return jsonify({'error': 'No autorizado'}), 401
    
    # Validate CSRF token
    if not validate_csrf_token():
        return redirect(url_for('admin.products'))
    
    try:
        category = models.Category.query.get_or_404(category_id)
        
        name = request.form['name'].strip()
        description = request.form.get('description', '').strip()
        
        if not name:
            flash('El nombre de la categoría es obligatorio', 'error')
            return redirect(url_for('admin.products'))
        
        # Check if name already exists (excluding current category)
        existing_category = models.Category.query.filter(
            models.Category.name == name, 
            models.Category.active == True, 
            models.Category.id != category_id
        ).first()
        if existing_category:
            flash('Ya existe una categoría con ese nombre', 'error')
            return redirect(url_for('admin.products'))
        
        category.name = name
        category.description = description
        
        db.session.commit()
        
        flash(f'Categoría {name} actualizada exitosamente', 'success')
        
    except Exception as e:
        db.session.rollback()
        flash(f'Error al actualizar categoría: {str(e)}', 'error')
    
    return redirect(url_for('admin.products'))

@bp.route('/categories/<int:category_id>/delete', methods=['POST'])
def delete_category(category_id):
    user = require_admin_or_manager()
    if not isinstance(user, models.User):
        return jsonify({'error': 'No autorizado'}), 401
    
    # Validate CSRF token
    if not validate_csrf_token():
        return redirect(url_for('admin.products'))
    
    try:
        category = models.Category.query.get_or_404(category_id)
        
        # Check if category has products
        products_count = models.Product.query.filter_by(category_id=category_id, active=True).count()
        if products_count > 0:
            flash(f'No se puede eliminar la categoría porque tiene {products_count} productos asociados', 'error')
            return redirect(url_for('admin.products'))
        
        category.active = False
        db.session.commit()
        
        flash(f'Categoría {category.name} eliminada exitosamente', 'success')
        
    except Exception as e:
        db.session.rollback()
        flash(f'Error al eliminar categoría: {str(e)}', 'error')
    
    return redirect(url_for('admin.products'))


# Table Management Routes  
@bp.route('/tables')
def tables():
    user = require_admin_or_manager_or_cashier()
    if not isinstance(user, models.User):
        return user
    
    # Get all tables with their current sales information
    tables = models.Table.query.order_by(models.Table.number).all()
    
    # Enrich tables with sale information for operational view
    enriched_tables = []
    for table in tables:
        # Get current pending sale for this table
        current_sale = models.Sale.query.filter_by(
            table_id=table.id, 
            status='pending'
        ).first()
        
        table_data = {
            'table': table,
            'current_sale': current_sale,
            'has_order': current_sale is not None,
            'order_total': current_sale.total if current_sale else 0,
            'order_items_count': len(current_sale.sale_items) if current_sale else 0
        }
        enriched_tables.append(table_data)
    
    return render_template('admin/tables.html', tables=enriched_tables, user_role=user.role.value)

@bp.route('/tables/create', methods=['POST'])
def create_table():
    user = require_admin_or_manager()
    if not isinstance(user, models.User):
        return jsonify({'error': 'No autorizado'}), 401
    
    # Validate CSRF token
    if not validate_csrf_token():
        return redirect(url_for('admin.tables'))
    
    try:
        number = request.form['number'].strip()
        name = request.form.get('name', '').strip()
        capacity = int(request.form.get('capacity', 4))
        
        if not number:
            flash('El número de mesa es obligatorio', 'error')
            return redirect(url_for('admin.tables'))
        
        # Check if number already exists
        existing_table = models.Table.query.filter_by(number=number).first()
        if existing_table:
            flash('Ya existe una mesa con ese número', 'error')
            return redirect(url_for('admin.tables'))
        
        new_table = models.Table()
        new_table.number = number
        new_table.name = name
        new_table.capacity = capacity
        new_table.status = models.TableStatus.AVAILABLE
        
        db.session.add(new_table)
        db.session.commit()
        
        flash(f'Mesa {number} creada exitosamente', 'success')
        
    except Exception as e:
        db.session.rollback()
        flash(f'Error al crear mesa: {str(e)}', 'error')
    
    return redirect(url_for('admin.tables'))

@bp.route('/tables/<int:table_id>/edit', methods=['POST'])
def edit_table(table_id):
    user = require_admin_or_manager()
    if not isinstance(user, models.User):
        return jsonify({'error': 'No autorizado'}), 401
    
    # Validate CSRF token
    if not validate_csrf_token():
        return redirect(url_for('admin.tables'))
    
    try:
        table = models.Table.query.get_or_404(table_id)
        
        number = request.form['number'].strip()
        name = request.form.get('name', '').strip()
        capacity = int(request.form.get('capacity', 4))
        status = request.form.get('status', 'available')
        
        if not number:
            flash('El número de mesa es obligatorio', 'error')
            return redirect(url_for('admin.tables'))
        
        # Check if number already exists (excluding current table)
        existing_table = models.Table.query.filter(
            models.Table.number == number, 
            models.Table.id != table_id
        ).first()
        if existing_table:
            flash('Ya existe una mesa con ese número', 'error')
            return redirect(url_for('admin.tables'))
        
        table.number = number
        table.name = name
        table.capacity = capacity
        table.status = models.TableStatus(status)
        
        db.session.commit()
        
        flash(f'Mesa {number} actualizada exitosamente', 'success')
        
    except Exception as e:
        db.session.rollback()
        flash(f'Error al actualizar mesa: {str(e)}', 'error')
    
    return redirect(url_for('admin.tables'))

@bp.route('/tables/<int:table_id>/delete', methods=['POST'])
def delete_table(table_id):
    user = require_admin_or_manager()
    if not isinstance(user, models.User):
        return jsonify({'error': 'No autorizado'}), 401
    
    # Validate CSRF token
    if not validate_csrf_token():
        return redirect(url_for('admin.tables'))
    
    try:
        table = models.Table.query.get_or_404(table_id)
        
        # Check if table has active sales
        active_sales = models.Sale.query.filter_by(table_id=table_id, status='pending').count()
        if active_sales > 0:
            flash(f'No se puede eliminar la mesa porque tiene {active_sales} ventas activas', 'error')
            return redirect(url_for('admin.tables'))
        
        db.session.delete(table)
        db.session.commit()
        
        flash(f'Mesa {table.number} eliminada exitosamente', 'success')
        
    except Exception as e:
        db.session.rollback()
        flash(f'Error al eliminar mesa: {str(e)}', 'error')
    
    return redirect(url_for('admin.tables'))


@bp.route('/company-settings/logo', methods=['POST'])
def company_settings_logo():
    user = require_admin()
    if not isinstance(user, models.User):
        return jsonify({'error': 'No autorizado'}), 401
    
    # Validate CSRF token
    if not validate_csrf_token():
        return redirect(url_for('admin.company_settings'))
    
    try:
        # Check if file was uploaded
        if 'logo_file' not in request.files:
            flash('No se seleccionó ningún archivo', 'error')
            return redirect(url_for('admin.company_settings'))
        
        file = request.files['logo_file']
        
        if file.filename == '':
            flash('No se seleccionó ningún archivo', 'error')
            return redirect(url_for('admin.company_settings'))
        
        # Validate file type
        allowed_extensions = {'png', 'jpg', 'jpeg', 'gif'}
        filename = file.filename or ''
        if not ('.' in filename and filename.rsplit('.', 1)[1].lower() in allowed_extensions):
            flash('Solo se permiten archivos PNG, JPG, JPEG y GIF', 'error')
            return redirect(url_for('admin.company_settings'))
        
        # Validate file size (max 500KB)
        file.seek(0, 2)  # Seek to end of file
        file_size = file.tell()
        file.seek(0)  # Reset to beginning
        if file_size > 500 * 1024:  # 500KB limit
            flash('El archivo es demasiado grande. Máximo 500KB permitido', 'error')
            return redirect(url_for('admin.company_settings'))
        
        # Create logos directory if it doesn't exist
        import os
        from werkzeug.utils import secure_filename
        logos_dir = os.path.join('static', 'uploads', 'logos')
        if not os.path.exists(logos_dir):
            os.makedirs(logos_dir, exist_ok=True)
        
        # Generate unique filename with secure_filename
        import uuid
        file_extension = filename.rsplit('.', 1)[1].lower()
        base_name = secure_filename(filename.rsplit('.', 1)[0])
        unique_filename = f'{base_name}_{uuid.uuid4().hex[:8]}.{file_extension}'
        
        # Save file
        file_path = os.path.join(logos_dir, unique_filename)
        file.save(file_path)
        
        # Update or create configuration
        logo_config = models.SystemConfiguration.query.filter_by(key='receipt_logo').first()
        if logo_config:
            # Remove old logo file if exists
            if logo_config.value:
                old_file_path = logo_config.value
                if os.path.exists(old_file_path):
                    os.remove(old_file_path)
            logo_config.value = file_path
            logo_config.updated_at = datetime.utcnow()
        else:
            logo_config = models.SystemConfiguration()
            logo_config.key = 'receipt_logo'
            logo_config.value = file_path
            logo_config.description = 'Logo personalizado para recibos'
            db.session.add(logo_config)
        
        db.session.commit()
        flash('Logo del recibo actualizado exitosamente', 'success')
        
    except Exception as e:
        db.session.rollback()
        flash(f'Error al actualizar logo: {str(e)}', 'error')
    
    return redirect(url_for('admin.company_settings'))

@bp.route('/company-settings/logo/remove', methods=['POST'])
def remove_logo():
    user = require_admin()
    if not isinstance(user, models.User):
        return jsonify({'error': 'No autorizado'}), 401
    
    # Validate CSRF token
    if not validate_csrf_token():
        return redirect(url_for('admin.company_settings'))
    
    try:
        logo_config = models.SystemConfiguration.query.filter_by(key='receipt_logo').first()
        if logo_config and logo_config.value:
            # Remove file
            import os
            if os.path.exists(logo_config.value):
                os.remove(logo_config.value)
            
            # Remove configuration
            db.session.delete(logo_config)
            db.session.commit()
            
            flash('Logo del recibo eliminado exitosamente', 'success')
        else:
            flash('No hay logo configurado para eliminar', 'warning')
        
    except Exception as e:
        db.session.rollback()
        flash(f'Error al eliminar logo: {str(e)}', 'error')
    
    return redirect(url_for('admin.company_settings'))


@bp.route('/reports')
def reports():
    user = require_admin_or_cashier()
    if not isinstance(user, models.User):
        return user
    
    if user.role.value != 'ADMINISTRADOR':
        flash('Solo los administradores pueden ver reportes', 'error')
        return redirect(url_for('admin.dashboard'))
    
    return render_template('admin/reports.html')


@bp.route('/invoices')
def invoices():
    """Vista para mostrar la lista de facturas/ventas"""
    user = require_admin_or_cashier()
    if not isinstance(user, models.User):
        return user
    
    # Obtener parámetros de filtro
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    search = request.args.get('search', '', type=str)
    status_filter = request.args.get('status', '', type=str)
    date_from = request.args.get('date_from', '', type=str)
    date_to = request.args.get('date_to', '', type=str)
    
    # Construir query base
    query = models.Sale.query
    
    # Aplicar filtros
    if search:
        query = query.filter(
            models.Sale.ncf.ilike(f'%{search}%') |
            models.Sale.customer_name.ilike(f'%{search}%') |
            models.Sale.customer_rnc.ilike(f'%{search}%')
        )
    
    if status_filter:
        query = query.filter(models.Sale.status == status_filter)
    
    if date_from:
        try:
            from_date = datetime.strptime(date_from, '%Y-%m-%d')
            query = query.filter(models.Sale.created_at >= from_date)
        except ValueError:
            pass
    
    if date_to:
        try:
            to_date = datetime.strptime(date_to, '%Y-%m-%d')
            # Agregar un día para incluir todo el día seleccionado
            to_date = to_date.replace(hour=23, minute=59, second=59)
            query = query.filter(models.Sale.created_at <= to_date)
        except ValueError:
            pass
    
    # Para cajeros, solo mostrar ventas de su caja registradora
    if user.role.value == 'CAJERO':
        cash_register = models.CashRegister.query.filter_by(user_id=user.id, active=True).first()
        if not cash_register:
            # Si el cajero no tiene caja registradora activa, no puede ver ninguna venta
            flash('No tienes una caja registradora asignada. Contacta al administrador.', 'error')
            return redirect(url_for('admin.dashboard'))
        query = query.filter(models.Sale.cash_register_id == cash_register.id)
    
    # Ordenar por fecha de creación (más recientes primero)
    query = query.order_by(models.Sale.created_at.desc())
    
    # Paginación
    sales = query.paginate(
        page=page,
        per_page=per_page,
        error_out=False
    )
    
    # Crear una consulta para estadísticas que respete todos los filtros aplicados
    stats_query = models.Sale.query
    
    # Aplicar todos los mismos filtros que se usaron para la consulta principal
    if search:
        stats_query = stats_query.filter(
            models.Sale.ncf.ilike(f'%{search}%') |
            models.Sale.customer_name.ilike(f'%{search}%') |
            models.Sale.customer_rnc.ilike(f'%{search}%')
        )
    
    if status_filter:
        stats_query = stats_query.filter(models.Sale.status == status_filter)
    
    if date_from:
        try:
            from_date = datetime.strptime(date_from, '%Y-%m-%d')
            stats_query = stats_query.filter(models.Sale.created_at >= from_date)
        except ValueError:
            pass
    
    if date_to:
        try:
            to_date = datetime.strptime(date_to, '%Y-%m-%d')
            to_date = to_date.replace(hour=23, minute=59, second=59)
            stats_query = stats_query.filter(models.Sale.created_at <= to_date)
        except ValueError:
            pass
    
    # Para cajeros, aplicar mismo filtro de caja registradora
    if user.role.value == 'CAJERO':
        cash_register = models.CashRegister.query.filter_by(user_id=user.id, active=True).first()
        if cash_register:
            stats_query = stats_query.filter(models.Sale.cash_register_id == cash_register.id)
    
    # Calcular estadísticas solo de ventas completadas con los filtros aplicados
    completed_stats_query = stats_query.filter(models.Sale.status == 'completed')
    total_sales = completed_stats_query.count()
    total_amount = completed_stats_query.with_entities(func.sum(models.Sale.total)).scalar() or 0
    
    return render_template('admin/invoices.html',
                         sales=sales,
                         total_sales=total_sales,
                         total_amount=total_amount,
                         search=search,
                         status_filter=status_filter,
                         date_from=date_from,
                         date_to=date_to)


@bp.route('/ncf-sequences')
def ncf_sequences():
    user = require_admin_or_cashier()
    if not isinstance(user, models.User):
        return user
    
    if user.role.value != 'ADMINISTRADOR':
        flash('Solo los administradores pueden gestionar secuencias NCF', 'error')
        return redirect(url_for('admin.dashboard'))
    
    # Get all NCF sequences (now independent of cash registers)
    sequences = models.NCFSequence.query.all()
    
    return render_template('admin/ncf_sequences.html', 
                         sequences=sequences)


@bp.route('/ncf-sequences/<int:sequence_id>/details', methods=['GET'])
def get_ncf_sequence_details(sequence_id):
    user = require_admin_or_manager()
    if not isinstance(user, models.User):
        return jsonify({'error': 'No autorizado'}), 401
    
    try:
        sequence = models.NCFSequence.query.get_or_404(sequence_id)
        
        return jsonify({
            'success': True,
            'sequence': {
                'id': sequence.id,
                'ncf_type': sequence.ncf_type.value,
                'serie': sequence.serie,
                'start_number': sequence.start_number,
                'end_number': sequence.end_number,
                'current_number': sequence.current_number,
                'active': sequence.active
            }
        })
        
    except Exception as e:
        return jsonify({'error': f'Error obteniendo secuencia: {str(e)}'}), 500


@bp.route('/ncf-sequences/create', methods=['POST'])
def create_ncf_sequence():
    user = require_admin_or_manager()
    if not isinstance(user, models.User):
        return jsonify({'error': 'No autorizado'}), 401
    
    # Validate CSRF token for security
    if not validate_csrf_token():
        return jsonify({'error': 'Token de seguridad inválido'}), 400
    
    try:
        # Get form data - cash register is now optional since sequences are independent
        ncf_type = request.form.get('ncf_type')
        serie = request.form.get('serie', '').strip().upper()
        start_number = request.form.get('start_number')
        end_number = request.form.get('end_number')
        
        # Validate required fields
        if not all([ncf_type, serie, start_number, end_number]):
            return jsonify({'error': 'Todos los campos son obligatorios'}), 400
        
        # Validate NCF type
        if ncf_type not in ['consumo', 'credito_fiscal', 'gubernamental']:
            return jsonify({'error': 'Tipo de NCF inválido'}), 400
        
        # Validate serie format (3 characters, alphanumeric)
        if len(serie) != 3 or not serie.isalnum():
            return jsonify({'error': 'La serie debe tener 3 caracteres alfanuméricos'}), 400
        
        # Validate number range
        try:
            start_num = int(start_number or 0)
            end_num = int(end_number or 0)
        except (ValueError, TypeError):
            return jsonify({'error': 'Los números deben ser enteros válidos'}), 400
        
        if start_num <= 0 or end_num <= 0:
            return jsonify({'error': 'Los números deben ser mayores a 0'}), 400
        
        if start_num >= end_num:
            return jsonify({'error': 'El número final debe ser mayor que el inicial'}), 400
        
        # Convert NCF type to enum
        ncf_type_enum = models.NCFType[ncf_type.upper()]
        
        # Check for existing active sequence of same type (only one allowed per type)
        existing_sequence = models.NCFSequence.query.filter_by(
            ncf_type=ncf_type_enum,
            active=True
        ).first()
        
        if existing_sequence:
            return jsonify({'error': f'Ya existe una secuencia NCF activa para tipo {ncf_type}. Solo puede haber una secuencia activa por tipo.'}), 400
        
        # Check for duplicate serie globally (series should be unique)
        duplicate_serie = models.NCFSequence.query.filter_by(
            serie=serie,
            active=True
        ).first()
        
        if duplicate_serie:
            return jsonify({'error': f'Ya existe una secuencia activa con serie {serie}'}), 400
        
        # Check for overlapping number ranges in same NCF type
        overlapping = models.NCFSequence.query.filter_by(
            ncf_type=ncf_type_enum
        ).filter(
            models.NCFSequence.start_number <= end_num,
            models.NCFSequence.end_number >= start_num
        ).first()
        
        if overlapping:
            return jsonify({'error': f'El rango de números ({start_num}-{end_num}) se solapa con una secuencia existente de tipo {ncf_type}'}), 400
        
        # Create new NCF sequence (independent of cash registers)
        new_sequence = models.NCFSequence()
        # cash_register_id defaults to None for independent sequences
        new_sequence.ncf_type = ncf_type_enum
        new_sequence.serie = serie
        new_sequence.start_number = start_num
        new_sequence.end_number = end_num
        new_sequence.current_number = start_num  # Start at the beginning
        new_sequence.active = True
        
        db.session.add(new_sequence)
        db.session.flush()  # Flush to generate sequence ID before creating audit record
        
        # Create audit record using relationship for consistency
        audit_record = models.NCFSequenceAudit()
        audit_record.sequence = new_sequence
        audit_record.user_id = user.id
        audit_record.action = 'created'
        audit_record.after_json = {
            'ncf_type': ncf_type,
            'serie': serie,
            'start_number': start_num,
            'end_number': end_num,
            'active': True
        }
        db.session.add(audit_record)
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': f'Secuencia NCF {serie} creada exitosamente',
            'sequence_id': new_sequence.id
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': f'Error creando secuencia: {str(e)}'}), 500


@bp.route('/ncf-sequences/<int:sequence_id>/edit', methods=['POST'])
def edit_ncf_sequence(sequence_id):
    user = require_admin_or_manager()
    if not isinstance(user, models.User):
        return jsonify({'error': 'No autorizado'}), 401
    
    # Validate CSRF token
    if not validate_csrf_token():
        return jsonify({'error': 'Token de seguridad inválido'}), 400
    
    try:
        sequence = models.NCFSequence.query.get_or_404(sequence_id)
        
        # Store original values for audit
        before_json = {
            'ncf_type': sequence.ncf_type.value,
            'serie': sequence.serie,
            'start_number': sequence.start_number,
            'end_number': sequence.end_number,
            'active': sequence.active
        }
        
        # Get form data
        end_number = request.form.get('end_number')
        active = request.form.get('active') == 'true'
        
        # Validate end_number if provided
        if end_number:
            try:
                end_num = int(end_number)
                if end_num <= sequence.current_number:
                    return jsonify({'error': f'El número final debe ser mayor al actual ({sequence.current_number})'}), 400
                if end_num < sequence.start_number:
                    return jsonify({'error': 'El número final no puede ser menor al inicial'}), 400
                sequence.end_number = end_num
            except (ValueError, TypeError):
                return jsonify({'error': 'El número final debe ser un entero válido'}), 400
        
        # Update active status
        old_active = sequence.active
        sequence.active = active
        
        # If activating, check that no other sequence of same type is active
        if active and not old_active:
            existing_active = models.NCFSequence.query.filter_by(
                ncf_type=sequence.ncf_type,
                active=True
            ).filter(models.NCFSequence.id != sequence_id).first()
            
            if existing_active:
                return jsonify({'error': f'Ya existe una secuencia activa para tipo {sequence.ncf_type.value}. Desactive la otra secuencia primero.'}), 400
            
            # Check for overlapping number ranges with other sequences of same type
            overlapping = models.NCFSequence.query.filter_by(
                ncf_type=sequence.ncf_type
            ).filter(
                models.NCFSequence.id != sequence_id,
                models.NCFSequence.start_number <= sequence.end_number,
                models.NCFSequence.end_number >= sequence.start_number
            ).first()
            
            if overlapping:
                return jsonify({'error': f'El rango de números ({sequence.start_number}-{sequence.end_number}) se solapa con una secuencia existente de tipo {sequence.ncf_type.value}'}), 400
        
        # Store new values for audit
        after_json = {
            'ncf_type': sequence.ncf_type.value,
            'serie': sequence.serie,
            'start_number': sequence.start_number,
            'end_number': sequence.end_number,
            'active': sequence.active
        }
        
        # Flush changes to ensure sequence is available for audit record
        db.session.flush()
        
        # Create audit record using relationship for better consistency
        audit_record = models.NCFSequenceAudit()
        audit_record.sequence = sequence
        audit_record.user_id = user.id
        audit_record.action = 'edited'
        audit_record.before_json = before_json
        audit_record.after_json = after_json
        db.session.add(audit_record)
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'Secuencia NCF actualizada exitosamente'
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': f'Error actualizando secuencia: {str(e)}'}), 500


@bp.route('/ncf-sequences/<int:sequence_id>/activate', methods=['POST'])
def activate_ncf_sequence(sequence_id):
    user = require_admin_or_manager()
    if not isinstance(user, models.User):
        return jsonify({'error': 'No autorizado'}), 401
    
    # Validate CSRF token
    if not validate_csrf_token():
        return jsonify({'error': 'Token de seguridad inválido'}), 400
    
    try:
        sequence = models.NCFSequence.query.get_or_404(sequence_id)
        
        if sequence.active:
            return jsonify({'error': 'La secuencia ya está activa'}), 400
        
        # Check that no other sequence of same type is active
        existing_active = models.NCFSequence.query.filter_by(
            ncf_type=sequence.ncf_type,
            active=True
        ).first()
        
        if existing_active:
            return jsonify({'error': f'Ya existe una secuencia activa para tipo {sequence.ncf_type.value}. Desactive la otra secuencia primero.'}), 400
        
        # Check for overlapping number ranges with other sequences of same type
        overlapping = models.NCFSequence.query.filter_by(
            ncf_type=sequence.ncf_type
        ).filter(
            models.NCFSequence.id != sequence_id,
            models.NCFSequence.start_number <= sequence.end_number,
            models.NCFSequence.end_number >= sequence.start_number
        ).first()
        
        if overlapping:
            return jsonify({'error': f'El rango de números ({sequence.start_number}-{sequence.end_number}) se solapa con una secuencia existente de tipo {sequence.ncf_type.value}'}), 400
        
        # Store values for audit
        before_json = {
            'ncf_type': sequence.ncf_type.value,
            'serie': sequence.serie,
            'start_number': sequence.start_number,
            'end_number': sequence.end_number,
            'active': False
        }
        
        sequence.active = True
        
        after_json = {
            'ncf_type': sequence.ncf_type.value,
            'serie': sequence.serie,
            'start_number': sequence.start_number,
            'end_number': sequence.end_number,
            'active': True
        }
        
        # Flush changes to ensure sequence is available for audit record
        db.session.flush()
        
        # Create audit record using relationship for better consistency
        audit_record = models.NCFSequenceAudit()
        audit_record.sequence = sequence
        audit_record.user_id = user.id
        audit_record.action = 'activated'
        audit_record.before_json = before_json
        audit_record.after_json = after_json
        db.session.add(audit_record)
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': f'Secuencia NCF {sequence.serie} activada exitosamente'
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': f'Error activando secuencia: {str(e)}'}), 500


@bp.route('/ncf-sequences/<int:sequence_id>/deactivate', methods=['POST'])
def deactivate_ncf_sequence(sequence_id):
    user = require_admin_or_manager()
    if not isinstance(user, models.User):
        return jsonify({'error': 'No autorizado'}), 401
    
    # Validate CSRF token
    if not validate_csrf_token():
        return jsonify({'error': 'Token de seguridad inválido'}), 400
    
    try:
        sequence = models.NCFSequence.query.get_or_404(sequence_id)
        
        if not sequence.active:
            return jsonify({'error': 'La secuencia ya está inactiva'}), 400
        
        # Store values for audit
        before_json = {
            'ncf_type': sequence.ncf_type.value,
            'serie': sequence.serie,
            'start_number': sequence.start_number,
            'end_number': sequence.end_number,
            'active': True
        }
        
        sequence.active = False
        
        after_json = {
            'ncf_type': sequence.ncf_type.value,
            'serie': sequence.serie,
            'start_number': sequence.start_number,
            'end_number': sequence.end_number,
            'active': False
        }
        
        # Flush changes to ensure sequence is available for audit record
        db.session.flush()
        
        # Create audit record using relationship for better consistency
        audit_record = models.NCFSequenceAudit()
        audit_record.sequence = sequence
        audit_record.user_id = user.id
        audit_record.action = 'deactivated'
        audit_record.before_json = before_json
        audit_record.after_json = after_json
        db.session.add(audit_record)
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': f'Secuencia NCF {sequence.serie} desactivada exitosamente'
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': f'Error desactivando secuencia: {str(e)}'}), 500


# User Management Routes
@bp.route('/users')
def users():
    user = require_admin_or_manager()
    if not isinstance(user, models.User):
        return user
    
    all_users = models.User.query.order_by(models.User.created_at.desc()).all()
    return render_template('admin/users.html', users=all_users)


@bp.route('/users/create', methods=['POST'])
def create_user():
    user = require_admin_or_manager()
    if not isinstance(user, models.User):
        return jsonify({'error': 'No autorizado'}), 401
    
    # Validate CSRF token
    if not validate_csrf_token():
        return redirect(url_for('admin.users'))
    
    try:
        username = request.form['username'].strip()
        name = request.form['name'].strip()
        email = request.form['email'].strip()
        role = request.form['role']
        password = request.form['password']
        
        # Validate input
        if not all([username, name, email, role, password]):
            flash('Todos los campos son obligatorios', 'error')
            return redirect(url_for('admin.users'))
        
        if role not in ['ADMINISTRADOR', 'CAJERO', 'MESERO', 'GERENTE']:
            flash('Rol inválido', 'error')
            return redirect(url_for('admin.users'))
        
        # Check if username or email already exists
        existing_user = models.User.query.filter(
            (models.User.username == username) | (models.User.email == email)
        ).first()
        
        if existing_user:
            flash('El usuario o email ya existe', 'error')
            return redirect(url_for('admin.users'))
        
        # Create user
        password_hash = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
        
        new_user = models.User()
        new_user.username = username
        new_user.name = name
        new_user.email = email
        new_user.password_hash = password_hash
        new_user.role = models.UserRole(role)
        new_user.active = True
        new_user.must_change_password = True
        
        db.session.add(new_user)
        db.session.commit()
        
        flash(f'Usuario {username} creado exitosamente', 'success')
        
    except Exception as e:
        db.session.rollback()
        flash(f'Error al crear usuario: {str(e)}', 'error')
    
    return redirect(url_for('admin.users'))


@bp.route('/users/<int:user_id>/edit', methods=['POST'])
def edit_user(user_id):
    user = require_admin_or_manager()
    if not isinstance(user, models.User):
        return jsonify({'error': 'No autorizado'}), 401
    
    # Validate CSRF token
    if not validate_csrf_token():
        return redirect(url_for('admin.users'))
    
    try:
        target_user = models.User.query.get_or_404(user_id)
        
        target_user.name = request.form['name'].strip()
        target_user.email = request.form['email'].strip()
        target_user.role = getattr(models.UserRole, request.form['role'].upper())
        target_user.active = request.form.get('active') == 'true'
        
        db.session.commit()
        flash(f'Usuario {target_user.username} actualizado exitosamente', 'success')
        
    except Exception as e:
        db.session.rollback()
        flash(f'Error al actualizar usuario: {str(e)}', 'error')
    
    return redirect(url_for('admin.users'))


@bp.route('/users/<int:user_id>/reset_password', methods=['POST'])
def reset_user_password(user_id):
    user = require_admin()
    if not isinstance(user, models.User):
        return jsonify({'error': 'No autorizado'}), 401
    
    # Validate CSRF token
    if not validate_csrf_token():
        return redirect(url_for('admin.users'))
    
    try:
        target_user = models.User.query.get_or_404(user_id)
        new_password = request.form['password']
        
        if len(new_password) < 6:
            flash('La contraseña debe tener al menos 6 caracteres', 'error')
            return redirect(url_for('admin.users'))
        
        password_hash = bcrypt.hashpw(new_password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
        target_user.password_hash = password_hash
        target_user.must_change_password = True
        
        db.session.commit()
        flash(f'Contraseña restablecida para {target_user.username}', 'success')
        
    except Exception as e:
        db.session.rollback()
        flash(f'Error al restablecer contraseña: {str(e)}', 'error')
    
    return redirect(url_for('admin.users'))


# Cash Register Management Routes
@bp.route('/cash-registers')
def cash_registers():
    user = require_admin_or_manager()
    if not isinstance(user, models.User):
        return user
    
    registers = models.CashRegister.query.order_by(models.CashRegister.created_at.desc()).all()
    active_users = models.User.query.filter_by(active=True).filter(
        models.User.role.in_([models.UserRole.ADMINISTRADOR, models.UserRole.CAJERO])
    ).all()
    
    return render_template('admin/cash_registers.html', registers=registers, users=active_users)


@bp.route('/cash-registers/create', methods=['POST'])
def create_cash_register():
    user = require_admin_or_manager()
    if not isinstance(user, models.User):
        return jsonify({'error': 'No autorizado'}), 401
    
    # Validate CSRF token
    if not validate_csrf_token():
        return redirect(url_for('admin.cash_registers'))
    
    try:
        name = request.form['name'].strip()
        
        if not name:
            flash('El nombre de la caja es obligatorio', 'error')
            return redirect(url_for('admin.cash_registers'))
        
        # Check if name already exists
        existing_register = models.CashRegister.query.filter_by(name=name, active=True).first()
        if existing_register:
            flash('Ya existe una caja con ese nombre', 'error')
            return redirect(url_for('admin.cash_registers'))
        
        new_register = models.CashRegister()
        new_register.name = name
        new_register.active = True
        
        db.session.add(new_register)
        db.session.commit()
        
        flash(f'Caja registradora {name} creada exitosamente', 'success')
        
    except Exception as e:
        db.session.rollback()
        flash(f'Error al crear caja registradora: {str(e)}', 'error')
    
    return redirect(url_for('admin.cash_registers'))


@bp.route('/cash-registers/<int:register_id>/assign', methods=['POST'])
def assign_cash_register(register_id):
    user = require_admin_or_manager()
    if not isinstance(user, models.User):
        return jsonify({'error': 'No autorizado'}), 401
    
    # Validate CSRF token
    if not validate_csrf_token():
        return redirect(url_for('admin.cash_registers'))
    
    try:
        register = models.CashRegister.query.get_or_404(register_id)
        user_id = request.form.get('user_id')
        
        # No special restrictions needed - all registers can be reassigned
        
        if user_id:
            # Unassign the register from any previous user
            models.CashRegister.query.filter_by(user_id=int(user_id)).update({'user_id': None})
            
            # Assign to new user
            register.user_id = int(user_id)
            assigned_user = models.User.query.get(user_id)
            if assigned_user:
                flash(f'Caja {register.name} asignada a {assigned_user.name}', 'success')
            else:
                flash('Usuario no encontrado', 'error')
        else:
            # Unassign
            register.user_id = None
            flash(f'Caja {register.name} desasignada', 'success')
        
        db.session.commit()
        
    except Exception as e:
        db.session.rollback()
        flash(f'Error al asignar caja registradora: {str(e)}', 'error')
    
    return redirect(url_for('admin.cash_registers'))


@bp.route('/cash-registers/<int:register_id>/edit', methods=['POST'])
def edit_cash_register(register_id):
    user = require_admin()
    if not isinstance(user, models.User):
        return jsonify({'error': 'No autorizado'}), 401
    
    # Validate CSRF token
    if not validate_csrf_token():
        return redirect(url_for('admin.cash_registers'))
    
    try:
        register = models.CashRegister.query.get_or_404(register_id)
        
        # No special restrictions needed - all registers can be edited
        
        register.name = request.form['name'].strip()
        register.active = request.form.get('active') == 'true'
        
        db.session.commit()
        flash(f'Caja registradora {register.name} actualizada exitosamente', 'success')
        
    except Exception as e:
        db.session.rollback()
        flash(f'Error al actualizar caja registradora: {str(e)}', 'error')
    
    return redirect(url_for('admin.cash_registers'))


@bp.route('/cash-registers/<int:register_id>/delete', methods=['POST'])
def delete_cash_register(register_id):
    user = require_admin_or_manager()
    if not isinstance(user, models.User):
        return jsonify({'error': 'No autorizado'}), 401
    
    # Validate CSRF token
    if not validate_csrf_token():
        return redirect(url_for('admin.cash_registers'))
    
    try:
        register = models.CashRegister.query.get_or_404(register_id)
        
        # No special restrictions needed - NCF sequences are now independent
        
        # Check if register has open sessions
        open_sessions = models.CashSession.query.filter_by(
            cash_register_id=register.id,
            status='open'
        ).count()
        
        if open_sessions > 0:
            flash('No se puede eliminar una caja con sesiones abiertas', 'error')
            return redirect(url_for('admin.cash_registers'))
        
        # Check if register has NCF sequences (for fiscal compliance)
        ncf_sequences_count = models.NCFSequence.query.filter_by(cash_register_id=register.id).count()
        
        if ncf_sequences_count > 0:
            # Mark as inactive instead of deleting for fiscal compliance
            register.active = False
            flash(f'Caja registradora {register.name} desactivada (tiene secuencias NCF asociadas)', 'warning')
        elif models.Sale.query.filter_by(cash_register_id=register.id).count() > 0:
            # Mark as inactive instead of deleting for audit purposes  
            register.active = False
            flash(f'Caja registradora {register.name} desactivada (se mantiene por auditoría)', 'warning')
        else:
            # Safe to delete if no sales or NCF sequences associated
            register_name = register.name
            db.session.delete(register)
            flash(f'Caja registradora {register_name} eliminada exitosamente', 'success')
        
        db.session.commit()
        
    except Exception as e:
        db.session.rollback()
        flash(f'Error al eliminar caja registradora: {str(e)}', 'error')
    
    return redirect(url_for('admin.cash_registers'))


# Company Configuration Routes
@bp.route('/company-settings')
def company_settings():
    """Show company configuration page"""
    user = require_admin()
    if not isinstance(user, models.User):
        return user
    
    # Initialize company settings if they don't exist
    init_result = initialize_company_settings()
    if not init_result['success']:
        flash(f'Error al inicializar configuraciones: {init_result["message"]}', 'error')
    
    # Get current company settings
    company_data = get_company_settings()
    if not company_data['success']:
        flash(f'Error al cargar configuraciones: {company_data["message"]}', 'error')
        company_data['settings'] = {}
    
    return render_template('admin/company_settings.html', 
                         company_settings=company_data['settings'])


@bp.route('/api/company-settings', methods=['GET'])
def api_get_company_settings():
    """API endpoint to get company settings"""
    user = require_admin()
    if not isinstance(user, models.User):
        return jsonify({'error': 'No autorizado'}), 401
    
    # Initialize settings if they don't exist
    initialize_company_settings()
    
    # Get current settings
    result = get_company_settings()
    
    if result['success']:
        return jsonify({
            'success': True,
            'settings': result['settings']
        })
    else:
        return jsonify({
            'success': False,
            'message': result['message']
        }), 500


@bp.route('/api/company-settings', methods=['POST'])
def api_update_company_settings():
    """API endpoint to update company settings"""
    user = require_admin()
    if not isinstance(user, models.User):
        return jsonify({'error': 'No autorizado'}), 401
    
    # Validate CSRF token for security
    if not validate_csrf_token():
        return jsonify({'error': 'Token de seguridad inválido'}), 400
    
    # Support both JSON and form data
    if request.is_json:
        data = request.get_json()
    else:
        data = request.form.to_dict()
    
    if not data:
        return jsonify({'error': 'No se proporcionaron datos'}), 400
    
    # Valid company setting keys
    valid_keys = [
        'company_name',
        'company_rnc',
        'company_address', 
        'company_phone',
        'company_email',
        'receipt_message',
        'receipt_footer',
        'receipt_logo',
        'fiscal_printer_enabled',
        'receipt_copies',
        'receipt_format'
    ]
    
    results = []
    errors = []
    
    for key, value in data.items():
        if key not in valid_keys:
            errors.append(f'Campo no válido: {key}')
            continue
        
        # Skip CSRF token
        if key == 'csrf_token':
            continue
            
        # Additional validation for RNC
        if key == 'company_rnc' and value:
            from utils import validate_rnc
            rnc_validation = validate_rnc(value)
            if not rnc_validation['valid']:
                errors.append(f'RNC inválido: {rnc_validation["message"]}')
                continue
        
        # Update each setting
        result = update_company_setting(key, str(value))
        
        if result['success']:
            results.append(f'{key} actualizado')
        else:
            errors.append(f'{key}: {result["message"]}')
    
    if errors:
        return jsonify({
            'success': False,
            'message': 'Algunos campos no se pudieron actualizar',
            'errors': errors,
            'updated': results
        }), 400
    else:
        return jsonify({
            'success': True,
            'message': f'Configuración actualizada: {len(results)} campos',
            'updated': results
        })


@bp.route('/api/company-settings/<setting_key>', methods=['PUT'])
def api_update_single_company_setting(setting_key):
    """API endpoint to update a single company setting"""
    user = require_admin()
    if not isinstance(user, models.User):
        return jsonify({'error': 'No autorizado'}), 401
    
    data = request.get_json()
    if not data or 'value' not in data:
        return jsonify({'error': 'Valor requerido'}), 400
    
    # Update the setting
    result = update_company_setting(setting_key, str(data['value']))
    
    if result['success']:
        return jsonify({
            'success': True,
            'message': result['message']
        })
    else:
        return jsonify({
            'success': False,
            'message': result['message']
        }), 400


@bp.route('/api/company-info', methods=['GET'])
def api_get_company_info():
    """Get formatted company information for receipts"""
    user = require_admin_or_cashier()
    if not isinstance(user, models.User):
        return jsonify({'error': 'No autorizado'}), 401
    
    # Get company info formatted for receipts
    company_info = get_company_info_for_receipt()
    
    return jsonify({
        'success': True,
        'company_info': company_info
    })


@bp.route('/company-settings/initialize', methods=['POST'])
def initialize_company_config():
    """Initialize company settings with defaults"""
    user = require_admin()
    if not isinstance(user, models.User):
        return user
    
    # Validate CSRF token
    if not validate_csrf_token():
        return redirect(url_for('admin.company_settings'))
    
    result = initialize_company_settings()
    
    if result['success']:
        flash(f'Configuraciones inicializadas: {result["message"]}', 'success')
    else:
        flash(f'Error: {result["message"]}', 'error')
    
    return redirect(url_for('admin.company_settings'))


@bp.route('/api/test-receipt', methods=['POST'])
def api_test_receipt():
    """Test receipt generation with sample data"""
    user = require_admin()
    if not isinstance(user, models.User):
        return jsonify({'error': 'No autorizado'}), 401
    
    # Validate CSRF token
    if not validate_csrf_token():
        return jsonify({'error': 'Token de seguridad inválido'}), 400
    
    try:
        from receipt_generator import DominicanReceiptGenerator
        from datetime import datetime
        import os
        
        # Create sample sale data for testing
        sample_sale_data = {
            'id': 9999,
            'created_at': datetime.now(),
            'ncf': 'B0100000001',
            'payment_method': 'efectivo',
            'total': 118.00,
            'subtotal': 100.00,
            'tax': 18.00,
            'customer_name': 'Cliente de Prueba',
            'items': [
                {
                    'quantity': 1,
                    'product_name': 'Producto de Prueba 1',
                    'price': 50.00
                },
                {
                    'quantity': 2,
                    'product_name': 'Producto de Prueba 2',
                    'price': 25.00
                }
            ]
        }
        
        # Get receipt format preference
        from utils import get_company_settings
        company_data = get_company_settings()
        receipt_format = '80mm'  # Default
        
        if company_data['success']:
            receipt_format = company_data['settings'].get('receipt_format', '80mm')
        
        # Generate receipt based on format
        generator = DominicanReceiptGenerator(format_type=receipt_format)
        
        # Generate both PDF and thermal versions
        pdf_path = generator.generate_fiscal_receipt(sample_sale_data)
        thermal_text = generator.generate_thermal_receipt(sample_sale_data)
        
        # Create relative path for frontend
        relative_pdf_path = os.path.relpath(pdf_path, 'static')
        
        return jsonify({
            'success': True,
            'message': f'Recibo de prueba generado exitosamente (formato {receipt_format})',
            'pdf_path': f'/static/{relative_pdf_path}',
            'thermal_preview': thermal_text[:500] + '...' if len(thermal_text) > 500 else thermal_text,
            'format': receipt_format
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error generando recibo de prueba: {str(e)}'
        }), 500


# ===========================
# TAX TYPES MANAGEMENT ROUTES
# ===========================

@bp.route('/tax-types')
def tax_types():
    """Tax types management page"""
    user = require_admin()
    if not isinstance(user, models.User):
        return user
    
    # Get all tax types ordered by display_order and name
    tax_types = models.TaxType.query.order_by(models.TaxType.display_order, models.TaxType.name).all()
    
    return render_template('admin/tax_types.html', tax_types=tax_types)


@bp.route('/api/tax-types', methods=['GET'])
def api_get_tax_types():
    """API to get all tax types"""
    from flask import session
    
    # Check if user is logged in 
    if 'user_id' not in session:
        return jsonify({'error': 'No autorizado'}), 401
    
    user = models.User.query.get(session['user_id'])
    if not user:
        return jsonify({'error': 'Usuario no encontrado'}), 401
    
    # Allow admins and cashiers to access tax types for POS operations
    if user.role.value not in ['ADMINISTRADOR', 'CAJERO']:
        return jsonify({'error': 'No tienes permisos para acceder a los tipos de impuesto'}), 403
    
    tax_types = models.TaxType.query.filter_by(active=True).order_by(models.TaxType.display_order, models.TaxType.name).all()
    
    return jsonify({
        'tax_types': [{
            'id': tax.id,
            'name': tax.name,
            'description': tax.description,
            'rate': tax.rate,
            'is_inclusive': tax.is_inclusive,
            'is_percentage': tax.is_percentage,
            'active': tax.active,
            'display_order': tax.display_order
        } for tax in tax_types]
    })


@bp.route('/api/tax-types', methods=['POST'])
def api_create_tax_type():
    """API to create a new tax type"""
    user = require_admin()
    if not isinstance(user, models.User):
        return jsonify({'error': 'No autorizado'}), 401
    
    # Validate CSRF token
    if not validate_csrf_token():
        return jsonify({'error': 'Token de seguridad inválido'}), 400
    
    data = request.get_json()
    
    # Validate required fields
    required_fields = ['name', 'rate']
    for field in required_fields:
        if not data.get(field):
            return jsonify({'error': f'Campo requerido: {field}'}), 400
    
    try:
        # Check if tax type with same name already exists
        existing = models.TaxType.query.filter_by(name=data['name']).first()
        if existing:
            return jsonify({'error': 'Ya existe un tipo de impuesto con ese nombre'}), 400
        
        # Create new tax type
        tax_type = models.TaxType()
        tax_type.name = data['name']
        tax_type.description = data.get('description', '')
        tax_type.rate = float(data['rate'])
        tax_type.is_inclusive = data.get('is_inclusive', False)
        tax_type.is_percentage = data.get('is_percentage', True)
        tax_type.display_order = data.get('display_order', 0)
        tax_type.active = True
        
        db.session.add(tax_type)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'Tipo de impuesto creado exitosamente',
            'tax_type': {
                'id': tax_type.id,
                'name': tax_type.name,
                'description': tax_type.description,
                'rate': tax_type.rate,
                'is_inclusive': tax_type.is_inclusive,
                'is_percentage': tax_type.is_percentage,
                'active': tax_type.active,
                'display_order': tax_type.display_order
            }
        })
        
    except ValueError:
        return jsonify({'error': 'Tasa de impuesto debe ser un número válido'}), 400
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': f'Error creando tipo de impuesto: {str(e)}'}), 500


@bp.route('/api/tax-types/<int:tax_type_id>', methods=['PUT'])
def api_update_tax_type(tax_type_id):
    """API to update a tax type"""
    user = require_admin()
    if not isinstance(user, models.User):
        return jsonify({'error': 'No autorizado'}), 401
    
    # Validate CSRF token
    if not validate_csrf_token():
        return jsonify({'error': 'Token de seguridad inválido'}), 400
    
    tax_type = models.TaxType.query.get_or_404(tax_type_id)
    data = request.get_json()
    
    try:
        # Check if another tax type with same name exists (exclude current one)
        if 'name' in data:
            existing = models.TaxType.query.filter(
                models.TaxType.name == data['name'],
                models.TaxType.id != tax_type_id
            ).first()
            if existing:
                return jsonify({'error': 'Ya existe un tipo de impuesto con ese nombre'}), 400
            tax_type.name = data['name']
        
        # Update fields if provided
        if 'description' in data:
            tax_type.description = data['description']
        if 'rate' in data:
            tax_type.rate = float(data['rate'])
        if 'is_inclusive' in data:
            tax_type.is_inclusive = data['is_inclusive']
        if 'is_percentage' in data:
            tax_type.is_percentage = data['is_percentage']
        if 'display_order' in data:
            tax_type.display_order = int(data['display_order'])
        if 'active' in data:
            tax_type.active = data['active']
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'Tipo de impuesto actualizado exitosamente',
            'tax_type': {
                'id': tax_type.id,
                'name': tax_type.name,
                'description': tax_type.description,
                'rate': tax_type.rate,
                'is_inclusive': tax_type.is_inclusive,
                'is_percentage': tax_type.is_percentage,
                'active': tax_type.active,
                'display_order': tax_type.display_order
            }
        })
        
    except ValueError:
        return jsonify({'error': 'Valores numéricos inválidos'}), 400
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': f'Error actualizando tipo de impuesto: {str(e)}'}), 500


@bp.route('/api/tax-types/<int:tax_type_id>', methods=['DELETE'])
def api_delete_tax_type(tax_type_id):
    """API to delete a tax type"""
    user = require_admin()
    if not isinstance(user, models.User):
        return jsonify({'error': 'No autorizado'}), 401
    
    # Validate CSRF token
    if not validate_csrf_token():
        return jsonify({'error': 'Token de seguridad inválido'}), 400
    
    tax_type = models.TaxType.query.get_or_404(tax_type_id)
    
    try:
        # Check if tax type is being used by any products
        product_count = models.ProductTax.query.filter_by(tax_type_id=tax_type_id).count()
        if product_count > 0:
            return jsonify({'error': f'No se puede eliminar. Este tipo de impuesto está siendo usado por {product_count} producto(s)'}), 400
        
        db.session.delete(tax_type)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'Tipo de impuesto eliminado exitosamente'
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': f'Error eliminando tipo de impuesto: {str(e)}'}), 500


# CUSTOMER MANAGEMENT ROUTES
@bp.route('/customers')
def customers():
    user = require_admin_or_manager()
    if not isinstance(user, models.User):
        return user
    
    customers = models.Customer.query.filter_by(active=True).order_by(models.Customer.name.asc()).all()
    return render_template('admin/customers.html', customers=customers)


@bp.route('/customers/create', methods=['POST'])
def create_customer():
    user = require_admin_or_manager()
    if not isinstance(user, models.User):
        return jsonify({'error': 'No autorizado'}), 401
    
    # Validate CSRF token
    if not validate_csrf_token():
        return redirect(url_for('admin.customers'))
    
    try:
        name = request.form['name'].strip()
        rnc = request.form.get('rnc', '').strip()
        phone = request.form.get('phone', '').strip()
        email = request.form.get('email', '').strip()
        address = request.form.get('address', '').strip()
        
        if not name:
            flash('El nombre del cliente es obligatorio', 'error')
            return redirect(url_for('admin.customers'))
        
        # Check if name already exists
        existing_customer = models.Customer.query.filter_by(name=name, active=True).first()
        if existing_customer:
            flash('Ya existe un cliente con ese nombre', 'error')
            return redirect(url_for('admin.customers'))
        
        # Check if RNC already exists (if provided)
        if rnc:
            existing_rnc = models.Customer.query.filter_by(rnc=rnc, active=True).first()
            if existing_rnc:
                flash('Ya existe un cliente con ese RNC/Cédula', 'error')
                return redirect(url_for('admin.customers'))
        
        new_customer = models.Customer()
        new_customer.name = name
        new_customer.rnc = rnc if rnc else None
        new_customer.phone = phone if phone else None
        new_customer.email = email if email else None
        new_customer.address = address if address else None
        new_customer.active = True
        
        db.session.add(new_customer)
        db.session.commit()
        
        flash(f'Cliente {name} creado exitosamente', 'success')
        
    except Exception as e:
        db.session.rollback()
        flash(f'Error al crear cliente: {str(e)}', 'error')
    
    return redirect(url_for('admin.customers'))


@bp.route('/customers/<int:customer_id>/edit', methods=['POST'])
def edit_customer(customer_id):
    user = require_admin_or_manager()
    if not isinstance(user, models.User):
        return jsonify({'error': 'No autorizado'}), 401
    
    # Validate CSRF token
    if not validate_csrf_token():
        return redirect(url_for('admin.customers'))
    
    try:
        customer = models.Customer.query.get_or_404(customer_id)
        
        name = request.form['name'].strip()
        rnc = request.form.get('rnc', '').strip()
        phone = request.form.get('phone', '').strip()
        email = request.form.get('email', '').strip()
        address = request.form.get('address', '').strip()
        
        if not name:
            flash('El nombre del cliente es obligatorio', 'error')
            return redirect(url_for('admin.customers'))
        
        # Check if name already exists (excluding current customer)
        existing_customer = models.Customer.query.filter(
            models.Customer.name == name,
            models.Customer.id != customer_id,
            models.Customer.active == True
        ).first()
        if existing_customer:
            flash('Ya existe un cliente con ese nombre', 'error')
            return redirect(url_for('admin.customers'))
        
        # Check if RNC already exists (excluding current customer)
        if rnc:
            existing_rnc = models.Customer.query.filter(
                models.Customer.rnc == rnc,
                models.Customer.id != customer_id,
                models.Customer.active == True
            ).first()
            if existing_rnc:
                flash('Ya existe un cliente con ese RNC/Cédula', 'error')
                return redirect(url_for('admin.customers'))
        
        customer.name = name
        customer.rnc = rnc if rnc else None
        customer.phone = phone if phone else None
        customer.email = email if email else None
        customer.address = address if address else None
        
        db.session.commit()
        
        flash(f'Cliente {name} actualizado exitosamente', 'success')
        
    except Exception as e:
        db.session.rollback()
        flash(f'Error al actualizar cliente: {str(e)}', 'error')
    
    return redirect(url_for('admin.customers'))


@bp.route('/customers/<int:customer_id>/delete', methods=['POST'])
def delete_customer(customer_id):
    user = require_admin_or_manager()
    if not isinstance(user, models.User):
        return jsonify({'error': 'No autorizado'}), 401
    
    # Validate CSRF token
    if not validate_csrf_token():
        return redirect(url_for('admin.customers'))
    
    try:
        customer = models.Customer.query.get_or_404(customer_id)
        
        # Check if customer has sales
        sales_count = models.Sale.query.filter_by(customer_id=customer_id).count()
        if sales_count > 0:
            flash(f'No se puede eliminar el cliente {customer.name} porque tiene {sales_count} ventas asociadas. Se desactivó en su lugar.', 'warning')
            customer.active = False
        else:
            customer.active = False
            flash(f'Cliente {customer.name} desactivado exitosamente', 'success')
        
        db.session.commit()
        
    except Exception as e:
        db.session.rollback()
        flash(f'Error al eliminar cliente: {str(e)}', 'error')
    
    return redirect(url_for('admin.customers'))


# SUPPLIER MANAGEMENT ROUTES
@bp.route('/suppliers')
def suppliers():
    user = require_admin_or_manager()
    if not isinstance(user, models.User):
        return user
    
    suppliers = models.Supplier.query.filter_by(active=True).order_by(models.Supplier.name.asc()).all()
    return render_template('admin/suppliers.html', suppliers=suppliers)


@bp.route('/suppliers/create', methods=['POST'])
def create_supplier():
    user = require_admin_or_manager()
    if not isinstance(user, models.User):
        return jsonify({'error': 'No autorizado'}), 401
    
    # Validate CSRF token
    if not validate_csrf_token():
        return redirect(url_for('admin.suppliers'))
    
    try:
        name = request.form['name'].strip()
        rnc = request.form.get('rnc', '').strip()
        contact_person = request.form.get('contact_person', '').strip()
        phone = request.form.get('phone', '').strip()
        email = request.form.get('email', '').strip()
        address = request.form.get('address', '').strip()
        
        if not name:
            flash('El nombre del proveedor es obligatorio', 'error')
            return redirect(url_for('admin.suppliers'))
        
        # Check if name already exists
        existing_supplier = models.Supplier.query.filter_by(name=name, active=True).first()
        if existing_supplier:
            flash('Ya existe un proveedor con ese nombre', 'error')
            return redirect(url_for('admin.suppliers'))
        
        # Check if RNC already exists (if provided)
        if rnc:
            existing_rnc = models.Supplier.query.filter_by(rnc=rnc, active=True).first()
            if existing_rnc:
                flash('Ya existe un proveedor con ese RNC', 'error')
                return redirect(url_for('admin.suppliers'))
        
        new_supplier = models.Supplier()
        new_supplier.name = name
        new_supplier.rnc = rnc if rnc else None
        new_supplier.contact_person = contact_person if contact_person else None
        new_supplier.phone = phone if phone else None
        new_supplier.email = email if email else None
        new_supplier.address = address if address else None
        new_supplier.active = True
        
        db.session.add(new_supplier)
        db.session.commit()
        
        flash(f'Proveedor {name} creado exitosamente', 'success')
        
    except Exception as e:
        db.session.rollback()
        flash(f'Error al crear proveedor: {str(e)}', 'error')
    
    return redirect(url_for('admin.suppliers'))


@bp.route('/suppliers/<int:supplier_id>/edit', methods=['POST'])
def edit_supplier(supplier_id):
    user = require_admin_or_manager()
    if not isinstance(user, models.User):
        return jsonify({'error': 'No autorizado'}), 401
    
    # Validate CSRF token
    if not validate_csrf_token():
        return redirect(url_for('admin.suppliers'))
    
    try:
        supplier = models.Supplier.query.get_or_404(supplier_id)
        
        name = request.form['name'].strip()
        rnc = request.form.get('rnc', '').strip()
        contact_person = request.form.get('contact_person', '').strip()
        phone = request.form.get('phone', '').strip()
        email = request.form.get('email', '').strip()
        address = request.form.get('address', '').strip()
        
        if not name:
            flash('El nombre del proveedor es obligatorio', 'error')
            return redirect(url_for('admin.suppliers'))
        
        # Check if name already exists (excluding current supplier)
        existing_supplier = models.Supplier.query.filter(
            models.Supplier.name == name,
            models.Supplier.id != supplier_id,
            models.Supplier.active == True
        ).first()
        if existing_supplier:
            flash('Ya existe un proveedor con ese nombre', 'error')
            return redirect(url_for('admin.suppliers'))
        
        # Check if RNC already exists (excluding current supplier)
        if rnc:
            existing_rnc = models.Supplier.query.filter(
                models.Supplier.rnc == rnc,
                models.Supplier.id != supplier_id,
                models.Supplier.active == True
            ).first()
            if existing_rnc:
                flash('Ya existe un proveedor con ese RNC', 'error')
                return redirect(url_for('admin.suppliers'))
        
        supplier.name = name
        supplier.rnc = rnc if rnc else None
        supplier.contact_person = contact_person if contact_person else None
        supplier.phone = phone if phone else None
        supplier.email = email if email else None
        supplier.address = address if address else None
        
        db.session.commit()
        
        flash(f'Proveedor {name} actualizado exitosamente', 'success')
        
    except Exception as e:
        db.session.rollback()
        flash(f'Error al actualizar proveedor: {str(e)}', 'error')
    
    return redirect(url_for('admin.suppliers'))


@bp.route('/suppliers/<int:supplier_id>/delete', methods=['POST'])
def delete_supplier(supplier_id):
    user = require_admin_or_manager()
    if not isinstance(user, models.User):
        return jsonify({'error': 'No autorizado'}), 401
    
    # Validate CSRF token
    if not validate_csrf_token():
        return redirect(url_for('admin.suppliers'))
    
    try:
        supplier = models.Supplier.query.get_or_404(supplier_id)
        
        # Check if supplier has purchases
        purchases_count = models.Purchase.query.filter_by(supplier_id=supplier_id).count()
        if purchases_count > 0:
            flash(f'No se puede eliminar el proveedor {supplier.name} porque tiene {purchases_count} compras asociadas. Se desactivó en su lugar.', 'warning')
            supplier.active = False
        else:
            supplier.active = False
            flash(f'Proveedor {supplier.name} desactivado exitosamente', 'success')
        
        db.session.commit()
        
    except Exception as e:
        db.session.rollback()
        flash(f'Error al eliminar proveedor: {str(e)}', 'error')
    
    return redirect(url_for('admin.suppliers'))


@bp.route('/api/sales-report')
def sales_report_api():
    """API endpoint para obtener datos de ventas por período"""
    user = require_admin_or_manager_or_cashier()
    if not isinstance(user, models.User):
        return jsonify({'error': 'No autorizado'}), 401
    
    # Obtener parámetros
    period = request.args.get('period', 'day')  # day, week, month, year, custom
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    
    try:
        from datetime import datetime, timedelta
        
        # Determinar rango de fechas según el período
        if period == 'day':
            start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
            end = datetime.now().replace(hour=23, minute=59, second=59, microsecond=999999)
        elif period == 'week':
            start = datetime.now() - timedelta(days=7)
            start = start.replace(hour=0, minute=0, second=0, microsecond=0)
            end = datetime.now().replace(hour=23, minute=59, second=59, microsecond=999999)
        elif period == 'month':
            start = datetime.now().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            end = datetime.now().replace(hour=23, minute=59, second=59, microsecond=999999)
        elif period == 'year':
            start = datetime.now().replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
            end = datetime.now().replace(hour=23, minute=59, second=59, microsecond=999999)
        elif period == 'custom' and start_date and end_date:
            start = datetime.strptime(start_date, '%Y-%m-%d')
            end = datetime.strptime(end_date, '%Y-%m-%d').replace(hour=23, minute=59, second=59)
        else:
            return jsonify({'error': 'Período inválido'}), 400
        
        # Consultar ventas completadas en el período
        query = models.Sale.query.filter(
            models.Sale.status == 'completed',
            models.Sale.created_at >= start,
            models.Sale.created_at <= end
        )
        
        # Para cajeros, solo sus ventas
        if user.role.value == 'CAJERO':
            cash_register = models.CashRegister.query.filter_by(user_id=user.id, active=True).first()
            if cash_register:
                query = query.filter(models.Sale.cash_register_id == cash_register.id)
        
        sales = query.order_by(models.Sale.created_at.desc()).all()
        
        # Calcular estadísticas
        total_sales = len(sales)
        total_amount = sum(sale.total for sale in sales)
        total_tax = sum(sale.tax_amount for sale in sales)
        total_subtotal = sum(sale.subtotal for sale in sales)
        
        # Agrupar por método de pago
        payment_methods = {}
        for sale in sales:
            method = sale.payment_method or 'Efectivo'
            if method not in payment_methods:
                payment_methods[method] = {'count': 0, 'total': 0}
            payment_methods[method]['count'] += 1
            payment_methods[method]['total'] += sale.total
        
        # Productos más vendidos
        product_sales = {}
        for sale in sales:
            for item in sale.sale_items:
                product_name = item.product.name
                if product_name not in product_sales:
                    product_sales[product_name] = {'quantity': 0, 'total': 0}
                product_sales[product_name]['quantity'] += item.quantity
                product_sales[product_name]['total'] += item.total_price
        
        # Ordenar productos por cantidad vendida
        top_products = sorted(
            [{'name': k, **v} for k, v in product_sales.items()],
            key=lambda x: x['quantity'],
            reverse=True
        )[:10]
        
        # Ventas por día (para gráficos)
        sales_by_day = {}
        for sale in sales:
            day_key = sale.created_at.strftime('%Y-%m-%d')
            if day_key not in sales_by_day:
                sales_by_day[day_key] = {'count': 0, 'total': 0}
            sales_by_day[day_key]['count'] += 1
            sales_by_day[day_key]['total'] += sale.total
        
        # Lista detallada de ventas
        sales_list = []
        for sale in sales:
            sales_list.append({
                'id': sale.id,
                'ncf': sale.ncf or 'N/A',
                'customer_name': sale.customer_name or 'Cliente General',
                'customer_rnc': sale.customer_rnc or '',
                'created_at': sale.created_at.strftime('%Y-%m-%d %H:%M:%S'),
                'subtotal': float(sale.subtotal),
                'tax_amount': float(sale.tax_amount),
                'total': float(sale.total),
                'payment_method': sale.payment_method or 'Efectivo',
                'user': sale.user.username if sale.user else 'N/A',
                'items': [{
                    'product_name': item.product.name,
                    'quantity': item.quantity,
                    'unit_price': float(item.unit_price),
                    'total_price': float(item.total_price)
                } for item in sale.sale_items]
            })
        
        return jsonify({
            'success': True,
            'period': period,
            'start_date': start.strftime('%Y-%m-%d'),
            'end_date': end.strftime('%Y-%m-%d'),
            'summary': {
                'total_sales': total_sales,
                'total_amount': float(total_amount),
                'total_tax': float(total_tax),
                'total_subtotal': float(total_subtotal),
                'average_sale': float(total_amount / total_sales) if total_sales > 0 else 0
            },
            'payment_methods': payment_methods,
            'top_products': top_products,
            'sales_by_day': sales_by_day,
            'sales': sales_list
        })
        
    except Exception as e:
        return jsonify({'error': f'Error al generar reporte: {str(e)}'}), 500


@bp.route('/api/sales-report/pdf')
def download_sales_report_pdf():
    """Generar y descargar PDF de reporte de ventas"""
    user = require_admin_or_manager_or_cashier()
    if not isinstance(user, models.User):
        flash('No autorizado', 'error')
        return redirect(url_for('auth.login'))
    
    # Obtener parámetros
    period = request.args.get('period', 'day')
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    
    try:
        from datetime import datetime, timedelta
        from receipt_generator import generate_sales_report_pdf
        from flask import send_file
        
        # Determinar rango de fechas según el período
        if period == 'day':
            start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
            end = datetime.now().replace(hour=23, minute=59, second=59, microsecond=999999)
            period_name = f"Día {start.strftime('%d/%m/%Y')}"
        elif period == 'week':
            start = datetime.now() - timedelta(days=7)
            start = start.replace(hour=0, minute=0, second=0, microsecond=0)
            end = datetime.now().replace(hour=23, minute=59, second=59, microsecond=999999)
            period_name = "Últimos 7 días"
        elif period == 'month':
            start = datetime.now().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            end = datetime.now().replace(hour=23, minute=59, second=59, microsecond=999999)
            period_name = f"Mes {start.strftime('%B %Y')}"
        elif period == 'year':
            start = datetime.now().replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
            end = datetime.now().replace(hour=23, minute=59, second=59, microsecond=999999)
            period_name = f"Año {start.year}"
        elif period == 'custom' and start_date and end_date:
            start = datetime.strptime(start_date, '%Y-%m-%d')
            end = datetime.strptime(end_date, '%Y-%m-%d').replace(hour=23, minute=59, second=59)
            period_name = f"{start.strftime('%d/%m/%Y')} - {end.strftime('%d/%m/%Y')}"
        else:
            flash('Período inválido', 'error')
            return redirect(url_for('admin.reports'))
        
        # Consultar ventas completadas en el período
        query = models.Sale.query.filter(
            models.Sale.status == 'completed',
            models.Sale.created_at >= start,
            models.Sale.created_at <= end
        )
        
        # Para cajeros, solo sus ventas
        if user.role.value == 'CAJERO':
            cash_register = models.CashRegister.query.filter_by(user_id=user.id, active=True).first()
            if cash_register:
                query = query.filter(models.Sale.cash_register_id == cash_register.id)
        
        sales = query.order_by(models.Sale.created_at.desc()).all()
        
        # Generar PDF
        pdf_path = generate_sales_report_pdf(sales, period_name, start, end)
        
        # Enviar archivo
        return send_file(
            pdf_path,
            as_attachment=True,
            download_name=f"reporte_ventas_{period}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf",
            mimetype='application/pdf'
        )
        
    except Exception as e:
        flash(f'Error al generar PDF: {str(e)}', 'error')
        return redirect(url_for('admin.reports'))


@bp.route('/api/products-report')
def products_report_api():
    """API endpoint para obtener datos de productos más vendidos por período"""
    user = require_admin_or_manager_or_cashier()
    if not isinstance(user, models.User):
        return jsonify({'error': 'No autorizado'}), 401
    
    # Obtener parámetros
    period = request.args.get('period', 'day')  # day, week, month, year, custom
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    limit = request.args.get('limit', 50)  # Top 50 por defecto
    
    try:
        limit = int(limit)
        if limit not in [10, 20, 50, 100]:
            limit = 50
    except:
        limit = 50
    
    try:
        from datetime import datetime, timedelta
        
        # Determinar rango de fechas según el período
        if period == 'day':
            start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
            end = datetime.now().replace(hour=23, minute=59, second=59, microsecond=999999)
            period_name = f"Día {start.strftime('%d/%m/%Y')}"
        elif period == 'week':
            start = datetime.now() - timedelta(days=7)
            start = start.replace(hour=0, minute=0, second=0, microsecond=0)
            end = datetime.now().replace(hour=23, minute=59, second=59, microsecond=999999)
            period_name = "Últimos 7 días"
        elif period == 'month':
            start = datetime.now().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            end = datetime.now().replace(hour=23, minute=59, second=59, microsecond=999999)
            period_name = f"Mes {start.strftime('%B %Y')}"
        elif period == 'year':
            start = datetime.now().replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
            end = datetime.now().replace(hour=23, minute=59, second=59, microsecond=999999)
            period_name = f"Año {start.year}"
        elif period == 'custom' and start_date and end_date:
            start = datetime.strptime(start_date, '%Y-%m-%d')
            end = datetime.strptime(end_date, '%Y-%m-%d').replace(hour=23, minute=59, second=59)
            period_name = f"{start.strftime('%d/%m/%Y')} - {end.strftime('%d/%m/%Y')}"
        else:
            return jsonify({'error': 'Período inválido'}), 400
        
        # Consultar items de ventas completadas en el período
        sale_items_query = db.session.query(
            models.SaleItem.product_id,
            models.Product.name,
            models.Category.name.label('category_name'),
            func.sum(models.SaleItem.quantity).label('total_quantity'),
            func.sum(models.SaleItem.total_price).label('total_revenue'),
            func.count(models.SaleItem.id).label('num_sales'),
            func.avg(models.SaleItem.unit_price).label('avg_price'),
            models.Product.cost
        ).join(
            models.Sale, models.SaleItem.sale_id == models.Sale.id
        ).join(
            models.Product, models.SaleItem.product_id == models.Product.id
        ).outerjoin(
            models.Category, models.Product.category_id == models.Category.id
        ).filter(
            models.Sale.status == 'completed',
            models.Sale.created_at >= start,
            models.Sale.created_at <= end
        ).group_by(
            models.SaleItem.product_id,
            models.Product.name,
            models.Category.name,
            models.Product.cost
        )
        
        # Para cajeros, solo sus ventas
        if user.role.value == 'CAJERO':
            cash_register = models.CashRegister.query.filter_by(user_id=user.id, active=True).first()
            if cash_register:
                sale_items_query = sale_items_query.filter(models.Sale.cash_register_id == cash_register.id)
        
        product_stats = sale_items_query.all()
        
        # Calcular totales generales
        total_products_sold = sum(p.total_quantity for p in product_stats)
        total_revenue = sum(p.total_revenue for p in product_stats)
        
        # Preparar datos de productos
        products_data = []
        for idx, product in enumerate(product_stats):
            # Calcular margen de ganancia
            total_cost = product.cost * product.total_quantity if product.cost else 0
            profit = product.total_revenue - total_cost
            profit_margin = (profit / product.total_revenue * 100) if product.total_revenue > 0 else 0
            
            # Calcular porcentaje sobre ventas totales
            revenue_percentage = (product.total_revenue / total_revenue * 100) if total_revenue > 0 else 0
            quantity_percentage = (product.total_quantity / total_products_sold * 100) if total_products_sold > 0 else 0
            
            products_data.append({
                'rank': idx + 1,
                'product_id': product.product_id,
                'name': product.name,
                'category': product.category_name or 'Sin categoría',
                'quantity_sold': int(product.total_quantity),
                'num_sales': int(product.num_sales),
                'total_revenue': float(product.total_revenue),
                'avg_price': float(product.avg_price),
                'cost': float(product.cost) if product.cost else 0,
                'profit': float(profit),
                'profit_margin': float(profit_margin),
                'revenue_percentage': float(revenue_percentage),
                'quantity_percentage': float(quantity_percentage)
            })
        
        # Ordenar por cantidad vendida
        products_by_quantity = sorted(products_data, key=lambda x: x['quantity_sold'], reverse=True)[:limit]
        
        # Ordenar por ingresos generados
        products_by_revenue = sorted(products_data, key=lambda x: x['total_revenue'], reverse=True)[:limit]
        
        # Estadísticas por categoría
        category_stats = {}
        for product in products_data:
            category = product['category']
            if category not in category_stats:
                category_stats[category] = {
                    'quantity_sold': 0,
                    'total_revenue': 0,
                    'num_products': 0
                }
            category_stats[category]['quantity_sold'] += product['quantity_sold']
            category_stats[category]['total_revenue'] += product['total_revenue']
            category_stats[category]['num_products'] += 1
        
        # Convertir a lista y ordenar
        categories_list = [
            {
                'name': k,
                'quantity_sold': v['quantity_sold'],
                'total_revenue': v['total_revenue'],
                'num_products': v['num_products'],
                'revenue_percentage': (v['total_revenue'] / total_revenue * 100) if total_revenue > 0 else 0
            }
            for k, v in category_stats.items()
        ]
        categories_list = sorted(categories_list, key=lambda x: x['total_revenue'], reverse=True)
        
        return jsonify({
            'success': True,
            'period': period,
            'period_name': period_name,
            'start_date': start.strftime('%Y-%m-%d'),
            'end_date': end.strftime('%Y-%m-%d'),
            'summary': {
                'total_products': len(products_data),
                'total_quantity_sold': int(total_products_sold),
                'total_revenue': float(total_revenue),
                'avg_revenue_per_product': float(total_revenue / len(products_data)) if len(products_data) > 0 else 0
            },
            'products_by_quantity': products_by_quantity,
            'products_by_revenue': products_by_revenue,
            'categories': categories_list
        })
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': f'Error al generar reporte: {str(e)}'}), 500


@bp.route('/api/products-report/pdf')
def download_products_report_pdf():
    """Generar y descargar PDF de reporte de productos más vendidos"""
    user = require_admin_or_manager_or_cashier()
    if not isinstance(user, models.User):
        flash('No autorizado', 'error')
        return redirect(url_for('auth.login'))
    
    # Obtener parámetros
    period = request.args.get('period', 'day')
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    limit = request.args.get('limit', 50)
    
    try:
        limit = int(limit)
        if limit not in [10, 20, 50, 100]:
            limit = 50
    except:
        limit = 50
    
    try:
        from datetime import datetime, timedelta
        from receipt_generator import generate_products_report_pdf
        from flask import send_file
        
        # Determinar rango de fechas según el período
        if period == 'day':
            start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
            end = datetime.now().replace(hour=23, minute=59, second=59, microsecond=999999)
            period_name = f"Día {start.strftime('%d/%m/%Y')}"
        elif period == 'week':
            start = datetime.now() - timedelta(days=7)
            start = start.replace(hour=0, minute=0, second=0, microsecond=0)
            end = datetime.now().replace(hour=23, minute=59, second=59, microsecond=999999)
            period_name = "Últimos 7 días"
        elif period == 'month':
            start = datetime.now().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            end = datetime.now().replace(hour=23, minute=59, second=59, microsecond=999999)
            period_name = f"Mes {start.strftime('%B %Y')}"
        elif period == 'year':
            start = datetime.now().replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
            end = datetime.now().replace(hour=23, minute=59, second=59, microsecond=999999)
            period_name = f"Año {start.year}"
        elif period == 'custom' and start_date and end_date:
            start = datetime.strptime(start_date, '%Y-%m-%d')
            end = datetime.strptime(end_date, '%Y-%m-%d').replace(hour=23, minute=59, second=59)
            period_name = f"{start.strftime('%d/%m/%Y')} - {end.strftime('%d/%m/%Y')}"
        else:
            flash('Período inválido', 'error')
            return redirect(url_for('admin.reports'))
        
        # Consultar items de ventas completadas en el período
        sale_items_query = db.session.query(
            models.SaleItem.product_id,
            models.Product.name,
            models.Category.name.label('category_name'),
            func.sum(models.SaleItem.quantity).label('total_quantity'),
            func.sum(models.SaleItem.total_price).label('total_revenue'),
            func.count(models.SaleItem.id).label('num_sales'),
            func.avg(models.SaleItem.unit_price).label('avg_price'),
            models.Product.cost
        ).join(
            models.Sale, models.SaleItem.sale_id == models.Sale.id
        ).join(
            models.Product, models.SaleItem.product_id == models.Product.id
        ).outerjoin(
            models.Category, models.Product.category_id == models.Category.id
        ).filter(
            models.Sale.status == 'completed',
            models.Sale.created_at >= start,
            models.Sale.created_at <= end
        ).group_by(
            models.SaleItem.product_id,
            models.Product.name,
            models.Category.name,
            models.Product.cost
        )
        
        # Para cajeros, solo sus ventas
        if user.role.value == 'CAJERO':
            cash_register = models.CashRegister.query.filter_by(user_id=user.id, active=True).first()
            if cash_register:
                sale_items_query = sale_items_query.filter(models.Sale.cash_register_id == cash_register.id)
        
        product_stats = sale_items_query.all()
        
        # Ordenar por cantidad vendida y limitar
        products_sorted = sorted(product_stats, key=lambda x: x.total_quantity, reverse=True)[:limit]
        
        # Generar PDF
        pdf_path = generate_products_report_pdf(products_sorted, period_name, start, end, limit)
        
        # Enviar archivo
        return send_file(
            pdf_path,
            as_attachment=True,
            download_name=f"reporte_productos_{period}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf",
            mimetype='application/pdf'
        )
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        flash(f'Error al generar PDF: {str(e)}', 'error')
        return redirect(url_for('admin.reports'))


@bp.route('/api/ncf-report')
def ncf_report_api():
    """API endpoint para obtener reporte de comprobantes NCF"""
    user = require_admin_or_manager_or_cashier()
    if not isinstance(user, models.User):
        return jsonify({'error': 'No autorizado'}), 401
    
    # Obtener parámetros
    ncf_type_filter = request.args.get('ncf_type', 'all')  # all, consumo, credito_fiscal, gubernamental
    status_filter = request.args.get('status', 'all')  # all, used, cancelled, available
    period = request.args.get('period', 'all')  # all, day, week, month, year, custom
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    
    try:
        from datetime import datetime, timedelta
        
        # Determinar rango de fechas según el período (para filtrar comprobantes emitidos)
        if period == 'day':
            start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
            end = datetime.now().replace(hour=23, minute=59, second=59, microsecond=999999)
            period_name = f"Día {start.strftime('%d/%m/%Y')}"
        elif period == 'week':
            start = datetime.now() - timedelta(days=7)
            start = start.replace(hour=0, minute=0, second=0, microsecond=0)
            end = datetime.now().replace(hour=23, minute=59, second=59, microsecond=999999)
            period_name = "Últimos 7 días"
        elif period == 'month':
            start = datetime.now().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            end = datetime.now().replace(hour=23, minute=59, second=59, microsecond=999999)
            period_name = f"Mes {start.strftime('%B %Y')}"
        elif period == 'year':
            start = datetime.now().replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
            end = datetime.now().replace(hour=23, minute=59, second=59, microsecond=999999)
            period_name = f"Año {start.year}"
        elif period == 'custom' and start_date and end_date:
            start = datetime.strptime(start_date, '%Y-%m-%d')
            end = datetime.strptime(end_date, '%Y-%m-%d').replace(hour=23, minute=59, second=59)
            period_name = f"{start.strftime('%d/%m/%Y')} - {end.strftime('%d/%m/%Y')}"
        else:
            start = None
            end = None
            period_name = "Todas las fechas"
        
        # Obtener todas las secuencias NCF
        sequences_query = models.NCFSequence.query
        
        # Filtrar por tipo si se especifica
        if ncf_type_filter != 'all':
            try:
                ncf_type_enum = models.NCFType(ncf_type_filter.upper())
                sequences_query = sequences_query.filter(models.NCFSequence.ncf_type == ncf_type_enum)
            except ValueError:
                pass
        
        sequences = sequences_query.all()
        
        # Mapeo de nombres amigables para tipos de NCF
        ncf_type_names = {
            'CONSUMO': 'Consumo Final',
            'CREDITO_FISCAL': 'Crédito Fiscal',
            'GUBERNAMENTAL': 'Gubernamental',
            'NOTA_CREDITO': 'Nota de Crédito',
            'NOTA_DEBITO': 'Nota de Débito'
        }
        
        # Estadísticas por tipo de NCF
        stats_by_type = {}
        alerts = []
        
        for sequence in sequences:
            ncf_type = sequence.ncf_type.value
            
            if ncf_type not in stats_by_type:
                stats_by_type[ncf_type] = {
                    'type': ncf_type,
                    'type_display': ncf_type_names.get(ncf_type, ncf_type),
                    'sequences': [],
                    'total_in_range': 0,
                    'total_used': 0,
                    'total_cancelled': 0,
                    'total_available': 0,
                    'utilization_percentage': 0
                }
            
            # Calcular estadísticas de la secuencia
            total_in_range = sequence.end_number - sequence.start_number + 1
            total_used = sequence.current_number - sequence.start_number
            available = sequence.end_number - sequence.current_number + 1
            
            # Contar NCFs cancelados de esta secuencia
            cancelled_count = models.CancelledNCF.query.filter_by(ncf_sequence_id=sequence.id).count()
            
            utilization = (total_used / total_in_range * 100) if total_in_range > 0 else 0
            
            # Agregar a estadísticas del tipo
            stats_by_type[ncf_type]['sequences'].append({
                'id': sequence.id,
                'serie': sequence.serie,
                'start_number': sequence.start_number,
                'end_number': sequence.end_number,
                'current_number': sequence.current_number,
                'total_in_range': total_in_range,
                'total_used': total_used,
                'available': available,
                'cancelled': cancelled_count,
                'utilization': round(utilization, 2),
                'active': sequence.active
            })
            
            stats_by_type[ncf_type]['total_in_range'] += total_in_range
            stats_by_type[ncf_type]['total_used'] += total_used
            stats_by_type[ncf_type]['total_cancelled'] += cancelled_count
            stats_by_type[ncf_type]['total_available'] += available
            
            # Generar alertas de rangos por agotarse
            if sequence.active:
                if available <= 20:
                    alerts.append({
                        'level': 'critical',
                        'type': ncf_type,
                        'type_display': ncf_type_names.get(ncf_type, ncf_type),
                        'serie': sequence.serie,
                        'available': available,
                        'message': f'CRÍTICO: Solo quedan {available} comprobantes en la serie {sequence.serie} ({ncf_type_names.get(ncf_type, ncf_type)})'
                    })
                elif available <= 100:
                    alerts.append({
                        'level': 'warning',
                        'type': ncf_type,
                        'type_display': ncf_type_names.get(ncf_type, ncf_type),
                        'serie': sequence.serie,
                        'available': available,
                        'message': f'ADVERTENCIA: Quedan {available} comprobantes en la serie {sequence.serie} ({ncf_type_names.get(ncf_type, ncf_type)})'
                    })
        
        # Calcular porcentaje de utilización por tipo
        for ncf_type in stats_by_type:
            total_range = stats_by_type[ncf_type]['total_in_range']
            total_used = stats_by_type[ncf_type]['total_used']
            stats_by_type[ncf_type]['utilization_percentage'] = round(
                (total_used / total_range * 100) if total_range > 0 else 0, 2
            )
        
        # Obtener listado de comprobantes emitidos
        ledger_query = models.NCFLedger.query.join(
            models.NCFSequence, models.NCFLedger.sequence_id == models.NCFSequence.id
        ).join(
            models.User, models.NCFLedger.user_id == models.User.id
        ).outerjoin(
            models.Sale, models.NCFLedger.sale_id == models.Sale.id
        )
        
        # Filtrar por período si se especifica
        if start and end:
            ledger_query = ledger_query.filter(
                models.NCFLedger.issued_at >= start,
                models.NCFLedger.issued_at <= end
            )
        
        # Filtrar por tipo de NCF si se especifica
        if ncf_type_filter != 'all':
            try:
                ncf_type_enum = models.NCFType(ncf_type_filter.upper())
                ledger_query = ledger_query.filter(models.NCFSequence.ncf_type == ncf_type_enum)
            except ValueError:
                pass
        
        # Ordenar por fecha de emisión descendente
        ledger_entries = ledger_query.order_by(models.NCFLedger.issued_at.desc()).limit(500).all()
        
        # Preparar listado de comprobantes
        ncf_list = []
        for ledger in ledger_entries:
            # Verificar si está cancelado
            cancelled = models.CancelledNCF.query.filter_by(ncf=ledger.ncf).first()
            
            # Aplicar filtro de estado
            if status_filter == 'cancelled' and not cancelled:
                continue
            elif status_filter == 'used' and cancelled:
                continue
            
            ncf_data = {
                'id': ledger.id,
                'ncf': ledger.ncf,
                'serie': ledger.serie,
                'number': ledger.number,
                'type': ledger.sequence.ncf_type.value,
                'type_display': ncf_type_names.get(ledger.sequence.ncf_type.value, ledger.sequence.ncf_type.value),
                'issued_at': ledger.issued_at.strftime('%d/%m/%Y %H:%M:%S'),
                'user': ledger.user.username,
                'status': 'cancelado' if cancelled else 'usado',
                'sale_id': ledger.sale_id,
                'client_name': None,
                'client_rnc': None,
                'amount': 0
            }
            
            # Obtener información de la venta si existe
            if ledger.sale:
                ncf_data['client_name'] = ledger.sale.client_name or 'Consumidor Final'
                ncf_data['client_rnc'] = ledger.sale.client_rnc or 'N/A'
                ncf_data['amount'] = float(ledger.sale.final_total)
            
            ncf_list.append(ncf_data)
        
        # Resumen general
        total_sequences = len(sequences)
        active_sequences = sum(1 for s in sequences if s.active)
        total_ncf_in_all_ranges = sum(s['total_in_range'] for s in stats_by_type.values())
        total_ncf_used = sum(s['total_used'] for s in stats_by_type.values())
        total_ncf_available = sum(s['total_available'] for s in stats_by_type.values())
        total_ncf_cancelled = sum(s['total_cancelled'] for s in stats_by_type.values())
        
        return jsonify({
            'success': True,
            'period': period,
            'period_name': period_name,
            'summary': {
                'total_sequences': total_sequences,
                'active_sequences': active_sequences,
                'total_ncf_in_all_ranges': total_ncf_in_all_ranges,
                'total_ncf_used': total_ncf_used,
                'total_ncf_available': total_ncf_available,
                'total_ncf_cancelled': total_ncf_cancelled,
                'global_utilization': round((total_ncf_used / total_ncf_in_all_ranges * 100) if total_ncf_in_all_ranges > 0 else 0, 2)
            },
            'stats_by_type': list(stats_by_type.values()),
            'alerts': sorted(alerts, key=lambda x: x['available']),
            'ncf_list': ncf_list[:100],  # Limitar a 100 para el frontend
            'total_ncf_count': len(ncf_list)
        })
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': f'Error al generar reporte: {str(e)}'}), 500


@bp.route('/api/ncf-report/pdf')
def download_ncf_report_pdf():
    """Generar y descargar PDF de reporte de comprobantes NCF"""
    user = require_admin_or_manager_or_cashier()
    if not isinstance(user, models.User):
        flash('No autorizado', 'error')
        return redirect(url_for('auth.login'))
    
    ncf_type_filter = request.args.get('ncf_type', 'all')
    status_filter = request.args.get('status', 'all')
    period = request.args.get('period', 'all')
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    
    try:
        from datetime import datetime, timedelta
        from receipt_generator import generate_ncf_report_pdf
        from flask import send_file
        
        if period == 'day':
            start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
            end = datetime.now().replace(hour=23, minute=59, second=59, microsecond=999999)
            period_name = f"Día {start.strftime('%d/%m/%Y')}"
        elif period == 'week':
            start = datetime.now() - timedelta(days=7)
            start = start.replace(hour=0, minute=0, second=0, microsecond=0)
            end = datetime.now().replace(hour=23, minute=59, second=59, microsecond=999999)
            period_name = "Últimos 7 días"
        elif period == 'month':
            start = datetime.now().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            end = datetime.now().replace(hour=23, minute=59, second=59, microsecond=999999)
            period_name = f"Mes {start.strftime('%B %Y')}"
        elif period == 'year':
            start = datetime.now().replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
            end = datetime.now().replace(hour=23, minute=59, second=59, microsecond=999999)
            period_name = f"Año {start.year}"
        elif period == 'custom' and start_date and end_date:
            start = datetime.strptime(start_date, '%Y-%m-%d')
            end = datetime.strptime(end_date, '%Y-%m-%d').replace(hour=23, minute=59, second=59)
            period_name = f"{start.strftime('%d/%m/%Y')} - {end.strftime('%d/%m/%Y')}"
        else:
            start = None
            end = None
            period_name = "Todas las fechas"
        
        sequences_query = models.NCFSequence.query
        
        if ncf_type_filter != 'all':
            try:
                ncf_type_enum = models.NCFType(ncf_type_filter.upper())
                sequences_query = sequences_query.filter(models.NCFSequence.ncf_type == ncf_type_enum)
            except ValueError:
                pass
        
        sequences = sequences_query.all()
        
        ledger_query = models.NCFLedger.query.join(
            models.NCFSequence, models.NCFLedger.sequence_id == models.NCFSequence.id
        ).join(
            models.User, models.NCFLedger.user_id == models.User.id
        ).outerjoin(
            models.Sale, models.NCFLedger.sale_id == models.Sale.id
        )
        
        if start and end:
            ledger_query = ledger_query.filter(
                models.NCFLedger.issued_at >= start,
                models.NCFLedger.issued_at <= end
            )
        
        if ncf_type_filter != 'all':
            try:
                ncf_type_enum = models.NCFType(ncf_type_filter.upper())
                ledger_query = ledger_query.filter(models.NCFSequence.ncf_type == ncf_type_enum)
            except ValueError:
                pass
        
        ledger_entries = ledger_query.order_by(models.NCFLedger.issued_at.desc()).limit(500).all()
        
        pdf_path = generate_ncf_report_pdf(sequences, ledger_entries, period_name, start, end)
        
        return send_file(
            pdf_path,
            as_attachment=True,
            download_name=f"reporte_ncf_{period}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf",
            mimetype='application/pdf'
        )
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        flash(f'Error al generar PDF: {str(e)}', 'error')
        return redirect(url_for('admin.reports'))


@bp.route('/api/users-sales-report')
def users_sales_report_api():
    """API endpoint para obtener datos de ventas por usuario"""
    user = require_admin_or_manager_or_cashier()
    if not isinstance(user, models.User):
        return jsonify({'error': 'No autorizado'}), 401
    
    # Obtener parámetros
    period = request.args.get('period', 'day')
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    role_filter = request.args.get('role', 'all')
    
    try:
        from datetime import datetime, timedelta
        
        # Determinar rango de fechas según el período
        if period == 'day':
            start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
            end = datetime.now().replace(hour=23, minute=59, second=59, microsecond=999999)
            period_name = f"Día {start.strftime('%d/%m/%Y')}"
        elif period == 'week':
            start = datetime.now() - timedelta(days=7)
            start = start.replace(hour=0, minute=0, second=0, microsecond=0)
            end = datetime.now().replace(hour=23, minute=59, second=59, microsecond=999999)
            period_name = "Últimos 7 días"
        elif period == 'month':
            start = datetime.now().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            end = datetime.now().replace(hour=23, minute=59, second=59, microsecond=999999)
            period_name = f"Mes {start.strftime('%B %Y')}"
        elif period == 'year':
            start = datetime.now().replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
            end = datetime.now().replace(hour=23, minute=59, second=59, microsecond=999999)
            period_name = f"Año {start.year}"
        elif period == 'custom' and start_date and end_date:
            start = datetime.strptime(start_date, '%Y-%m-%d')
            end = datetime.strptime(end_date, '%Y-%m-%d').replace(hour=23, minute=59, second=59)
            period_name = f"{start.strftime('%d/%m/%Y')} - {end.strftime('%d/%m/%Y')}"
        else:
            return jsonify({'error': 'Período inválido'}), 400
        
        # Consulta base para ventas completadas en el período
        sales_query = db.session.query(
            models.User.id,
            models.User.name,
            models.User.username,
            models.User.role,
            func.count(models.Sale.id).label('num_sales'),
            func.sum(models.Sale.total).label('total_amount'),
            func.avg(models.Sale.total).label('avg_ticket'),
            func.sum(
                db.session.query(func.sum(models.SaleItem.quantity))
                .filter(models.SaleItem.sale_id == models.Sale.id)
                .correlate(models.Sale)
                .scalar_subquery()
            ).label('total_products')
        ).join(
            models.Sale, models.User.id == models.Sale.user_id
        ).filter(
            models.Sale.status == 'completed',
            models.Sale.created_at >= start,
            models.Sale.created_at <= end
        ).group_by(
            models.User.id,
            models.User.name,
            models.User.username,
            models.User.role
        )
        
        # Aplicar filtro de rol si se especifica
        if role_filter != 'all':
            try:
                role_filter_upper = role_filter.upper()
                sales_query = sales_query.filter(models.User.role == role_filter_upper)
            except ValueError:
                pass
        
        # Para cajeros, solo sus propias ventas
        if user.role.value == 'CAJERO':
            sales_query = sales_query.filter(models.User.id == user.id)
        
        user_stats = sales_query.all()
        
        # Calcular totales generales
        total_sales = sum(u.num_sales for u in user_stats)
        total_amount = sum(u.total_amount for u in user_stats if u.total_amount)
        total_users = len(user_stats)
        
        # Preparar datos de usuarios
        users_data = []
        for idx, user_stat in enumerate(user_stats):
            # Obtener caja asignada (si es cajero)
            cash_register = None
            if user_stat.role.value == 'CAJERO':
                register = models.CashRegister.query.filter_by(
                    user_id=user_stat.id, 
                    active=True
                ).first()
                if register:
                    cash_register = register.name
            
            # Calcular porcentajes
            sales_percentage = (user_stat.num_sales / total_sales * 100) if total_sales > 0 else 0
            amount_percentage = (user_stat.total_amount / total_amount * 100) if total_amount > 0 else 0
            
            users_data.append({
                'rank': idx + 1,
                'user_id': user_stat.id,
                'name': user_stat.name,
                'username': user_stat.username,
                'role': user_stat.role.value,
                'num_sales': int(user_stat.num_sales),
                'total_amount': float(user_stat.total_amount) if user_stat.total_amount else 0,
                'avg_ticket': float(user_stat.avg_ticket) if user_stat.avg_ticket else 0,
                'total_products': int(user_stat.total_products) if user_stat.total_products else 0,
                'cash_register': cash_register,
                'sales_percentage': float(sales_percentage),
                'amount_percentage': float(amount_percentage)
            })
        
        # Ordenar por cantidad de ventas
        users_by_sales = sorted(users_data, key=lambda x: x['num_sales'], reverse=True)
        
        # Actualizar ranking
        for idx, user_data in enumerate(users_by_sales):
            user_data['rank'] = idx + 1
        
        # Ordenar por monto vendido
        users_by_amount = sorted(users_data, key=lambda x: x['total_amount'], reverse=True)
        
        # Encontrar mejores usuarios
        top_by_sales = users_by_sales[0] if users_by_sales else None
        top_by_amount = users_by_amount[0] if users_by_amount else None
        
        # Estadísticas por rol
        role_stats = {}
        for user_data in users_data:
            role = user_data['role']
            if role not in role_stats:
                role_stats[role] = {
                    'num_users': 0,
                    'num_sales': 0,
                    'total_amount': 0
                }
            role_stats[role]['num_users'] += 1
            role_stats[role]['num_sales'] += user_data['num_sales']
            role_stats[role]['total_amount'] += user_data['total_amount']
        
        # Convertir role_stats a lista
        role_stats_list = []
        for role, stats in role_stats.items():
            role_stats_list.append({
                'role': role,
                'num_users': stats['num_users'],
                'num_sales': stats['num_sales'],
                'total_amount': stats['total_amount'],
                'avg_per_user': stats['total_amount'] / stats['num_users'] if stats['num_users'] > 0 else 0
            })
        
        response_data = {
            'period': period_name,
            'start_date': start.strftime('%Y-%m-%d'),
            'end_date': end.strftime('%Y-%m-%d'),
            'users_by_sales': users_by_sales,
            'users_by_amount': users_by_amount,
            'summary': {
                'total_users': total_users,
                'total_sales': total_sales,
                'total_amount': float(total_amount) if total_amount else 0,
                'avg_per_user': float(total_amount / total_users) if total_users > 0 and total_amount else 0,
                'avg_sales_per_user': float(total_sales / total_users) if total_users > 0 else 0,
                'top_by_sales': {
                    'name': top_by_sales['name'],
                    'num_sales': top_by_sales['num_sales']
                } if top_by_sales else None,
                'top_by_amount': {
                    'name': top_by_amount['name'],
                    'total_amount': top_by_amount['total_amount']
                } if top_by_amount else None
            },
            'role_stats': role_stats_list
        }
        
        return jsonify(response_data)
    
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': f'Error al generar reporte: {str(e)}'}), 500


@bp.route('/api/users-sales-report/pdf')
def download_users_sales_report_pdf():
    """Generar y descargar PDF de reporte de ventas por usuario"""
    user = require_admin_or_manager_or_cashier()
    if not isinstance(user, models.User):
        flash('No autorizado', 'error')
        return redirect(url_for('auth.login'))
    
    # Obtener parámetros
    period = request.args.get('period', 'day')
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    role_filter = request.args.get('role', 'all')
    
    try:
        from datetime import datetime, timedelta
        from receipt_generator import generate_users_sales_report_pdf
        from flask import send_file
        
        # Determinar rango de fechas según el período
        if period == 'day':
            start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
            end = datetime.now().replace(hour=23, minute=59, second=59, microsecond=999999)
            period_name = f"Día {start.strftime('%d/%m/%Y')}"
        elif period == 'week':
            start = datetime.now() - timedelta(days=7)
            start = start.replace(hour=0, minute=0, second=0, microsecond=0)
            end = datetime.now().replace(hour=23, minute=59, second=59, microsecond=999999)
            period_name = "Últimos 7 días"
        elif period == 'month':
            start = datetime.now().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            end = datetime.now().replace(hour=23, minute=59, second=59, microsecond=999999)
            period_name = f"Mes {start.strftime('%B %Y')}"
        elif period == 'year':
            start = datetime.now().replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
            end = datetime.now().replace(hour=23, minute=59, second=59, microsecond=999999)
            period_name = f"Año {start.year}"
        elif period == 'custom' and start_date and end_date:
            start = datetime.strptime(start_date, '%Y-%m-%d')
            end = datetime.strptime(end_date, '%Y-%m-%d').replace(hour=23, minute=59, second=59)
            period_name = f"{start.strftime('%d/%m/%Y')} - {end.strftime('%d/%m/%Y')}"
        else:
            flash('Período inválido', 'error')
            return redirect(url_for('admin.reports'))
        
        # Consulta base para ventas completadas en el período
        sales_query = db.session.query(
            models.User.id,
            models.User.name,
            models.User.username,
            models.User.role,
            func.count(models.Sale.id).label('num_sales'),
            func.sum(models.Sale.total).label('total_amount'),
            func.avg(models.Sale.total).label('avg_ticket'),
            func.sum(
                db.session.query(func.sum(models.SaleItem.quantity))
                .filter(models.SaleItem.sale_id == models.Sale.id)
                .correlate(models.Sale)
                .scalar_subquery()
            ).label('total_products')
        ).join(
            models.Sale, models.User.id == models.Sale.user_id
        ).filter(
            models.Sale.status == 'completed',
            models.Sale.created_at >= start,
            models.Sale.created_at <= end
        ).group_by(
            models.User.id,
            models.User.name,
            models.User.username,
            models.User.role
        )
        
        # Aplicar filtro de rol si se especifica
        if role_filter != 'all':
            try:
                role_filter_upper = role_filter.upper()
                sales_query = sales_query.filter(models.User.role == role_filter_upper)
            except ValueError:
                pass
        
        # Para cajeros, solo sus propias ventas
        if user.role.value == 'CAJERO':
            sales_query = sales_query.filter(models.User.id == user.id)
        
        user_stats = sales_query.all()
        
        # Preparar datos de usuarios
        users_data = []
        for user_stat in user_stats:
            # Obtener caja asignada (si es cajero)
            cash_register = None
            if user_stat.role.value == 'CAJERO':
                register = models.CashRegister.query.filter_by(
                    user_id=user_stat.id, 
                    active=True
                ).first()
                if register:
                    cash_register = register.name
            
            users_data.append({
                'user_id': user_stat.id,
                'name': user_stat.name,
                'username': user_stat.username,
                'role': user_stat.role.value,
                'num_sales': int(user_stat.num_sales),
                'total_amount': float(user_stat.total_amount) if user_stat.total_amount else 0,
                'avg_ticket': float(user_stat.avg_ticket) if user_stat.avg_ticket else 0,
                'total_products': int(user_stat.total_products) if user_stat.total_products else 0,
                'cash_register': cash_register
            })
        
        # Generar PDF
        pdf_path = generate_users_sales_report_pdf(users_data, period_name, start, end, role_filter)
        
        return send_file(
            pdf_path,
            as_attachment=True,
            download_name=f"reporte_ventas_usuarios_{period}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf",
            mimetype='application/pdf'
        )
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        flash(f'Error al generar PDF: {str(e)}', 'error')
        return redirect(url_for('admin.reports'))


@bp.route('/api/bluetooth/status', methods=['GET'])
def get_bluetooth_status():
    """Verificar disponibilidad de Bluetooth en el sistema"""
    user = require_admin()
    if not isinstance(user, models.User):
        return jsonify({'error': 'No autorizado'}), 401
    
    try:
        from thermal_printer import check_bluetooth_available
        status = check_bluetooth_available()
        return jsonify(status)
    except Exception as e:
        return jsonify({
            'available': False,
            'powered': False,
            'message': f'Error verificando Bluetooth: {str(e)}'
        }), 500


@bp.route('/api/bluetooth/scan', methods=['POST'])
def scan_bluetooth_devices_endpoint():
    """Escanear dispositivos Bluetooth cercanos"""
    user = require_admin()
    if not isinstance(user, models.User):
        return jsonify({'error': 'No autorizado'}), 401
    
    try:
        data = request.get_json() or {}
        scan_duration = data.get('scan_duration', 8)
        
        from thermal_printer import scan_bluetooth_devices
        devices = scan_bluetooth_devices(scan_duration=scan_duration)
        
        return jsonify({
            'success': True,
            'devices': devices,
            'count': len(devices),
            'message': f'Encontrados {len(devices)} dispositivos'
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'Error escaneando dispositivos: {str(e)}'
        }), 500


@bp.route('/api/bluetooth/connect', methods=['POST'])
def connect_bluetooth_printer():
    """Conectar una impresora Bluetooth"""
    user = require_admin()
    if not isinstance(user, models.User):
        return jsonify({'error': 'No autorizado'}), 401
    
    try:
        data = request.get_json()
        if not data or 'mac_address' not in data:
            return jsonify({'error': 'Dirección MAC requerida'}), 400
        
        mac_address = data['mac_address']
        rfcomm_port = data.get('rfcomm_port', '/dev/rfcomm0')
        
        from thermal_printer import bind_bluetooth_printer
        result = bind_bluetooth_printer(mac_address, rfcomm_port)
        
        if result['success']:
            update_company_setting('printer_bluetooth_mac', mac_address)
            update_company_setting('printer_bluetooth_port', rfcomm_port)
            update_company_setting('printer_type', 'bluetooth')
            
            import os
            os.environ['PRINTER_TYPE'] = 'bluetooth'
            os.environ['PRINTER_BLUETOOTH_MAC'] = mac_address
            os.environ['PRINTER_BLUETOOTH_PORT'] = rfcomm_port
            
            from thermal_printer import reset_thermal_printer
            reset_thermal_printer()
            
            return jsonify(result)
        else:
            update_company_setting('printer_type', 'file')
            update_company_setting('printer_bluetooth_mac', '')
            
            import os
            os.environ['PRINTER_TYPE'] = 'file'
            os.environ['PRINTER_BLUETOOTH_MAC'] = ''
            
            from thermal_printer import reset_thermal_printer
            reset_thermal_printer()
            
            return jsonify(result), 400
            
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error conectando impresora: {str(e)}'
        }), 500


@bp.route('/api/bluetooth/disconnect', methods=['POST'])
def disconnect_bluetooth_printer():
    """Desconectar impresora Bluetooth"""
    user = require_admin()
    if not isinstance(user, models.User):
        return jsonify({'error': 'No autorizado'}), 401
    
    try:
        import subprocess
        
        try:
            rfcomm_check = subprocess.run(
                ['which', 'rfcomm'],
                capture_output=True,
                text=True,
                timeout=2
            )
            
            if rfcomm_check.returncode != 0:
                update_company_setting('printer_type', 'file')
                update_company_setting('printer_bluetooth_mac', '')
                import os
                os.environ['PRINTER_TYPE'] = 'file'
                os.environ['PRINTER_BLUETOOTH_MAC'] = ''
                
                from thermal_printer import reset_thermal_printer
                reset_thermal_printer()
                
                return jsonify({
                    'success': True,
                    'message': 'Configuración actualizada (rfcomm no disponible en este sistema)'
                })
        except (FileNotFoundError, subprocess.SubprocessError):
            update_company_setting('printer_type', 'file')
            update_company_setting('printer_bluetooth_mac', '')
            import os
            os.environ['PRINTER_TYPE'] = 'file'
            os.environ['PRINTER_BLUETOOTH_MAC'] = ''
            
            from thermal_printer import reset_thermal_printer
            reset_thermal_printer()
            
            return jsonify({
                'success': True,
                'message': 'Configuración actualizada (Bluetooth no soportado en este entorno)'
            })
        
        result = subprocess.run(
            ['rfcomm', 'release', '/dev/rfcomm0'],
            capture_output=True,
            text=True,
            timeout=5
        )
        
        update_company_setting('printer_type', 'file')
        update_company_setting('printer_bluetooth_mac', '')
        
        import os
        os.environ['PRINTER_TYPE'] = 'file'
        os.environ['PRINTER_BLUETOOTH_MAC'] = ''
        
        from thermal_printer import reset_thermal_printer
        reset_thermal_printer()
        
        if result.returncode == 0:
            return jsonify({
                'success': True,
                'message': 'Impresora Bluetooth desconectada correctamente'
            })
        else:
            return jsonify({
                'success': True,
                'message': 'Configuración actualizada (puerto ya estaba liberado)'
            })
    except subprocess.TimeoutExpired:
        return jsonify({
            'success': False,
            'message': 'Timeout al desconectar la impresora'
        }), 200
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error desconectando impresora: {str(e)}'
        }), 200
