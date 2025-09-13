from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


db = SQLAlchemy(model_class=Base)
from datetime import datetime
from sqlalchemy import String, Integer, Float, DateTime, Boolean, Text, ForeignKey, Enum
from sqlalchemy.orm import Mapped, mapped_column, relationship
import enum


class UserRole(enum.Enum):
    ADMINISTRADOR = "ADMINISTRADOR"
    CAJERO = "CAJERO"
    MESERO = "MESERO"
    GERENTE = "GERENTE"


class NCFType(enum.Enum):
    CONSUMO = "CONSUMO"
    CREDITO_FISCAL = "CREDITO_FISCAL"
    GUBERNAMENTAL = "GUBERNAMENTAL"
    NOTA_CREDITO = "NOTA_CREDITO"
    NOTA_DEBITO = "NOTA_DEBITO"


class TableStatus(enum.Enum):
    AVAILABLE = "available"
    OCCUPIED = "occupied"
    RESERVED = "reserved"


class OrderStatus(enum.Enum):
    NOT_SENT = "not_sent"
    SENT_TO_KITCHEN = "sent_to_kitchen"
    IN_PREPARATION = "in_preparation"
    READY = "ready"
    SERVED = "served"


class User(db.Model):
    __tablename__ = 'users'
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    username: Mapped[str] = mapped_column(String(80), unique=True, nullable=False)
    email: Mapped[str] = mapped_column(String(120), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(128), nullable=False)
    role: Mapped[UserRole] = mapped_column(Enum(UserRole, native_enum=False), nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    must_change_password: Mapped[bool] = mapped_column(Boolean, default=False)
    last_login: Mapped[datetime] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    
    # Relationships
    sales = relationship("Sale", foreign_keys="Sale.user_id", back_populates="user")
    cash_registers = relationship("CashRegister", back_populates="user")
    password_reset_tokens = relationship("PasswordResetToken", back_populates="user")


class CashRegister(db.Model):
    __tablename__ = 'cash_registers'
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey('users.id'), nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    
    # Relationships
    user = relationship("User", back_populates="cash_registers")
    ncf_sequences = relationship("NCFSequence", back_populates="cash_register")
    sales = relationship("Sale", back_populates="cash_register")


class NCFSequence(db.Model):
    __tablename__ = 'ncf_sequences'
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    cash_register_id: Mapped[int] = mapped_column(Integer, ForeignKey('cash_registers.id'))
    ncf_type: Mapped[NCFType] = mapped_column(Enum(NCFType), nullable=False)
    serie: Mapped[str] = mapped_column(String(3), nullable=False)  # e.g., "B01", "B02"
    start_number: Mapped[int] = mapped_column(Integer, nullable=False)
    end_number: Mapped[int] = mapped_column(Integer, nullable=False)
    current_number: Mapped[int] = mapped_column(Integer, nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    
    # Relationships
    cash_register = relationship("CashRegister", back_populates="ncf_sequences")
    sales = relationship("Sale", back_populates="ncf_sequence")


class Category(db.Model):
    __tablename__ = 'categories'
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str] = mapped_column(Text)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    
    # Relationships
    products = relationship("Product", back_populates="category")


class TaxType(db.Model):
    __tablename__ = 'tax_types'
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)  # e.g., "ITBIS", "Propina", "IVA"
    description: Mapped[str] = mapped_column(Text)
    rate: Mapped[float] = mapped_column(Float, nullable=False)  # e.g., 0.18, 0.10
    is_inclusive: Mapped[bool] = mapped_column(Boolean, default=False)  # True si está incluido en el precio
    is_percentage: Mapped[bool] = mapped_column(Boolean, default=True)  # True para porcentaje, False para monto fijo
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    display_order: Mapped[int] = mapped_column(Integer, default=0)  # Para ordenar en formularios
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    
    # Relationships - productos podrán tener múltiples tipos de impuestos
    product_taxes = relationship("ProductTax", back_populates="tax_type")


