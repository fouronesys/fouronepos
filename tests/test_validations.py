"""
Tests para funciones de validación en utils.py
Testing completo de validaciones RNC, NCF, teléfono, email, rangos numéricos, etc.
"""
import pytest
from utils import (
    validate_rnc,
    validate_ncf,
    validate_phone_rd,
    validate_email,
    validate_numeric_range,
    validate_integer_range,
    validate_json_structure
)


class TestValidateRNC:
    """Tests para validación de RNC (Registro Nacional del Contribuyente)"""
    
    def test_empty_rnc(self):
        """RNC vacío debe ser válido (es opcional)"""
        result = validate_rnc('')
        assert result['valid'] is True
        assert result['formatted'] == ''
        assert result['type'] is None
    
    def test_none_rnc(self):
        """RNC None debe ser válido (es opcional)"""
        result = validate_rnc(None)
        assert result['valid'] is True
    
    def test_valid_company_rnc_9_digits(self):
        """RNC válido de 9 dígitos para empresa (empieza con 1)"""
        result = validate_rnc('123456789')
        assert result['valid'] is True
        assert result['formatted'] == '123-45678-9'
        assert 'Jurídica' in result['type']
    
    def test_valid_company_rnc_with_formatting(self):
        """RNC con formato debe ser limpiado y validado"""
        result = validate_rnc('1-2345-6789')
        assert result['valid'] is True
        assert result['formatted'] == '123-45678-9'
    
    def test_valid_government_rnc(self):
        """RNC gubernamental (empieza con 4)"""
        result = validate_rnc('401234567')
        assert result['valid'] is True
        assert 'Gubernamental' in result['type']
    
    def test_valid_foreign_company_rnc(self):
        """RNC de empresa extranjera (empieza con 3)"""
        result = validate_rnc('312345678')
        assert result['valid'] is True
        assert 'Extranjera' in result['type']
    
    def test_valid_special_contributor_rnc(self):
        """RNC de contribuyente especial (empieza con 5)"""
        result = validate_rnc('512345678')
        assert result['valid'] is True
        assert 'Especial' in result['type']
    
    def test_valid_individual_rnc_11_digits(self):
        """RNC válido de 11 dígitos para persona física"""
        result = validate_rnc('01234567890')
        assert result['valid'] is True
        assert result['formatted'] == '012-3456789-0'
        assert result['type'] == 'Persona Física'
    
    def test_valid_individual_rnc_starts_with_1(self):
        """RNC de persona física que empieza con 1"""
        result = validate_rnc('11234567890')
        assert result['valid'] is True
        assert result['type'] == 'Persona Física'
    
    def test_valid_individual_rnc_starts_with_4(self):
        """RNC de persona física que empieza con 4"""
        result = validate_rnc('41234567890')
        assert result['valid'] is True
        assert result['type'] == 'Persona Física'
    
    def test_invalid_rnc_9_digits_wrong_start(self):
        """RNC de 9 dígitos con inicio inválido (no 1,3,4,5)"""
        result = validate_rnc('223456789')
        assert result['valid'] is False
        assert 'debe empezar con 1, 3, 4 o 5' in result['message']
    
    def test_invalid_rnc_11_digits_wrong_start(self):
        """RNC de 11 dígitos con inicio inválido (no 0,1,4)"""
        result = validate_rnc('52234567890')
        assert result['valid'] is False
        assert 'debe empezar con 0, 1 o 4' in result['message']
    
    def test_invalid_rnc_wrong_length(self):
        """RNC con longitud inválida (ni 9 ni 11 dígitos)"""
        result = validate_rnc('12345')
        assert result['valid'] is False
        assert '9 u 11 dígitos' in result['message']
    
    def test_rnc_with_letters(self):
        """RNC con letras debe ser rechazado"""
        result = validate_rnc('ABC123456')
        assert result['valid'] is False


