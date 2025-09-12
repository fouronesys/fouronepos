"""
Initialize database with sample data for Dominican Republic POS system
"""
import bcrypt
from main import app, db
import models

def create_sample_data():
    with app.app_context():
        # Clear existing data
        db.drop_all()
        db.create_all()
        
        # Create users
        admin_password = bcrypt.hashpw('admin123'.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
        cashier_password = bcrypt.hashpw('cajero123'.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
        waiter_password = bcrypt.hashpw('mesero123'.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
        
        admin = models.User(
            username='admin',
            password_hash=admin_password,
            role=models.UserRole.ADMINISTRADOR,
            name='Administrador Principal'
        )
        
        cashier = models.User(
            username='cajero1',
            password_hash=cashier_password,
            role=models.UserRole.CAJERO,
            name='Juan Pérez'
        )
        
        waiter = models.User(
            username='mesero1',
            password_hash=waiter_password,
            role=models.UserRole.MESERO,
            name='María González'
        )
        
        db.session.add_all([admin, cashier, waiter])
        db.session.commit()
        
        # Create cash register
        cash_register = models.CashRegister(
            name='Caja Principal',
            user_id=cashier.id
        )
        
        db.session.add(cash_register)
        db.session.commit()
        
        # Create NCF sequences
        ncf_consumo = models.NCFSequence(
            cash_register_id=cash_register.id,
            ncf_type=models.NCFType.CONSUMO,
            serie='B01',
            start_number=1,
            end_number=10000,
            current_number=1
        )
        
        ncf_credito = models.NCFSequence(
            cash_register_id=cash_register.id,
            ncf_type=models.NCFType.CREDITO_FISCAL,
            serie='B02',
            start_number=1,
            end_number=5000,
            current_number=1
        )
        
        db.session.add_all([ncf_consumo, ncf_credito])
        db.session.commit()
        
        # Create categories
        bebidas = models.Category(name='Bebidas', description='Bebidas alcohólicas y no alcohólicas')
        comidas = models.Category(name='Comidas', description='Platos principales y entradas')
        postres = models.Category(name='Postres', description='Postres y dulces')
        
        db.session.add_all([bebidas, comidas, postres])
        db.session.commit()
        
        # Create products
        products = [
            # Bebidas
            models.Product(name='Cerveza Presidente', description='Cerveza premium dominicana', category_id=bebidas.id, cost=45, price=80, stock=100),
            models.Product(name='Cerveza Brahma', description='Cerveza importada brasileña', category_id=bebidas.id, cost=40, price=75, stock=80),
            models.Product(name='Ron Brugal', description='Ron premium dominicano añejo', category_id=bebidas.id, cost=350, price=500, stock=20),
            models.Product(name='Coca Cola', description='Refresco de cola 355ml', category_id=bebidas.id, cost=25, price=50, stock=150),
            models.Product(name='Agua', description='Agua natural 500ml', category_id=bebidas.id, cost=15, price=30, stock=200),
            
            # Comidas
            models.Product(name='Pollo al Horno', description='Pollo asado con especias dominicanas', category_id=comidas.id, cost=180, price=350, stock=25),
            models.Product(name='Pescado Frito', description='Pescado fresco frito criollo', category_id=comidas.id, cost=200, price=400, stock=15),
            models.Product(name='Mangu', description='Puré de plátano verde tradicional', category_id=comidas.id, cost=80, price=150, stock=30),
            models.Product(name='Tostones', description='Plátano verde frito doble cocción', category_id=comidas.id, cost=40, price=80, stock=50),
            models.Product(name='Ensalada Verde', description='Mix de vegetales frescos', category_id=comidas.id, cost=50, price=120, stock=35),
            
            # Postres
            models.Product(name='Flan', description='Flan de vainilla casero', category_id=postres.id, cost=30, price=80, stock=20),
            models.Product(name='Tres Leches', description='Pastel tres leches tradicional', category_id=postres.id, cost=45, price=120, stock=15),
            models.Product(name='Helado', description='Helado artesanal varios sabores', category_id=postres.id, cost=25, price=60, stock=40)
        ]
        
        db.session.add_all(products)
        db.session.commit()
        
        # Create tables
        tables = []
        for i in range(1, 13):  # 12 tables
            table = models.Table(
                number=str(i),
                name=f'Mesa {i}',
                capacity=4 if i <= 8 else 6,  # First 8 tables for 4, last 4 for 6
                status=models.TableStatus.AVAILABLE
            )
            tables.append(table)
        
        db.session.add_all(tables)
        db.session.commit()
        
        # Create sample supplier
        supplier = models.Supplier(
            name='Distribuidora del Caribe',
            rnc='130123456',
            contact_person='Carlos Martínez',
            phone='809-555-0123',
            email='carlos@distribuidora.com.do',
            address='Av. 27 de Febrero, Santo Domingo'
        )
        
        db.session.add(supplier)
        db.session.commit()
        
        print("✅ Base de datos inicializada con datos de muestra")
        print("\n👤 Usuarios creados:")
        print("   - admin / admin123 (Administrador)")
        print("   - cajero1 / cajero123 (Cajero)")
        print("   - mesero1 / mesero123 (Mesero)")
        print("\n📦 Productos de muestra añadidos")
        print("🏪 12 mesas configuradas")
        print("🧾 Secuencias NCF configuradas")

if __name__ == '__main__':
    create_sample_data()