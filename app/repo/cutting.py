"""Cutting one stock item into several pieces."""
from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload, selectinload

from app.core.errors import DomainError, NotFoundError
from app.models.Alchemy_models import CutOperation, Location, Order, StockItem, User
from app.repo import activity
from app.repo.stock import ACTIVE_ORDER_STATUSES, ITEM_LOAD, check_order_is_open, get_material

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


def pack_pieces(
    items: list[tuple[int, int]], piece_lengths_mm: list[int], kerf_mm: int, min_usable_length_mm: int = 0
) -> tuple[dict[int, list[int]], list[int]]:
    """
    Spread pieces over several stock items.

    `items` are (id, length) pairs of the free stock. Returns which pieces go
    to which item, as indexes into `piece_lengths_mm`, and the indexes of the
    pieces that fit nowhere.

    First-fit-decreasing with best fit: pieces are placed longest first. A
    piece goes into the already started item where it leaves the least room;
    if it fits none of them, an untouched item is started: an exact fit if
    there is one, otherwise the shortest item that leaves a usable remainder,
    and only as a last resort one whose remainder would be too short to keep.
    Starting short items first uses up offcuts before whole pieces.
    This is a heuristic: the result is good, but not always the best possible.
    """
    free = sorted(items, key=lambda item: (item[1], item[0]))  # shortest first, then oldest
    started: list[dict] = []  # each: id, length, pieces (indexes), used (length incl. kerf)
    unplaced: list[int] = []

    def room_after(bin_, length: int) -> int:
        # Another piece in a started item costs its length plus one cut
        return bin_["length"] - bin_["used"] - kerf_mm - length

    order = sorted(range(len(piece_lengths_mm)), key=lambda i: (-piece_lengths_mm[i], i))
    for index in order:
        length = piece_lengths_mm[index]

        fitting = [b for b in started if room_after(b, length) >= 0]
        if fitting:
            target = min(fitting, key=lambda b: (room_after(b, length), b["id"]))
            target["pieces"].append(index)
            target["used"] += kerf_mm + length
            continue

        def waste_rank(position: int) -> tuple[int, int]:
            # 0: exact fit, 1: leaves a usable remainder, 2: leaves scrap.
            # `free` is sorted, so the position breaks ties towards the shortest item.
            left = free[position][1] - length - kerf_mm
            if free[position][1] == length:
                return 0, position
            return (1 if left >= min_usable_length_mm else 2), position

        candidates = [i for i, (_, item_length) in enumerate(free) if item_length >= length]
        if not candidates:
            unplaced.append(index)
            continue
        item_id, item_length = free.pop(min(candidates, key=waste_rank))
        started.append({"id": item_id, "length": item_length, "pieces": [index], "used": length})

    return {b["id"]: sorted(b["pieces"]) for b in started}, sorted(unplaced)


async def plan_multi_cut(
    db: AsyncSession,
    material_id: int,
    pieces: list[dict],
    kerf_mm: int | None = None,
) -> dict:
    """
    Propose how to cut the given pieces out of several free stock items.
    Nothing is changed; the result is meant to be passed to cut_many.
    """
    material = await get_material(db, material_id)
    kerf = material.kerf_mm if kerf_mm is None else kerf_mm

    result = await db.execute(
        select(StockItem)
        .options(*ITEM_LOAD)
        .where(StockItem.material_id == material_id, StockItem.status == "in_stock")
        .order_by(StockItem.id)
        .execution_options(populate_existing=True)
    )
    items = {item.id: item for item in result.scalars().all()}

    lengths = [piece["length_mm"] for piece in pieces]
    assignment, unplaced = pack_pieces(
        [(i.id, i.length_mm) for i in items.values()], lengths, kerf, material.min_usable_length_mm
    )

    cuts = []
    for item_id, indexes in assignment.items():
        item = items[item_id]
        plan = plan_cut(item.length_mm, [lengths[i] for i in indexes], kerf)
        cuts.append({
            "item": item,
            "pieces": [pieces[i] for i in indexes],
            "remainder_mm": plan.remainder_mm,
            "kerf_loss_mm": plan.kerf_loss_mm,
            "remainder_fate": _remainder_fate(plan.remainder_mm, material.min_usable_length_mm),
        })
    # Fullest items first: they are the ones cut with the least left over
    cuts.sort(key=lambda cut: (cut["remainder_mm"], cut["item"].id))

    return {
        "cuts": cuts,
        "unplaced": [pieces[i] for i in unplaced],
        "longest_available_mm": max((i.length_mm for i in items.values()), default=None),
    }


