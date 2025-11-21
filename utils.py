"""
Utility functions for Dominican Republic POS system
Includes RNC validation and NCF compliance for DGII 606
"""
import re
import uuid
import logging
from typing import Optional, Dict, Any
from datetime import datetime
from flask import jsonify, session

# Configure logging
logger = logging.getLogger(__name__)


def generate_error_id() -> str:
    """
    Genera un ID único para rastreo de errores
    
    Returns:
        str: ID único en formato UUID corto (primeros 8 caracteres)
    """
    return str(uuid.uuid4())[:8].upper()


def get_user_context() -> Dict[str, Any]:
    """
    Obtiene contexto del usuario actual para logging
    
    Returns:
        Dict con información del usuario (user_id, username, role)
    """
    try:
        from models import User
        user_id = session.get('user_id')
        if user_id:
            user = User.query.get(user_id)
            if user:
                return {
                    'user_id': user.id,
                    'username': user.username,
                    'role': user.role.value if hasattr(user.role, 'value') else str(user.role)
                }
    except Exception:
        pass
    
    return {'user_id': None, 'username': 'anonymous', 'role': 'unknown'}


def log_error(error_type: str, message: str, error_id: str = None, 
              context: Dict[str, Any] = None, exc_info: bool = False):
    """
    Logging centralizado de errores con contexto completo
    
    Args:
        error_type: Tipo de error ('validation', 'permission', 'not_found', 'server', 'business')
        message: Mensaje descriptivo del error
        error_id: ID único del error (se genera automáticamente si no se proporciona)
        context: Contexto adicional (sale_id, product_id, etc.)
        exc_info: Si se debe incluir información de excepción
    """
    if error_id is None:
        error_id = generate_error_id()
    
    user_ctx = get_user_context()
    
    log_data = {
        'error_id': error_id,
        'error_type': error_type,
        'msg_detail': message,
        'user_id': user_ctx.get('user_id'),
        'username': user_ctx.get('username'),
        'role': user_ctx.get('role'),
    }
    
    if context:
        log_data.update(context)
    
    # Determinar nivel de log según tipo de error
    if error_type in ['validation', 'business']:
        logger.warning(f"[{error_id}] {message}", extra=log_data, exc_info=exc_info)
    elif error_type in ['permission', 'not_found']:
        logger.warning(f"[{error_id}] {message}", extra=log_data, exc_info=exc_info)
    else:  # server errors
        logger.error(f"[{error_id}] {message}", extra=log_data, exc_info=exc_info)


def log_success(operation: str, message: str, context: Dict[str, Any] = None):
    """
    Logging de operaciones críticas exitosas
    
    Args:
        operation: Nombre de la operación (ej: 'sale_finalized', 'product_created')
        message: Mensaje descriptivo del éxito
        context: Contexto adicional (sale_id, product_id, amount, etc.)
    """
    user_ctx = get_user_context()
    
    log_data = {
        'operation': operation,
        'msg_detail': message,
        'user_id': user_ctx.get('user_id'),
        'username': user_ctx.get('username'),
        'role': user_ctx.get('role'),
        'timestamp': datetime.utcnow().isoformat()
    }
    
    if context:
        log_data.update(context)
    
    logger.info(f"[SUCCESS] {operation}: {message}", extra=log_data)


def error_response(error_type: str, message: str, details: Optional[str] = None, 
                   field: Optional[str] = None, status_code: int = 400, 
                   log_context: Dict[str, Any] = None, **kwargs):
    """
    Genera una respuesta de error estandarizada para endpoints de API con logging automático
    
    Args:
        error_type: Tipo de error ('validation', 'permission', 'not_found', 'server', 'business')
        message: Mensaje principal del error (breve y claro)
        details: Detalles adicionales del error (opcional)
        field: Campo que causó el error (opcional)
        status_code: Código HTTP de respuesta (default: 400)
        log_context: Contexto adicional para logging (sale_id, product_id, etc.)
        **kwargs: Datos adicionales a incluir en la respuesta
    
    Returns:
        tuple: (jsonify response, status_code)
    
    Examples:
        >>> return error_response(
        ...     error_type='validation',
        ...     message='Stock insuficiente',
        ...     details=f'No hay suficiente stock de {product.name}',
        ...     field='quantity',
        ...     stock_available=product.stock,
        ...     quantity_requested=quantity,
        ...     log_context={'sale_id': sale.id, 'product_id': product.id}
        ... )
        
        >>> return error_response(
        ...     error_type='permission',
        ...     message='Acceso denegado',
        ...     details='Solo cajeros y administradores pueden finalizar ventas',
        ...     status_code=403,
        ...     log_context={'sale_id': sale_id}
        ... )
    """
    # Generar ID único para el error
    error_id = generate_error_id()
    
    # Log automático del error con contexto
    log_error(
        error_type=error_type,
        message=message,
        error_id=error_id,
        context=log_context or {}
    )
    
    response_data = {
        'error': message,
        'type': error_type,
        'error_id': error_id,
        'timestamp': datetime.utcnow().isoformat()
    }
    
    if details:
        response_data['details'] = details
    
    if field:
        response_data['field'] = field
    
    # Añadir datos adicionales (excluyendo log_context que es solo para logging interno)
    response_data.update(kwargs)
    
    return jsonify(response_data), status_code


def validate_rnc(rnc: str) -> Dict[str, Any]:
    """
    Validate Dominican Republic RNC (Registro Nacional del Contribuyente)
    
    Args:
        rnc: The RNC string to validate
        
    Returns:
        Dict with validation result and details
    """
    if not rnc:
        return {
            'valid': True,  # RNC is optional
            'formatted': '',
            'type': None,
            'message': 'RNC not provided'
        }
    
    # Remove spaces, dashes, and other non-digit characters
    clean_rnc = re.sub(r'[^\d]', '', rnc)
    
    # Dominican Republic RNC validation rules:
    # - Individual: 11 digits (starts with 0, 1, or 4)
    # - Company: 9 digits (starts with 1, 3, or 5)
    # - Government: 9 digits (starts with 4)
    
    if len(clean_rnc) == 9:
        if not re.match(r'^[1345]\d{8}$', clean_rnc):
            return {
                'valid': False,
                'formatted': clean_rnc,
                'type': None,
                'message': 'RNC de 9 dígitos debe empezar con 1, 3, 4 o 5'
            }
        
        # Determine type based on first digit
        first_digit = clean_rnc[0]
        if first_digit == '1':
            rnc_type = 'Persona Jurídica Nacional'
        elif first_digit == '3':
            rnc_type = 'Persona Jurídica Extranjera'
        elif first_digit == '4':
            rnc_type = 'Entidad Gubernamental'
        elif first_digit == '5':
            rnc_type = 'Contribuyente Especial'
        else:
            rnc_type = 'Empresa'
            
        return {
            'valid': True,
            'formatted': f"{clean_rnc[:3]}-{clean_rnc[3:8]}-{clean_rnc[8]}",
            'type': rnc_type,
            'message': f'RNC válido - {rnc_type}'
        }
    
    elif len(clean_rnc) == 11:
        if not re.match(r'^[014]\d{10}$', clean_rnc):
            return {
                'valid': False,
                'formatted': clean_rnc,
                'type': None,
                'message': 'RNC de 11 dígitos debe empezar con 0, 1 o 4'
            }
        
        # All 11-digit RNCs are for individuals (Persona Física)
        return {
            'valid': True,
            'formatted': f"{clean_rnc[:3]}-{clean_rnc[3:10]}-{clean_rnc[10]}",
            'type': 'Persona Física',
            'message': 'RNC válido - Persona Física'
        }
    
    else:
        return {
            'valid': False,
            'formatted': clean_rnc,
            'type': None,
            'message': f'RNC debe tener 9 u 11 dígitos, recibido {len(clean_rnc)}'
        }


