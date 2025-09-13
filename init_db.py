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
            # Los productos se pueden agregar aquí cuando sea necesario
        ]
        
        # Solo agregar productos si hay alguno definido
        if products:
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
        if products:
            print("\n📦 Productos de muestra añadidos")
        else:
            print("\n📦 Lista de productos inicializada (vacía)")
        print("🏪 12 mesas configuradas")
        print("🧾 Secuencias NCF configuradas")

if __name__ == '__main__':
    create_sample_data()