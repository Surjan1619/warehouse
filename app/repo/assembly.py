"""
Assemblies: everything taken from stock for one finished product (a gate).

An assembly is planned first (nothing changes) and then finished in one
transaction: the cuts of the plan and the piece goods are either all saved or
none of them is. The cutting itself is the existing `_apply_cut`, the goods go
through `inventory.apply_quantity_change`.
"""
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload, selectinload

from app.core.errors import DomainError, NotFoundError
from app.models.Alchemy_models import Assembly, Movement, Product, StockItem, User
from app.repo import activity, inventory
from app.repo.cutting import CUT_LOAD, _apply_cut, plan_multi_cut
from app.repo.stock import get_material

# At most this many pieces of one material per assembly
MAX_PIECES_PER_MATERIAL = 200

ASSEMBLY_LOAD = (
    joinedload(Assembly.user),
    selectinload(Assembly.cuts).options(*CUT_LOAD),
    selectinload(Assembly.movements).options(
        joinedload(Movement.product).options(joinedload(Product.product_type), joinedload(Product.location))
    ),
)


def _merge_products(products: list[dict]) -> dict[int, int]:
    """The same product added twice counts once, with the quantities summed."""
    merged: dict[int, int] = {}
    for line in products:
        merged[line["product_id"]] = merged.get(line["product_id"], 0) + line["quantity"]
    return merged


async def plan_assembly(db: AsyncSession, materials: list[dict], products: list[dict]) -> dict:
    """
    Preview an assembly. For each material the requested pieces are spread
    over free stock items by the existing `plan_multi_cut`; for each product
    the requested quantity is compared with what is in stock. Nothing changes.
    """
    # Lines of the same material are planned together: they may share a stock item
    pieces_by_material: dict[int, list[dict]] = {}
    for line in materials:
        pieces = pieces_by_material.setdefault(line["material_id"], [])
        for piece in line["pieces"]:
            pieces.extend({"length_mm": piece["length_mm"], "used": piece["used"]} for _ in range(piece["quantity"]))

    planned_materials = []
    for material_id, pieces in pieces_by_material.items():
        if len(pieces) > MAX_PIECES_PER_MATERIAL:
            raise DomainError(f"Too many pieces of one material: at most {MAX_PIECES_PER_MATERIAL}", status_code=422)
        material = await get_material(db, material_id)
        plan = await plan_multi_cut(db, material_id, pieces)
        planned_materials.append({"material": material, **plan})

    planned_products = []
    for product_id, quantity in _merge_products(products).items():
        product = await inventory.get_product(db, product_id)
        planned_products.append({"product": product, "quantity": quantity, "available": product.quantity or 0})

    ok = all(not m["unplaced"] for m in planned_materials) and all(
        p["quantity"] <= p["available"] for p in planned_products
    )
    return {"materials": planned_materials, "products": planned_products, "ok": ok}


async def _find_by_key(db: AsyncSession, client_key: str) -> Assembly | None:
    result = await db.execute(select(Assembly.id).where(Assembly.client_key == client_key))
    assembly_id = result.scalar_one_or_none()
    return await get_assembly(db, assembly_id) if assembly_id is not None else None


async def create_assembly(
    db: AsyncSession,
    client_key: str,
    cuts: list[dict],
    products: list[dict],
    name: str | None = None,
    note: str | None = None,
    user_id: int | None = None,
) -> tuple[Assembly, bool]:
    """
    Finish an assembly in one transaction: make the cuts of the plan and take
    the goods out of stock. Any failure rolls everything back.

    `client_key` identifies the draft: a repeated submit of the same draft
    (a double click, a retry after a lost response) returns the assembly saved
    the first time instead of taking the material twice. Returns the assembly
    and whether this call created it.
    """
    if not cuts and not products:
        raise DomainError("The assembly is empty", status_code=422)

    existing = await _find_by_key(db, client_key)
    if existing is not None:
        return existing, False

    if user_id is not None and await db.get(User, user_id) is None:
        user_id = None

    try:
        assembly = Assembly(name=name, note=note, client_key=client_key, user_id=user_id)
        db.add(assembly)
        # The unique key is checked here: a simultaneous submit of the same
        # draft waits for the first one and then fails, see `except IntegrityError`
        await db.flush()

        operation_ids = []
        for cut in cuts:
            # Only free pieces, as in the plan: a piece reserved for an order stays with it.
            # _apply_cut locks the row and checks the status once more.
            source = await db.get(StockItem, cut["source_item_id"])
            if source is not None and source.status != "in_stock":
                raise DomainError(
                    f"Piece {source.code} is no longer free (status: {source.status}); refresh the plan",
                    status_code=409,
                )
            operation_ids.append(await _apply_cut(
                db, cut["source_item_id"], cut["pieces"], user_id=user_id, assembly_id=assembly.id,
            ))

        issued = []
        for product_id, quantity in _merge_products(products).items():
            product = await inventory.apply_quantity_change(
                db, product_id, -quantity, inventory.ISSUE, user_id, assembly_id=assembly.id
            )
            issued.append({"product_id": product_id, "name": product.name, "quantity": quantity})

        activity.add_event(
            db, activity.ASSEMBLE, user_id,
            # Totals stay 0: the pieces and lengths are already counted by the cut events
            quantity=0,
            details={"assembly_id": assembly.id, "name": name, "cut_operation_ids": operation_ids, "products": issued},
        )
        await db.commit()
    except IntegrityError:
        await db.rollback()
        existing = await _find_by_key(db, client_key)
        if existing is None:
            raise
        return existing, False
    except Exception:
        await db.rollback()
        raise

    return await get_assembly(db, assembly.id), True


async def get_assembly(db: AsyncSession, assembly_id: int) -> Assembly:
    result = await db.execute(
        select(Assembly)
        .options(*ASSEMBLY_LOAD)
        .where(Assembly.id == assembly_id)
        .execution_options(populate_existing=True)
    )
    assembly = result.scalar_one_or_none()
    if assembly is None:
        raise NotFoundError("Assembly not found")
    return assembly


async def list_assemblies(db: AsyncSession, limit: int = 50, offset: int = 0):
    result = await db.execute(
        select(Assembly)
        .options(*ASSEMBLY_LOAD)
        .order_by(Assembly.id.desc())
        .limit(limit)
        .offset(offset)
    )
    return result.scalars().all()