def validate_ncf(ncf: str, ncf_type: Optional[str] = None) -> Dict[str, Any]:
    """
    Validate Dominican Republic NCF (Números de Comprobante Fiscal)
    According to DGII 606 regulations
    
    Args:
        ncf: The NCF string to validate
        ncf_type: Expected NCF type ('consumo', 'credito_fiscal', 'gubernamental')
        
    Returns:
        Dict with validation result and details
    """
    if not ncf:
        return {
            'valid': True,  # NCF is optional for purchases
            'formatted': '',
            'type': None,
            'series': None,
            'number': None,
            'message': 'NCF not provided'
        }
    
    # Remove spaces and convert to uppercase
    clean_ncf = re.sub(r'\s+', '', ncf.upper())
    
    # NCF format: AXXNNNNNNNN
    # A = Type identifier (B, E, P, etc.)
    # XX = Series (01-99)
    # NNNNNNNN = Sequential number (8 digits)
    
    ncf_pattern = r'^([BEPAFGKLC])(\d{2})(\d{8})$'
    match = re.match(ncf_pattern, clean_ncf)
    
    if not match:
        return {
            'valid': False,
            'formatted': clean_ncf,
            'type': None,
            'series': None,
            'number': None,
            'message': 'Formato de NCF inválido. Debe ser: AXXNNNNNNNN (ej: B0100000001)'
        }
    
    type_code, series, number = match.groups()
    series_num = int(series)
    number_num = int(number)
    
    # Validate series (01-99)
    if series_num < 1 or series_num > 99:
        return {
            'valid': False,
            'formatted': clean_ncf,
            'type': None,
            'series': series,
            'number': number,
            'message': 'Serie del NCF debe estar entre 01 y 99'
        }
    
    # Validate number range (00000001-99999999)
    if number_num < 1 or number_num > 99999999:
        return {
            'valid': False,
            'formatted': clean_ncf,
            'type': None,
            'series': series,
            'number': number,
            'message': 'Número del NCF debe estar entre 00000001 y 99999999'
        }
    
    # Determine NCF type based on type code
    ncf_types = {
        'B': 'Crédito Fiscal',
        'E': 'Consumidor Final',
        'P': 'Pagos al Exterior',
        'A': 'Nota de Crédito',
        'F': 'Facturas de Consumo',
        'G': 'Gastos Menores',
        'K': 'Único de Ingresos',
        'L': 'Liquidación',
        'C': 'Nota de Débito'
    }
    
    detected_type = ncf_types.get(type_code, 'Tipo Desconocido')
    
    # Validate expected type if provided
    if ncf_type:
        expected_codes = {
            'credito_fiscal': ['B'],
            'consumo': ['E', 'F'],
            'gubernamental': ['G', 'K', 'L'],
            'nota_credito': ['A'],
            'nota_debito': ['C'],
            'exterior': ['P']
        }
        
        expected = expected_codes.get(ncf_type.lower(), [])
        if expected and type_code not in expected:
            return {
                'valid': False,
                'formatted': clean_ncf,
                'type': detected_type,
                'series': series,
                'number': number,
                'message': f'Tipo de NCF no coincide. Esperado: {ncf_type}, Detectado: {detected_type}'
            }
    
    return {
        'valid': True,
        'formatted': clean_ncf,
        'type': detected_type,
        'series': series,
        'number': number,
        'message': f'NCF válido - {detected_type}'
    }


def format_currency_rd(amount: float) -> str:
    """
    Format currency for Dominican Republic (RD$)
    
    Args:
        amount: The amount to format
        
    Returns:
        Formatted currency string
    """
    return f"RD$ {amount:,.2f}"


