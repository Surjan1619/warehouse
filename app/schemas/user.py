from typing import Literal

from pydantic import BaseModel, Field, ConfigDict

# "admin" manages users; "worker" is a warehouse employee
Role = Literal["admin", "worker"]


class UserCreate(BaseModel):
    """Schema for creating a user (admin only)."""
    username: str = Field(..., min_length=3, max_length=50)
    password: str = Field(..., min_length=6, max_length=128)
    role: Role = "worker"


class UserUpdate(BaseModel):
    """Schema for changing a user (admin only). Only the given fields change."""
    password: str | None = Field(None, min_length=6, max_length=128)
    role: Role | None = None
    is_active: bool | None = None


class UserRead(BaseModel):
    """Schema for returning user data (excluding sensitive fields like password)."""
    id: int
    username: str
    role: str
    is_active: bool

    # Allows Pydantic to read ORM model attributes directly
    model_config = ConfigDict(from_attributes=True)


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserRead
