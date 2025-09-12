from flask import Blueprint, render_template, request, redirect, url_for, session, flash, jsonify
import models
from main import db

bp = Blueprint('waiter', __name__, url_prefix='/waiter')


def require_waiter():
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))
    
    user = models.User.query.get(session['user_id'])
    if not user or user.role.value != 'mesero':
        flash('Acceso denegado', 'error')
        return redirect(url_for('auth.login'))
    
    return user


@bp.route('/tables')
def tables():
    user = require_waiter()
    if not isinstance(user, models.User):
        return user
    
    tables = models.Table.query.all()
    return render_template('waiter/tables.html', tables=tables)


@bp.route('/table/<int:table_id>')
def table_detail(table_id):
    user = require_waiter()
    if not isinstance(user, models.User):
        return user
    
    table = models.Table.query.get_or_404(table_id)
    
    # Get current active sale for this table
    current_sale = models.Sale.query.filter_by(
        table_id=table_id, 
        status='pending'
    ).first()
    
    # Get products by category
    categories = models.Category.query.filter_by(active=True).all()
    
    return render_template('waiter/table_detail.html', 
                         table=table, 
                         current_sale=current_sale,
                         categories=categories)


@bp.route('/menu')
def menu():
    user = require_waiter()
    if not isinstance(user, models.User):
        return user
    
    categories = models.Category.query.filter_by(active=True).all()
    return render_template('waiter/menu.html', categories=categories)