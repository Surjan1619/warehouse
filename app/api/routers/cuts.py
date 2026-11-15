from typing import List

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.db import get_db
from app.models.Alchemy_models import User
from app.repo import cutting
from app.schemas.stock import CutRead, CutRequest, CutSuggestRequest, CutSuggestResponse

router = APIRouter()


@router.post("/suggest", response_model=CutSuggestResponse)
async def suggest(suggest_in: CutSuggestRequest, db: AsyncSession = Depends(get_db)):
    """
    Suggest which stock items the given pieces can be cut from.
    The most economical option (smallest remainder) comes first. Nothing is changed.
    """
    return await cutting.suggest_sources(
        db,
        material_id=suggest_in.material_id,
        piece_lengths_mm=suggest_in.pieces,
        kerf_mm=suggest_in.kerf_mm,
    )


@router.post("/", response_model=CutRead, status_code=201)
async def cut(
    cut_in: CutRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Cut a stock item into pieces.
    The remainder returns to stock, or becomes scrap when it is shorter than
    the material's minimum usable length.
    """
    return await cutting.cut_item(
        db,
        source_item_id=cut_in.source_item_id,
        pieces=[piece.model_dump() for piece in cut_in.pieces],
        kerf_mm=cut_in.kerf_mm,
        scrap_remainder=cut_in.scrap_remainder,
        note=cut_in.note,
        user_id=current_user.id,
    )


@router.get("/", response_model=List[CutRead])
async def get_cuts(source_item_id: int | None = None, limit: int = 100, db: AsyncSession = Depends(get_db)):
    """Fetch recent cut operations, newest first."""
    return await cutting.list_cuts(db, source_item_id=source_item_id, limit=min(max(limit, 1), 500))


@router.get("/{cut_id}", response_model=CutRead)
async def get_cut(cut_id: int, db: AsyncSession = Depends(get_db)):
    """Fetch one cut operation with its resulting pieces."""
    return await cutting.get_cut(db, cut_id)