def calculate_itbis(subtotal: float, rate: float = 0.18) -> float:
    """
    Calculate ITBIS (Dominican Republic tax)
    
    Args:
        subtotal: The subtotal amount
        rate: Tax rate (default 18% estándar, también soporta 16% reducido y 0% exento)
        
    Returns:
        Tax amount
    """
    return round(subtotal * rate, 2)


def validate_phone_rd(phone: str) -> Dict[str, Any]:
    """
    Validate Dominican Republic phone number
    
    Args:
        phone: The phone number to validate
        
    Returns:
        Dict with validation result and formatted number
    """
    if not phone:
        return {
            'valid': True,
            'formatted': '',
            'message': 'Teléfono no proporcionado'
        }
    
    # Remove all non-digit characters
    clean_phone = re.sub(r'[^\d]', '', phone)
    
    # Dominican Republic phone patterns:
    # Mobile: 809/829/849 + 7 digits
    # Landline: 809/829/849 + 7 digits
    # International format: +1 + area code + number
    
    if len(clean_phone) == 10:
        # Local format: 8097771234
        area_code = clean_phone[:3]
        number = clean_phone[3:]
        
        if area_code in ['809', '829', '849']:
            return {
                'valid': True,
                'formatted': f"({area_code}) {number[:3]}-{number[3:]}",
                'message': 'Teléfono válido'
            }
    
    elif len(clean_phone) == 11 and clean_phone.startswith('1'):
        # International format: 18097771234
        area_code = clean_phone[1:4]
        number = clean_phone[4:]
        
        if area_code in ['809', '829', '849']:
            return {
                'valid': True,
                'formatted': f"+1 ({area_code}) {number[:3]}-{number[3:]}",
                'message': 'Teléfono válido (formato internacional)'
            }
    
    return {
        'valid': False,
        'formatted': phone,
        'message': 'Formato de teléfono inválido. Use: 809-777-1234 o +1-809-777-1234'
    }


def sanitize_input(value: str, max_length: int = 255) -> str:
    """
    Sanitize input string for database storage
    
    Args:
        value: The input string
        max_length: Maximum allowed length
        
    Returns:
        Sanitized string
    """
    if not value:
        return ''
    
    # Remove potentially dangerous characters
    sanitized = re.sub(r'[<>"\']', '', str(value))
    
    # Trim whitespace and limit length
    sanitized = sanitized.strip()[:max_length]
    
    return sanitized


def validate_email(email: str) -> Dict[str, Any]:
    """
    Validate email address
    
    Args:
        email: The email address to validate
        
    Returns:
        Dict with validation result
    """
    if not email:
        return {
            'valid': True,
            'formatted': '',
            'message': 'Email no proporcionado'
        }
    
    # Basic email pattern
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    
    if re.match(pattern, email.lower()):
        return {
            'valid': True,
            'formatted': email.lower(),
            'message': 'Email válido'
        }
    else:
        return {
            'valid': False,
            'formatted': email,
            'message': 'Formato de email inválido'
        }


def validate_numeric_range(value: Any, min_val: float = None, max_val: float = None, field_name: str = "Campo") -> Dict[str, Any]:
    """
    Validate numeric values within a range
    
    Args:
        value: The value to validate
        min_val: Minimum allowed value
        max_val: Maximum allowed value
        field_name: Name of the field for error messages
        
    Returns:
        Dict with validation result
    """
    try:
        num_value = float(value)
        
        if min_val is not None and num_value < min_val:
            return {
                'valid': False,
                'value': num_value,
                'message': f'{field_name} debe ser mayor o igual a {min_val}'
            }
        
        if max_val is not None and num_value > max_val:
            return {
                'valid': False,
                'value': num_value,
                'message': f'{field_name} debe ser menor o igual a {max_val}'
            }
        
        return {
            'valid': True,
            'value': num_value,
            'message': f'{field_name} válido'
        }
        
    except (ValueError, TypeError):
        return {
            'valid': False,
            'value': value,
            'message': f'{field_name} debe ser un número válido'
        }


