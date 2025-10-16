from flask import Blueprint, render_template, jsonify, session, redirect, url_for
import models
from models import db
from sqlalchemy import func
from datetime import datetime

bp = Blueprint('fiscal_audit', __name__, url_prefix='/fiscal-audit')


def require_admin():
    """Require admin access for fiscal audit reports"""
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))
    
    user = models.User.query.get(session['user_id'])
    if not user or user.role.value != 'ADMINISTRADOR':
        return redirect(url_for('admin.dashboard'))
    
    return user


@bp.route('/')
def dashboard():
    """Dashboard de auditoría fiscal interna"""
    user = require_admin()
    if not isinstance(user, models.User):
        return user
    
    # Estadísticas generales
    total_products = models.Product.query.filter_by(active=True).count()
    total_tax_types = models.TaxType.query.filter_by(active=True).count()
    
    # Productos sin tax_types
    products_without_taxes = db.session.query(models.Product).outerjoin(
        models.ProductTax
    ).filter(
        models.Product.active == True,
        models.ProductTax.id == None
    ).count()
    
    # Productos con múltiples tax_types de categoría TAX
    products_with_multiple_itbis = []
    all_products = models.Product.query.filter_by(active=True).all()
    
    for product in all_products:
        fiscal_taxes = [
            pt.tax_type for pt in product.product_taxes 
            if pt.tax_type.tax_category == models.TaxCategory.TAX and pt.tax_type.rate > 0
        ]
        if len(fiscal_taxes) > 1:
            products_with_multiple_itbis.append({
                'id': product.id,
                'name': product.name,
                'tax_types': [{'name': tt.name, 'rate': tt.rate} for tt in fiscal_taxes]
            })
    
    # Productos con mezcla de inclusivos y exclusivos
    products_with_mixed_taxes = []
    for product in all_products:
        fiscal_taxes = [
            pt.tax_type for pt in product.product_taxes 
            if pt.tax_type.tax_category == models.TaxCategory.TAX
        ]
        inclusive = [tt for tt in fiscal_taxes if tt.is_inclusive]
        exclusive = [tt for tt in fiscal_taxes if not tt.is_inclusive]
        
        if inclusive and exclusive:
            products_with_mixed_taxes.append({
                'id': product.id,
                'name': product.name,
                'inclusive': [tt.name for tt in inclusive],
                'exclusive': [tt.name for tt in exclusive]
            })
    
    # Tax types activos vs inactivos
    active_tax_types = models.TaxType.query.filter_by(active=True).all()
    inactive_tax_types = models.TaxType.query.filter_by(active=False).all()
    
    # Distribución de productos por tipo de ITBIS (todos los tipos, no solo el primero)
    itbis_distribution = {}
    for product in all_products:
        product_itbis = []
        for pt in product.product_taxes:
            if pt.tax_type.tax_category == models.TaxCategory.TAX:
                product_itbis.append(pt.tax_type.name)
        
        if product_itbis:
            # Usar todos los ITBIS como clave (ordenados para consistencia)
            key = ', '.join(sorted(product_itbis))
            itbis_distribution[key] = itbis_distribution.get(key, 0) + 1
        else:
            # Productos sin ITBIS
            itbis_distribution['Sin configuración fiscal'] = itbis_distribution.get('Sin configuración fiscal', 0) + 1
    
    # Calcular puntuación de cumplimiento fiscal (0-100)
    compliance_score = 100
    
    # Penalizaciones
    if products_without_taxes > 0:
        compliance_score -= min(50, products_without_taxes * 10)  # -10 por producto sin tax_type
    
    if len(products_with_multiple_itbis) > 0:
        compliance_score -= min(30, len(products_with_multiple_itbis) * 5)  # -5 por producto con múltiples ITBIS
    
    if len(products_with_mixed_taxes) > 0:
        compliance_score -= min(20, len(products_with_mixed_taxes) * 5)  # -5 por producto con mezcla
    
    compliance_score = max(0, compliance_score)
    
    # Nivel de cumplimiento
    if compliance_score >= 95:
        compliance_level = 'Excelente'
        compliance_class = 'success'
    elif compliance_score >= 80:
        compliance_level = 'Bueno'
        compliance_class = 'info'
    elif compliance_score >= 60:
        compliance_level = 'Aceptable'
        compliance_class = 'warning'
    else:
        compliance_level = 'Crítico'
        compliance_class = 'danger'
    
    return render_template('fiscal_audit/dashboard.html',
                         total_products=total_products,
                         total_tax_types=total_tax_types,
                         products_without_taxes=products_without_taxes,
                         products_with_multiple_itbis=products_with_multiple_itbis,
                         products_with_mixed_taxes=products_with_mixed_taxes,
                         active_tax_types=active_tax_types,
                         inactive_tax_types=inactive_tax_types,
                         itbis_distribution=itbis_distribution,
                         compliance_score=compliance_score,
                         compliance_level=compliance_level,
                         compliance_class=compliance_class)


