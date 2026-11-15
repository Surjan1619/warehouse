"""Materials, orders and individually tracked stock items."""
from uuid import uuid4

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.core.errors import DomainError, NotFoundError
from app.models.Alchemy_models import Location, Material, Order, StockItem

# Relationships needed by StockItemRead; lazy loading does not work in async mode
ITEM_LOAD = (
    joinedload(StockItem.material),
    joinedload(StockItem.location),
    joinedload(StockItem.order),
    joinedload(StockItem.created_by),
)

ACTIVE_ORDER_STATUSES = ("new", "in_progress")


# --- Materials ---
async def get_all_materials(db: AsyncSession):
    result = await db.execute(select(Material).order_by(Material.name))
    return result.scalars().all()


async def get_material(db: AsyncSession, material_id: int) -> Material:
    material = await db.get(Material, material_id)
    if material is None:
        raise NotFoundError("Material not found")
    return material


async def create_material(db: AsyncSession, data: dict) -> Material:
    material = Material(**data)
    db.add(material)
    await _commit(db, "Material with this SKU already exists")
    await db.refresh(material)
    return material


async def update_material(db: AsyncSession, material_id: int, data: dict) -> Material:
    material = await get_material(db, material_id)
    for key, value in data.items():
        setattr(material, key, value)
    await _commit(db, "Material with this SKU already exists")
    await db.refresh(material)
    return material


async def delete_material(db: AsyncSession, material_id: int) -> None:
    material = await get_material(db, material_id)
    in_use = await db.scalar(
        select(func.count()).select_from(StockItem).where(StockItem.material_id == material_id)
    )
    if in_use:
        raise DomainError("Cannot delete material: stock items refer to it")
    await db.delete(material)
    await db.commit()


# --- Orders ---
async def get_all_orders(db: AsyncSession, status: str | None = None):
    query = select(Order).order_by(Order.id.desc())
    if status:
        query = query.where(Order.status == status)
    result = await db.execute(query)
    return result.scalars().all()


async def get_order(db: AsyncSession, order_id: int) -> Order:
    order = await db.get(Order, order_id)
    if order is None:
        raise NotFoundError("Order not found")
    return order


async def create_order(db: AsyncSession, data: dict) -> Order:
    number = data.pop("number", None)
    # Without an explicit number, use a unique placeholder until the id is known
    order = Order(number=number or f"tmp-{uuid4().hex}", **data)
    db.add(order)
    try:
        await db.flush()
    except IntegrityError:
        await db.rollback()
        raise DomainError("Order with this number already exists", status_code=409)
    if number is None:
        order.number = f"ORD-{order.id:05d}"
    await _commit(db, "Order with this number already exists")
    await db.refresh(order)
    return order


async def update_order(db: AsyncSession, order_id: int, data: dict) -> Order:
    order = await get_order(db, order_id)
    new_status = data.get("status")
    for key, value in data.items():
        setattr(order, key, value)

    if new_status in ("done", "cancelled"):
        # Closing an order settles its reserved pieces:
        # done -> they are consumed, cancelled -> they return to free stock
        result = await db.execute(
            select(StockItem).where(StockItem.order_id == order_id, StockItem.status == "reserved")
        )
        for item in result.scalars():
            if new_status == "done":
                item.status = "used"
            else:
                item.status = "in_stock"
                item.order_id = None

    await db.commit()
    await db.refresh(order)
    return order


async def get_order_items(db: AsyncSession, order_id: int):
    result = await db.execute(
        select(StockItem).options(*ITEM_LOAD).where(StockItem.order_id == order_id).order_by(StockItem.id)
    )
    return result.scalars().all()


# --- Stock items ---
async def list_items(
    db: AsyncSession,
    status: str | None = None,
    material_id: int | None = None,
    order_id: int | None = None,
    location_id: int | None = None,
    min_length_mm: int | None = None,
):
    query = select(StockItem).options(*ITEM_LOAD).order_by(StockItem.id)
    if status:
        query = query.where(StockItem.status == status)
    if material_id is not None:
        query = query.where(StockItem.material_id == material_id)
    if order_id is not None:
        query = query.where(StockItem.order_id == order_id)
    if location_id is not None:
        query = query.where(StockItem.location_id == location_id)
    if min_length_mm is not None:
        query = query.where(StockItem.length_mm >= min_length_mm)
    result = await db.execute(query)
    return result.scalars().all()