def validate_integer_range(value: Any, min_val: int = None, max_val: int = None, field_name: str = "Campo") -> Dict[str, Any]:
    """
    Validate integer values within a range
    
    Args:
        value: The value to validate
        min_val: Minimum allowed value
        max_val: Maximum allowed value
        field_name: Name of the field for error messages
        
    Returns:
        Dict with validation result
    """
    try:
        int_value = int(value)
        
        if min_val is not None and int_value < min_val:
            return {
                'valid': False,
                'value': int_value,
                'message': f'{field_name} debe ser mayor o igual a {min_val}'
            }
        
        if max_val is not None and int_value > max_val:
            return {
                'valid': False,
                'value': int_value,
                'message': f'{field_name} debe ser menor o igual a {max_val}'
            }
        
        return {
            'valid': True,
            'value': int_value,
            'message': f'{field_name} válido'
        }
        
    except (ValueError, TypeError):
        return {
            'valid': False,
            'value': value,
            'message': f'{field_name} debe ser un número entero válido'
        }


def sanitize_html_output(text: str) -> str:
    """
    Sanitize text for HTML output to prevent XSS
    
    Args:
        text: The text to sanitize
        
    Returns:
        Sanitized text
    """
    if not text:
        return ''
    
    # Replace HTML special characters
    text = str(text)
    text = text.replace('&', '&amp;')
    text = text.replace('<', '&lt;')
    text = text.replace('>', '&gt;')
    text = text.replace('"', '&quot;')
    text = text.replace("'", '&#x27;')
    
    return text


def validate_json_structure(data: dict, required_fields: list, optional_fields: list = None) -> Dict[str, Any]:
    """
    Validate JSON structure for API endpoints
    
    Args:
        data: The JSON data to validate
        required_fields: List of required field names
        optional_fields: List of optional field names
        
    Returns:
        Dict with validation result
    """
    if not isinstance(data, dict):
        return {
            'valid': False,
            'message': 'Los datos deben ser un objeto JSON válido'
        }
    
    # Check required fields
    missing_fields = []
    for field in required_fields:
        if field not in data or data[field] is None or data[field] == '':
            missing_fields.append(field)
    
    if missing_fields:
        return {
            'valid': False,
            'message': f'Campos requeridos faltantes: {", ".join(missing_fields)}'
        }
    
    # Check for unexpected fields
    allowed_fields = set(required_fields)
    if optional_fields:
        allowed_fields.update(optional_fields)
    
    unexpected_fields = []
    for field in data.keys():
        if field not in allowed_fields:
            unexpected_fields.append(field)
    
    if unexpected_fields:
        return {
            'valid': False,
            'message': f'Campos no permitidos: {", ".join(unexpected_fields)}'
        }
    
    return {
        'valid': True,
        'message': 'Estructura JSON válida'
    }


