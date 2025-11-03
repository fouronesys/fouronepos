"""
Tests para endpoints de API con casos de error
Testing completo del manejo de errores en endpoints /api/sales
"""
import pytest
import json
import os
import sys

# Configure environment for testing
os.environ['SESSION_SECRET'] = 'test_secret_key_for_testing_only'
os.environ['DATABASE_URL'] = 'sqlite:///:memory:'

from main import app
from models import db, User, Product, Category, Sale, SaleItem, CashRegister, Table, UserRole, TaxType, ProductTax
from werkzeug.security import generate_password_hash


@pytest.fixture(scope='module')
def test_app():
    """Fixture para configurar la aplicación en modo de testing"""
    app.config['TESTING'] = True
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
    app.config['WTF_CSRF_ENABLED'] = False  # Disable CSRF for tests
    app.config['SERVER_NAME'] = 'localhost'
    app.secret_key = 'test_secret_key_for_testing_only'
    
    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()


@pytest.fixture
def client(test_app):
    """Fixture para el cliente de testing"""
    return test_app.test_client()


@pytest.fixture
def app_context(test_app):
    """Fixture para el contexto de aplicación"""
    with test_app.app_context():
        yield


@pytest.fixture
def authenticated_cashier(client, app_context):
    """
    Fixture para crear y autenticar un usuario cajero
    Returns: tuple (user, session_data)
    """
    # Create cashier user
    cashier = User(
        username='cajero_test',
        email='cajero@test.com',
        role=UserRole.CAJERO
    )
    cashier.password_hash = generate_password_hash('password123')
    db.session.add(cashier)
    
    # Create cash register for cashier
    cash_register = CashRegister(
        name='Caja Test',
        current_cash=1000.00,
        is_active=True
    )
    db.session.add(cash_register)
    db.session.commit()
    
    # Login the cashier
    with client.session_transaction() as sess:
        sess['user_id'] = cashier.id
        sess['username'] = cashier.username
        sess['role'] = cashier.role.value
    
    return cashier, cash_register


@pytest.fixture
def authenticated_waiter(client, app_context):
    """
    Fixture para crear y autenticar un usuario mesero
    Returns: user
    """
    # Create waiter user
    waiter = User(
        username='mesero_test',
        email='mesero@test.com',
        role=UserRole.MESERO
    )
    waiter.password_hash = generate_password_hash('password123')
    db.session.add(waiter)
    db.session.commit()
    
    # Login the waiter
    with client.session_transaction() as sess:
        sess['user_id'] = waiter.id
        sess['username'] = waiter.username
        sess['role'] = waiter.role.value
    
    return waiter


@pytest.fixture
def sample_products(app_context):
    """Fixture para crear productos de prueba"""
    # Create category
    category = Category(name='Bebidas', active=True)
    db.session.add(category)
    db.session.flush()
    
    # Create products
    product1 = Product(
        name='Coca Cola 2L',
        price=100.00,
        cost=50.00,
        stock=50,
        min_stock=10,
        product_type='inventariable',
        category_id=category.id,
        active=True
    )
    
    product2 = Product(
        name='Agua Mineral',
        price=25.00,
        cost=10.00,
        stock=0,  # Sin stock para testing
        min_stock=5,
        product_type='inventariable',
        category_id=category.id,
        active=True
    )
    
    product3 = Product(
        name='Servicio de Mesero',
        price=50.00,
        cost=0.00,
        stock=0,
        min_stock=0,
        product_type='servicio',
        category_id=category.id,
        active=True
    )
    
    db.session.add_all([product1, product2, product3])
    db.session.commit()
    
    return {
        'with_stock': product1,
        'without_stock': product2,
        'service': product3,
        'category': category
    }


@pytest.fixture
def sample_table(app_context):
    """Fixture para crear mesa de prueba"""
    table = Table(
        number=1,
        capacity=4,
        status='available',
        active=True
    )
    db.session.add(table)
    db.session.commit()
    return table


