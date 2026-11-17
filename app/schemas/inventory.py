from pydantic import BaseModel, Field


class QuantityChange(BaseModel):
    """How many pieces of a product arrive or leave."""
    quantity: int = Field(..., ge=1, le=100000)
