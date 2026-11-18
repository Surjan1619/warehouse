"""Putting a supplier's specification into stock: preview, confirm, no second time."""
import json
from collections import Counter

from sqlalchemy import func, select

from app.models.Alchemy_models import ActivityEvent, DocumentImport, Material, Movement, Product, StockItem
from tests.spec_files import EUR, RUB, make_spec
from tests.conftest import TEST_PASSWORD

XLSM = "application/vnd.ms-excel.sheet.macroEnabled.12"


def upload(path_or_bytes, name="spec.xlsm"):
    data = path_or_bytes if isinstance(path_or_bytes, bytes) else path_or_bytes.read_bytes()
    return {"file": (name, data, XLSM)}


async def preview(client, headers, source, **kw):
    return await client.post("/imports/preview", files=upload(source, **kw), headers=headers)


async def confirm(client, headers, source, data=None, **kw):
    return await client.post("/imports/", files=upload(source, **kw), data=data or {}, headers=headers)


async def count(sessions, model) -> int:
    async with sessions() as db:
        return await db.scalar(select(func.count()).select_from(model))


async def test_preview_tells_everything_and_writes_nothing(client, worker, sessions):
    _, headers = worker
    response = await preview(client, headers, RUB, name="618E_7.XLSM")
    assert response.status_code == 200, response.text
    body = response.json()
    assert (body["number"], body["date"], body["filename"]) == ("618E/7", "2026-08-03", "618E_7.XLSM")
    assert body["can_import"] is True and body["previous"] is None
    assert body["summary"] == {
        "stock_rows": 21, "stock_pieces": 3075, "new_materials": 12,
        "goods_rows": 17, "new_products": 13, "problems": 0,
    }
    profile = next(r for r in body["rows"] if r["line"] == 19)
    assert (profile["kind"], profile["quantity"], profile["length_mm"], profile["pieces"]) == ("stock", "3045", 7000, 435)
    assert profile["material"] is None  # nothing has its code yet

    assert await count(sessions, StockItem) == 0
    assert await count(sessions, Material) == 0
    assert await count(sessions, DocumentImport) == 0


async def test_confirm_puts_the_whole_document_into_stock(client, worker, admin, sessions):
    user, headers = worker
    response = await confirm(client, headers, RUB)
    assert response.status_code == 201, response.text
    result = response.json()
    assert (result["number"], result["rows"], result["stock_pieces"]) == ("618E/7", 38, 3075)
    assert (result["new_materials"], result["new_products"]) == (12, 13)

    async with sessions() as db:
        items = (await db.execute(select(StockItem))).scalars().all()
        assert len(items) == 3075
        assert {i.document_import_id for i in items} == {result["import_id"]}
        assert {i.created_by_id for i in items} == {user.id}
        assert {i.note for i in items} == {"Спецификация № 618E/7"}

        profile = await db.scalar(select(Material).where(Material.sku == "303001113"))
        assert profile.name == "Профиль роллетный роликовой прокатки AG/77, цвет 113"
        lengths = Counter(i.length_mm for i in items if i.material_id == profile.id)
        assert lengths == {5000: 225, 5500: 450, 7000: 435 + 435 + 300}

        # Two rows of 100 pairs of the same roller: one product of 200 pairs
        roller = await db.scalar(select(Product).where(Product.sku == "1031501"))
        assert (roller.name, roller.quantity, roller.unit) == ("Ролик направляющий RGV/77, цвет 00", 200, "пар")
        drive = await db.scalar(select(Product).where(Product.sku == "326017000"))
        assert (drive.quantity, drive.unit) == (110, "кмт")
        moves = (await db.execute(select(Movement))).scalars().all()
        assert len(moves) == 17 and {m.document_import_id for m in moves} == {result["import_id"]}

        events = (await db.execute(select(ActivityEvent).order_by(ActivityEvent.id))).scalars().all()
    actions = Counter(e.action for e in events)
    assert actions == {"receive": 21, "product_receive": 17, "import": 1}
    imported = events[-1]
    assert (imported.action, imported.user_id, imported.details["stock_pieces"]) == ("import", user.id, 3075)
    # The first receipt of a product just created is marked new, the second row of it is not
    roller_events = [e for e in events if e.action == "product_receive" and e.details["product_name"].startswith("Ролик")]
    assert [e.details.get("new", False) for e in roller_events] == [True, False]
    assert [e.details["unit"] for e in roller_events] == ["пар", "пар"]


async def test_the_same_delivery_is_not_taken_twice(client, worker, sessions):
    _, headers = worker
    assert (await confirm(client, headers, RUB)).status_code == 201

    # The copy in euros has the same number and date
    again = await preview(client, headers, EUR)
    assert again.status_code == 200
    assert again.json()["can_import"] is False
    assert again.json()["previous"]["number"] == "618E/7"
    assert again.json()["previous"]["user"]["username"]

    for source in (EUR, RUB):
        response = await confirm(client, headers, source)
        assert response.status_code == 409
        assert response.json()["detail"] == "This document is already in stock"
    assert await count(sessions, StockItem) == 3075
    assert await count(sessions, DocumentImport) == 1


