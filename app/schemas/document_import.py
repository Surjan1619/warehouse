"""Putting a supplier's specification into stock: the preview and the result."""
from datetime import date, datetime, timezone
from typing import Literal

from pydantic import BaseModel, ConfigDict, field_serializer

from app.schemas.product import ProductRead
from app.schemas.stock import MaterialRead, UserBrief


class ImportRow(BaseModel):
    """One row of the document and what it would become."""

    line: int
    code: str | None
    article: str | None
    name: str
    color: str | None
    unit: str
    quantity: str | None  # as in the document: metres for cuttable stock
    length_mm: int | None
    kind: Literal["stock", "goods"] | None  # None when the row cannot go into stock
    pieces: int | None
    count: int | None
    problem: str | None
    # Name of the material or product to be created when nothing has the code yet
    title: str
    material: MaterialRead | None = None
    product: ProductRead | None = None


class ImportSummary(BaseModel):
    stock_rows: int
    stock_pieces: int
    new_materials: int
    goods_rows: int
    new_products: int
    problems: int


class DocumentImportRead(BaseModel):
    id: int
    number: str | None
    doc_date: date | None
    supplier: str | None
    filename: str | None
    user: UserBrief | None = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

    @field_serializer("created_at")
    def created_at_as_utc(self, value: datetime) -> str:
        return value.replace(tzinfo=timezone.utc).isoformat()


class ImportPreview(BaseModel):
    number: str | None
    date: date | None
    supplier: str | None
    filename: str | None
    rows: list[ImportRow]
    summary: ImportSummary
    # Set when this document is already in stock
    previous: DocumentImportRead | None = None
    can_import: bool


class ImportedRow(BaseModel):
    line: int
    kind: Literal["stock", "goods"]
    title: str
    pieces: int | None = None
    length_mm: int | None = None
    first_item_id: int | None = None
    last_item_id: int | None = None
    count: int | None = None
    unit: str | None = None
    quantity_after: int | None = None


class ImportResult(BaseModel):
    import_id: int
    number: str | None
    date: str | None
    supplier: str | None
    filename: str | None
    rows: int
    stock_pieces: int
    new_materials: int
    new_products: int
    result: list[ImportedRow]
