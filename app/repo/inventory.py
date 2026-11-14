from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from fastapi import HTTPException
from app.models.Alchemy_models import Product, Movement

async def sell_product(db: AsyncSession, product_id: int, quantity: int):
    """Process a sale: verify stock, decrement quantity, and log movement."""
    result = await db.execute(select(Product).where(Product.id == product_id))
    prod = result.scalar_one_or_none()

    if not prod or (prod.quantity or 0) < quantity:
        raise HTTPException(status_code=400, detail="Insufficient stock")

    # Decrement stock and log sale movement
    prod.quantity -= quantity
    db.add(Movement(product_id=prod.id, change_type="sale", quantity_changed=-quantity))
    await db.commit()
    return True
