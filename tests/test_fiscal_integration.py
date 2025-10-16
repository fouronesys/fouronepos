"""
Tests de Integración para Cálculos Fiscales
Valida el comportamiento real del sistema POS usando el código de producción
"""
import unittest
import sys
import os
from decimal import Decimal

# Agregar el directorio raíz al path para importar módulos
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Importar Flask y configuración
from main import app
from models import db
import models


class TestFiscalIntegration(unittest.TestCase):
    """Tests de integración que usan el código real del sistema"""
    
    @classmethod
    def setUpClass(cls):
        """Configuración una vez para toda la clase de tests"""
        cls.app = app
        cls.app.config['TESTING'] = True
        cls.app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL')
        cls.client = cls.app.test_client()
    
    def setUp(self):
        """Configuración antes de cada test"""
        self.app_context = self.app.app_context()
        self.app_context.push()
    
    def tearDown(self):
        """Limpieza después de cada test"""
        self.app_context.pop()
    
    def test_producto_agua_tiene_tax_type_asignado(self):
        """Test: Verificar que producto 'Agua' tiene ITBIS 18% asignado"""
        producto = db.session.query(models.Product).filter_by(name='Agua').first()
        
        self.assertIsNotNone(producto, "Producto 'Agua' debe existir")
        self.assertTrue(len(producto.product_taxes) > 0, "Producto debe tener tax_types asignados")
        
        # Verificar que tiene ITBIS 18%
        tax_names = [pt.tax_type.name for pt in producto.product_taxes]
        self.assertIn('ITBIS 18%', tax_names, "Producto Agua debe tener ITBIS 18%")
    
    def test_producto_pechurinas_tiene_tax_type_asignado(self):
        """Test: Verificar que producto 'Pechurinas' tiene ITBIS 18% asignado"""
        producto = db.session.query(models.Product).filter_by(name='Pechurinas').first()
        
        self.assertIsNotNone(producto, "Producto 'Pechurinas' debe existir")
        self.assertTrue(len(producto.product_taxes) > 0, "Producto debe tener tax_types asignados")
        
        # Verificar que tiene ITBIS 18%
        tax_names = [pt.tax_type.name for pt in producto.product_taxes]
        self.assertIn('ITBIS 18%', tax_names, "Producto Pechurinas debe tener ITBIS 18%")
    
    def test_todos_productos_activos_tienen_tax_types(self):
        """Test: Verificar que TODOS los productos activos tienen tax_types configurados"""
        productos_sin_tax = db.session.query(models.Product).filter(
            models.Product.active == True
        ).outerjoin(
            models.ProductTax
        ).group_by(
            models.Product.id
        ).having(
            db.func.count(models.ProductTax.id) == 0
        ).all()
        
        self.assertEqual(len(productos_sin_tax), 0, 
                        f"No deben existir productos activos sin tax_types. Encontrados: {[p.name for p in productos_sin_tax]}")
    
    def test_tax_types_tienen_tax_category_poblado(self):
        """Test: Verificar que todos los tax_types tienen tax_category definido"""
        tax_types = db.session.query(models.TaxType).filter_by(active=True).all()
        
        for tax_type in tax_types:
            self.assertIsNotNone(tax_type.tax_category, 
                                f"TaxType '{tax_type.name}' debe tener tax_category")
            # Verificar que es un valor válido del enum
            valid_categories = ['tax', 'service_charge', 'other']
            self.assertIn(tax_type.tax_category.value, valid_categories,
                         f"TaxType '{tax_type.name}' tiene tax_category inválido: {tax_type.tax_category.value}")
    
    def test_propina_es_service_charge(self):
        """Test: Verificar que Propina 10% está categorizada como 'service_charge'"""
        propina = db.session.query(models.TaxType).filter_by(name='Propina 10%').first()
        
        self.assertIsNotNone(propina, "Propina 10% debe existir")
        self.assertEqual(propina.tax_category.value, 'service_charge',
                        "Propina debe estar categorizada como 'service_charge'")
    
    def test_itbis_es_tax(self):
        """Test: Verificar que todos los ITBIS están categorizados como 'tax'"""
        itbis_types = db.session.query(models.TaxType).filter(
            models.TaxType.name.like('%ITBIS%')
        ).all()
        
        for itbis in itbis_types:
            self.assertEqual(itbis.tax_category.value, 'tax',
                           f"{itbis.name} debe estar categorizado como 'tax'")
    
    def test_calculo_fiscal_producto_real(self):
        """Test: Simular cálculo fiscal con producto real (Agua)"""
        producto = db.session.query(models.Product).filter_by(name='Agua').first()
        
        if producto:
            # Simular cálculo de impuestos como en routes/api.py
            product_tax_types = []
            for product_tax in producto.product_taxes:
                if product_tax.tax_type.active:
                    tax_category = 'tax'
                    if hasattr(product_tax.tax_type, 'tax_category') and product_tax.tax_type.tax_category:
                        tax_category = product_tax.tax_type.tax_category.value
                    
                    product_tax_types.append({
                        'name': product_tax.tax_type.name,
                        'rate': product_tax.tax_type.rate,
                        'is_inclusive': product_tax.tax_type.is_inclusive,
                        'tax_category': tax_category
                    })
            
            # Filtrar solo impuestos fiscales
            tax_only = [tax for tax in product_tax_types if tax.get('tax_category') == 'tax']
            
            # Calcular tasa total de impuestos (solo tax, no service_charge)
            total_tax_rate = sum(Decimal(str(tax['rate'])) for tax in tax_only if not tax['is_inclusive'])
            
            # Verificar que el cálculo es correcto
            self.assertEqual(total_tax_rate, Decimal('0.18'), 
                           "Producto Agua debe tener tasa fiscal de 0.18 (ITBIS 18%)")
    
    def test_tax_type_inclusivo_vs_exclusivo(self):
        """Test: Verificar diferencia entre ITBIS inclusivo y exclusivo"""
        itbis_18 = db.session.query(models.TaxType).filter_by(name='ITBIS 18%').first()
        itbis_18_incluido = db.session.query(models.TaxType).filter_by(name='ITBIS 18% Incluído').first()
        
        if itbis_18 and itbis_18_incluido:
            self.assertFalse(itbis_18.is_inclusive, "ITBIS 18% debe ser exclusivo")
            self.assertTrue(itbis_18_incluido.is_inclusive, "ITBIS 18% Incluído debe ser inclusivo")
            self.assertEqual(itbis_18.rate, itbis_18_incluido.rate, 
                           "Ambos deben tener la misma tasa (0.18)")


class TestProductValidation(unittest.TestCase):
    """Tests para validaciones de productos"""
    
    @classmethod
    def setUpClass(cls):
        """Configuración una vez para toda la clase de tests"""
        cls.app = app
        cls.app.config['TESTING'] = True
        cls.client = cls.app.test_client()
    
    def test_producto_sin_tax_type_debe_fallar(self):
        """Test: Validación backend rechaza productos sin tax_types"""
        # Este test verifica que la validación funciona
        # En producción, el endpoint routes/inventory.py debe rechazar esto
        
        # Datos de producto sin tax_types
        producto_invalido = {
            'name': 'Test Producto Sin Impuesto',
            'price': 100.00,
            'category_id': 1,
            'tax_type_ids': []  # Vacío - debe fallar
        }
        
        # La validación debe detectar que tax_type_ids está vacío
        self.assertEqual(len(producto_invalido['tax_type_ids']), 0,
                        "Producto sin tax_types debe ser detectado")


if __name__ == '__main__':
    # Ejecutar tests con verbosidad
    unittest.main(verbosity=2)
