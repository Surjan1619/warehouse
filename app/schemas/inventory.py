from pydantic import BaseModel, Field, ConfigDict

class CutProductRequest(BaseModel):
    """Request schema for processing a product cut (splitting/modifying)."""
    source_product_id: int
    cut_length: float = Field(gt=0)
    pieces_count: int = Field(ge=1)

    model_config = ConfigDict(from_attributes=True)

class SaleProductRequest(BaseModel):
    """Request schema for selling products."""
    product_id: int
    quantity: int = Field(ge=1)

    model_config = ConfigDict(from_attributes=True)

class InventoryResponse(BaseModel):
    """General response schema for inventory update operations."""
    status: str
    product_id: int
    new_quantity: int

    model_config = ConfigDict(from_attributes=True)
