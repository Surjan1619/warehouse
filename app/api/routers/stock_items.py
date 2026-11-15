from typing import List

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.db import get_db
from app.models.Alchemy_models import User
from app.repo import stock
from app.schemas.stock import (
    ItemStatus,
    StockItemAssign,
    StockItemHistory,
    StockItemRead,
    StockItemReceive,
    StockItemUpdate,
)

router = APIRouter()


@router.get("/", response_model=List[StockItemRead])
async def get_items(
    status: ItemStatus | None = None,
    material_id: int | None = None,
    order_id: int | None = None,
    location_id: int | None = None,
    min_length_mm: int | None = None,
    number: str | None = Query(None, max_length=30, description="Piece number: T-000123 or 123"),
    db: AsyncSession = Depends(get_db),
):
    """Fetch stock items with optional filters. `number` finds one piece by its number."""
    return await stock.list_items(
        db,
        status=status,
        material_id=material_id,
        order_id=order_id,
        location_id=location_id,
        min_length_mm=min_length_mm,
        number=number,
    )


@router.post("/", response_model=List[StockItemRead], status_code=201)
async def receive_items(
    receive_in: StockItemReceive,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Put `count` new pieces of one material and length into stock."""
    return await stock.receive_items(db, **receive_in.model_dump(), user_id=current_user.id)


@router.get("/{item_id}", response_model=StockItemRead)
async def get_item(item_id: int, db: AsyncSession = Depends(get_db)):
    """Fetch one stock item."""
    return await stock.get_item(db, item_id)


@router.get("/{item_id}/history", response_model=StockItemHistory)
async def get_item_history(item_id: int, db: AsyncSession = Depends(get_db)):
    """Fetch the pieces this one was cut from and the pieces cut from it."""
    item, ancestors, children = await stock.get_item_history(db, item_id)
    return {"item": item, "ancestors": ancestors, "children": children}


@router.patch("/{item_id}", response_model=StockItemRead)
async def edit_item(item_id: int, item_in: StockItemUpdate, db: AsyncSession = Depends(get_db)):
    """Move a piece to another location or change its note."""
    return await stock.update_item(db, item_id, item_in.model_dump(exclude_unset=True))


@router.post("/{item_id}/assign", response_model=StockItemRead)
async def assign_item(item_id: int, assign_in: StockItemAssign, db: AsyncSession = Depends(get_db)):
    """Reserve a free piece for an order."""
    return await stock.assign_item(db, item_id, assign_in.order_id)


@router.post("/{item_id}/release", response_model=StockItemRead)
async def release_item(item_id: int, db: AsyncSession = Depends(get_db)):
    """Return a reserved piece to free stock."""
    return await stock.release_item(db, item_id)


@router.post("/{item_id}/use", response_model=StockItemRead)
async def use_item(
    item_id: int, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)
):
    """Mark a reserved piece as consumed by its order."""
    return await stock.use_item(db, item_id, user_id=current_user.id)


@router.post("/{item_id}/scrap", response_model=StockItemRead)
async def scrap_item(
    item_id: int, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)
):
    """Write a free piece off as scrap."""
    return await stock.scrap_item(db, item_id, user_id=current_user.id)