def initialize_company_settings():
    """
    Initialize default company settings in SystemConfiguration table
    
    Returns:
        Dict with initialization status
    """
    from models import SystemConfiguration, db
    
    # Default company settings for Dominican Republic business
    default_settings = {
        'company_name': {
            'value': 'Mi Empresa',
            'description': 'Nombre de la empresa que aparece en los recibos'
        },
        'company_rnc': {
            'value': '',
            'description': 'RNC (Registro Nacional de Contribuyente) de la empresa'
        },
        'company_address': {
            'value': '',
            'description': 'Dirección física de la empresa'
        },
        'company_phone': {
            'value': '',
            'description': 'Teléfono de contacto de la empresa'
        },
        'company_email': {
            'value': '',
            'description': 'Email de contacto de la empresa'
        },
        'receipt_message': {
            'value': 'Gracias por su compra',
            'description': 'Mensaje personalizado que aparece en los recibos'
        },
        'receipt_footer': {
            'value': 'www.miempresa.com',
            'description': 'Información adicional en el pie del recibo'
        },
        'fiscal_printer_enabled': {
            'value': 'false',
            'description': 'Habilitar impresión fiscal automática'
        },
        'receipt_copies': {
            'value': '1',
            'description': 'Número de copias del recibo a imprimir'
        },
        'receipt_format': {
            'value': '80mm',
            'description': 'Formato del recibo (80mm o 58mm)'
        },
        'printer_type': {
            'value': 'file',
            'description': 'Tipo de impresora: usb, serial, network, bluetooth, file'
        },
        'printer_network_host': {
            'value': '192.168.1.100',
            'description': 'Dirección IP de la impresora de red'
        },
        'printer_network_port': {
            'value': '9100',
            'description': 'Puerto de la impresora de red'
        },
        'printer_bluetooth_mac': {
            'value': '',
            'description': 'Dirección MAC de la impresora Bluetooth'
        },
        'printer_bluetooth_port': {
            'value': '/dev/rfcomm0',
            'description': 'Puerto RFCOMM para impresora Bluetooth'
        },
        'printer_paper_width': {
            'value': '80',
            'description': 'Ancho del papel de la impresora térmica (58 o 80)'
        },
        'printer_auto_cut': {
            'value': 'true',
            'description': 'Corte automático del papel después de imprimir'
        }
    }
    
    created_count = 0
    updated_count = 0
    
    try:
        for key, config in default_settings.items():
            # Check if setting already exists
            existing_setting = SystemConfiguration.query.filter_by(key=key).first()
            
            if existing_setting:
                # Update description if it has changed
                if existing_setting.description != config['description']:
                    existing_setting.description = config['description']
                    updated_count += 1
            else:
                # Create new setting
                new_setting = SystemConfiguration()
                new_setting.key = key
                new_setting.value = config['value']
                new_setting.description = config['description']
                db.session.add(new_setting)
                created_count += 1
        
        db.session.commit()
        
        return {
            'success': True,
            'created': created_count,
            'updated': updated_count,
            'message': f'Configuraciones inicializadas: {created_count} creadas, {updated_count} actualizadas'
        }
        
    except Exception as e:
        db.session.rollback()
        return {
            'success': False,
            'message': f'Error al inicializar configuraciones: {str(e)}'
        }


def get_company_settings() -> Dict[str, Any]:
    """
    Get all company settings from SystemConfiguration
    
    Returns:
        Dict with company settings
    """
    from models import SystemConfiguration
    
    # Company setting keys
    company_keys = [
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
        'receipt_format',
        'printer_type',
        'printer_network_host',
        'printer_network_port',
        'printer_bluetooth_mac',
        'printer_bluetooth_port',
        'printer_paper_width',
        'printer_auto_cut'
    ]
    
    settings = {}
    
    try:
        for key in company_keys:
            config = SystemConfiguration.query.filter_by(key=key).first()
            settings[key] = config.value if config else ''
        
        return {
            'success': True,
            'settings': settings
        }
        
    except Exception as e:
        return {
            'success': False,
            'message': f'Error al obtener configuraciones: {str(e)}',
            'settings': {}
        }


def update_company_setting(key: str, value: str) -> Dict[str, Any]:
    """
    Update a specific company setting
    
    Args:
        key: Setting key to update
        value: New value for the setting
        
    Returns:
        Dict with update status
    """
    from models import SystemConfiguration, db
    
    # Validate RNC if updating company RNC
    if key == 'company_rnc' and value:
        rnc_validation = validate_rnc(value)
        if not rnc_validation['valid']:
            return {
                'success': False,
                'message': f'RNC inválido: {rnc_validation["message"]}'
            }
        # Use formatted RNC
        value = rnc_validation['formatted']
    
    # Validate phone if updating company phone
    if key == 'company_phone' and value:
        phone_validation = validate_phone_rd(value)
        if not phone_validation['valid']:
            return {
                'success': False,
                'message': f'Teléfono inválido: {phone_validation["message"]}'
            }
        # Use formatted phone
        value = phone_validation['formatted']
    
    try:
        # Find existing setting or create new one
        setting = SystemConfiguration.query.filter_by(key=key).first()
        
        if setting:
            setting.value = value
        else:
            setting = SystemConfiguration()
            setting.key = key
            setting.value = value
            setting.description = f'Configuración: {key}'
            db.session.add(setting)
        
        db.session.commit()
        
        return {
            'success': True,
            'message': f'Configuración {key} actualizada correctamente'
        }
        
    except Exception as e:
        db.session.rollback()
        return {
            'success': False,
            'message': f'Error al actualizar configuración: {str(e)}'
        }


