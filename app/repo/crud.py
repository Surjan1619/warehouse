from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import func, select
from sqlalchemy.orm import joinedload
from app.models.Alchemy_models import User, Product, ProductType, Location, Movement
from app.core.errors import DomainError, NotFoundError
from app.core.security import hash_password
from app.repo import activity, inventory

async def get_user_by_username(db: AsyncSession, username: str):
    """Retrieve a single user by username, or None if not found."""
    result = await db.execute(select(User).where(User.username == username))
    return result.scalar_one_or_none()

# User CRUD
async def create_user(db: AsyncSession, username: str, role: str, plain_password: str):
    """Hash password and persist a new user entity."""
    hashed_password = hash_password(plain_password)
    user = User(username=username, role=role, password_hash=hashed_password)
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user

async def get_user(db: AsyncSession, user_id: int):
    """Retrieve a single user by their primary key."""
    result = await db.execute(select(User).where(User.id == user_id))
    return result.scalar_one_or_none()

async def get_all_users(db: AsyncSession):
    """Fetch all users ordered by id."""
    result = await db.execute(select(User).order_by(User.id))
    return result.scalars().all()

async def create_user_checked(db: AsyncSession, username: str, role: str, plain_password: str):
    """Create a user, refusing a username that is already taken."""
    if await get_user_by_username(db, username):
        raise DomainError("User already exists", status_code=409)
    return await create_user(db, username=username, role=role, plain_password=plain_password)

async def update_user(db: AsyncSession, user_id: int, data: dict, acting_user_id: int):
    """
    Change password, role or active flag of a user.
    An admin cannot deactivate or demote their own account, so the system
    is never left without a way to manage users.
    """
    user = await get_user(db, user_id)
    if user is None:
        raise NotFoundError("User not found")

    if user.id == acting_user_id:
        if data.get("is_active") is False:
            raise DomainError("You cannot deactivate your own account")
        if data.get("role") not in (None, user.role):
            raise DomainError("You cannot change your own role")

    if data.get("password"):
        user.password_hash = hash_password(data["password"])
    if data.get("role") is not None:
        user.role = data["role"]
    if data.get("is_active") is not None:
        user.is_active = data["is_active"]

    await db.commit()
    await db.refresh(user)
    return user

# Product CRUD
async def get_all_product_types(db: AsyncSession):
    """Fetch all available product types."""
    result = await db.execute(select(ProductType))
    return result.scalars().all()

async def create_product_type(db: AsyncSession, name: str, required_attributes: dict = None):
    """Persist a new product type, or return the existing one if it already exists."""
    result = await db.execute(select(ProductType).where(ProductType.name == name))
    existing = result.scalar_one_or_none()
    if existing:
        return existing
        
    product_type = ProductType(name=name, required_attributes=required_attributes or {})
    db.add(product_type)
    await db.commit()
    await db.refresh(product_type)
    return product_type

async def create_product(db: AsyncSession, name: str, quantity: int = 0, product_type_id: int = None, length: float = None, width: float = None, thickness: float = None, shape: str = None, weight: float = None, location_id: int = None, user_id: int | None = None, unit: str = "шт"):
    """Persist a new product. A starting quantity is journalled as goods received."""
    product = Product(
        name=name,
        quantity=quantity,
        unit=unit,
        product_type_id=product_type_id,
        location_id=location_id,
        length=length,
        width=width,
        thickness=thickness,
        shape=shape,
        weight=weight
    )
    db.add(product)
    if quantity:
        await db.flush()  # assigns product.id
        if user_id is not None and await db.get(User, user_id) is None:
            user_id = None
        type_name = await inventory.type_name_of(db, product)
        inventory.add_product_event(db, product, activity.PRODUCT_RECEIVE, quantity, user_id, type_name, new=True)
    await db.commit()
    # Re-fetch the product with the relationship loaded to satisfy the Pydantic schema
    result = await db.execute(
        select(Product)
        .options(joinedload(Product.product_type), joinedload(Product.location))
        .where(Product.id == product.id)
    )
    return result.scalar_one()

async def get_all_products(db: AsyncSession):
    """Fetch all available products with their associated ProductType."""
    result = await db.execute(select(Product).options(joinedload(Product.product_type), joinedload(Product.location)))
    return result.scalars().unique().all()

async def delete_product(db: AsyncSession, product_id: int):
    """
    Delete a product by ID. A product that was restocked or issued keeps its
    history in `movements`, so it cannot be deleted.
    """
    result = await db.execute(select(Product).where(Product.id == product_id))
    product = result.scalar_one_or_none()
    if product:
        moved = await db.scalar(select(func.count()).select_from(Movement).where(Movement.product_id == product_id))
        if moved:
            raise DomainError("Product has stock movements and cannot be deleted", status_code=409)
        await db.delete(product)
        await db.commit()
        return True
    return False

async def get_products_by_type(db: AsyncSession, product_type_id: int):
    """Check if any products are linked to a specific type."""
    result = await db.execute(select(Product).where(Product.product_type_id == product_type_id))
    return result.scalars().all()

async def delete_product_type(db: AsyncSession, product_type_id: int):
    """Delete a product type if no products are linked to it."""
    linked_products = await get_products_by_type(db, product_type_id)
    if linked_products:
        return False
    
    result = await db.execute(select(ProductType).where(ProductType.id == product_type_id))
    product_type = result.scalar_one_or_none()
    if product_type:
        await db.delete(product_type)
        await db.commit()
        return True
    return False

# Location CRUD
async def get_all_locations(db: AsyncSession):
    """Fetch all warehouse locations."""
    result = await db.execute(select(Location))
    return result.scalars().all()

async def create_location(db: AsyncSession, name: str, capacity: int = None):
    """Persist a new location, refusing a name that is already taken."""
    existing = await db.execute(select(Location).where(Location.name == name))
    if existing.scalar_one_or_none():
        raise DomainError("Location with this name already exists", status_code=409)
    location = Location(name=name, capacity=capacity)
    db.add(location)
    await db.commit()
    await db.refresh(location)
    return location
