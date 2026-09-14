from passlib.context import CryptContext

# Настройка контекста для хэширования (используем bcrypt)
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def hash_password(password: str) -> str:
    """password hashing"""
    return pwd_context.hash(password)

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Hash to Hash verify"""
    return pwd_context.verify(plain_password, hashed_password)
