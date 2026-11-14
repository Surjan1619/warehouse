from typing import List

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_admin
from app.core.db import get_db
from app.models.Alchemy_models import User
from app.repo import crud
from app.schemas.user import UserCreate, UserRead, UserUpdate

# Every endpoint here is admin-only
router = APIRouter(dependencies=[Depends(require_admin)])


@router.get("/", response_model=List[UserRead])
async def get_users(db: AsyncSession = Depends(get_db)):
    """Fetch all users."""
    return await crud.get_all_users(db)


@router.post("/", response_model=UserRead, status_code=201)
async def add_user(user_in: UserCreate, db: AsyncSession = Depends(get_db)):
    """Create a user."""
    return await crud.create_user_checked(
        db, username=user_in.username, role=user_in.role, plain_password=user_in.password
    )


@router.patch("/{user_id}", response_model=UserRead)
async def edit_user(
    user_id: int,
    user_in: UserUpdate,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin),
):
    """Change a user's password or role, or activate / deactivate the account."""
    return await crud.update_user(db, user_id, user_in.model_dump(exclude_unset=True), acting_user_id=admin.id)