class ProductTax(db.Model):
    """Tabla intermedia para relacionar productos con múltiples tipos de impuestos"""
    __tablename__ = 'product_taxes'
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    product_id: Mapped[int] = mapped_column(Integer, ForeignKey('products.id'), nullable=False)
    tax_type_id: Mapped[int] = mapped_column(Integer, ForeignKey('tax_types.id'), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    
    # Relationships
    product = relationship("Product", back_populates="product_taxes")
    tax_type = relationship("TaxType", back_populates="product_taxes")
    
    # Constraint para evitar duplicados
    __table_args__ = (
        db.UniqueConstraint('product_id', 'tax_type_id', name='unique_product_tax'),
    )


class Product(db.Model):
    __tablename__ = 'products'
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str] = mapped_column(Text)
    category_id: Mapped[int] = mapped_column(Integer, ForeignKey('categories.id'))
    cost: Mapped[float] = mapped_column(Float, default=0.0)
    price: Mapped[float] = mapped_column(Float, nullable=False)
    tax_rate: Mapped[float] = mapped_column(Float, default=0.18)  # ITBIS: 0% exento, 16% reducido (lácteos, café, azúcares, cacao), 18% estándar
    is_tax_included: Mapped[bool] = mapped_column(Boolean, default=False)  # True si el impuesto está incluido en el precio
    stock: Mapped[int] = mapped_column(Integer, default=0)
    min_stock: Mapped[int] = mapped_column(Integer, default=5)
    product_type: Mapped[str] = mapped_column(String(20), default='inventariable')  # 'inventariable' o 'consumible'
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    
    # Relationships
    category = relationship("Category", back_populates="products")
    sale_items = relationship("SaleItem", back_populates="product")
    product_taxes = relationship("ProductTax", back_populates="product")


class Supplier(db.Model):
    __tablename__ = 'suppliers'
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    rnc: Mapped[str] = mapped_column(String(20))  # RNC (Registro Nacional del Contribuyente)
    contact_person: Mapped[str] = mapped_column(String(100))
    phone: Mapped[str] = mapped_column(String(20))
    email: Mapped[str] = mapped_column(String(100))
    address: Mapped[str] = mapped_column(Text)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    
    # Relationships
    purchases = relationship("Purchase", back_populates="supplier")


class Purchase(db.Model):
    __tablename__ = 'purchases'
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    supplier_id: Mapped[int] = mapped_column(Integer, ForeignKey('suppliers.id'))
    ncf_supplier: Mapped[str] = mapped_column(String(20))  # NCF del proveedor
    total_amount: Mapped[float] = mapped_column(Float, nullable=False)
    tax_amount: Mapped[float] = mapped_column(Float, default=0.0)
    notes: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    
    # Relationships
    supplier = relationship("Supplier", back_populates="purchases")
    purchase_items = relationship("PurchaseItem", back_populates="purchase")


class PurchaseItem(db.Model):
    __tablename__ = 'purchase_items'
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    purchase_id: Mapped[int] = mapped_column(Integer, ForeignKey('purchases.id'))
    product_id: Mapped[int] = mapped_column(Integer, ForeignKey('products.id'))
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    unit_cost: Mapped[float] = mapped_column(Float, nullable=False)
    total_cost: Mapped[float] = mapped_column(Float, nullable=False)
    
    # Relationships
    purchase = relationship("Purchase", back_populates="purchase_items")
    product = relationship("Product")


class Table(db.Model):
    __tablename__ = 'tables'
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    number: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(100))
    capacity: Mapped[int] = mapped_column(Integer, default=4)
    status: Mapped[TableStatus] = mapped_column(Enum(TableStatus), default=TableStatus.AVAILABLE)
    
    # Relationships
    sales = relationship("Sale", back_populates="table")


