from flask import Blueprint, render_template, request, redirect, url_for, session, flash, jsonify
import models
from models import db

bp = Blueprint('waiter', __name__, url_prefix='/waiter')


def require_waiter():
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))
    
    user = models.User.query.get(session['user_id'])
    if not user or user.role.value != 'MESERO':
        flash('Acceso denegado', 'error')
        return redirect(url_for('auth.login'))
    
    return user


@bp.route('/tables')
def tables():
    user = require_waiter()
    if not isinstance(user, models.User):
        return user
    
    # Get tables with their current sales information
    tables = models.Table.query.all()
    
    # Enrich tables with sale information
    enriched_tables = []
    for table in tables:
        # Get current tab or pending sale for this table
        current_sale = models.Sale.query.filter_by(
            table_id=table.id
        ).filter(
            models.Sale.status.in_(['pending', 'tab_open'])
        ).first()
        
        is_tab = current_sale and current_sale.status == 'tab_open'
        
        table_data = {
            'table': table,
            'current_sale': current_sale,
            'has_order': current_sale is not None,
            'is_tab': is_tab,
            'order_total': current_sale.total if current_sale and not is_tab else sum(item.total_price for item in current_sale.sale_items) if current_sale else 0,
            'order_items_count': len(current_sale.sale_items) if current_sale else 0
        }
        enriched_tables.append(table_data)
    
    return render_template('waiter/tables.html', tables=enriched_tables)


@bp.route('/table/<int:table_id>')
def table_detail(table_id):
    user = require_waiter()
    if not isinstance(user, models.User):
        return user
    
    table = models.Table.query.get_or_404(table_id)
    
    # Get current active tab or pending sale for this table
    current_sale = models.Sale.query.filter_by(
        table_id=table_id
    ).filter(
        models.Sale.status.in_(['pending', 'tab_open'])
    ).first()
    
    # Get products by category
    categories = models.Category.query.filter_by(active=True).all()
    
    is_tab = current_sale and current_sale.status == 'tab_open'
    
    return render_template('waiter/table_detail.html', 
                         table=table, 
                         current_sale=current_sale,
                         is_tab=is_tab,
                         categories=categories)


@bp.route('/menu')
def menu():
    user = require_waiter()
    if not isinstance(user, models.User):
        return user
    
    categories = models.Category.query.filter_by(active=True).all()
    return render_template('waiter/menu.html', categories=categories)