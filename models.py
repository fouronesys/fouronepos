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
    ADMINISTRADOR = "administrador"
    CAJERO = "cajero"
    MESERO = "mesero"


class NCFType(enum.Enum):
    CONSUMO = "consumo"
    CREDITO_FISCAL = "credito_fiscal"
    GUBERNAMENTAL = "gubernamental"


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
    role: Mapped[UserRole] = mapped_column(Enum(UserRole), nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    must_change_password: Mapped[bool] = mapped_column(Boolean, default=False)
    last_login: Mapped[datetime] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    
    # Relationships
    sales = relationship("Sale", back_populates="user")
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


class Product(db.Model):
    __tablename__ = 'products'
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str] = mapped_column(Text)
    category_id: Mapped[int] = mapped_column(Integer, ForeignKey('categories.id'))
    cost: Mapped[float] = mapped_column(Float, default=0.0)
    price: Mapped[float] = mapped_column(Float, nullable=False)
    tax_rate: Mapped[float] = mapped_column(Float, default=0.18)  # 18% ITBIS by default
    stock: Mapped[int] = mapped_column(Integer, default=0)
    min_stock: Mapped[int] = mapped_column(Integer, default=5)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    
    # Relationships
    category = relationship("Category", back_populates="products")
    sale_items = relationship("SaleItem", back_populates="product")


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
    total: Mapped[float] = mapped_column(Float, nullable=False)
    payment_method: Mapped[str] = mapped_column(String(50), default="efectivo")
    status: Mapped[str] = mapped_column(String(20), default="pending")  # completed, pending, cancelled
    order_status: Mapped[OrderStatus] = mapped_column(Enum(OrderStatus), default=OrderStatus.NOT_SENT)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    
    # Relationships
    cash_register = relationship("CashRegister", back_populates="sales")
    user = relationship("User", back_populates="sales")
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
    
    # Relationships
    sale = relationship("Sale", back_populates="sale_items")
    product = relationship("Product", back_populates="sale_items")


class CancelledNCF(db.Model):
    __tablename__ = 'cancelled_ncfs'
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    ncf: Mapped[str] = mapped_column(String(20), nullable=False)
    ncf_type: Mapped[NCFType] = mapped_column(Enum(NCFType), nullable=False)
    reason: Mapped[str] = mapped_column(Text)
    cancelled_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    cancelled_by: Mapped[int] = mapped_column(Integer, ForeignKey('users.id'))
    
    # Relationships
    cancelled_by_user = relationship("User")


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