@bp.route('/api/summary')
def api_summary():
    """API endpoint para obtener resumen de auditoría fiscal"""
    user = require_admin()
    if not isinstance(user, models.User):
        return jsonify({'error': 'No autorizado'}), 401
    
    # Obtener todos los productos activos
    all_products = models.Product.query.filter_by(active=True).all()
    
    # Análisis de productos
    products_analysis = {
        'total': len(all_products),
        'without_taxes': 0,
        'with_multiple_itbis': [],
        'with_mixed_inclusive_exclusive': [],
        'by_itbis_type': {}
    }
    
    for product in all_products:
        # Verificar productos sin tax_types
        if not product.product_taxes:
            products_analysis['without_taxes'] += 1
            continue
        
        # Analizar tax_types del producto
        fiscal_taxes = [
            pt.tax_type for pt in product.product_taxes 
            if pt.tax_type.tax_category == models.TaxCategory.TAX
        ]
        
        # Verificar múltiples ITBIS
        itbis_taxes = [tt for tt in fiscal_taxes if tt.rate > 0]
        if len(itbis_taxes) > 1:
            products_analysis['with_multiple_itbis'].append({
                'id': product.id,
                'name': product.name,
                'itbis_types': [tt.name for tt in itbis_taxes]
            })
        
        # Verificar mezcla de inclusivos/exclusivos
        inclusive = [tt for tt in fiscal_taxes if tt.is_inclusive]
        exclusive = [tt for tt in fiscal_taxes if not tt.is_inclusive]
        if inclusive and exclusive:
            products_analysis['with_mixed_inclusive_exclusive'].append({
                'id': product.id,
                'name': product.name,
                'inclusive': [tt.name for tt in inclusive],
                'exclusive': [tt.name for tt in exclusive]
            })
        
        # Distribución por tipo de ITBIS (todos los tipos, no solo el primero)
        if fiscal_taxes:
            # Crear clave con todos los tipos de ITBIS (ordenados)
            itbis_names = sorted([tt.name for tt in fiscal_taxes])
            itbis_key = ', '.join(itbis_names) if itbis_names else 'Sin ITBIS'
            products_analysis['by_itbis_type'][itbis_key] = products_analysis['by_itbis_type'].get(itbis_key, 0) + 1
        else:
            products_analysis['by_itbis_type']['Sin configuración fiscal'] = products_analysis['by_itbis_type'].get('Sin configuración fiscal', 0) + 1
    
    # Análisis de tax_types
    tax_types_analysis = {
        'total': models.TaxType.query.count(),
        'active': models.TaxType.query.filter_by(active=True).count(),
        'inactive': models.TaxType.query.filter_by(active=False).count(),
        'by_category': {}
    }
    
    # Distribución por categoría
    for category in models.TaxCategory:
        count = models.TaxType.query.filter_by(
            tax_category=category,
            active=True
        ).count()
        tax_types_analysis['by_category'][category.value] = count
    
    # Calcular puntuación de cumplimiento
    compliance_score = 100
    issues = []
    
    if products_analysis['without_taxes'] > 0:
        penalty = min(50, products_analysis['without_taxes'] * 10)
        compliance_score -= penalty
        issues.append({
            'severity': 'critical',
            'message': f"{products_analysis['without_taxes']} producto(s) sin tipos de impuestos asignados",
            'penalty': penalty
        })
    
    if len(products_analysis['with_multiple_itbis']) > 0:
        penalty = min(30, len(products_analysis['with_multiple_itbis']) * 5)
        compliance_score -= penalty
        issues.append({
            'severity': 'high',
            'message': f"{len(products_analysis['with_multiple_itbis'])} producto(s) con múltiples tipos de ITBIS",
            'penalty': penalty
        })
    
    if len(products_analysis['with_mixed_inclusive_exclusive']) > 0:
        penalty = min(20, len(products_analysis['with_mixed_inclusive_exclusive']) * 5)
        compliance_score -= penalty
        issues.append({
            'severity': 'medium',
            'message': f"{len(products_analysis['with_mixed_inclusive_exclusive'])} producto(s) con mezcla de impuestos inclusivos y exclusivos",
            'penalty': penalty
        })
    
    compliance_score = max(0, compliance_score)
    
    return jsonify({
        'compliance_score': compliance_score,
        'issues': issues,
        'products_analysis': products_analysis,
        'tax_types_analysis': tax_types_analysis,
        'generated_at': datetime.utcnow().isoformat()
    })


@bp.route('/api/products-without-taxes')
def api_products_without_taxes():
    """API endpoint para obtener productos sin tax_types"""
    user = require_admin()
    if not isinstance(user, models.User):
        return jsonify({'error': 'No autorizado'}), 401
    
    # Query para productos sin tax_types
    products = db.session.query(models.Product).outerjoin(
        models.ProductTax
    ).filter(
        models.Product.active == True,
        models.ProductTax.id == None
    ).all()
    
    result = [{
        'id': p.id,
        'name': p.name,
        'price': p.price,
        'category': p.category.name if p.category else 'Sin categoría'
    } for p in products]
    
    return jsonify({
        'count': len(result),
        'products': result
    })