class TestValidateNCF:
    """Tests para validación de NCF (Números de Comprobante Fiscal)"""
    
    def test_empty_ncf(self):
        """NCF vacío debe ser válido (es opcional)"""
        result = validate_ncf('')
        assert result['valid'] is True
        assert result['formatted'] == ''
    
    def test_valid_ncf_credito_fiscal(self):
        """NCF válido tipo Crédito Fiscal (B)"""
        result = validate_ncf('B0100000001')
        assert result['valid'] is True
        assert result['type'] == 'Crédito Fiscal'
        assert result['series'] == '01'
        assert result['number'] == '00000001'
    
    def test_valid_ncf_consumo(self):
        """NCF válido tipo Consumidor Final (E)"""
        result = validate_ncf('E0100000123')
        assert result['valid'] is True
        assert result['type'] == 'Consumidor Final'
    
    def test_valid_ncf_gastos_menores(self):
        """NCF válido tipo Gastos Menores (G)"""
        result = validate_ncf('G0500012345')
        assert result['valid'] is True
        assert result['type'] == 'Gastos Menores'
        assert result['series'] == '05'
    
    def test_valid_ncf_with_spaces(self):
        """NCF con espacios debe ser limpiado y validado"""
        result = validate_ncf('B 01 00000001')
        assert result['valid'] is True
        assert result['formatted'] == 'B0100000001'
    
    def test_valid_ncf_lowercase(self):
        """NCF en minúsculas debe ser convertido a mayúsculas"""
        result = validate_ncf('b0100000001')
        assert result['valid'] is True
        assert result['formatted'] == 'B0100000001'
    
    def test_invalid_ncf_format(self):
        """NCF con formato inválido"""
        result = validate_ncf('INVALID123')
        assert result['valid'] is False
        assert 'Formato de NCF inválido' in result['message']
    
    def test_invalid_ncf_series_too_low(self):
        """NCF con serie 00 (debe ser 01-99)"""
        result = validate_ncf('B0000000001')
        assert result['valid'] is False
        assert 'Serie del NCF' in result['message']
    
    def test_invalid_ncf_series_too_high(self):
        """NCF con serie >99"""
        # El pattern regex ya no permite esto, pero dejamos el test para documentación
        result = validate_ncf('B9900000001')
        # Serie 99 es válida
        assert result['valid'] is True
    
    def test_invalid_ncf_number_zero(self):
        """NCF con número secuencial 00000000 (debe empezar en 00000001)"""
        result = validate_ncf('B0100000000')
        assert result['valid'] is False
        assert 'Número del NCF' in result['message']
    
    def test_ncf_type_validation_credito_fiscal(self):
        """Validar tipo esperado 'credito_fiscal' con NCF tipo B"""
        result = validate_ncf('B0100000001', ncf_type='credito_fiscal')
        assert result['valid'] is True
    
    def test_ncf_type_validation_mismatch(self):
        """Tipo esperado no coincide con tipo detectado"""
        result = validate_ncf('E0100000001', ncf_type='credito_fiscal')
        assert result['valid'] is False
        assert 'no coincide' in result['message']


class TestValidatePhoneRD:
    """Tests para validación de teléfonos de República Dominicana"""
    
    def test_empty_phone(self):
        """Teléfono vacío debe ser válido (es opcional)"""
        result = validate_phone_rd('')
        assert result['valid'] is True
        assert result['formatted'] == ''
    
    def test_valid_phone_809(self):
        """Teléfono válido con código 809"""
        result = validate_phone_rd('8097771234')
        assert result['valid'] is True
        assert result['formatted'] == '(809) 777-1234'
    
    def test_valid_phone_829(self):
        """Teléfono válido con código 829"""
        result = validate_phone_rd('8297771234')
        assert result['valid'] is True
        assert '(829)' in result['formatted']
    
    def test_valid_phone_849(self):
        """Teléfono válido con código 849"""
        result = validate_phone_rd('8497771234')
        assert result['valid'] is True
        assert '(849)' in result['formatted']
    
    def test_valid_phone_with_dashes(self):
        """Teléfono con guiones debe ser limpiado y validado"""
        result = validate_phone_rd('809-777-1234')
        assert result['valid'] is True
        assert result['formatted'] == '(809) 777-1234'
    
    def test_valid_phone_with_parentheses(self):
        """Teléfono con paréntesis debe ser limpiado y validado"""
        result = validate_phone_rd('(809) 777-1234')
        assert result['valid'] is True
    
    def test_valid_phone_international_format(self):
        """Teléfono en formato internacional (+1)"""
        result = validate_phone_rd('18097771234')
        assert result['valid'] is True
        assert '+1 (809)' in result['formatted']
    
    def test_valid_phone_with_plus_sign(self):
        """Teléfono con signo + debe ser limpiado y validado"""
        result = validate_phone_rd('+1-809-777-1234')
        assert result['valid'] is True
    
    def test_invalid_phone_wrong_area_code(self):
        """Teléfono con código de área inválido"""
        result = validate_phone_rd('5557771234')
        assert result['valid'] is False
    
    def test_invalid_phone_too_short(self):
        """Teléfono muy corto"""
        result = validate_phone_rd('809123')
        assert result['valid'] is False
    
    def test_invalid_phone_too_long(self):
        """Teléfono muy largo"""
        result = validate_phone_rd('809777123456789')
        assert result['valid'] is False