class TestCreateSaleEndpoint:
    """Tests para endpoint POST /api/sales"""
    
    def test_create_sale_success(self, client, authenticated_cashier):
        """Crear venta exitosamente"""
        cashier, cash_register = authenticated_cashier
        
        response = client.post('/api/sales',
            data=json.dumps({}),
            content_type='application/json'
        )
        
        assert response.status_code == 201
        data = json.loads(response.data)
        assert 'sale_id' in data
        assert data['status'] == 'pending'
    
    def test_create_sale_without_authentication(self, client):
        """Intentar crear venta sin autenticación"""
        response = client.post('/api/sales',
            data=json.dumps({}),
            content_type='application/json'
        )
        
        assert response.status_code == 401
        data = json.loads(response.data)
        assert data['type'] == 'permission'
        assert 'error_id' in data
        assert 'No autorizado' in data['error']
    
    def test_create_sale_with_valid_table(self, client, authenticated_cashier, sample_table):
        """Crear venta con mesa válida"""
        cashier, cash_register = authenticated_cashier
        
        response = client.post('/api/sales',
            data=json.dumps({'table_id': sample_table.id}),
            content_type='application/json'
        )
        
        assert response.status_code == 201
        data = json.loads(response.data)
        assert 'sale_id' in data
    
    def test_create_sale_with_invalid_table(self, client, authenticated_cashier):
        """Crear venta con mesa inexistente"""
        cashier, cash_register = authenticated_cashier
        
        response = client.post('/api/sales',
            data=json.dumps({'table_id': 99999}),
            content_type='application/json'
        )
        
        assert response.status_code == 404
        data = json.loads(response.data)
        assert data['type'] == 'not_found'
        assert 'Mesa no encontrada' in data['error']
        assert 'error_id' in data
    
    def test_create_sale_with_invalid_table_id_type(self, client, authenticated_cashier):
        """Crear venta con ID de mesa inválido (no numérico)"""
        cashier, cash_register = authenticated_cashier
        
        response = client.post('/api/sales',
            data=json.dumps({'table_id': 'invalid'}),
            content_type='application/json'
        )
        
        assert response.status_code == 400
        data = json.loads(response.data)
        assert data['type'] == 'validation'
        assert 'error_id' in data


