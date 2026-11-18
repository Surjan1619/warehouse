from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, ConfigDict, field_serializer

from app.schemas.stock import MaterialRead, UserBrief

Action = Literal["receive", "cut", "use", "scrap", "assemble", "product_receive", "product_issue", "import", "reset"]


class StockItemBrief(BaseModel):
    id: int
    code: str
    length_mm: int
    model_config = ConfigDict(from_attributes=True)


class ProductTypeBrief(BaseModel):
    id: int
    name: str
    model_config = ConfigDict(from_attributes=True)


class ProductBrief(BaseModel):
    id: int
    name: str | None = None
    product_type: ProductTypeBrief | None = None
    model_config = ConfigDict(from_attributes=True)


class ActivityEventRead(BaseModel):
    id: int
    created_at: datetime
    action: Action
    user: UserBrief | None = None
    material: MaterialRead | None = None
    stock_item: StockItemBrief | None = None
    cut_operation_id: int | None = None
    # Set for piece goods; None after the product was deleted (its name stays in details)
    product: ProductBrief | None = None
    quantity: int
    length_mm: int
    details: dict | None = None
    model_config = ConfigDict(from_attributes=True)

    @field_serializer("created_at")
    def created_at_as_utc(self, value: datetime) -> str:
        # The database keeps UTC without an offset. Stating the offset lets
        # the browser show the moment in the viewer's own time zone.
        return value.replace(tzinfo=timezone.utc).isoformat()


class ActivityPage(BaseModel):
    items: list[ActivityEventRead]
    # Number of entries matching the filters, regardless of limit and offset
    total: int