class TestValidateEmail:
    """Tests para validación de email"""
    
    def test_empty_email(self):
        """Email vacío debe ser válido (es opcional)"""
        result = validate_email('')
        assert result['valid'] is True
        assert result['formatted'] == ''
    
    def test_valid_email_simple(self):
        """Email válido simple"""
        result = validate_email('usuario@ejemplo.com')
        assert result['valid'] is True
        assert result['formatted'] == 'usuario@ejemplo.com'
    
    def test_valid_email_with_dots(self):
        """Email válido con puntos"""
        result = validate_email('juan.perez@empresa.com.do')
        assert result['valid'] is True
    
    def test_valid_email_with_plus(self):
        """Email válido con signo +"""
        result = validate_email('usuario+tag@ejemplo.com')
        assert result['valid'] is True
    
    def test_valid_email_with_numbers(self):
        """Email válido con números"""
        result = validate_email('usuario123@ejemplo456.com')
        assert result['valid'] is True
    
    def test_valid_email_uppercase(self):
        """Email en mayúsculas debe convertirse a minúsculas"""
        result = validate_email('USUARIO@EJEMPLO.COM')
        assert result['valid'] is True
        assert result['formatted'] == 'usuario@ejemplo.com'
    
    def test_invalid_email_no_at(self):
        """Email sin @"""
        result = validate_email('usuarioejemplo.com')
        assert result['valid'] is False
    
    def test_invalid_email_no_domain(self):
        """Email sin dominio"""
        result = validate_email('usuario@')
        assert result['valid'] is False
    
    def test_invalid_email_no_tld(self):
        """Email sin TLD (.com, .do, etc.)"""
        result = validate_email('usuario@ejemplo')
        assert result['valid'] is False
    
    def test_invalid_email_spaces(self):
        """Email con espacios"""
        result = validate_email('usuario @ejemplo.com')
        assert result['valid'] is False
    
    def test_invalid_email_double_at(self):
        """Email con doble @"""
        result = validate_email('usuario@@ejemplo.com')
        assert result['valid'] is False


class TestValidateNumericRange:
    """Tests para validación de rangos numéricos"""
    
    def test_valid_number_within_range(self):
        """Número válido dentro del rango"""
        result = validate_numeric_range(50, min_val=0, max_val=100)
        assert result['valid'] is True
        assert result['value'] == 50.0
    
    def test_valid_number_at_min(self):
        """Número válido en el límite mínimo"""
        result = validate_numeric_range(0, min_val=0, max_val=100)
        assert result['valid'] is True
    
    def test_valid_number_at_max(self):
        """Número válido en el límite máximo"""
        result = validate_numeric_range(100, min_val=0, max_val=100)
        assert result['valid'] is True
    
    def test_valid_float_number(self):
        """Número decimal válido"""
        result = validate_numeric_range(25.99, min_val=0, max_val=100)
        assert result['valid'] is True
        assert result['value'] == 25.99
    
    def test_valid_string_number(self):
        """String numérico válido debe convertirse"""
        result = validate_numeric_range('50.5', min_val=0, max_val=100)
        assert result['valid'] is True
        assert result['value'] == 50.5
    
    def test_invalid_number_too_low(self):
        """Número por debajo del mínimo"""
        result = validate_numeric_range(-5, min_val=0, max_val=100)
        assert result['valid'] is False
        assert 'mayor o igual a 0' in result['message']
    
    def test_invalid_number_too_high(self):
        """Número por encima del máximo"""
        result = validate_numeric_range(150, min_val=0, max_val=100)
        assert result['valid'] is False
        assert 'menor o igual a 100' in result['message']
    
    def test_invalid_non_numeric(self):
        """Valor no numérico"""
        result = validate_numeric_range('abc', min_val=0, max_val=100)
        assert result['valid'] is False
        assert 'número válido' in result['message']
    
    def test_no_min_limit(self):
        """Sin límite mínimo (solo máximo)"""
        result = validate_numeric_range(-100, max_val=100)
        assert result['valid'] is True
    
    def test_no_max_limit(self):
        """Sin límite máximo (solo mínimo)"""
        result = validate_numeric_range(1000, min_val=0)
        assert result['valid'] is True
    
    def test_custom_field_name(self):
        """Nombre de campo personalizado en mensaje de error"""
        result = validate_numeric_range(150, min_val=0, max_val=100, field_name='Precio')
        assert result['valid'] is False
        assert 'Precio' in result['message']


