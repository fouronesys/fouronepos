"""
Utility functions for Dominican Republic POS system
Includes RNC validation and NCF compliance for DGII 606
"""
import re
from typing import Optional, Dict, Any


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
        'receipt_copies'
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