class Sale(db.Model):
    __tablename__ = 'sales'
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    cash_register_id: Mapped[int] = mapped_column(Integer, ForeignKey('cash_registers.id'), nullable=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey('users.id'))
    table_id: Mapped[int] = mapped_column(Integer, ForeignKey('tables.id'), nullable=True)
    ncf_sequence_id: Mapped[int] = mapped_column(Integer, ForeignKey('ncf_sequences.id'), nullable=True)
    ncf: Mapped[str] = mapped_column(String(20), nullable=True, unique=True)
    subtotal: Mapped[float] = mapped_column(Float, nullable=False)
    tax_amount: Mapped[float] = mapped_column(Float, default=0.0)
    service_charge_amount: Mapped[float] = mapped_column(Float, default=0.0)  # Propina/service charge
    total: Mapped[float] = mapped_column(Float, nullable=False)
    payment_method: Mapped[str] = mapped_column(String(50), default="cash")
    cash_received: Mapped[float] = mapped_column(Float, nullable=True)  # Amount of cash received
    change_amount: Mapped[float] = mapped_column(Float, nullable=True)  # Change to be given
    status: Mapped[str] = mapped_column(String(20), default="pending")  # completed, pending, cancelled
    order_status: Mapped[OrderStatus] = mapped_column(Enum(OrderStatus), default=OrderStatus.NOT_SENT)
    # Client info for fiscal/government invoices (NCF compliance)
    customer_name: Mapped[str] = mapped_column(String(200), nullable=True)
    customer_rnc: Mapped[str] = mapped_column(String(20), nullable=True) 
    # Internal reference description (not printed on receipt)
    description: Mapped[str] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    # Cancellation fields
    cancellation_reason: Mapped[str] = mapped_column(Text, nullable=True)
    cancelled_at: Mapped[datetime] = mapped_column(DateTime, nullable=True)
    cancelled_by: Mapped[int] = mapped_column(Integer, ForeignKey('users.id'), nullable=True)
    
    # Relationships
    cash_register = relationship("CashRegister", back_populates="sales")
    user = relationship("User", foreign_keys=[user_id], back_populates="sales")
    cancelled_by_user = relationship("User", foreign_keys=[cancelled_by])
    table = relationship("Table", back_populates="sales")
    ncf_sequence = relationship("NCFSequence", back_populates="sales")
    sale_items = relationship("SaleItem", back_populates="sale")


class SaleItem(db.Model):
    __tablename__ = 'sale_items'
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    sale_id: Mapped[int] = mapped_column(Integer, ForeignKey('sales.id'))
    product_id: Mapped[int] = mapped_column(Integer, ForeignKey('products.id'))
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    unit_price: Mapped[float] = mapped_column(Float, nullable=False)
    total_price: Mapped[float] = mapped_column(Float, nullable=False)
    tax_rate: Mapped[float] = mapped_column(Float, nullable=False, default=0.18)  # Almacena la tasa de impuesto del producto
    is_tax_included: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)  # Si el impuesto está incluido en el precio
    
    # Relationships
    sale = relationship("Sale", back_populates="sale_items")
    product = relationship("Product", back_populates="sale_items")


class CancelledNCF(db.Model):
    __tablename__ = 'cancelled_ncfs'
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    ncf: Mapped[str] = mapped_column(String(20), nullable=False)
    ncf_type: Mapped[NCFType] = mapped_column(Enum(NCFType), nullable=False)
    ncf_sequence_id: Mapped[int] = mapped_column(Integer, ForeignKey('ncf_sequences.id'), nullable=True)
    original_sale_id: Mapped[int] = mapped_column(Integer, ForeignKey('sales.id'), nullable=True)
    reason: Mapped[str] = mapped_column(Text)
    cancelled_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    cancelled_by: Mapped[int] = mapped_column(Integer, ForeignKey('users.id'))
    
    # Relationships
    cancelled_by_user = relationship("User")