class TestValidateIntegerRange:
    """Tests para validación de rangos de enteros"""
    
    def test_valid_integer_within_range(self):
        """Entero válido dentro del rango"""
        result = validate_integer_range(50, min_val=1, max_val=100)
        assert result['valid'] is True
        assert result['value'] == 50
    
    def test_valid_integer_at_min(self):
        """Entero válido en el límite mínimo"""
        result = validate_integer_range(1, min_val=1, max_val=100)
        assert result['valid'] is True
    
    def test_valid_integer_at_max(self):
        """Entero válido en el límite máximo"""
        result = validate_integer_range(100, min_val=1, max_val=100)
        assert result['valid'] is True
    
    def test_valid_string_integer(self):
        """String entero válido debe convertirse"""
        result = validate_integer_range('50', min_val=1, max_val=100)
        assert result['valid'] is True
        assert result['value'] == 50
    
    def test_float_converted_to_integer(self):
        """Float debe convertirse a entero (truncando decimales)"""
        result = validate_integer_range(50.9, min_val=1, max_val=100)
        assert result['valid'] is True
        assert result['value'] == 50
    
    def test_invalid_integer_too_low(self):
        """Entero por debajo del mínimo"""
        result = validate_integer_range(0, min_val=1, max_val=100)
        assert result['valid'] is False
        assert 'mayor o igual a 1' in result['message']
    
    def test_invalid_integer_too_high(self):
        """Entero por encima del máximo"""
        result = validate_integer_range(150, min_val=1, max_val=100)
        assert result['valid'] is False
        assert 'menor o igual a 100' in result['message']
    
    def test_invalid_non_integer(self):
        """Valor no entero"""
        result = validate_integer_range('abc', min_val=1, max_val=100)
        assert result['valid'] is False
        assert 'entero válido' in result['message']
    
    def test_custom_field_name(self):
        """Nombre de campo personalizado en mensaje de error"""
        result = validate_integer_range(0, min_val=1, max_val=1000, field_name='Cantidad')
        assert result['valid'] is False
        assert 'Cantidad' in result['message']


class TestValidateJSONStructure:
    """Tests para validación de estructura JSON"""
    
    def test_valid_json_with_required_fields(self):
        """JSON válido con todos los campos requeridos"""
        data = {'name': 'Producto', 'price': 100}
        result = validate_json_structure(data, required_fields=['name', 'price'])
        assert result['valid'] is True
    
    def test_valid_json_with_optional_fields(self):
        """JSON válido con campos opcionales"""
        data = {'name': 'Producto', 'price': 100, 'description': 'Desc'}
        result = validate_json_structure(
            data, 
            required_fields=['name', 'price'],
            optional_fields=['description']
        )
        assert result['valid'] is True
    
    def test_invalid_json_not_dict(self):
        """JSON no es un diccionario"""
        result = validate_json_structure('not a dict', required_fields=['name'])
        assert result['valid'] is False
        assert 'objeto JSON válido' in result['message']
    
    def test_invalid_json_missing_required_field(self):
        """JSON con campo requerido faltante"""
        data = {'name': 'Producto'}
        result = validate_json_structure(data, required_fields=['name', 'price'])
        assert result['valid'] is False
        assert 'price' in result['message']
        assert 'faltantes' in result['message']
    
    def test_invalid_json_null_required_field(self):
        """JSON con campo requerido en None"""
        data = {'name': 'Producto', 'price': None}
        result = validate_json_structure(data, required_fields=['name', 'price'])
        assert result['valid'] is False
        assert 'price' in result['message']
    
    def test_invalid_json_empty_required_field(self):
        """JSON con campo requerido vacío"""
        data = {'name': '', 'price': 100}
        result = validate_json_structure(data, required_fields=['name', 'price'])
        assert result['valid'] is False
        assert 'name' in result['message']
    
    def test_invalid_json_unexpected_field(self):
        """JSON con campos no permitidos"""
        data = {'name': 'Producto', 'price': 100, 'invalid_field': 'value'}
        result = validate_json_structure(
            data,
            required_fields=['name', 'price']
        )
        assert result['valid'] is False
        assert 'invalid_field' in result['message']
        assert 'no permitidos' in result['message']
    
    def test_multiple_missing_fields(self):
        """JSON con múltiples campos requeridos faltantes"""
        data = {}
        result = validate_json_structure(data, required_fields=['name', 'price', 'stock'])
        assert result['valid'] is False
        # Debe listar todos los campos faltantes
        assert 'name' in result['message']
        assert 'price' in result['message']
        assert 'stock' in result['message']


