"""
API de prueba para funcionalidades de impresión térmica
SOLO PARA ADMINISTRADORES - Con protección CSRF
"""
from flask import Blueprint, jsonify, request, session
from datetime import datetime
import models

# Lazy imports to prevent startup failures if thermal printer dependencies are missing
def safe_thermal_import():
    """Safely import thermal printer modules with error handling"""
    try:
        from thermal_printer import test_thermal_printer, get_thermal_printer_status, print_receipt_auto
        from receipt_generator import generate_thermal_receipt_text
        return test_thermal_printer, get_thermal_printer_status, print_receipt_auto, generate_thermal_receipt_text
    except ImportError as e:
        return None, None, None, None

bp = Blueprint('test_api', __name__, url_prefix='/api/test')

def require_admin():
    """Require admin login for test endpoints"""
    if 'user_id' not in session:
        return jsonify({'error': 'Acceso no autorizado - se requiere login'}), 401
    
    user = models.User.query.get(session['user_id'])
    if not user or user.role.value != 'ADMINISTRADOR':
        return jsonify({'error': 'Acceso denegado - se requieren permisos de administrador'}), 403
    
    return user

def validate_csrf_token():
    """Validate CSRF token for API requests"""
    try:
        from flask_wtf.csrf import validate_csrf
        csrf_token = request.headers.get('X-CSRFToken') or request.json.get('csrf_token') if request.json else None
        if not csrf_token:
            return jsonify({'error': 'Token CSRF requerido'}), 400
        validate_csrf(csrf_token)
        return None
    except Exception as e:
        return jsonify({'error': 'Token CSRF inválido'}), 400

@bp.route('/thermal-printer/status', methods=['GET'])
def get_printer_status():
    """Obtiene el estado de la impresora térmica"""
    try:
        status = get_thermal_printer_status()
        return jsonify({
            'success': True,
            'status': status
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@bp.route('/thermal-printer/test', methods=['POST'])
def test_printer():
    """Prueba de impresión térmica"""
    try:
        success = test_thermal_printer()
        return jsonify({
            'success': success,
            'message': 'Prueba de impresión completada' if success else 'Error en prueba de impresión'
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@bp.route('/receipt/sample', methods=['POST'])
def test_receipt_generation():
    """Genera e imprime un recibo de prueba"""
    try:
        # Sample sale data for testing
        sample_sale_data = {
            'id': 999,
            'created_at': datetime.now().isoformat(),
            'ncf': 'B0199999999',
            'total': 250.00,
            'subtotal': 223.21,
            'tax_amount': 26.79,
            'payment_method': 'efectivo',
            'customer_name': 'Cliente de Prueba',
            'customer_rnc': '12345678901',
            'cash_received': 300.00,
            'change_amount': 50.00,
            'items': [
                {
                    'product_name': 'Producto de Prueba 1',
                    'quantity': 2,
                    'price': 50.00,
                    'tax_rate': 0.18,
                    'is_tax_included': True
                },
                {
                    'product_name': 'Producto de Prueba 2', 
                    'quantity': 1,
                    'price': 123.21,
                    'tax_rate': 0.18,
                    'is_tax_included': True
                }
            ]
        }
        
        # Generate receipt text
        receipt_text = generate_thermal_receipt_text(sample_sale_data)
        
        # Attempt thermal printing
        print_success = print_receipt_auto(sample_sale_data)
        
        return jsonify({
            'success': True,
            'receipt_generated': True,
            'thermal_print_success': print_success,
            'receipt_text': receipt_text,
            'message': 'Recibo de prueba generado' + (' e impreso' if print_success else ' pero no se pudo imprimir')
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500