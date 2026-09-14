from pydantic import BaseModel, Field, ConfigDict

# --- Тип товара ---
class ProductTypeBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)

class ProductTypeCreate(ProductTypeBase):
    pass

class ProductTypeRead(ProductTypeBase):
    id: int

    model_config = ConfigDict(from_attributes=True)


# --- Товар и его характеристики ---
class ProductBase(BaseModel):
    length: float | None = Field(None, ge=0)
    width: float | None = Field(None, ge=0)
    thickness: float | None = Field(None, ge=0)
    shape: str | None = Field(None, max_length=50)
    weight: float | None = Field(None, ge=0)
    quantity: int | None = Field(None, ge=0)
    product_type_id: int | None = None

class ProductCreate(ProductBase):
    pass

# Схема для обновления (все поля опциональные, чтобы можно было изменить только часть характеристик)
class ProductUpdate(BaseModel):
    length: float | None = Field(None, ge=0)
    width: float | None = Field(None, ge=0)
    thickness: float | None = Field(None, ge=0)
    shape: str | None = Field(None, max_length=50)
    weight: float | None = Field(None, ge=0)
    quantity: int | None = Field(None, ge=0)
    product_type_id: int | None = None

class ProductRead(ProductBase):
    id: int
    product_type: ProductTypeRead | None = None # Вложенная схема для удобного отображения типа товара

    model_config = ConfigDict(from_attributes=True)