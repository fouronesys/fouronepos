"""
Script para limpiar datos del sistema POS
Mantiene solo: productos, categorías, usuarios y cajas
Elimina todos los demás datos
"""
from main import app, db
import models

def clean_database():
    with app.app_context():
        print("🧹 Iniciando limpieza de datos...")
        
        # Eliminar datos en orden correcto para respetar foreign keys
        
        # 1. Eliminar registros de auditoría y logs
        print("  - Eliminando registros de auditoría...")
        models.RegisterReassignmentLog.query.delete()
        models.NCFLedger.query.delete()
        models.NCFSequenceAudit.query.delete()
        
        # 2. Eliminar notas de crédito
        print("  - Eliminando notas de crédito...")
        models.CreditNoteItem.query.delete()
        models.CreditNote.query.delete()
        models.CancelledNCF.query.delete()
        
        # 3. Eliminar ventas
        print("  - Eliminando ventas...")
        models.SaleItem.query.delete()
        models.Sale.query.delete()
        
        # 4. Eliminar compras
        print("  - Eliminando compras...")
        models.PurchaseItem.query.delete()
        models.Purchase.query.delete()
        
        # 5. Eliminar ajustes de inventario
        print("  - Eliminando ajustes de inventario...")
        models.StockAdjustment.query.delete()
        
        # 6. Eliminar mesas
        print("  - Eliminando mesas...")
        models.Table.query.delete()
        
        # 7. Eliminar clientes y proveedores
        print("  - Eliminando clientes y proveedores...")
        models.Customer.query.delete()
        models.Supplier.query.delete()
        
        # 8. Eliminar secuencias NCF
        print("  - Eliminando secuencias NCF...")
        models.NCFSequence.query.delete()
        
        # 9. Eliminar sesiones de caja
        print("  - Eliminando sesiones de caja...")
        models.CashSession.query.delete()
        
        # 10. Eliminar tokens de reseteo de contraseña
        print("  - Eliminando tokens de reseteo...")
        models.PasswordResetToken.query.delete()
        
        # 11. Eliminar configuración del sistema
        print("  - Eliminando configuración del sistema...")
        models.SystemConfiguration.query.delete()
        
        # 12. Eliminar impuestos de productos
        print("  - Eliminando relaciones de impuestos...")
        models.ProductTax.query.delete()
        models.TaxType.query.delete()
        
        # Commit de todos los cambios
        db.session.commit()
        
        print("\n✅ Limpieza completada!")
        print("\n📊 Datos mantenidos:")
        print(f"  - Usuarios: {models.User.query.count()}")
        print(f"  - Cajas: {models.CashRegister.query.count()}")
        print(f"  - Categorías: {models.Category.query.count()}")
        print(f"  - Productos: {models.Product.query.count()}")

if __name__ == '__main__':
    confirmation = input("⚠️  ADVERTENCIA: Este script eliminará todos los datos excepto usuarios, cajas, categorías y productos.\n¿Está seguro de continuar? (escriba 'SI' para confirmar): ")
    
    if confirmation == 'SI':
        clean_database()
    else:
        print("❌ Operación cancelada.")