async def get_item(db: AsyncSession, item_id: int) -> StockItem:
    # populate_existing: an object already in the session keeps its old
    # relationship values (expire_on_commit is off), so force a reload
    result = await db.execute(
        select(StockItem)
        .options(*ITEM_LOAD)
        .where(StockItem.id == item_id)
        .execution_options(populate_existing=True)
    )
    item = result.scalar_one_or_none()
    if item is None:
        raise NotFoundError("Stock item not found")
    return item


async def get_items_by_ids(db: AsyncSession, ids: list[int]):
    if not ids:
        return []
    result = await db.execute(
        select(StockItem)
        .options(*ITEM_LOAD)
        .where(StockItem.id.in_(ids))
        .order_by(StockItem.id)
        .execution_options(populate_existing=True)
    )
    return result.scalars().all()


async def receive_items(
    db: AsyncSession,
    material_id: int,
    length_mm: int,
    count: int,
    location_id: int | None,
    note: str | None,
    user_id: int | None = None,
):
    """Put `count` identical pieces into stock; `user_id` is who received them."""
    await get_material(db, material_id)
    await _check_location(db, location_id)
    items = [
        StockItem(
            material_id=material_id,
            length_mm=length_mm,
            location_id=location_id,
            note=note,
            created_by_id=user_id,
        )
        for _ in range(count)
    ]
    db.add_all(items)
    await db.commit()
    return await get_items_by_ids(db, [item.id for item in items])


async def update_item(db: AsyncSession, item_id: int, data: dict) -> StockItem:
    item = await get_item(db, item_id)
    if "location_id" in data:
        await _check_location(db, data["location_id"])
    for key, value in data.items():
        setattr(item, key, value)
    await db.commit()
    return await get_item(db, item_id)


async def assign_item(db: AsyncSession, item_id: int, order_id: int) -> StockItem:
    """Reserve a free piece for an order."""
    item = await get_item(db, item_id)
    if item.status != "in_stock":
        raise DomainError(f"Only a piece in stock can be reserved (current status: {item.status})")
    await check_order_is_open(db, order_id)
    item.status = "reserved"
    item.order_id = order_id
    await db.commit()
    return await get_item(db, item_id)


async def release_item(db: AsyncSession, item_id: int) -> StockItem:
    """Return a reserved piece to free stock."""
    item = await get_item(db, item_id)
    if item.status != "reserved":
        raise DomainError(f"Only a reserved piece can be released (current status: {item.status})")
    item.status = "in_stock"
    item.order_id = None
    await db.commit()
    return await get_item(db, item_id)


async def use_item(db: AsyncSession, item_id: int) -> StockItem:
    """Mark a reserved piece as consumed by its order."""
    item = await get_item(db, item_id)
    if item.status != "reserved":
        raise DomainError(f"Only a reserved piece can be marked as used (current status: {item.status})")
    item.status = "used"
    await db.commit()
    return await get_item(db, item_id)


async def scrap_item(db: AsyncSession, item_id: int) -> StockItem:
    """Write a free piece off as scrap."""
    item = await get_item(db, item_id)
    if item.status != "in_stock":
        raise DomainError(f"Only a piece in stock can be scrapped (current status: {item.status})")
    item.status = "scrap"
    await db.commit()
    return await get_item(db, item_id)


async def get_item_history(db: AsyncSession, item_id: int):
    item = await get_item(db, item_id)

    ancestors = []
    seen = {item.id}
    parent_id = item.parent_id
    while parent_id is not None and parent_id not in seen:
        parent = await get_item(db, parent_id)
        ancestors.append(parent)
        seen.add(parent.id)
        parent_id = parent.parent_id

    result = await db.execute(
        select(StockItem).options(*ITEM_LOAD).where(StockItem.parent_id == item_id).order_by(StockItem.id)
    )
    children = result.scalars().all()
    return item, ancestors, children


# --- Helpers ---
async def check_order_is_open(db: AsyncSession, order_id: int) -> Order:
    order = await get_order(db, order_id)
    if order.status not in ACTIVE_ORDER_STATUSES:
        raise DomainError(f"Order {order.number} is closed (status: {order.status})")
    return order


async def _check_location(db: AsyncSession, location_id: int | None) -> None:
    if location_id is not None and await db.get(Location, location_id) is None:
        raise NotFoundError("Location not found")


async def _commit(db: AsyncSession, conflict_detail: str) -> None:
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise DomainError(conflict_detail, status_code=409)
