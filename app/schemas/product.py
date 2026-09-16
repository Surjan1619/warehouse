from pydantic import BaseModel, Field, ConfigDict

# --- Product Type Schemas ---
class ProductTypeBase(BaseModel):
    """Base schema for product category validation."""
    name: str = Field(..., min_length=1, max_length=100)
    required_attributes: dict | None = None

class ProductTypeCreate(ProductTypeBase):
    """Schema for creating a new product type."""
    pass

class ProductTypeRead(ProductTypeBase):
    """Schema for reading product type data."""
    id: int

    model_config = ConfigDict(from_attributes=True)


# --- Product and Characteristics Schemas ---
class ProductBase(BaseModel):
    """Base schema for product validation (common attributes)."""
    name: str = Field(..., min_length=1)
    length: float | None = Field(None, ge=0)
    width: float | None = Field(None, ge=0)
    thickness: float | None = Field(None, ge=0)
    shape: str | None = Field(None, max_length=50)
    weight: float | None = Field(None, ge=0)
    quantity: int | None = Field(None, ge=0)
    product_type_id: int | None = None

class ProductCreate(ProductBase):
    """Schema for registering a new product."""
    pass

class ProductUpdate(BaseModel):
    """Schema for updating partial product information."""
    length: float | None = Field(None, ge=0)
    width: float | None = Field(None, ge=0)
    thickness: float | None = Field(None, ge=0)
    shape: str | None = Field(None, max_length=50)
    weight: float | None = Field(None, ge=0)
    quantity: int | None = Field(None, ge=0)
    product_type_id: int | None = None

class ProductRead(ProductBase):
    """Schema for reading product data, including nested category info."""
    id: int
    product_type: ProductTypeRead | None = None 

    model_config = ConfigDict(from_attributes=True)
