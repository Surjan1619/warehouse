"""Cutting one stock item into several pieces."""
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload, selectinload

from app.core.errors import DomainError, NotFoundError
from app.models.Alchemy_models import CutOperation, Location, StockItem, User
from app.repo import activity
from app.repo.stock import ITEM_LOAD, check_order_is_open, get_material

CUT_LOAD = (
    joinedload(CutOperation.source_item).options(*ITEM_LOAD),
    selectinload(CutOperation.results).options(*ITEM_LOAD),
)


@dataclass
class CutPlan:
    """Result of fitting the requested pieces into a source length."""
    cuts: int            # number of saw cuts
    kerf_loss_mm: int    # length consumed by the saw
    remainder_mm: int    # what is left after the pieces and the kerf


def plan_cut(source_length_mm: int, piece_lengths_mm: list[int], kerf_mm: int) -> CutPlan:
    """
    Work out how the pieces fit into the source piece.

    Separating n pieces from each other takes n-1 cuts. If material is left
    over after that, one more cut separates the remainder; when the leftover
    is no wider than the saw blade, that last cut consumes it entirely.
    """
    pieces_total = sum(piece_lengths_mm)
    between_cuts = len(piece_lengths_mm) - 1
    required = pieces_total + kerf_mm * between_cuts
    if required > source_length_mm:
        raise DomainError(
            f"Pieces do not fit: {pieces_total} mm of pieces plus {kerf_mm * between_cuts} mm "
            f"of kerf is {required} mm, but the source piece is {source_length_mm} mm"
        )

    leftover = source_length_mm - required
    if leftover == 0:
        return CutPlan(cuts=between_cuts, kerf_loss_mm=kerf_mm * between_cuts, remainder_mm=0)

    remainder = max(0, leftover - kerf_mm)
    return CutPlan(
        cuts=between_cuts + 1,
        kerf_loss_mm=source_length_mm - pieces_total - remainder,
        remainder_mm=remainder,
    )


async def suggest_sources(
    db: AsyncSession,
    material_id: int,
    piece_lengths_mm: list[int],
    kerf_mm: int | None = None,
) -> dict:
    """
    Find the free stock items the given pieces can be cut from, most
    economical first.

    Best fit: the smaller the remainder, the higher the item ranks, so an
    exact fit comes first and a short offcut is preferred over a full-length
    piece. Among equal remainders the oldest item wins. Items with the same
    length and location are interchangeable and are returned as one group.
    """
    material = await get_material(db, material_id)
    kerf = material.kerf_mm if kerf_mm is None else kerf_mm
    required = sum(piece_lengths_mm) + kerf * (len(piece_lengths_mm) - 1)

    result = await db.execute(
        select(StockItem)
        .options(*ITEM_LOAD)
        .where(StockItem.material_id == material_id, StockItem.status == "in_stock")
        .order_by(StockItem.length_mm, StockItem.id)
        .execution_options(populate_existing=True)
    )
    items = result.scalars().all()

    groups: dict[tuple, dict] = {}
    for item in items:
        if item.length_mm < required:
            continue
        key = (item.length_mm, item.location_id)
        if key in groups:
            groups[key]["item_ids"].append(item.id)
            continue
        plan = plan_cut(item.length_mm, piece_lengths_mm, kerf)
        if plan.remainder_mm == 0:
            fate = "none"
        elif plan.remainder_mm >= material.min_usable_length_mm:
            fate = "stock"
        else:
            fate = "scrap"
        groups[key] = {
            "item": item,
            "item_ids": [item.id],
            "remainder_mm": plan.remainder_mm,
            "kerf_loss_mm": plan.kerf_loss_mm,
            "remainder_fate": fate,
        }

    candidates = sorted(groups.values(), key=lambda g: (g["remainder_mm"], g["item"].id))
    for group in candidates:
        group["count"] = len(group["item_ids"])

    return {
        "required_mm": required,
        "candidates": candidates,
        "longest_available_mm": max((item.length_mm for item in items), default=None),
    }


