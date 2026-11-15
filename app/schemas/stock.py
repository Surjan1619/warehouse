from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.product import LocationRead

ItemStatus = Literal["in_stock", "reserved", "used", "cut", "scrap"]
OrderStatus = Literal["new", "in_progress", "done", "cancelled"]


# --- Materials ---
class MaterialBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    kind: str | None = Field(None, max_length=50)
    sku: str | None = Field(None, max_length=50)
    color: str | None = Field(None, max_length=50)
    kerf_mm: int = Field(0, ge=0, le=100)
    min_usable_length_mm: int = Field(300, ge=0)


class MaterialCreate(MaterialBase):
    pass


class MaterialUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=100)
    kind: str | None = Field(None, max_length=50)
    sku: str | None = Field(None, max_length=50)
    color: str | None = Field(None, max_length=50)
    kerf_mm: int | None = Field(None, ge=0, le=100)
    min_usable_length_mm: int | None = Field(None, ge=0)


class MaterialRead(MaterialBase):
    id: int
    model_config = ConfigDict(from_attributes=True)


# --- Orders ---
class OrderBase(BaseModel):
    customer_name: str = Field(..., min_length=1, max_length=150)
    customer_phone: str | None = Field(None, max_length=50)
    address: str | None = Field(None, max_length=255)
    gate_type: str | None = Field(None, max_length=50)
    width_mm: int | None = Field(None, gt=0)
    height_mm: int | None = Field(None, gt=0)
    note: str | None = Field(None, max_length=500)


class OrderCreate(OrderBase):
    # Generated automatically when omitted
    number: str | None = Field(None, min_length=1, max_length=50)


class OrderUpdate(BaseModel):
    customer_name: str | None = Field(None, min_length=1, max_length=150)
    customer_phone: str | None = Field(None, max_length=50)
    address: str | None = Field(None, max_length=255)
    gate_type: str | None = Field(None, max_length=50)
    width_mm: int | None = Field(None, gt=0)
    height_mm: int | None = Field(None, gt=0)
    note: str | None = Field(None, max_length=500)
    status: OrderStatus | None = None


class OrderRead(OrderBase):
    id: int
    number: str
    status: OrderStatus
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


# --- Stock items ---
class StockItemReceive(BaseModel):
    """Put new pieces of one material and length into stock."""
    material_id: int
    length_mm: int = Field(..., gt=0)
    count: int = Field(1, ge=1, le=500)
    location_id: int | None = None
    note: str | None = Field(None, max_length=500)


class StockItemUpdate(BaseModel):
    location_id: int | None = None
    note: str | None = Field(None, max_length=500)


class StockItemAssign(BaseModel):
    order_id: int


class UserBrief(BaseModel):
    """Who performed an action; only what is safe to show to any user."""
    id: int
    username: str
    model_config = ConfigDict(from_attributes=True)


class StockItemRead(BaseModel):
    id: int
    code: str
    material: MaterialRead
    length_mm: int
    status: ItemStatus
    location: LocationRead | None = None
    order: OrderRead | None = None
    parent_id: int | None = None
    cut_operation_id: int | None = None
    note: str | None = None
    # Who received the piece or made the cut that produced it; None for older records
    created_by: UserBrief | None = None
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


class StockItemHistory(BaseModel):
    """Where a piece came from and what it was cut into."""
    item: StockItemRead
    # From the direct parent up to the original piece
    ancestors: list[StockItemRead]
    # Pieces cut directly from this one
    children: list[StockItemRead]


class OrderDetail(OrderRead):
    items: list[StockItemRead]
    total_length_mm: int


# --- Cutting ---
class CutPiece(BaseModel):
    length_mm: int = Field(..., gt=0)
    # Link the piece to an order; without `used` it is reserved for that order
    order_id: int | None = None
    # The piece is consumed right away instead of going back to stock
    used: bool = False
    # Defaults to the location of the source piece
    location_id: int | None = None
    note: str | None = Field(None, max_length=500)


class CutRequest(BaseModel):
    source_item_id: int
    pieces: list[CutPiece] = Field(..., min_length=1, max_length=100)
    # Defaults to the kerf of the material
    kerf_mm: int | None = Field(None, ge=0, le=100)
    # Write the remainder off as scrap even if it is long enough to keep
    scrap_remainder: bool = False
    note: str | None = Field(None, max_length=500)


class CutRead(BaseModel):
    id: int
    source_item: StockItemRead
    kerf_mm: int
    kerf_loss_mm: int
    user_id: int | None = None
    note: str | None = None
    created_at: datetime
    # Requested pieces plus the remainder, if any
    results: list[StockItemRead]
    model_config = ConfigDict(from_attributes=True)


# --- Choosing what to cut from ---
class CutSuggestRequest(BaseModel):
    material_id: int
    # Lengths of the pieces that are needed, in millimetres
    pieces: list[Annotated[int, Field(gt=0)]] = Field(..., min_length=1, max_length=100)
    # Defaults to the kerf of the material
    kerf_mm: int | None = Field(None, ge=0, le=100)


class CutCandidate(BaseModel):
    """Interchangeable stock items (same length and location) the pieces can be cut from."""
    # The piece to take: the oldest of the group
    item: StockItemRead
    # Every item of the group, oldest first
    item_ids: list[int]
    count: int
    remainder_mm: int
    kerf_loss_mm: int
    # "none": the piece is used up; "stock": the remainder is kept; "scrap": it is too short to keep
    remainder_fate: Literal["none", "stock", "scrap"]


class CutSuggestResponse(BaseModel):
    # Length the pieces take together with the cuts between them
    required_mm: int
    # Most economical first: the smaller the remainder, the higher
    candidates: list[CutCandidate]
    # Longest free piece of this material, to explain an empty list
    longest_available_mm: int | None = None
