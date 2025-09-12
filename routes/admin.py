from flask import Blueprint, render_template, request, redirect, url_for, session, flash, jsonify
import models
from main import db
from datetime import datetime, date
from sqlalchemy import func, and_

bp = Blueprint('admin', __name__, url_prefix='/admin')


def require_admin_or_cashier():
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))
    
    user = models.User.query.get(session['user_id'])
    if not user or user.role.value not in ['administrador', 'cajero']:
        flash('Acceso denegado', 'error')
        return redirect(url_for('auth.login'))
    
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