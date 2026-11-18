"""
Putting a supplier's specification into stock.

`preview_import` reads the file and tells, row by row, what would happen:
which material or product the row matches by its code ("Код") and how many
pieces or units it brings. Nothing is written.

`confirm_import` reads the same file again (the browser sends the file, never
the rows, so what goes into stock is what the document says) and does it all in
one transaction:
- a row with a length becomes identical stock items of its material, created
  from the row when no material has that code yet;
- any other row is added to the quantity of its product, created likewise;
- every row is journalled (`receive` / `product_receive`), and one `import`
  entry tells about the document.

The same document is accepted once: by its number and date, and by the file
itself, so the copy of a specification in another currency is refused.
"""
from __future__ import annotations

import hashlib

from sqlalchemy import or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.core.errors import DomainError, NotFoundError
from app.models.Alchemy_models import DocumentImport, Location, Material, Product, ProductType, StockItem, User
from app.repo import activity, inventory
from app.repo import spec_parser as sp

# A product matched by its code is counted in another unit than the document says
UNIT_DIFFERS = "unit_differs"


def file_hash(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


async def find_previous(db: AsyncSession, spec: sp.Specification, sha256: str) -> DocumentImport | None:
    """The earlier import of the same document, if any."""
    same = [DocumentImport.file_sha256 == sha256]
    if spec.number:
        same.append((DocumentImport.number == spec.number) & (DocumentImport.doc_date == spec.date))
    result = await db.execute(
        select(DocumentImport).options(joinedload(DocumentImport.user)).where(or_(*same)).order_by(DocumentImport.id)
    )
    return result.scalars().first()


async def _by_codes(db: AsyncSession, model, codes: set[str]) -> dict:
    if not codes:
        return {}
    result = await db.execute(select(model).where(model.sku.in_(codes)))
    return {item.sku: item for item in result.scalars()}


async def _match(db: AsyncSession, spec: sp.Specification) -> tuple[dict[str, Material], dict[str, Product]]:
    materials = await _by_codes(db, Material, {r.code for r in spec.rows if r.kind == sp.STOCK and r.code})
    products = await _by_codes(db, Product, {r.code for r in spec.rows if r.kind == sp.GOODS and r.code})
    # A product counted in pieces cannot take a delivery counted in pairs
    for row in spec.rows:
        product = products.get(row.code) if row.kind == sp.GOODS else None
        if product is not None and (product.unit or "шт") != row.unit:
            row.problem = UNIT_DIFFERS
    return materials, products


def _row_view(row: sp.SpecRow, materials: dict, products: dict) -> dict:
    material = materials.get(row.code) if row.kind == sp.STOCK else None
    product = products.get(row.code) if row.kind == sp.GOODS else None
    return {
        "line": row.line,
        "code": row.code,
        "article": row.article,
        "name": row.name,
        "color": row.color,
        "unit": row.unit,
        "quantity": str(row.quantity) if row.quantity is not None else None,
        "length_mm": row.length_mm,
        "kind": row.kind if row.problem is None else None,
        "pieces": row.pieces,
        "count": row.count,
        "problem": row.problem,
        "title": row.title,
        "material": material,
        "product": product,
    }


def _summary(spec: sp.Specification, materials: dict, products: dict) -> dict:
    stock = [r for r in spec.rows if r.kind == sp.STOCK and r.problem is None]
    goods = [r for r in spec.rows if r.kind == sp.GOODS and r.problem is None]
    return {
        "stock_rows": len(stock),
        "stock_pieces": sum(r.pieces for r in stock),
        "new_materials": len({r.code or r.title for r in stock if r.code not in materials}),
        "goods_rows": len(goods),
        "new_products": len({r.code or r.title for r in goods if r.code not in products}),
        "problems": sum(1 for r in spec.rows if r.problem is not None),
    }


async def preview_import(db: AsyncSession, data: bytes, filename: str | None) -> dict:
    """What the document would put into stock. Writes nothing."""
    spec = sp.parse_specification(data)
    previous = await find_previous(db, spec, file_hash(data))
    materials, products = await _match(db, spec)
    return {
        "number": spec.number,
        "date": spec.date,
        "supplier": spec.supplier,
        "filename": filename,
        "rows": [_row_view(row, materials, products) for row in spec.rows],
        "summary": _summary(spec, materials, products),
        "previous": previous,
        "can_import": spec.ok and previous is None,
    }


async def confirm_import(
    db: AsyncSession,
    data: bytes,
    filename: str | None,
    user_id: int | None,
    location_id: int | None = None,
    product_type_ids: dict[int, int] | None = None,
) -> dict:
    """
    Put the document into stock in one transaction. `product_type_ids` maps an
    Excel row number to the type for a product created from that row.
    """
    spec = sp.parse_specification(data)
    sha256 = file_hash(data)
    if await find_previous(db, spec, sha256) is not None:
        raise DomainError("This document is already in stock", status_code=409)
    materials, products = await _match(db, spec)
    if not spec.ok:
        raise DomainError("The document has rows that cannot be put into stock", status_code=422)

    if location_id is not None and await db.get(Location, location_id) is None:
        raise NotFoundError("Location not found")
    product_type_ids = product_type_ids or {}
    for type_id in set(product_type_ids.values()):
        if await db.get(ProductType, type_id) is None:
            raise NotFoundError("Product type not found")
    if user_id is not None and await db.get(User, user_id) is None:
        user_id = None

    note = f"Спецификация № {spec.number}" if spec.number else (filename or "Импорт из документа")[:500]
    rows_done: list[dict] = []
    try:
        document = DocumentImport(
            number=spec.number, doc_date=spec.date, supplier=spec.supplier,
            filename=(filename or "")[:255] or None, file_sha256=sha256, user_id=user_id,
        )
        db.add(document)
        await db.flush()

        new_materials = new_products = pieces_total = 0
        for row in spec.rows:
            # Rows without a code are told apart by their name, so two such rows share one entry
            key = row.code or f"title:{row.title}"
            if row.kind == sp.STOCK:
                material = materials.get(key)
                if material is None:
                    material = Material(name=row.title, sku=row.code, color=row.color)
                    db.add(material)
                    await db.flush()
                    new_materials += 1
                    materials[key] = material
                items = [
                    StockItem(
                        material_id=material.id, length_mm=row.length_mm, location_id=location_id, note=note,
                        created_by_id=user_id, document_import_id=document.id,
                    )
                    for _ in range(row.pieces)
                ]
                db.add_all(items)
                await db.flush()
                ids = [item.id for item in items]
                activity.add_event(
                    db, activity.RECEIVE, user_id, material_id=material.id,
                    stock_item_id=ids[0] if len(ids) == 1 else None,
                    quantity=len(ids), length_mm=row.length_mm * len(ids),
                    details={"piece_length_mm": row.length_mm, "item_ids": ids, "document_import_id": document.id},
                )
                pieces_total += len(ids)
                rows_done.append({
                    "line": row.line, "kind": sp.STOCK, "title": material.name, "pieces": len(ids),
                    "length_mm": row.length_mm, "first_item_id": min(ids), "last_item_id": max(ids),
                })
            else:
                product = products.get(key)
                new = product is None
                if new:
                    product = Product(
                        name=row.title, sku=row.code, unit=row.unit, quantity=0,
                        product_type_id=product_type_ids.get(row.line), location_id=location_id,
                    )
                    db.add(product)
                    await db.flush()
                    new_products += 1
                    products[key] = product
                product = await inventory.apply_quantity_change(
                    db, product.id, row.count, inventory.RECEIVE, user_id,
                    document_import_id=document.id, new=new,
                )
                rows_done.append({
                    "line": row.line, "kind": sp.GOODS, "title": product.name, "count": row.count,
                    "unit": product.unit, "quantity_after": product.quantity,
                })

        details = {
            "document_import_id": document.id, "number": spec.number,
            "date": spec.date.isoformat() if spec.date else None, "supplier": spec.supplier,
            "filename": document.filename, "rows": len(spec.rows), "stock_pieces": pieces_total,
            "new_materials": new_materials, "new_products": new_products,
        }
        activity.add_event(db, activity.IMPORT, user_id, quantity=len(spec.rows), details=details)
        await db.commit()
    except IntegrityError:
        # Another import of the same document won the race
        await db.rollback()
        raise DomainError("This document is already in stock", status_code=409) from None
    except Exception:
        await db.rollback()
        raise
    return {"import_id": document.id, **details, "result": rows_done}


async def list_imports(db: AsyncSession, limit: int = 50) -> list[DocumentImport]:
    result = await db.execute(
        select(DocumentImport).options(joinedload(DocumentImport.user)).order_by(DocumentImport.id.desc()).limit(limit)
    )
    return list(result.scalars())
