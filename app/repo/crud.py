from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models.Alchemy_models import User, Product
from app.core.security import hash_password

async def get_user_by_username(db: AsyncSession, username: str):
    result = await db.execute(select(User).where(User.username == username))
    return result.scalar_one_or_none()

# User CRUD
async def create_user(db: AsyncSession, username: str, role: str, plain_password: str):
    hashed_password = hash_password(plain_password)
    user = User(username=username, role=role, password_hash=hashed_password)
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user

async def get_user(db: AsyncSession, user_id: int):
    result = await db.execute(select(User).where(User.id == user_id))
    return result.scalar_one_or_none()

# Product CRUD
async def create_product(db: AsyncSession, name: str, quantity: int = 0):
    product = Product(name=name, quantity=quantity)
    db.add(product)
    await db.commit()
    await db.refresh(product)
    return product

async def get_all_products(db: AsyncSession):
    result = await db.execute(select(Product))
    return result.scalars().all()
