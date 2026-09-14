from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from fastapi import HTTPException
from app.models.Alchemy_models import Product, Movement
from typing import Optional

async def cut_product(db: AsyncSession, source_id: int, cut_length: float, pieces: int):
    # 1. Fetch source
    result = await db.execute(select(Product).where(Product.id == source_id))
    source = result.scalar_one_or_none()
    
    if not source or (source.quantity or 0) < 1:
        raise HTTPException(status_code=400, detail="Product not found or out of stock")

    # 2. Decrement source
    source.quantity -= 1
    db.add(Movement(product_id=source.id, change_type="cut_source", quantity_changed=-1))

    # 3. Find or create result
    result_query = select(Product).where(
        Product.product_type_id == source.product_type_id,
        Product.shape == source.shape,
        Product.width == source.width,
        Product.thickness == source.thickness,
        Product.weight == source.weight,
        Product.length == cut_length
    )
    result = await db.execute(result_query)
    target = result.scalar_one_or_none()

    if target:
        target.quantity = (target.quantity or 0) + pieces
        target_id = target.id
    else:
        new_prod = Product(
            product_type_id=source.product_type_id,
            shape=source.shape,
            width=source.width,
            thickness=source.thickness,
            weight=source.weight,
            length=cut_length,
            quantity=pieces
        )
        db.add(new_prod)
        await db.flush() # Get ID
        target_id = new_prod.id
    
    db.add(Movement(product_id=target_id, change_type="cut_result", quantity_changed=pieces))
    await db.commit()
    return target_id, (target.quantity if target else pieces)

async def sell_product(db: AsyncSession, product_id: int, quantity: int):
    result = await db.execute(select(Product).where(Product.id == product_id))
    prod = result.scalar_one_or_none()

    if not prod or (prod.quantity or 0) < quantity:
        raise HTTPException(status_code=400, detail="Insufficient stock")

    prod.quantity -= quantity
    db.add(Movement(product_id=prod.id, change_type="sale", quantity_changed=-quantity))
    await db.commit()
    return True
