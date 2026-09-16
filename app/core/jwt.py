import jwt
from datetime import datetime, timedelta, timezone
from typing import Any
from app.core.config import settings

# Retrieve JWT configuration from application settings
SECRET_KEY = settings.JWT_SECRET
ALGORITHM = settings.ALGORITHM
ACCESS_TOKEN_EXPIRE_MINUTES = settings.ACCESS_TOKEN_EXPIRE_MINUTES

def create_access_token(subject: str | Any, expires_delta: timedelta = None) -> str:
    """
    Generate a new JWT access token.
    'subject' (sub) represents the identifier of the token owner (e.g., user ID).
    """
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        # Default expiration time from settings if no specific delta provided
        expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    
    # Token payload: expiration timestamp and subject identifier
    to_encode = {"exp": expire, "sub": str(subject)}
    
    # Encode with secret key and specified algorithm (HS256 by default)
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt
