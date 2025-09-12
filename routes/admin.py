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