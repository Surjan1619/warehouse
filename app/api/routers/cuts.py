from typing import List

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.repo import cutting
from app.schemas.stock import CutRead, CutRequest

router = APIRouter()


@router.post("/", response_model=CutRead, status_code=201)
async def cut(cut_in: CutRequest, request: Request, db: AsyncSession = Depends(get_db)):
    """
    Cut a stock item into pieces.
    The remainder returns to stock, or becomes scrap when it is shorter than
    the material's minimum usable length.
    """
    # Set by AuthMiddleware from the token's "sub" claim
    raw_user_id = getattr(request.state, "user_id", None)
    user_id = int(raw_user_id) if raw_user_id is not None and str(raw_user_id).isdigit() else None

    return await cutting.cut_item(
        db,
        source_item_id=cut_in.source_item_id,
        pieces=[piece.model_dump() for piece in cut_in.pieces],
        kerf_mm=cut_in.kerf_mm,
        scrap_remainder=cut_in.scrap_remainder,
        note=cut_in.note,
        user_id=user_id,
    )


@router.get("/", response_model=List[CutRead])
async def get_cuts(source_item_id: int | None = None, limit: int = 100, db: AsyncSession = Depends(get_db)):
    """Fetch recent cut operations, newest first."""
    return await cutting.list_cuts(db, source_item_id=source_item_id, limit=min(max(limit, 1), 500))


@router.get("/{cut_id}", response_model=CutRead)
async def get_cut(cut_id: int, db: AsyncSession = Depends(get_db)):
    """Fetch one cut operation with its resulting pieces."""
    return await cutting.get_cut(db, cut_id)