async def test_known_codes_are_added_to_what_is_there(client, worker, sessions):
    _, headers = worker
    await client.post("/materials/", json={"name": "Шина 90", "sku": "S-1"}, headers=headers)
    existing = (await client.post(
        "/products/", json={"name": "Мотор (наш)", "quantity": 4, "unit": "шт", "sku": "M-1"}, headers=headers
    )).json()
    async with sessions() as db:  # the product API does not take a code: set it as an import would
        product = await db.get(Product, existing["id"])
        product.sku = "M-1"
        await db.commit()

    data = make_spec([
        ["S-1", "GR90", "Шина направляющая", "213", "6", "м", 12],
        ["M-1", "AM2", "Привод", "-", "-", "шт", 3],
    ])
    body = (await preview(client, headers, data)).json()
    assert body["summary"]["new_materials"] == 0 and body["summary"]["new_products"] == 0
    assert body["rows"][0]["material"]["name"] == "Шина 90"
    assert body["rows"][1]["product"]["name"] == "Мотор (наш)"

    assert (await confirm(client, headers, data)).status_code == 201
    async with sessions() as db:
        assert (await db.get(Product, existing["id"], populate_existing=True)).quantity == 7
        assert await count(sessions, Material) == 1
        assert await db.scalar(select(func.count()).select_from(StockItem).where(StockItem.length_mm == 6000)) == 2


async def test_a_product_in_other_units_is_not_mixed(client, worker, sessions):
    _, headers = worker
    data = make_spec([["R-1", "RGV", "Ролик", "-", "-", "пар", 10]], number="A-1")
    assert (await confirm(client, headers, data)).status_code == 201

    other = make_spec([["R-1", "RGV", "Ролик", "-", "-", "шт", 10]], number="A-2")
    body = (await preview(client, headers, other)).json()
    assert body["rows"][0]["problem"] == "unit_differs" and body["can_import"] is False
    assert (await confirm(client, headers, other)).status_code == 422
    async with sessions() as db:
        assert (await db.scalar(select(Product).where(Product.sku == "R-1"))).quantity == 10


async def test_rows_with_problems_stop_the_whole_document(client, worker, sessions):
    _, headers = worker
    data = make_spec([
        ["A-1", "AG", "Профиль", "113", "7", "м", 14],
        ["B-1", "AG", "Профиль", "113", "7", "м", 10],  # 10 m is not whole pieces of 7 m
    ])
    body = (await preview(client, headers, data)).json()
    assert [r["problem"] for r in body["rows"]] == [None, "not_whole_pieces"]
    assert body["summary"]["problems"] == 1 and body["can_import"] is False
    response = await confirm(client, headers, data)
    assert response.status_code == 422
    assert await count(sessions, StockItem) == 0
    assert await count(sessions, DocumentImport) == 0


async def test_place_and_types_for_new_goods(client, worker, admin, sessions):
    _, headers = worker
    _, admin_headers = admin
    place = (await client.post("/locations/", json={"name": "Стеллаж Б"}, headers=headers)).json()
    motors = (await client.post("/products/types", json={"name": "Моторы"}, headers=admin_headers)).json()
    data = make_spec([
        ["A-1", "AG", "Профиль", "113", "7", "м", 7],
        ["M-1", "AM2", "Привод", "-", "-", "кмт", 2],
    ])
    bad = await confirm(client, headers, data, {"product_types": json.dumps({"7": 999})})
    assert bad.status_code == 404
    response = await confirm(
        client, headers, data, {"location_id": str(place["id"]), "product_types": json.dumps({"7": motors["id"]})}
    )
    assert response.status_code == 201, response.text
    async with sessions() as db:
        item = await db.scalar(select(StockItem))
        product = await db.scalar(select(Product).where(Product.sku == "M-1"))
    assert item.location_id == place["id"]
    assert (product.location_id, product.product_type_id, product.unit) == (place["id"], motors["id"], "кмт")


async def test_files_that_are_not_specifications(client, worker):
    _, headers = worker
    response = await preview(client, headers, b"just text", name="notes.txt")
    assert response.status_code == 422
    assert response.json()["detail"] == "Not an Excel file"


async def test_needs_a_token(client):
    assert (await client.post("/imports/preview", files=upload(RUB))).status_code == 401


async def test_history_and_clearing(client, worker, admin, sessions):
    _, headers = worker
    _, admin_headers = admin
    await confirm(client, headers, RUB)
    history = (await client.get("/imports/", headers=headers)).json()
    assert [h["number"] for h in history] == ["618E/7"]
    assert history[0]["created_at"].endswith("+00:00")

    response = await client.post(
        "/maintenance/clear", json={"password": TEST_PASSWORD, "stock": True}, headers=admin_headers
    )
    assert response.status_code == 200, response.text
    assert response.json()["deleted"]["document_imports"] == 1
    # After clearing, the same document can be taken in again
    assert (await confirm(client, headers, RUB)).status_code == 201