class TestAddSaleItemEndpoint:
    """Tests para endpoint POST /api/sales/<id>/items"""
    
    def test_add_item_success(self, client, authenticated_cashier, sample_products):
        """Agregar producto exitosamente"""
        cashier, cash_register = authenticated_cashier
        
        # Create sale first
        sale_response = client.post('/api/sales',
            data=json.dumps({}),
            content_type='application/json'
        )
        sale_id = json.loads(sale_response.data)['sale_id']
        
        # Add item
        product = sample_products['with_stock']
        response = client.post(f'/api/sales/{sale_id}/items',
            data=json.dumps({
                'product_id': product.id,
                'quantity': 2
            }),
            content_type='application/json'
        )
        
        assert response.status_code == 200
        data = json.loads(response.data)
        assert 'item_id' in data
        assert data['quantity'] == 2
    
    def test_add_item_without_data(self, client, authenticated_cashier):
        """Intentar agregar ítem sin datos"""
        cashier, cash_register = authenticated_cashier
        
        # Create sale
        sale_response = client.post('/api/sales',
            data=json.dumps({}),
            content_type='application/json'
        )
        sale_id = json.loads(sale_response.data)['sale_id']
        
        # Try to add item without data
        response = client.post(f'/api/sales/{sale_id}/items',
            content_type='application/json'
        )
        
        assert response.status_code == 400
        data = json.loads(response.data)
        assert data['type'] == 'validation'
        assert 'Datos no proporcionados' in data['error']
        assert 'error_id' in data
    
    def test_add_item_missing_required_fields(self, client, authenticated_cashier):
        """Intentar agregar ítem sin campos requeridos"""
        cashier, cash_register = authenticated_cashier
        
        # Create sale
        sale_response = client.post('/api/sales',
            data=json.dumps({}),
            content_type='application/json'
        )
        sale_id = json.loads(sale_response.data)['sale_id']
        
        # Try to add item without product_id
        response = client.post(f'/api/sales/{sale_id}/items',
            data=json.dumps({'quantity': 1}),
            content_type='application/json'
        )
        
        assert response.status_code == 400
        data = json.loads(response.data)
        assert data['type'] == 'validation'
        assert 'product_id' in data['details']
        assert 'error_id' in data
    
    def test_add_item_invalid_quantity_zero(self, client, authenticated_cashier, sample_products):
        """Intentar agregar ítem con cantidad 0"""
        cashier, cash_register = authenticated_cashier
        
        # Create sale
        sale_response = client.post('/api/sales',
            data=json.dumps({}),
            content_type='application/json'
        )
        sale_id = json.loads(sale_response.data)['sale_id']
        
        # Try to add item with quantity 0
        product = sample_products['with_stock']
        response = client.post(f'/api/sales/{sale_id}/items',
            data=json.dumps({
                'product_id': product.id,
                'quantity': 0
            }),
            content_type='application/json'
        )
        
        assert response.status_code == 400
        data = json.loads(response.data)
        assert data['type'] == 'validation'
        assert 'Cantidad' in data['error']
        assert 'error_id' in data
    
    def test_add_item_invalid_quantity_too_high(self, client, authenticated_cashier, sample_products):
        """Intentar agregar ítem con cantidad > 1000"""
        cashier, cash_register = authenticated_cashier
        
        # Create sale
        sale_response = client.post('/api/sales',
            data=json.dumps({}),
            content_type='application/json'
        )
        sale_id = json.loads(sale_response.data)['sale_id']
        
        # Try to add item with quantity > 1000
        product = sample_products['with_stock']
        response = client.post(f'/api/sales/{sale_id}/items',
            data=json.dumps({
                'product_id': product.id,
                'quantity': 1500
            }),
            content_type='application/json'
        )
        
        assert response.status_code == 400
        data = json.loads(response.data)
        assert data['type'] == 'validation'
        assert 'max_allowed' in data
        assert data['max_allowed'] == 1000
        assert 'error_id' in data
    
    def test_add_item_insufficient_stock(self, client, authenticated_cashier, sample_products):
        """Intentar agregar ítem con stock insuficiente"""
        cashier, cash_register = authenticated_cashier
        
        # Create sale
        sale_response = client.post('/api/sales',
            data=json.dumps({}),
            content_type='application/json'
        )
        sale_id = json.loads(sale_response.data)['sale_id']
        
        # Try to add item with insufficient stock
        product = sample_products['without_stock']
        response = client.post(f'/api/sales/{sale_id}/items',
            data=json.dumps({
                'product_id': product.id,
                'quantity': 1
            }),
            content_type='application/json'
        )
        
        assert response.status_code == 400
        data = json.loads(response.data)
        assert data['type'] == 'business'
        assert 'Stock insuficiente' in data['error']
        assert 'available_stock' in data
        assert 'error_id' in data
    
    def test_add_item_to_nonexistent_sale(self, client, authenticated_cashier, sample_products):
        """Intentar agregar ítem a venta inexistente"""
        cashier, cash_register = authenticated_cashier
        
        product = sample_products['with_stock']
        response = client.post('/api/sales/99999/items',
            data=json.dumps({
                'product_id': product.id,
                'quantity': 1
            }),
            content_type='application/json'
        )
        
        assert response.status_code == 404
        data = json.loads(response.data)
        assert data['type'] == 'not_found'
        assert 'Venta no encontrada' in data['error']
        assert 'error_id' in data
    
    def test_add_item_nonexistent_product(self, client, authenticated_cashier):
        """Intentar agregar producto inexistente"""
        cashier, cash_register = authenticated_cashier
        
        # Create sale
        sale_response = client.post('/api/sales',
            data=json.dumps({}),
            content_type='application/json'
        )
        sale_id = json.loads(sale_response.data)['sale_id']
        
        # Try to add nonexistent product
        response = client.post(f'/api/sales/{sale_id}/items',
            data=json.dumps({
                'product_id': 99999,
                'quantity': 1
            }),
            content_type='application/json'
        )
        
        assert response.status_code == 404
        data = json.loads(response.data)
        assert data['type'] == 'not_found'
        assert 'Producto no encontrado' in data['error']
        assert 'error_id' in data


