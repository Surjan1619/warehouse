from passlib.context import CryptContext

# Use sha256_crypt for secure password hashing. 
# It provides strong, salting-based protection compatible with common server environments.
pwd_context = CryptContext(schemes=["sha256_crypt"], deprecated="auto")

def hash_password(password: str) -> str:
    """Generate a secure cryptographic hash for the provided plaintext password."""
    return pwd_context.hash(password)

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify if the provided plaintext password matches the stored hash."""
    return pwd_context.verify(plain_password, hashed_password)