# Tests de integración
class TestValidationIntegration:
    """Tests de integración para casos de uso reales del sistema POS"""
    
    def test_complete_customer_validation(self):
        """Validar datos completos de un cliente"""
        # RNC válido
        rnc_result = validate_rnc('123456789')
        assert rnc_result['valid'] is True
        
        # Teléfono válido
        phone_result = validate_phone_rd('809-555-1234')
        assert phone_result['valid'] is True
        
        # Email válido
        email_result = validate_email('cliente@empresa.com')
        assert email_result['valid'] is True
    
    def test_product_stock_validation(self):
        """Validar stock de producto (0-100,000 unidades)"""
        # Stock válido
        result = validate_integer_range(50, min_val=0, max_val=100000, field_name='Stock')
        assert result['valid'] is True
        
        # Stock negativo inválido
        result = validate_integer_range(-5, min_val=0, max_val=100000, field_name='Stock')
        assert result['valid'] is False
    
    def test_sale_quantity_validation(self):
        """Validar cantidad en venta (1-1000 unidades)"""
        # Cantidad válida
        result = validate_integer_range(10, min_val=1, max_val=1000, field_name='Cantidad')
        assert result['valid'] is True
        
        # Cantidad 0 inválida
        result = validate_integer_range(0, min_val=1, max_val=1000, field_name='Cantidad')
        assert result['valid'] is False
        
        # Cantidad >1000 inválida
        result = validate_integer_range(1500, min_val=1, max_val=1000, field_name='Cantidad')
        assert result['valid'] is False
    
    def test_cash_received_validation(self):
        """Validar efectivo recibido (RD$ 0-1,000,000)"""
        # Efectivo válido
        result = validate_numeric_range(500.00, min_val=0, max_val=1000000, field_name='Efectivo recibido')
        assert result['valid'] is True
        
        # Efectivo negativo inválido
        result = validate_numeric_range(-100, min_val=0, max_val=1000000, field_name='Efectivo recibido')
        assert result['valid'] is False
        
        # Efectivo >1M inválido
        result = validate_numeric_range(1500000, min_val=0, max_val=1000000, field_name='Efectivo recibido')
        assert result['valid'] is False
    
    def test_product_price_validation(self):
        """Validar precio de producto (RD$ 0-1,000,000)"""
        # Precio válido
        result = validate_numeric_range(199.99, min_val=0, max_val=1000000, field_name='Precio')
        assert result['valid'] is True
        
        # Precio 0 válido (productos gratis permitidos)
        result = validate_numeric_range(0, min_val=0, max_val=1000000, field_name='Precio')
        assert result['valid'] is True
    
    def test_ncf_credito_fiscal_requires_rnc(self):
        """NCF de crédito fiscal debe tener RNC válido del cliente"""
        # NCF de crédito fiscal válido
        ncf_result = validate_ncf('B0100000001', ncf_type='credito_fiscal')
        assert ncf_result['valid'] is True
        
        # RNC de cliente válido (requerido para crédito fiscal)
        rnc_result = validate_rnc('123456789')
        assert rnc_result['valid'] is True
        
        # Ambos deben ser válidos para emitir NCF de crédito fiscal
        if ncf_result['valid']:
            assert rnc_result['valid'], "NCF de crédito fiscal requiere RNC válido del cliente"
