"""
Activity journal: who did what, with what, and when.

Writing an event does not commit. The caller adds the event to the same
transaction as the action it describes, so the two are saved or rolled back
together and the journal never disagrees with the data.
"""
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.models.Alchemy_models import ActivityEvent

# Pieces were put into stock
RECEIVE = "receive"
# A piece was cut; quantity and length describe the source piece
CUT = "cut"
# Pieces were consumed
USE = "use"
# Pieces were written off as scrap
SCRAP = "scrap"

ACTIONS = frozenset({RECEIVE, CUT, USE, SCRAP})

EVENT_LOAD = (
    joinedload(ActivityEvent.user),
    joinedload(ActivityEvent.material),
    joinedload(ActivityEvent.stock_item),
)


def add_event(
    db: AsyncSession,
    action: str,
    user_id: int | None,
    *,
    material_id: int | None = None,
    stock_item_id: int | None = None,
    cut_operation_id: int | None = None,
    quantity: int = 1,
    length_mm: int = 0,
    details: dict | None = None,
) -> ActivityEvent:
    """
    Add an event to the session without committing.

    `quantity` is the number of pieces and `length_mm` their total length;
    reports are sums of these two columns.
    """
    if action not in ACTIONS:
        raise ValueError(f"Unknown journal action: {action!r}")
    if quantity < 0 or length_mm < 0:
        raise ValueError("Journal quantity and length cannot be negative")

    event = ActivityEvent(
        action=action,
        user_id=user_id,
        material_id=material_id,
        stock_item_id=stock_item_id,
        cut_operation_id=cut_operation_id,
        quantity=quantity,
        length_mm=length_mm,
        details=details,
    )
    db.add(event)
    return event


async def list_events(
    db: AsyncSession,
    *,
    user_id: int | None = None,
    action: str | None = None,
    material_id: int | None = None,
    stock_item_id: int | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    limit: int = 100,
    offset: int = 0,
):
    """
    Fetch journal entries, newest first.
    `date_from` is inclusive and `date_to` exclusive.
    """
    query = (
        select(ActivityEvent)
        .options(*EVENT_LOAD)
        .order_by(ActivityEvent.created_at.desc(), ActivityEvent.id.desc())
        .limit(limit)
        .offset(offset)
    )
    if user_id is not None:
        query = query.where(ActivityEvent.user_id == user_id)
    if action is not None:
        query = query.where(ActivityEvent.action == action)
    if material_id is not None:
        query = query.where(ActivityEvent.material_id == material_id)
    if stock_item_id is not None:
        query = query.where(ActivityEvent.stock_item_id == stock_item_id)
    if date_from is not None:
        query = query.where(ActivityEvent.created_at >= date_from)
    if date_to is not None:
        query = query.where(ActivityEvent.created_at < date_to)

    result = await db.execute(query)
    return result.scalars().all()
