"""
Clearing the database, for an administrator who confirmed it with their password.

Three groups can be cleared, in any sensible combination:
- stock: stock items, cuts, assemblies, orders, piece goods and their movements,
  imported supplier documents;
- journal: the activity journal;
- catalog: materials, storage locations and product types.

Users are never touched, so somebody can always log in afterwards. Rows are
deleted, not truncated: numbering goes on, so a code like T-000123 written on
a piece before the clearing is never given to another piece.
Everything happens in one transaction; one journal entry records who cleared what.
"""
from sqlalchemy import delete, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import DomainError
from app.core.security import verify_password
from app.models.Alchemy_models import (
    ActivityEvent,
    Assembly,
    CutOperation,
    DocumentImport,
    Location,
    Material,
    Movement,
    Order,
    Product,
    ProductType,
    StockItem,
    User,
)
from app.repo import activity

STOCK = "stock"
JOURNAL = "journal"
CATALOG = "catalog"


async def _delete(db: AsyncSession, model) -> int:
    result = await db.execute(delete(model))
    return result.rowcount or 0


async def clear_database(
    db: AsyncSession, admin: User, password: str, stock: bool, journal: bool, catalog: bool
) -> dict[str, int]:
    """
    Delete the chosen groups after checking the administrator's password.
    Returns how many rows of each table were deleted.
    """
    # The token alone is not enough: whoever got hold of it must also know the password
    if not password or not verify_password(password, admin.password_hash):
        raise DomainError("Wrong password", status_code=403)
    if not (stock or journal or catalog):
        raise DomainError("Nothing chosen to clear", status_code=422)
    # Stock items and goods refer to materials, locations and types
    if catalog and not stock:
        raise DomainError("The catalog can only be cleared together with the stock", status_code=422)

    deleted: dict[str, int] = {}
    try:
        if journal:
            deleted["activity_log"] = await _delete(db, ActivityEvent)
        else:
            # The kept journal must not point at rows that go away; its text stays in `details`
            links = {}
            if stock:
                links.update(stock_item_id=None, cut_operation_id=None, product_id=None)
            if catalog:
                links.update(material_id=None)
            if links:
                await db.execute(update(ActivityEvent).values(**links))

        if stock:
            # stock_items and cut_operations refer to each other: cut the links first
            await db.execute(update(StockItem).values(parent_id=None, cut_operation_id=None))
            deleted["cut_operations"] = await _delete(db, CutOperation)
            deleted["stock_items"] = await _delete(db, StockItem)
            deleted["orders"] = await _delete(db, Order)
            deleted["movements"] = await _delete(db, Movement)
            deleted["products"] = await _delete(db, Product)
            deleted["assemblies"] = await _delete(db, Assembly)
            # After the stock items and movements that refer to them
            deleted["document_imports"] = await _delete(db, DocumentImport)

        if catalog:
            deleted["materials"] = await _delete(db, Material)
            deleted["locations"] = await _delete(db, Location)
            deleted["product_types"] = await _delete(db, ProductType)

        groups = [name for name, chosen in ((STOCK, stock), (JOURNAL, journal), (CATALOG, catalog)) if chosen]
        activity.add_event(
            db, activity.RESET, admin.id, quantity=0, details={"groups": groups, "deleted": deleted},
        )
        await db.commit()
    except Exception:
        await db.rollback()
        raise
    return deleted
