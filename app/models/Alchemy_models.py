from datetime import datetime
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy import Boolean, CheckConstraint, String, true, Integer, Float, ForeignKey, DateTime, func

class Base(DeclarativeBase):
    """Base class for all ORM models."""
    pass

class User(Base):
    """ORM model for application users."""
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(50), unique=True, index=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    # "admin" or "worker"
    role: Mapped[str] = mapped_column(String(50), nullable=False)
    # Deactivated users cannot log in; they are kept because history refers to them
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=true())

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

class Location(Base):
    """ORM model for warehouse storage locations."""
    __tablename__ = "locations"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    capacity: Mapped[int | None] = mapped_column(Integer, nullable=True)

    products: Mapped[list["Product"]] = relationship(back_populates="location")

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
    location_id: Mapped[int | None] = mapped_column(ForeignKey("locations.id"), nullable=True)
    
    product_type: Mapped["ProductType | None"] = relationship(back_populates="products")
    location: Mapped["Location | None"] = relationship(back_populates="products")
    movements: Mapped[list["Movement"]] = relationship(back_populates="product")


# --- Piece-tracked stock: materials, orders, individual stock items, cuts ---

class Material(Base):
    """Catalogue entry for a cuttable long product (profile, guide rail, shaft...)."""
    __tablename__ = "materials"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    kind: Mapped[str | None] = mapped_column(String(50), nullable=True)
    sku: Mapped[str | None] = mapped_column(String(50), unique=True, nullable=True)
    color: Mapped[str | None] = mapped_column(String(50), nullable=True)
    # Width of material lost per cut, in millimetres
    kerf_mm: Mapped[int] = mapped_column(Integer, nullable=False, server_default="3")
    # Remainders shorter than this are written off as scrap
    min_usable_length_mm: Mapped[int] = mapped_column(Integer, nullable=False, server_default="300")

    items: Mapped[list["StockItem"]] = relationship(back_populates="material")


class Order(Base):
    """Customer order for a gate; cut pieces are assigned to it."""
    __tablename__ = "orders"

    id: Mapped[int] = mapped_column(primary_key=True)
    number: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    customer_name: Mapped[str] = mapped_column(String(150), nullable=False)
    customer_phone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    address: Mapped[str | None] = mapped_column(String(255), nullable=True)
    # "roller", "sectional" or any other free-form gate type
    gate_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    width_mm: Mapped[int | None] = mapped_column(Integer, nullable=True)
    height_mm: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # "new", "in_progress", "done", "cancelled"
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default="new")
    note: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    items: Mapped[list["StockItem"]] = relationship(back_populates="order")


class StockItem(Base):
    """One physical piece of material with its own length and history."""
    __tablename__ = "stock_items"
    __table_args__ = (CheckConstraint("length_mm > 0", name="ck_stock_items_length_positive"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    material_id: Mapped[int] = mapped_column(
        ForeignKey("materials.id", name="fk_stock_items_material_id"), nullable=False, index=True
    )
    length_mm: Mapped[int] = mapped_column(Integer, nullable=False)
    # "in_stock", "reserved", "used", "cut", "scrap"
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default="in_stock", index=True)
    location_id: Mapped[int | None] = mapped_column(
        ForeignKey("locations.id", name="fk_stock_items_location_id"), nullable=True
    )
    # The piece this one was cut from, and the operation that produced it
    parent_id: Mapped[int | None] = mapped_column(
        ForeignKey("stock_items.id", name="fk_stock_items_parent_id"), nullable=True, index=True
    )
    cut_operation_id: Mapped[int | None] = mapped_column(
        ForeignKey("cut_operations.id", name="fk_stock_items_cut_operation_id", use_alter=True),
        nullable=True,
        index=True,
    )
    order_id: Mapped[int | None] = mapped_column(
        ForeignKey("orders.id", name="fk_stock_items_order_id"), nullable=True, index=True
    )
    note: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    material: Mapped["Material"] = relationship(back_populates="items")
    location: Mapped["Location | None"] = relationship()
    order: Mapped["Order | None"] = relationship(back_populates="items")
    parent: Mapped["StockItem | None"] = relationship(remote_side=[id], foreign_keys=[parent_id])
    cut_operation: Mapped["CutOperation | None"] = relationship(
        back_populates="results", foreign_keys=[cut_operation_id]
    )

    @property
    def code(self) -> str:
        """Human-readable number to write on the piece."""
        return f"T-{self.id:06d}"


class CutOperation(Base):
    """A single cutting of one stock item into several pieces."""
    __tablename__ = "cut_operations"

    id: Mapped[int] = mapped_column(primary_key=True)
    source_item_id: Mapped[int] = mapped_column(
        ForeignKey("stock_items.id", name="fk_cut_operations_source_item_id"), nullable=False, index=True
    )
    user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", name="fk_cut_operations_user_id"), nullable=True
    )
    kerf_mm: Mapped[int] = mapped_column(Integer, nullable=False)
    # Total length consumed by the saw in this operation
    kerf_loss_mm: Mapped[int] = mapped_column(Integer, nullable=False)
    note: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    source_item: Mapped["StockItem"] = relationship(foreign_keys=[source_item_id])
    user: Mapped["User | None"] = relationship()
    results: Mapped[list["StockItem"]] = relationship(
        back_populates="cut_operation", foreign_keys="StockItem.cut_operation_id"
    )
