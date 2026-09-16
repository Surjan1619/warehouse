from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.db import get_db
from app.core.security import verify_password
from app.core.jwt import create_access_token
from app.repo.crud import create_user, get_user_by_username
from app.schemas.user import UserCreate

# Router instance for authentication-related endpoints
router = APIRouter()

@router.post("/register")
async def register(user_in: UserCreate, db: AsyncSession = Depends(get_db)):
    """
    Register a new user in the system.
    Checks if username is unique, then creates the user record.
    """
    user = await get_user_by_username(db, username=user_in.username)
    if user:
        raise HTTPException(status_code=400, detail="User already exists")
    user = await create_user(db, username=user_in.username, role=user_in.role, plain_password=user_in.password)
    return {"id": user.id, "username": user.username}

@router.post("/login")
async def login(db: AsyncSession = Depends(get_db), form_data: OAuth2PasswordRequestForm = Depends()):
    """
    Login endpoint. Expects OAuth2 password form data (username, password).
    Verifies credentials and returns a JWT access token if valid.
    """
    user = await get_user_by_username(db, username=form_data.username)
    # Check if user exists and verify password hash against plaintext password
    if not user or not verify_password(form_data.password, user.password_hash):
        raise HTTPException(status_code=400, detail="Incorrect username or password")
    
    # Generate and return a JWT access token upon successful authentication
    access_token = create_access_token(subject=str(user.id))
    return {"access_token": access_token, "token_type": "bearer"}
