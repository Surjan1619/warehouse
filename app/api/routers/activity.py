from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_admin
from app.core.db import get_db
from app.repo import activity
from app.schemas.activity import Action, ActivityPage

# The journal shows what every worker did, so it is for admins only
router = APIRouter(dependencies=[Depends(require_admin)])


def _to_db_time(value: datetime | None) -> datetime | None:
    """The journal stores UTC without an offset; bring a filter value to the same form."""
    if value is None or value.tzinfo is None:
        return value
    return value.astimezone(timezone.utc).replace(tzinfo=None)


@router.get("/", response_model=ActivityPage)
async def get_activity(
    user_id: int | None = None,
    action: Action | None = None,
    material_id: int | None = None,
    stock_item_id: int | None = None,
    date_from: datetime | None = Query(None, description="Inclusive. Send with a UTC offset."),
    date_to: datetime | None = Query(None, description="Exclusive. Send with a UTC offset."),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    """Fetch journal entries, newest first, with the total number that match the filters."""
    filters = dict(
        user_id=user_id,
        action=action,
        material_id=material_id,
        stock_item_id=stock_item_id,
        date_from=_to_db_time(date_from),
        date_to=_to_db_time(date_to),
    )
    return {
        "items": await activity.list_events(db, **filters, limit=limit, offset=offset),
        "total": await activity.count_events(db, **filters),
    }