def _remainder_fate(remainder_mm: int, min_usable_length_mm: int) -> str:
    if remainder_mm == 0:
        return "none"
    return "stock" if remainder_mm >= min_usable_length_mm else "scrap"


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
        groups[key] = {
            "item": item,
            "item_ids": [item.id],
            "remainder_mm": plan.remainder_mm,
            "kerf_loss_mm": plan.kerf_loss_mm,
            "remainder_fate": _remainder_fate(plan.remainder_mm, material.min_usable_length_mm),
        }

    candidates = sorted(groups.values(), key=lambda g: (g["remainder_mm"], g["item"].id))
    for group in candidates:
        group["count"] = len(group["item_ids"])

    return {
        "required_mm": required,
        "candidates": candidates,
        "longest_available_mm": max((item.length_mm for item in items), default=None),
    }


async def _apply_cut(
    db: AsyncSession,
    source_item_id: int,
    pieces: list[dict],
    kerf_mm: int | None = None,
    scrap_remainder: bool = False,
    note: str | None = None,
    user_id: int | None = None,
    assembly_id: int | None = None,
) -> int:
    """
    Cut a stock item inside the caller's transaction, without committing.
    The source is kept with status "cut"; every piece and the remainder
    become new stock items that point back to it. Returns the operation id.
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
        assembly_id=assembly_id,
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
    await db.flush()
    return operation.id


async def cut_item(
    db: AsyncSession,
    source_item_id: int,
    pieces: list[dict],
    kerf_mm: int | None = None,
    scrap_remainder: bool = False,
    note: str | None = None,
    user_id: int | None = None,
) -> CutOperation:
    """Cut one stock item and save the result."""
    operation_id = await _apply_cut(
        db, source_item_id, pieces, kerf_mm=kerf_mm, scrap_remainder=scrap_remainder, note=note, user_id=user_id
    )
    await db.commit()
    return await get_cut(db, operation_id)


async def cut_many(db: AsyncSession, cuts: list[dict], user_id: int | None = None) -> list[CutOperation]:
    """
    Cut several stock items as one action: either every cut is saved or none.
    Each element of `cuts` holds `source_item_id` and `pieces`.
    """
    operation_ids = []
    try:
        for cut in cuts:
            operation_ids.append(
                await _apply_cut(db, cut["source_item_id"], cut["pieces"], note=cut.get("note"), user_id=user_id)
            )
    except Exception:
        # Undo the cuts already applied in this batch
        await db.rollback()
        raise
    await db.commit()
    return [await get_cut(db, operation_id) for operation_id in operation_ids]


async def cancel_cut(db: AsyncSession, cut_id: int, user_id: int | None = None) -> CutOperation:
    """
    Undo a cut made by mistake. The source gets back the status it had before
    the cut, and every piece of the cut becomes "cancelled". Nothing is deleted,
    so the history keeps both the cut and its cancellation.

    A cut whose piece was cut further cannot be undone until that later cut is
    cancelled: otherwise its pieces would hang on a piece that no longer exists.
    """
    result = await db.execute(select(CutOperation).where(CutOperation.id == cut_id).with_for_update())
    operation = result.scalar_one_or_none()
    if operation is None:
        raise NotFoundError("Cut operation not found")
    if operation.cancelled_at is not None:
        raise DomainError("This cut is already cancelled", status_code=409)

    # Lock the source and the pieces so that nobody cuts them meanwhile
    result = await db.execute(
        select(StockItem)
        .where((StockItem.id == operation.source_item_id) | (StockItem.cut_operation_id == operation.id))
        .order_by(StockItem.id)
        .with_for_update()
    )
    items = result.scalars().all()
    source = next(item for item in items if item.id == operation.source_item_id)
    pieces = [item for item in items if item.id != source.id]

    cut_further = [piece for piece in pieces if piece.status == "cut"]
    if cut_further:
        codes = ", ".join(piece.code for piece in cut_further)
        raise DomainError(f"Pieces {codes} were cut further; cancel those cuts first", status_code=409)

    # Before the cut the source was either free or reserved for its order.
    # A reservation for an order closed since then is not restored.
    order = await db.get(Order, source.order_id) if source.order_id is not None else None
    if order is not None and order.status in ACTIVE_ORDER_STATUSES:
        source.status = "reserved"
    else:
        source.status = "in_stock"
        source.order_id = None

    for piece in pieces:
        piece.status = "cancelled"
        # The piece no longer exists, so it must not count towards an order
        piece.order_id = None

    if user_id is not None and await db.get(User, user_id) is None:
        user_id = None
    # Stored in UTC without an offset, like every other time in the database
    operation.cancelled_at = datetime.now(timezone.utc).replace(tzinfo=None)
    operation.cancelled_by_id = user_id
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
