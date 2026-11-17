"""Piece goods (products counted by quantity): restocking and taking out of stock."""
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.core.errors import DomainError, NotFoundError
from app.models.Alchemy_models import Movement, Product, ProductType, User
from app.repo import activity

RECEIVE = "receive"
ISSUE = "issue"


async def get_product(db: AsyncSession, product_id: int) -> Product:
    # populate_existing: the product may already sit in the session with old values
    result = await db.execute(
        select(Product)
        .options(joinedload(Product.product_type), joinedload(Product.location))
        .where(Product.id == product_id)
        .execution_options(populate_existing=True)
    )
    product = result.scalar_one_or_none()
    if product is None:
        raise NotFoundError("Product not found")
    return product


async def apply_quantity_change(
    db: AsyncSession,
    product_id: int,
    delta: int,
    change_type: str,
    user_id: int | None,
    assembly_id: int | None = None,
) -> Product:
    """
    Add `delta` to the quantity and record the movement inside the caller's
    transaction, without committing.
    """
    # Lock the row so that two simultaneous issues cannot both take the last piece
    result = await db.execute(select(Product).where(Product.id == product_id).with_for_update())
    product = result.scalar_one_or_none()
    if product is None:
        raise NotFoundError("Product not found")

    current = product.quantity or 0
    if current + delta < 0:
        raise DomainError(f"Not enough in stock: {current} left")

    # The token may outlive its user; do not let that break the change
    if user_id is not None and await db.get(User, user_id) is None:
        user_id = None

    product.quantity = current + delta
    add_product_event(
        db, product, activity.PRODUCT_RECEIVE if delta > 0 else activity.PRODUCT_ISSUE, abs(delta), user_id,
        await type_name_of(db, product), assembly_id=assembly_id,
    )
    db.add(Movement(
        product_id=product.id,
        change_type=change_type,
        quantity_changed=delta,
        user_id=user_id,
        assembly_id=assembly_id,
    ))
    await db.flush()
    return product


async def type_name_of(db: AsyncSession, product: Product) -> str | None:
    if product.product_type_id is None:
        return None
    product_type = await db.get(ProductType, product.product_type_id)
    return product_type.name if product_type else None


def add_product_event(
    db: AsyncSession,
    product: Product,
    action: str,
    quantity: int,
    user_id: int | None,
    type_name: str | None,
    assembly_id: int | None = None,
    new: bool = False,
) -> None:
    """
    Journal a change of a piece good, in the caller's transaction. The name and
    type are copied into `details` so the entry stays readable after the
    product is deleted or renamed.
    """
    details = {"product_name": product.name, "product_type": type_name, "quantity_after": product.quantity or 0}
    if assembly_id is not None:
        details["assembly_id"] = assembly_id
    if new:
        details["new"] = True
    activity.add_event(db, action, user_id, product_id=product.id, quantity=quantity, details=details)


async def _change_quantity(
    db: AsyncSession, product_id: int, delta: int, change_type: str, user_id: int | None
) -> Product:
    """Change the quantity as a transaction of its own."""
    await apply_quantity_change(db, product_id, delta, change_type, user_id)
    await db.commit()
    return await get_product(db, product_id)


async def receive_product(db: AsyncSession, product_id: int, quantity: int, user_id: int | None = None) -> Product:
    """Restock: the quantity grows by `quantity`."""
    return await _change_quantity(db, product_id, quantity, RECEIVE, user_id)


async def issue_product(db: AsyncSession, product_id: int, quantity: int, user_id: int | None = None) -> Product:
    """Take `quantity` pieces out of stock; refused when there are fewer."""
    return await _change_quantity(db, product_id, -quantity, ISSUE, user_id)
