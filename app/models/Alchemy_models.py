from datetime import datetime
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy import String, Integer, Float, ForeignKey, DateTime, func

class Base(DeclarativeBase):
    """Base class for all ORM models."""
    pass

class User(Base):
    """ORM model for application users."""
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(50), unique=True, index=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(50), nullable=False)

from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy import String, Integer, Float, ForeignKey, DateTime, func

class ProductType(Base):
    """ORM model for product categories."""
    __tablename__ = "product_types"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    required_attributes: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=True)
    
    # Relationship to products
    products: Mapped[list["Product"]] = relationship(back_populates="product_type")

class Movement(Base):
    """ORM model for tracking changes in product quantities."""
    __tablename__ = "movements"

    id: Mapped[int] = mapped_column(primary_key=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"), nullable=False)
    # Types: "cut_source", "cut_result", "sale", "purchase"
    change_type: Mapped[str] = mapped_column(String(50), nullable=False) 
    quantity_changed: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    product: Mapped["Product"] = relationship(back_populates="movements")

class Product(Base):
    """ORM model for warehouse items."""
    __tablename__ = "products"

    id: Mapped[int] = mapped_column(primary_key=True)
    length: Mapped[float | None] = mapped_column(Float, nullable=True)
    width: Mapped[float | None] = mapped_column(Float, nullable=True)
    thickness: Mapped[float | None] = mapped_column(Float, nullable=True)
    shape: Mapped[str | None] = mapped_column(String(50), nullable=True)
    weight: Mapped[float | None] = mapped_column(Float, nullable=True)
    quantity: Mapped[int | None] = mapped_column(Integer, nullable=True)
    name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    product_type_id: Mapped[int | None] = mapped_column(ForeignKey("product_types.id"), nullable=True)
    
    product_type: Mapped["ProductType | None"] = relationship(back_populates="products")
    movements: Mapped[list["Movement"]] = relationship(back_populates="product")
