from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.db import get_db
from app.core.security import verify_password
from app.core.jwt import create_access_token
from app.models.Alchemy_models import User
from app.repo.crud import get_user_by_username
from app.schemas.user import LoginResponse, UserRead

# Router instance for authentication-related endpoints.
# There is no public registration: users are created by an admin via /users.
router = APIRouter()


@router.post("/login", response_model=LoginResponse)
async def login(db: AsyncSession = Depends(get_db), form_data: OAuth2PasswordRequestForm = Depends()):
    """
    Login endpoint. Expects OAuth2 password form data (username, password).
    Returns a JWT access token and the user, so the client knows the role.
    """
    user = await get_user_by_username(db, username=form_data.username)
    # The same answer for a wrong name, a wrong password and a deactivated
    # account, so the response does not reveal which usernames exist
    if not user or not verify_password(form_data.password, user.password_hash) or not user.is_active:
        raise HTTPException(status_code=400, detail="Incorrect username or password")

    access_token = create_access_token(subject=str(user.id))
    return {"access_token": access_token, "token_type": "bearer", "user": user}


@router.get("/me", response_model=UserRead)
async def me(current_user: User = Depends(get_current_user)):
    """Return the user the token belongs to."""
    return current_user