async def cut_item(
    db: AsyncSession,
    source_item_id: int,
    pieces: list[dict],
    kerf_mm: int | None = None,
    scrap_remainder: bool = False,
    note: str | None = None,
    user_id: int | None = None,
) -> CutOperation:
    """
    Cut a stock item. The source is kept with status "cut"; every piece and
    the remainder become new stock items that point back to it.
    """
    # Lock the source row so that two simultaneous cuts cannot both succeed
    result = await db.execute(
        select(StockItem)
        .options(joinedload(StockItem.material))
        .where(StockItem.id == source_item_id)
        .with_for_update(of=StockItem)
    )
    source = result.scalar_one_or_none()
    if source is None:
        raise NotFoundError("Stock item not found")
    if source.status not in ("in_stock", "reserved"):
        raise DomainError(f"This piece cannot be cut (current status: {source.status})")

    material = source.material
    kerf = material.kerf_mm if kerf_mm is None else kerf_mm
    plan = plan_cut(source.length_mm, [p["length_mm"] for p in pieces], kerf)

    # Validate targets before anything is written
    for order_id in {p["order_id"] for p in pieces if p.get("order_id") is not None}:
        await check_order_is_open(db, order_id)
    for location_id in {p["location_id"] for p in pieces if p.get("location_id") is not None}:
        if await db.get(Location, location_id) is None:
            raise NotFoundError("Location not found")

    # The token may outlive its user; do not let that break the cut
    if user_id is not None and await db.get(User, user_id) is None:
        user_id = None

    operation = CutOperation(
        source_item_id=source.id,
        user_id=user_id,
        kerf_mm=kerf,
        kerf_loss_mm=plan.kerf_loss_mm,
        note=note,
    )
    db.add(operation)
    await db.flush()  # assigns operation.id

    for piece in pieces:
        order_id = piece.get("order_id")
        db.add(StockItem(
            material_id=source.material_id,
            length_mm=piece["length_mm"],
            status=_piece_status(piece),
            order_id=order_id,
            location_id=piece.get("location_id") or source.location_id,
            parent_id=source.id,
            cut_operation_id=operation.id,
            note=piece.get("note"),
            created_by_id=user_id,
        ))

    scrap = None
    if plan.remainder_mm > 0:
        keep = plan.remainder_mm >= material.min_usable_length_mm and not scrap_remainder
        remainder = StockItem(
            material_id=source.material_id,
            length_mm=plan.remainder_mm,
            status="in_stock" if keep else "scrap",
            # Scrap leaves the shelf; a kept remainder stays where the source was
            location_id=source.location_id if keep else None,
            parent_id=source.id,
            cut_operation_id=operation.id,
            note="Остаток после резки" if keep else "Отходы после резки",
            created_by_id=user_id,
        )
        db.add(remainder)
        if not keep:
            scrap = remainder

    # Journal: the cut itself, then what was consumed and what was lost in it
    journal = {"material_id": source.material_id, "cut_operation_id": operation.id}
    activity.add_event(
        db, activity.CUT, user_id, stock_item_id=source.id, length_mm=source.length_mm,
        details={"pieces_mm": [p["length_mm"] for p in pieces], "remainder_mm": plan.remainder_mm}, **journal,
    )
    used_lengths = [p["length_mm"] for p in pieces if p.get("used")]
    if used_lengths:
        activity.add_event(
            db, activity.USE, user_id, quantity=len(used_lengths), length_mm=sum(used_lengths), **journal
        )
    if scrap is not None:
        await db.flush()  # assigns scrap.id
        activity.add_event(
            db, activity.SCRAP, user_id, stock_item_id=scrap.id, length_mm=scrap.length_mm, **journal
        )

    source.status = "cut"
    await db.commit()
    return await get_cut(db, operation.id)


def _piece_status(piece: dict) -> str:
    """A piece is consumed at once, reserved for an order, or returned to stock."""
    if piece.get("used"):
        return "used"
    return "reserved" if piece.get("order_id") is not None else "in_stock"


async def get_cut(db: AsyncSession, cut_id: int) -> CutOperation:
    result = await db.execute(
        select(CutOperation)
        .options(*CUT_LOAD)
        .where(CutOperation.id == cut_id)
        .execution_options(populate_existing=True)
    )
    operation = result.scalar_one_or_none()
    if operation is None:
        raise NotFoundError("Cut operation not found")
    return operation


async def list_cuts(db: AsyncSession, source_item_id: int | None = None, limit: int = 100):
    query = select(CutOperation).options(*CUT_LOAD).order_by(CutOperation.id.desc()).limit(limit)
    if source_item_id is not None:
        query = query.where(CutOperation.source_item_id == source_item_id)
    result = await db.execute(query)
    return result.scalars().all()
