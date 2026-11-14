from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import jwt, JWTError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.core.jwt import SECRET_KEY, ALGORITHM
from app.models.Alchemy_models import User
from app.repo.crud import get_user

ROLE_ADMIN = "admin"

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/login")

_unauthorized = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Invalid or expired token",
    headers={"WWW-Authenticate": "Bearer"},
)


async def get_current_user(
    db: AsyncSession = Depends(get_db), token: str = Depends(oauth2_scheme)
) -> User:
    """
    Load the user the token belongs to.
    A token of a deleted or deactivated user is rejected even if it has not expired.
    """
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id = int(payload.get("sub"))
    except (JWTError, TypeError, ValueError):
        raise _unauthorized

    user = await get_user(db, user_id)
    if user is None or not user.is_active:
        raise _unauthorized
    return user


async def require_admin(current_user: User = Depends(get_current_user)) -> User:
    """Allow the request only for users with the admin role."""
    if current_user.role != ROLE_ADMIN:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required")
    return current_user
