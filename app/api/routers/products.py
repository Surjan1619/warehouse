from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List

from app.api.deps import get_current_user, require_admin
from app.core.db import get_db
from app.models.Alchemy_models import User
from app.repo import inventory
from app.repo.crud import (
    get_all_products, 
    create_product, 
    get_all_product_types, 
    create_product_type,
    delete_product,
    delete_product_type
)
from app.schemas.product import (
    ProductRead, 
    ProductCreate, 
    ProductTypeRead, 
    ProductTypeCreate
)
from app.schemas.inventory import QuantityChange

router = APIRouter()

@router.get("/", response_model=List[ProductRead])
async def get_products(db: AsyncSession = Depends(get_db)):
    """Fetch all products."""
    return await get_all_products(db)

@router.get("/types", response_model=List[ProductTypeRead])
async def get_product_types(db: AsyncSession = Depends(get_db)):
    """Fetch all product types."""
    return await get_all_product_types(db)

@router.post("/types", response_model=ProductTypeRead, dependencies=[Depends(require_admin)])
async def add_product_type(type_in: ProductTypeCreate, db: AsyncSession = Depends(get_db)):
    """Create a new product type. Admin only."""
    return await create_product_type(db, name=type_in.name, required_attributes=type_in.required_attributes)

@router.post("/", response_model=ProductRead)
async def add_product(
    product_in: ProductCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create a new product. A starting quantity is journalled as goods received."""
    return await create_product(
        db, 
        name=product_in.name,
        quantity=product_in.quantity or 0, 
        product_type_id=product_in.product_type_id,
        location_id=product_in.location_id,
        length=product_in.length,
        width=product_in.width,
        thickness=product_in.thickness,
        shape=product_in.shape,
        weight=product_in.weight,
        user_id=current_user.id,
    )

@router.post("/{product_id}/receive", response_model=ProductRead)
async def receive_product(
    product_id: int,
    change: QuantityChange,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Restock a product: its quantity grows by `quantity`."""
    return await inventory.receive_product(db, product_id, change.quantity, user_id=current_user.id)


@router.post("/{product_id}/issue", response_model=ProductRead)
async def issue_product(
    product_id: int,
    change: QuantityChange,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Take pieces of a product out of stock. Refused when there are fewer than asked."""
    return await inventory.issue_product(db, product_id, change.quantity, user_id=current_user.id)


@router.delete("/{product_id}")
async def remove_product(product_id: int, db: AsyncSession = Depends(get_db)):
    """Delete a product."""
    success = await delete_product(db, product_id)
    if not success:
        raise HTTPException(status_code=404, detail="Product not found")
    return {"message": "Product deleted"}

@router.delete("/types/{type_id}", dependencies=[Depends(require_admin)])
async def remove_product_type(type_id: int, db: AsyncSession = Depends(get_db)):
    """Delete a product type if not in use. Admin only."""
    success = await delete_product_type(db, type_id)
    if not success:
        raise HTTPException(status_code=400, detail="Cannot delete type: in use or not found")
    return {"message": "Type deleted"}
