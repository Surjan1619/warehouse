from typing import List

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.db import get_db
from app.models.Alchemy_models import User
from app.repo import stock
from app.schemas.stock import OrderCreate, OrderDetail, OrderRead, OrderStatus, OrderUpdate

router = APIRouter()


@router.get("/", response_model=List[OrderRead])
async def get_orders(status: OrderStatus | None = None, db: AsyncSession = Depends(get_db)):
    """Fetch orders, newest first, optionally filtered by status."""
    return await stock.get_all_orders(db, status=status)


@router.post("/", response_model=OrderRead, status_code=201)
async def add_order(order_in: OrderCreate, db: AsyncSession = Depends(get_db)):
    """Create an order. The number is generated when not given."""
    return await stock.create_order(db, order_in.model_dump())


@router.get("/{order_id}", response_model=OrderDetail)
async def get_order(order_id: int, db: AsyncSession = Depends(get_db)):
    """Fetch an order together with the pieces assigned to it."""
    order = await stock.get_order(db, order_id)
    items = await stock.get_order_items(db, order_id)
    return OrderDetail(
        **OrderRead.model_validate(order).model_dump(),
        items=items,
        total_length_mm=sum(item.length_mm for item in items),
    )


@router.patch("/{order_id}", response_model=OrderRead)
async def edit_order(
    order_id: int,
    order_in: OrderUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Update the given fields of an order.
    Status "done" marks its reserved pieces as used; "cancelled" returns them to stock.
    """
    return await stock.update_order(
        db, order_id, order_in.model_dump(exclude_unset=True), user_id=current_user.id
    )
