from datetime import date, datetime
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy import Boolean, CheckConstraint, Date, String, true, Integer, Float, ForeignKey, DateTime, UniqueConstraint, func

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
    # "receive" (restocked), "issue" (taken out of stock); older rows may hold "sale", "purchase"
    change_type: Mapped[str] = mapped_column(String(50), nullable=False)
    # Positive when stock grows, negative when it shrinks
    quantity_changed: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    # Who made the change; None for rows written before this column existed
    user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", name="fk_movements_user_id"), nullable=True
    )
    # The assembly the goods were taken out for, if any
    assembly_id: Mapped[int | None] = mapped_column(
        ForeignKey("assemblies.id", name="fk_movements_assembly_id"), nullable=True, index=True
    )
    # The supplier's document the goods came with, if they were imported from one
    document_import_id: Mapped[int | None] = mapped_column(
        ForeignKey("document_imports.id", name="fk_movements_document_import_id"), nullable=True, index=True
    )

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
    # What one unit of quantity is: "шт", "пар" (pair), "кмт" (set). 100 pairs stay 100.
    unit: Mapped[str] = mapped_column(String(10), nullable=False, server_default="шт")
    # The supplier's code ("Код" in the specification); imported rows are matched by it
    sku: Mapped[str | None] = mapped_column(String(50), unique=True, nullable=True)
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
    # Width of material lost per cut, in millimetres; 0 means cuts are not accounted for
    kerf_mm: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
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
    # "in_stock", "reserved", "used", "cut", "scrap"; "cancelled" for a piece of a cancelled cut
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
    # Who put the piece into the system: received it, or made the cut that produced it
    created_by_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", name="fk_stock_items_created_by_id"), nullable=True, index=True
    )
    # The supplier's document the piece came with, if it was imported from one
    document_import_id: Mapped[int | None] = mapped_column(
        ForeignKey("document_imports.id", name="fk_stock_items_document_import_id"), nullable=True, index=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    material: Mapped["Material"] = relationship(back_populates="items")
    created_by: Mapped["User | None"] = relationship()
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
    # Set when the cut is undone: the source is back in stock, the results are "cancelled"
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    cancelled_by_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", name="fk_cut_operations_cancelled_by_id"), nullable=True
    )
    # The assembly the cut was made for, if any
    assembly_id: Mapped[int | None] = mapped_column(
        ForeignKey("assemblies.id", name="fk_cut_operations_assembly_id"), nullable=True, index=True
    )

    source_item: Mapped["StockItem"] = relationship(foreign_keys=[source_item_id])
    user: Mapped["User | None"] = relationship(foreign_keys=[user_id])
    results: Mapped[list["StockItem"]] = relationship(
        back_populates="cut_operation", foreign_keys="StockItem.cut_operation_id", order_by="StockItem.id"
    )


class Assembly(Base):
    """
    One finished product (e.g. a gate) put together from stock: the cuts made
    for it and the piece goods taken out for it, saved in one transaction.
    """
    __tablename__ = "assemblies"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str | None] = mapped_column(String(150), nullable=True)
    note: Mapped[str | None] = mapped_column(String(500), nullable=True)
    # Generated by the browser for each draft; a repeated submit returns the saved assembly
    client_key: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", name="fk_assemblies_user_id"), nullable=True, index=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), index=True)

    user: Mapped["User | None"] = relationship()
    cuts: Mapped[list["CutOperation"]] = relationship(order_by="CutOperation.id")
    movements: Mapped[list["Movement"]] = relationship(order_by="Movement.id")


class DocumentImport(Base):
    """
    A supplier's specification put into stock from its Excel file. Remembered so
    that the same delivery is not put into stock twice (e.g. its copy in another
    currency): the number with the date, and the file itself, are unique.
    """
    __tablename__ = "document_imports"
    __table_args__ = (UniqueConstraint("number", "doc_date", name="uq_document_imports_number_date"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    number: Mapped[str | None] = mapped_column(String(50), nullable=True)
    doc_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    supplier: Mapped[str | None] = mapped_column(String(255), nullable=True)
    filename: Mapped[str | None] = mapped_column(String(255), nullable=True)
    file_sha256: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", name="fk_document_imports_user_id"), nullable=True, index=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), index=True)

    user: Mapped["User | None"] = relationship()


class ActivityEvent(Base):
    """
    One entry of the activity journal: who did what, with what, and when.

    The journal is append-only. `quantity` and `length_mm` hold the totals the
    event accounts for, so reports are sums over this table.
    """
    __tablename__ = "activity_log"

    id: Mapped[int] = mapped_column(primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), index=True)
    user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", name="fk_activity_log_user_id"), nullable=True, index=True
    )
    # One of the names in app/repo/activity.py: "receive", "cut", "use", "scrap", ...
    action: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    material_id: Mapped[int | None] = mapped_column(
        ForeignKey("materials.id", name="fk_activity_log_material_id"), nullable=True, index=True
    )
    # The piece the event is about, when it concerns a single one
    stock_item_id: Mapped[int | None] = mapped_column(
        ForeignKey("stock_items.id", name="fk_activity_log_stock_item_id"), nullable=True, index=True
    )
    cut_operation_id: Mapped[int | None] = mapped_column(
        ForeignKey("cut_operations.id", name="fk_activity_log_cut_operation_id"), nullable=True
    )
    # The piece good the event is about. Deleting the product keeps the entry:
    # its name stays in `details`
    product_id: Mapped[int | None] = mapped_column(
        ForeignKey("products.id", name="fk_activity_log_product_id", ondelete="SET NULL"), nullable=True, index=True
    )
    # Number of pieces and their total length in millimetres
    quantity: Mapped[int] = mapped_column(Integer, nullable=False, server_default="1")
    length_mm: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    # Anything else worth keeping, e.g. the old and the new value of an edit
    details: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    user: Mapped["User | None"] = relationship()
    material: Mapped["Material | None"] = relationship()
    stock_item: Mapped["StockItem | None"] = relationship()
    product: Mapped["Product | None"] = relationship()
