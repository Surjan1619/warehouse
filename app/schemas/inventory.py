from pydantic import BaseModel, Field, ConfigDict

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
