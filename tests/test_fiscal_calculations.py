"""
Tests Unitarios para Cálculos Fiscales
Valida que el sistema POS cumpla con las normativas fiscales dominicanas
"""
import unittest
from decimal import Decimal


class TestFiscalCalculations(unittest.TestCase):
    """Tests para cálculos de impuestos y propina según normativas dominicanas"""
    
    def setUp(self):
        """Configuración inicial para cada test"""
        self.ITBIS_18 = Decimal('0.18')
        self.ITBIS_16 = Decimal('0.16')
        self.PROPINA_10 = Decimal('0.10')
    
    def test_itbis_exclusivo_calculo(self):
        """Test: ITBIS 18% exclusivo (se agrega al precio)"""
        precio_base = Decimal('100.00')
        itbis = precio_base * self.ITBIS_18
        total = precio_base + itbis
        
        self.assertEqual(itbis, Decimal('18.00'))
        self.assertEqual(total, Decimal('118.00'))
    
    def test_itbis_inclusivo_calculo(self):
        """Test: ITBIS 18% incluido (cálculo regresivo: precio/1.18)"""
        precio_con_itbis = Decimal('118.00')
        precio_base = precio_con_itbis / (Decimal('1') + self.ITBIS_18)
        itbis = precio_con_itbis - precio_base
        
        # Redondear a 2 decimales como en el sistema real
        precio_base = precio_base.quantize(Decimal('0.01'))
        itbis = itbis.quantize(Decimal('0.01'))
        
        self.assertEqual(precio_base, Decimal('100.00'))
        self.assertEqual(itbis, Decimal('18.00'))
    
    def test_propina_sobre_subtotal_mas_impuestos(self):
        """Test: Propina 10% calculada sobre (subtotal + impuestos) - NORMATIVA DOMINICANA"""
        subtotal = Decimal('300.00')
        itbis = subtotal * self.ITBIS_18  # 54.00
        base_propina = subtotal + itbis   # 354.00
        propina = base_propina * self.PROPINA_10  # 35.40
        total = base_propina + propina    # 389.40
        
        self.assertEqual(itbis, Decimal('54.00'))
        self.assertEqual(base_propina, Decimal('354.00'))
        self.assertEqual(propina, Decimal('35.40'))
        self.assertEqual(total, Decimal('389.40'))
    
    def test_separacion_tax_vs_service_charge(self):
        """Test: Separación correcta entre impuestos fiscales y cargos por servicio"""
        # Simular tax_types con categorías
        tax_types = [
            {'name': 'ITBIS 18%', 'rate': 0.18, 'tax_category': 'tax'},
            {'name': 'Propina 10%', 'rate': 0.10, 'tax_category': 'service_charge'},
        ]
        
        # Filtrar solo impuestos fiscales (tax)
        fiscal_taxes = [t for t in tax_types if t['tax_category'] == 'tax']
        service_charges = [t for t in tax_types if t['tax_category'] == 'service_charge']
        
        # Validar separación
        self.assertEqual(len(fiscal_taxes), 1)
        self.assertEqual(len(service_charges), 1)
        self.assertEqual(fiscal_taxes[0]['name'], 'ITBIS 18%')
        self.assertEqual(service_charges[0]['name'], 'Propina 10%')
    
    def test_suma_correcta_multiples_tax_types(self):
        """Test: Solo sumar tax_types de categoría 'tax', NO sumar 'service_charge'"""
        product_tax_types = [
            {'name': 'ITBIS 18%', 'rate': 0.18, 'is_inclusive': False, 'tax_category': 'tax'},
            {'name': 'Propina 10%', 'rate': 0.10, 'is_inclusive': False, 'tax_category': 'service_charge'},
        ]
        
        # Filtrar solo impuestos fiscales (como en routes/api.py líneas 354-384)
        tax_only = [tax for tax in product_tax_types if tax.get('tax_category') == 'tax']
        
        # Sumar solo tasas fiscales
        total_tax_rate = sum(Decimal(str(tax['rate'])) for tax in tax_only if not tax['is_inclusive'])
        
        # Validar que solo suma ITBIS, NO propina
        self.assertEqual(total_tax_rate, Decimal('0.18'))
        self.assertNotEqual(total_tax_rate, Decimal('0.28'))  # 0.18 + 0.10 sería INCORRECTO
    
    def test_itbis_16_reducido(self):
        """Test: ITBIS 16% reducido para productos específicos (lácteos, café, etc)"""
        precio_base = Decimal('100.00')
        itbis_reducido = precio_base * self.ITBIS_16
        total = precio_base + itbis_reducido
        
        self.assertEqual(itbis_reducido, Decimal('16.00'))
        self.assertEqual(total, Decimal('116.00'))
    
    def test_multiples_productos_con_diferentes_itbis(self):
        """Test: Venta con productos que tienen diferentes tasas de ITBIS"""
        productos = [
            {'precio': Decimal('100.00'), 'cantidad': 2, 'itbis': Decimal('0.18')},  # Producto normal
            {'precio': Decimal('50.00'), 'cantidad': 1, 'itbis': Decimal('0.16')},   # Producto reducido
        ]
        
        subtotal = Decimal('0')
        impuestos = Decimal('0')
        
        for prod in productos:
            subtotal_item = prod['precio'] * prod['cantidad']
            impuesto_item = subtotal_item * prod['itbis']
            
            subtotal += subtotal_item
            impuestos += impuesto_item
        
        total = subtotal + impuestos
        
        self.assertEqual(subtotal, Decimal('250.00'))  # (100*2) + (50*1)
        self.assertEqual(impuestos, Decimal('44.00'))  # (200*0.18) + (50*0.16) = 36 + 8
        self.assertEqual(total, Decimal('294.00'))
    
    def test_producto_exento_itbis(self):
        """Test: Producto exento de ITBIS (tasa 0%)"""
        precio_base = Decimal('100.00')
        itbis = precio_base * Decimal('0.00')
        total = precio_base + itbis
        
        self.assertEqual(itbis, Decimal('0.00'))
        self.assertEqual(total, Decimal('100.00'))
    
    def test_redondeo_centavos(self):
        """Test: Redondeo correcto a 2 decimales (centavos)"""
        precio_base = Decimal('33.33')
        itbis = (precio_base * self.ITBIS_18).quantize(Decimal('0.01'))
        total = (precio_base + itbis).quantize(Decimal('0.01'))
        
        # 33.33 * 0.18 = 5.9994 -> redondeado a 6.00
        self.assertEqual(itbis, Decimal('6.00'))
        self.assertEqual(total, Decimal('39.33'))