def get_company_info_for_receipt() -> Dict[str, str]:
    """
    Get formatted company information for receipt generation
    
    Returns:
        Dict with formatted company information
    """
    company_data = get_company_settings()
    
    if not company_data['success']:
        # Return default values if there's an error
        return {
            'name': 'Mi Empresa',
            'rnc': '',
            'address': '',
            'phone': '',
            'email': '',
            'message': 'Gracias por su compra',
            'footer': '',
            'logo': ''
        }
    
    settings = company_data['settings']
    
    # Fix logo URL to be absolute
    logo_path = settings.get('receipt_logo', '') or ''
    if logo_path and not logo_path.startswith(('http://', 'https://', '/')):
        # Make relative paths absolute by adding leading slash
        logo_path = '/' + logo_path.lstrip('/')
    
    return {
        'name': settings.get('company_name', 'Mi Empresa') or 'Mi Empresa',
        'rnc': settings.get('company_rnc', '') or '',
        'address': settings.get('company_address', '') or '',
        'phone': settings.get('company_phone', '') or '',
        'email': settings.get('company_email', '') or '',
        'message': settings.get('receipt_message', 'Gracias por su compra') or 'Gracias por su compra',
        'footer': settings.get('receipt_footer', '') or '',
        'logo': logo_path
    }


def sync_printer_settings_to_env():
    """
    Sync printer settings from database to environment variables
    This ensures the thermal printer module picks up the latest configuration
    """
    import os
    
    settings_result = get_company_settings()
    if not settings_result['success']:
        logger.warning("Could not sync printer settings: failed to get company settings")
        return
    
    settings = settings_result['settings']
    
    # Mapping of database keys to environment variable names
    printer_env_mapping = {
        'printer_type': 'PRINTER_TYPE',
        'printer_network_host': 'PRINTER_NETWORK_HOST',
        'printer_network_port': 'PRINTER_NETWORK_PORT',
        'printer_bluetooth_mac': 'PRINTER_BLUETOOTH_MAC',
        'printer_bluetooth_port': 'PRINTER_BLUETOOTH_PORT',
        'printer_usb_vendor_id': 'PRINTER_USB_VENDOR_ID',
        'printer_usb_product_id': 'PRINTER_USB_PRODUCT_ID',
        'printer_serial_port': 'PRINTER_SERIAL_PORT',
        'printer_serial_baudrate': 'PRINTER_SERIAL_BAUDRATE',
        'printer_paper_width': 'PRINTER_PAPER_WIDTH',
        'printer_auto_cut': 'PRINTER_AUTO_CUT',
        'printer_auto_open_drawer': 'PRINTER_AUTO_OPEN_DRAWER'
    }
    
    # Sync each printer setting to environment variable
    for db_key, env_var in printer_env_mapping.items():
        value = settings.get(db_key, '')
        if value:
            os.environ[env_var] = str(value)
            logger.info(f"Synced {db_key} to environment variable {env_var}")
        elif env_var in os.environ:
            # Remove env var if setting is empty
            del os.environ[env_var]
            logger.info(f"Removed environment variable {env_var}")
    
    logger.info("Printer settings synchronized to environment variables")