class CreditNote(db.Model):
    __tablename__ = 'credit_notes'
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    original_sale_id: Mapped[int] = mapped_column(Integer, ForeignKey('sales.id'), nullable=False)
    ncf_sequence_id: Mapped[int] = mapped_column(Integer, ForeignKey('ncf_sequences.id'), nullable=False)
    ncf: Mapped[str] = mapped_column(String(20), nullable=False, unique=True)
    note_type: Mapped[NCFType] = mapped_column(Enum(NCFType), nullable=False)  # NOTA_CREDITO or NOTA_DEBITO
    amount: Mapped[float] = mapped_column(Float, nullable=False)
    tax_amount: Mapped[float] = mapped_column(Float, default=0.0)
    total: Mapped[float] = mapped_column(Float, nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="completed")  # completed, cancelled
    customer_name: Mapped[str] = mapped_column(String(200), nullable=True)
    customer_rnc: Mapped[str] = mapped_column(String(20), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    created_by: Mapped[int] = mapped_column(Integer, ForeignKey('users.id'), nullable=False)
    
    # Relationships
    original_sale = relationship("Sale", foreign_keys=[original_sale_id])
    ncf_sequence = relationship("NCFSequence")
    created_by_user = relationship("User", foreign_keys=[created_by])
    credit_note_items = relationship("CreditNoteItem", back_populates="credit_note")


class CreditNoteItem(db.Model):
    __tablename__ = 'credit_note_items'
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    credit_note_id: Mapped[int] = mapped_column(Integer, ForeignKey('credit_notes.id'), nullable=False)
    original_sale_item_id: Mapped[int] = mapped_column(Integer, ForeignKey('sale_items.id'), nullable=True)
    product_id: Mapped[int] = mapped_column(Integer, ForeignKey('products.id'), nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    unit_price: Mapped[float] = mapped_column(Float, nullable=False)
    total_price: Mapped[float] = mapped_column(Float, nullable=False)
    tax_rate: Mapped[float] = mapped_column(Float, nullable=False, default=0.18)
    is_tax_included: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    
    # Relationships
    credit_note = relationship("CreditNote", back_populates="credit_note_items")
    original_sale_item = relationship("SaleItem", foreign_keys=[original_sale_item_id])
    product = relationship("Product")


class StockAdjustment(db.Model):
    __tablename__ = 'stock_adjustments'
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    product_id: Mapped[int] = mapped_column(Integer, ForeignKey('products.id'), nullable=False)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey('users.id'), nullable=False)
    adjustment_type: Mapped[str] = mapped_column(String(50), nullable=False)  # 'manual', 'purchase', 'sale', 'waste', 'return'
    old_stock: Mapped[int] = mapped_column(Integer, nullable=False)
    adjustment: Mapped[int] = mapped_column(Integer, nullable=False)  # Can be positive or negative
    new_stock: Mapped[int] = mapped_column(Integer, nullable=False)
    reason: Mapped[str] = mapped_column(Text)
    reference_id: Mapped[int] = mapped_column(Integer, nullable=True)  # Purchase ID, Sale ID, etc.
    reference_type: Mapped[str] = mapped_column(String(50), nullable=True)  # 'purchase', 'sale', etc.
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    
    # Relationships
    product = relationship("Product")
    user = relationship("User")


class PasswordResetToken(db.Model):
    __tablename__ = 'password_reset_tokens'
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey('users.id'), nullable=False)
    token: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    used_at: Mapped[datetime] = mapped_column(DateTime, nullable=True)
    ip_address: Mapped[str] = mapped_column(String(45), nullable=True)  # IPv4 or IPv6
    
    # Relationships
    user = relationship("User", back_populates="password_reset_tokens")


class SystemConfiguration(db.Model):
    __tablename__ = 'system_configuration'
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    key: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    value: Mapped[str] = mapped_column(Text, nullable=True)
    description: Mapped[str] = mapped_column(Text, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)