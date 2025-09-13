from flask import Blueprint, render_template, request, redirect, url_for, session, flash, jsonify
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
    
    low_stock_products = models.Product.query.filter(
        models.Product.stock <= models.Product.min_stock,
        models.Product.active == True,
        models.Product.product_type == 'inventariable'
    ).all()
    
    return render_template('admin/dashboard.html', 
                         daily_sales=daily_sales,
                         daily_transactions=daily_transactions,
                         low_stock_products=low_stock_products)


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
    
    return render_template('admin/pos.html', 
                         cash_register=cash_register,
                         categories=categories,
                         edit_sale_data=edit_sale_data)


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
    
    sequences = models.NCFSequence.query.filter_by(active=True).all()
    cash_registers = models.CashRegister.query.filter_by(active=True).all()
    
    # Get or create shared cash register for NCF sequences
    shared_cash_register = models.CashRegister.query.filter_by(
        name="Secuencias NCF Compartidas",
        active=True
    ).first()
    
    # Create shared cash register if it doesn't exist
    if not shared_cash_register:
        shared_cash_register = models.CashRegister()
        shared_cash_register.name = "Secuencias NCF Compartidas"
        shared_cash_register.user_id = user.id  # Assign to current admin user
        shared_cash_register.active = True
        db.session.add(shared_cash_register)
        db.session.commit()
    
    return render_template('admin/ncf_sequences.html', 
                         sequences=sequences, 
                         cash_registers=cash_registers,
                         shared_cash_register_id=shared_cash_register.id)


@bp.route('/ncf-sequences/create', methods=['POST'])
def create_ncf_sequence():
    user = require_admin_or_manager()
    if not isinstance(user, models.User):
        return jsonify({'error': 'No autorizado'}), 401
    
    # Validate CSRF token for security
    if not validate_csrf_token():
        return jsonify({'error': 'Token de seguridad inválido'}), 400
    
    try:
        # Get form data
        cash_register_id = request.form.get('cash_register_id')
        ncf_type = request.form.get('ncf_type')
        serie = request.form.get('serie', '').strip().upper()
        start_number = request.form.get('start_number')
        end_number = request.form.get('end_number')
        
        # Validate required fields
        if not all([cash_register_id, ncf_type, serie, start_number, end_number]):
            return jsonify({'error': 'Todos los campos son obligatorios'}), 400
        
        # Validate cash register exists
        cash_register = models.CashRegister.query.get(cash_register_id)
        if not cash_register or not cash_register.active:
            return jsonify({'error': 'Caja registradora inválida'}), 400
        
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
        
        # Check for duplicate series in same cash register and NCF type
        existing_sequence = models.NCFSequence.query.filter_by(
            cash_register_id=cash_register_id,
            ncf_type=ncf_type_enum,
            serie=serie,
            active=True
        ).first()
        
        if existing_sequence:
            return jsonify({'error': f'Ya existe una secuencia activa con serie {serie} para este tipo de NCF y caja'}), 400
        
        # Check for overlapping number ranges in same cash register and NCF type
        overlapping = models.NCFSequence.query.filter_by(
            cash_register_id=cash_register_id,
            ncf_type=ncf_type_enum,
            active=True
        ).filter(
            models.NCFSequence.start_number <= end_num,
            models.NCFSequence.end_number >= start_num
        ).first()
        
        if overlapping:
            return jsonify({'error': 'El rango de números se solapa con una secuencia existente'}), 400
        
        # Ensure cash_register_id is valid
        if not cash_register_id:
            return jsonify({'error': 'ID de caja registradora requerido'}), 400
            
        # Create new NCF sequence
        new_sequence = models.NCFSequence()
        new_sequence.cash_register_id = int(cash_register_id)
        new_sequence.ncf_type = ncf_type_enum
        new_sequence.serie = serie
        new_sequence.start_number = start_num
        new_sequence.end_number = end_num
        new_sequence.current_number = start_num  # Start at the beginning
        new_sequence.active = True
        
        db.session.add(new_sequence)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': f'Secuencia NCF {serie} creada exitosamente',
            'sequence_id': new_sequence.id
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': f'Error creando secuencia: {str(e)}'}), 500


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
        
        register.name = request.form['name'].strip()
        register.active = request.form.get('active') == 'true'
        
        db.session.commit()
        flash(f'Caja registradora {register.name} actualizada exitosamente', 'success')
        
    except Exception as e:
        db.session.rollback()
        flash(f'Error al actualizar caja registradora: {str(e)}', 'error')
    
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
    user = require_admin()
    if not isinstance(user, models.User):
        return jsonify({'error': 'No autorizado'}), 401
    
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
        tax_type = models.TaxType(
            name=data['name'],
            description=data.get('description', ''),
            rate=float(data['rate']),
            is_inclusive=data.get('is_inclusive', False),
            is_percentage=data.get('is_percentage', True),
            display_order=data.get('display_order', 0),
            active=True
        )
        
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