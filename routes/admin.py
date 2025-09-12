from flask import Blueprint, render_template, request, redirect, url_for, session, flash, jsonify
import models
from models import db
from datetime import datetime, date
from sqlalchemy import func, and_
import bcrypt
import secrets
from flask_wtf.csrf import validate_csrf
from werkzeug.exceptions import BadRequest

bp = Blueprint('admin', __name__, url_prefix='/admin')


def validate_csrf_token():
    """Validate CSRF token for POST requests"""
    try:
        validate_csrf(request.form.get('csrf_token'))
    except BadRequest:
        flash('Token de seguridad inválido. Inténtalo de nuevo.', 'error')
        return False
    return True


def require_admin_or_cashier():
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))
    
    user = models.User.query.get(session['user_id'])
    if not user or user.role.value not in ['administrador', 'cajero']:
        flash('Acceso denegado', 'error')
        return redirect(url_for('auth.login'))
    
    return user


def require_admin():
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))
    
    user = models.User.query.get(session['user_id'])
    if not user or user.role.value != 'administrador':
        flash('Solo los administradores pueden acceder a esta sección', 'error')
        return redirect(url_for('admin.dashboard'))
    
    return user


@bp.route('/dashboard')
def dashboard():
    user = require_admin_or_cashier()
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
        models.Product.active == True
    ).all()
    
    return render_template('admin/dashboard.html', 
                         daily_sales=daily_sales,
                         daily_transactions=daily_transactions,
                         low_stock_products=low_stock_products)


@bp.route('/pos')
def pos():
    user = require_admin_or_cashier()
    if not isinstance(user, models.User):
        return user
    
    # Get cash register for this user
    cash_register = models.CashRegister.query.filter_by(user_id=user.id, active=True).first()
    if not cash_register:
        flash('No tienes una caja asignada. Contacta al administrador.', 'error')
        return redirect(url_for('admin.dashboard'))
    
    # Get products by category
    categories = models.Category.query.filter_by(active=True).all()
    
    return render_template('admin/pos.html', 
                         cash_register=cash_register,
                         categories=categories)


@bp.route('/products')
def products():
    user = require_admin_or_cashier()
    if not isinstance(user, models.User):
        return user
    
    if user.role.value != 'administrador':
        flash('Solo los administradores pueden gestionar productos', 'error')
        return redirect(url_for('admin.dashboard'))
    
    products = models.Product.query.filter_by(active=True).all()
    categories = models.Category.query.filter_by(active=True).all()
    
    return render_template('admin/products.html', products=products, categories=categories)


@bp.route('/categories/create', methods=['POST'])
def create_category():
    user = require_admin()
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
    user = require_admin()
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
    user = require_admin()
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
    user = require_admin()
    if not isinstance(user, models.User):
        return user
    
    tables = models.Table.query.order_by(models.Table.number).all()
    return render_template('admin/tables.html', tables=tables)

@bp.route('/tables/create', methods=['POST'])
def create_table():
    user = require_admin()
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
    user = require_admin()
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
    user = require_admin()
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


# System Configuration Routes
@bp.route('/settings')
def settings():
    user = require_admin()
    if not isinstance(user, models.User):
        return user
    
    # Get current logo configuration
    logo_config = models.SystemConfiguration.query.filter_by(key='receipt_logo').first()
    current_logo = logo_config.value if logo_config else None
    
    return render_template('admin/settings.html', current_logo=current_logo)

@bp.route('/settings/logo', methods=['POST'])
def update_logo():
    user = require_admin()
    if not isinstance(user, models.User):
        return jsonify({'error': 'No autorizado'}), 401
    
    # Validate CSRF token
    if not validate_csrf_token():
        return redirect(url_for('admin.settings'))
    
    try:
        # Check if file was uploaded
        if 'logo_file' not in request.files:
            flash('No se seleccionó ningún archivo', 'error')
            return redirect(url_for('admin.settings'))
        
        file = request.files['logo_file']
        
        if file.filename == '':
            flash('No se seleccionó ningún archivo', 'error')
            return redirect(url_for('admin.settings'))
        
        # Validate file type
        allowed_extensions = {'png', 'jpg', 'jpeg', 'gif'}
        filename = file.filename or ''
        if not ('.' in filename and filename.rsplit('.', 1)[1].lower() in allowed_extensions):
            flash('Solo se permiten archivos PNG, JPG, JPEG y GIF', 'error')
            return redirect(url_for('admin.settings'))
        
        # Validate file size (max 500KB)
        file.seek(0, 2)  # Seek to end of file
        file_size = file.tell()
        file.seek(0)  # Reset to beginning
        if file_size > 500 * 1024:  # 500KB limit
            flash('El archivo es demasiado grande. Máximo 500KB permitido', 'error')
            return redirect(url_for('admin.settings'))
        
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
    
    return redirect(url_for('admin.settings'))

@bp.route('/settings/logo/remove', methods=['POST'])
def remove_logo():
    user = require_admin()
    if not isinstance(user, models.User):
        return jsonify({'error': 'No autorizado'}), 401
    
    # Validate CSRF token
    if not validate_csrf_token():
        return redirect(url_for('admin.settings'))
    
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
    
    return redirect(url_for('admin.settings'))


@bp.route('/reports')
def reports():
    user = require_admin_or_cashier()
    if not isinstance(user, models.User):
        return user
    
    if user.role.value != 'administrador':
        flash('Solo los administradores pueden ver reportes', 'error')
        return redirect(url_for('admin.dashboard'))
    
    return render_template('admin/reports.html')


@bp.route('/ncf-sequences')
def ncf_sequences():
    user = require_admin_or_cashier()
    if not isinstance(user, models.User):
        return user
    
    if user.role.value != 'administrador':
        flash('Solo los administradores pueden gestionar secuencias NCF', 'error')
        return redirect(url_for('admin.dashboard'))
    
    sequences = models.NCFSequence.query.filter_by(active=True).all()
    cash_registers = models.CashRegister.query.filter_by(active=True).all()
    
    return render_template('admin/ncf_sequences.html', sequences=sequences, cash_registers=cash_registers)


# User Management Routes
@bp.route('/users')
def users():
    user = require_admin()
    if not isinstance(user, models.User):
        return user
    
    all_users = models.User.query.order_by(models.User.created_at.desc()).all()
    return render_template('admin/users.html', users=all_users)


@bp.route('/users/create', methods=['POST'])
def create_user():
    user = require_admin()
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
        
        if role not in ['administrador', 'cajero', 'mesero']:
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
        new_user.role = getattr(models.UserRole, role.upper())
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
    user = require_admin()
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
    user = require_admin()
    if not isinstance(user, models.User):
        return user
    
    registers = models.CashRegister.query.order_by(models.CashRegister.created_at.desc()).all()
    active_users = models.User.query.filter_by(active=True).filter(
        models.User.role.in_([models.UserRole.ADMINISTRADOR, models.UserRole.CAJERO])
    ).all()
    
    return render_template('admin/cash_registers.html', registers=registers, users=active_users)


@bp.route('/cash-registers/create', methods=['POST'])
def create_cash_register():
    user = require_admin()
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
    user = require_admin()
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