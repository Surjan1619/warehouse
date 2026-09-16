from pydantic import BaseModel, Field, ConfigDict

class UserBase(BaseModel):
    """Base schema for User data validation."""
    username: str = Field(..., min_length=3, max_length=50)
    role: str = Field(..., min_length=2, max_length=50)

class UserCreate(UserBase):
    """Schema for registering a new user."""
    password: str = Field(..., min_length=6)

class UserRead(UserBase):
    """Schema for returning user data (excluding sensitive fields like password)."""
    id: int

    # Allows Pydantic to read ORM model attributes directly
    model_config = ConfigDict(from_attributes=True)