class TestFinalizeSaleEndpoint:
    """Tests para endpoint POST /api/sales/<id>/finalize"""
    
    def test_finalize_sale_waiter_permission_denied(self, client, authenticated_waiter, sample_products):
        """Mesero no puede finalizar ventas (solo cajeros)"""
        waiter = authenticated_waiter
        
        # Create sale
        sale_response = client.post('/api/sales',
            data=json.dumps({}),
            content_type='application/json'
        )
        sale_id = json.loads(sale_response.data)['sale_id']
        
        # Add item
        product = sample_products['with_stock']
        client.post(f'/api/sales/{sale_id}/items',
            data=json.dumps({
                'product_id': product.id,
                'quantity': 1
            }),
            content_type='application/json'
        )
        
        # Try to finalize as waiter
        response = client.post(f'/api/sales/{sale_id}/finalize',
            data=json.dumps({
                'payment_method': 'cash'
            }),
            content_type='application/json'
        )
        
        assert response.status_code == 403
        data = json.loads(response.data)
        assert data['type'] == 'permission'
        assert 'Permisos insuficientes' in data['error']
        assert 'required_roles' in data
        assert 'error_id' in data
    
    def test_finalize_sale_invalid_payment_method(self, client, authenticated_cashier, sample_products):
        """Intentar finalizar con método de pago inválido"""
        cashier, cash_register = authenticated_cashier
        
        # Create sale and add item
        sale_response = client.post('/api/sales',
            data=json.dumps({}),
            content_type='application/json'
        )
        sale_id = json.loads(sale_response.data)['sale_id']
        
        product = sample_products['with_stock']
        client.post(f'/api/sales/{sale_id}/items',
            data=json.dumps({
                'product_id': product.id,
                'quantity': 1
            }),
            content_type='application/json'
        )
        
        # Try to finalize with invalid payment method
        response = client.post(f'/api/sales/{sale_id}/finalize',
            data=json.dumps({
                'payment_method': 'bitcoin'
            }),
            content_type='application/json'
        )
        
        assert response.status_code == 400
        data = json.loads(response.data)
        assert data['type'] == 'validation'
        assert 'Método de pago inválido' in data['error']
        assert 'valid_options' in data
        assert set(data['valid_options']) == {'cash', 'card', 'transfer'}
        assert 'error_id' in data
    
    def test_finalize_sale_invalid_cash_received_negative(self, client, authenticated_cashier, sample_products):
        """Intentar finalizar con efectivo recibido negativo"""
        cashier, cash_register = authenticated_cashier
        
        # Create sale and add item
        sale_response = client.post('/api/sales',
            data=json.dumps({}),
            content_type='application/json'
        )
        sale_id = json.loads(sale_response.data)['sale_id']
        
        product = sample_products['with_stock']
        client.post(f'/api/sales/{sale_id}/items',
            data=json.dumps({
                'product_id': product.id,
                'quantity': 1
            }),
            content_type='application/json'
        )
        
        # Try to finalize with negative cash
        response = client.post(f'/api/sales/{sale_id}/finalize',
            data=json.dumps({
                'payment_method': 'cash',
                'cash_received': -100
            }),
            content_type='application/json'
        )
        
        assert response.status_code == 400
        data = json.loads(response.data)
        assert data['type'] == 'validation'
        assert 'error_id' in data
    
    def test_finalize_sale_invalid_cash_received_too_high(self, client, authenticated_cashier, sample_products):
        """Intentar finalizar con efectivo > RD$ 1,000,000"""
        cashier, cash_register = authenticated_cashier
        
        # Create sale and add item
        sale_response = client.post('/api/sales',
            data=json.dumps({}),
            content_type='application/json'
        )
        sale_id = json.loads(sale_response.data)['sale_id']
        
        product = sample_products['with_stock']
        client.post(f'/api/sales/{sale_id}/items',
            data=json.dumps({
                'product_id': product.id,
                'quantity': 1
            }),
            content_type='application/json'
        )
        
        # Try to finalize with cash > 1M
        response = client.post(f'/api/sales/{sale_id}/finalize',
            data=json.dumps({
                'payment_method': 'cash',
                'cash_received': 1500000
            }),
            content_type='application/json'
        )
        
        assert response.status_code == 400
        data = json.loads(response.data)
        assert data['type'] == 'validation'
        assert 'max_allowed' in data
        assert data['max_allowed'] == 1000000
        assert 'error_id' in data
    
    def test_finalize_sale_credito_fiscal_without_customer_name(self, client, authenticated_cashier, sample_products):
        """Intentar finalizar NCF crédito fiscal sin nombre de cliente"""
        cashier, cash_register = authenticated_cashier
        
        # Create sale and add item
        sale_response = client.post('/api/sales',
            data=json.dumps({}),
            content_type='application/json'
        )
        sale_id = json.loads(sale_response.data)['sale_id']
        
        product = sample_products['with_stock']
        client.post(f'/api/sales/{sale_id}/items',
            data=json.dumps({
                'product_id': product.id,
                'quantity': 1
            }),
            content_type='application/json'
        )
        
        # Try to finalize as credito_fiscal without customer name
        response = client.post(f'/api/sales/{sale_id}/finalize',
            data=json.dumps({
                'payment_method': 'cash',
                'ncf_type': 'credito_fiscal',
                'customer_rnc': '123456789'
            }),
            content_type='application/json'
        )
        
        assert response.status_code == 400
        data = json.loads(response.data)
        assert data['type'] == 'validation'
        assert 'nombre del cliente' in data['error'].lower()
        assert 'error_id' in data
    
    def test_finalize_sale_credito_fiscal_without_customer_rnc(self, client, authenticated_cashier, sample_products):
        """Intentar finalizar NCF crédito fiscal sin RNC de cliente"""
        cashier, cash_register = authenticated_cashier
        
        # Create sale and add item
        sale_response = client.post('/api/sales',
            data=json.dumps({}),
            content_type='application/json'
        )
        sale_id = json.loads(sale_response.data)['sale_id']
        
        product = sample_products['with_stock']
        client.post(f'/api/sales/{sale_id}/items',
            data=json.dumps({
                'product_id': product.id,
                'quantity': 1
            }),
            content_type='application/json'
        )
        
        # Try to finalize as credito_fiscal without customer RNC
        response = client.post(f'/api/sales/{sale_id}/finalize',
            data=json.dumps({
                'payment_method': 'cash',
                'ncf_type': 'credito_fiscal',
                'customer_name': 'Empresa Test'
            }),
            content_type='application/json'
        )
        
        assert response.status_code == 400
        data = json.loads(response.data)
        assert data['type'] == 'validation'
        assert 'rnc del cliente' in data['error'].lower()
        assert 'error_id' in data
    
    def test_finalize_sale_invalid_rnc_format(self, client, authenticated_cashier, sample_products):
        """Intentar finalizar con RNC en formato inválido"""
        cashier, cash_register = authenticated_cashier
        
        # Create sale and add item
        sale_response = client.post('/api/sales',
            data=json.dumps({}),
            content_type='application/json'
        )
        sale_id = json.loads(sale_response.data)['sale_id']
        
        product = sample_products['with_stock']
        client.post(f'/api/sales/{sale_id}/items',
            data=json.dumps({
                'product_id': product.id,
                'quantity': 1
            }),
            content_type='application/json'
        )
        
        # Try to finalize with invalid RNC
        response = client.post(f'/api/sales/{sale_id}/finalize',
            data=json.dumps({
                'payment_method': 'cash',
                'customer_rnc': '12345'  # RNC too short
            }),
            content_type='application/json'
        )
        
        assert response.status_code == 400
        data = json.loads(response.data)
        assert data['type'] == 'validation'
        assert 'error_id' in data