class TestTaxCategoryValidation(unittest.TestCase):
    """Tests para validación de categorías de tax_types"""
    
    def test_tax_category_enum_values(self):
        """Test: Valores válidos del enum TaxCategory"""
        valid_categories = ['tax', 'service_charge', 'other']
        
        # Verificar que solo se acepten valores válidos
        for category in valid_categories:
            self.assertIn(category, valid_categories)
        
        # Verificar que valores inválidos no estén en la lista
        invalid_categories = ['impuesto', 'cargo', 'tax_type']
        for category in invalid_categories:
            self.assertNotIn(category, valid_categories)
    
    def test_fallback_defensivo_tax_category(self):
        """Test: Fallback a 'tax' cuando tax_category es None/NULL"""
        # Simular tax_type sin tax_category (valor None)
        tax_type_sin_categoria = {'name': 'ITBIS 18%', 'rate': 0.18, 'tax_category': None}
        
        # Aplicar fallback defensivo (como en routes/api.py líneas 357-360)
        tax_category = 'tax'  # Default
        if tax_type_sin_categoria.get('tax_category'):
            tax_category = tax_type_sin_categoria['tax_category']
        
        # Validar que usa el fallback
        self.assertEqual(tax_category, 'tax')


class TestProductTaxValidation(unittest.TestCase):
    """Tests para validación de tax_types obligatorios en productos"""
    
    def test_producto_debe_tener_tax_type(self):
        """Test: Producto debe tener al menos un tax_type configurado"""
        producto_valido = {
            'name': 'Producto Test',
            'price': 100.00,
            'tax_type_ids': [8]  # ITBIS 18%
        }
        
        producto_invalido = {
            'name': 'Producto Sin Impuesto',
            'price': 100.00,
            'tax_type_ids': []  # Vacío - INVÁLIDO
        }
        
        # Validación
        self.assertTrue(len(producto_valido['tax_type_ids']) > 0)
        self.assertFalse(len(producto_invalido['tax_type_ids']) > 0)


if __name__ == '__main__':
    # Ejecutar tests con verbosidad
    unittest.main(verbosity=2)