class TestErrorResponseStructure:
    """Tests para verificar la estructura de respuestas de error"""
    
    def test_error_response_has_required_fields(self, client):
        """Todas las respuestas de error tienen campos requeridos"""
        # Trigger an error (no authentication)
        response = client.post('/api/sales',
            data=json.dumps({}),
            content_type='application/json'
        )
        
        data = json.loads(response.data)
        
        # Verify required fields
        assert 'error' in data
        assert 'type' in data
        assert 'error_id' in data
        assert 'timestamp' in data
        
        # Verify error_id format (8 characters uppercase)
        assert len(data['error_id']) == 8
        assert data['error_id'].isupper()
        
        # Verify timestamp is ISO format
        assert 'T' in data['timestamp']
    
    def test_error_types_are_valid(self, client, authenticated_cashier, sample_products):
        """Los tipos de error son válidos"""
        cashier, cash_register = authenticated_cashier
        
        # Test validation error
        sale_response = client.post('/api/sales',
            data=json.dumps({}),
            content_type='application/json'
        )
        sale_id = json.loads(sale_response.data)['sale_id']
        
        response = client.post(f'/api/sales/{sale_id}/items',
            data=json.dumps({'product_id': 1, 'quantity': 0}),
            content_type='application/json'
        )
        data = json.loads(response.data)
        assert data['type'] in ['validation', 'business', 'permission', 'not_found', 'server']
    
    def test_validation_error_includes_field(self, client, authenticated_cashier):
        """Errores de validación incluyen el campo problemático"""
        cashier, cash_register = authenticated_cashier
        
        # Create sale
        sale_response = client.post('/api/sales',
            data=json.dumps({}),
            content_type='application/json'
        )
        sale_id = json.loads(sale_response.data)['sale_id']
        
        # Trigger validation error with invalid quantity
        response = client.post(f'/api/sales/{sale_id}/items',
            data=json.dumps({'product_id': 1, 'quantity': 1500}),
            content_type='application/json'
        )
        
        data = json.loads(response.data)
        if data['type'] == 'validation':
            # Field should be present for validation errors
            assert 'field' in data or 'details' in data
