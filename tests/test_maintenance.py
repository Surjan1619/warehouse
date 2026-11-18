"""Clearing the database: admin only, with the admin's password, in one transaction."""
from sqlalchemy import func, select

from app.models.Alchemy_models import ActivityEvent, Material, Product, StockItem, User
from tests.conftest import TEST_PASSWORD


async def fill(client, headers, material, receive):
    """Some of everything: stock, a cut, an assembly, goods, a journal."""
    await receive(6000)
    source = (await receive(6000))[0]
    cut = await client.post("/cuts/", json={"source_item_id": source["id"], "pieces": [{"length_mm": 2000}]}, headers=headers)
    assert cut.status_code == 201
    product = (await client.post("/products/", json={"name": "Мотор", "quantity": 3}, headers=headers)).json()
    await client.post(f"/products/{product['id']}/issue", json={"quantity": 1}, headers=headers)
    body = {"client_key": "k" * 16, "products": [{"product_id": product["id"], "quantity": 1}]}
    assert (await client.post("/assemblies/", json=body, headers=headers)).status_code == 201
    await client.post("/locations/", json={"name": "Стеллаж А"}, headers=headers)


async def count(sessions, model) -> int:
    async with sessions() as db:
        return await db.scalar(select(func.count()).select_from(model))


async def events(sessions):
    async with sessions() as db:
        return (await db.execute(select(ActivityEvent).order_by(ActivityEvent.id))).scalars().all()


async def clear(client, headers, **body):
    return await client.post("/maintenance/clear", json={"password": TEST_PASSWORD, **body}, headers=headers)


async def test_wrong_password_changes_nothing(client, admin, worker, material, receive, sessions):
    _, admin_headers = admin
    await fill(client, worker[1], material, receive)
    before = await count(sessions, StockItem)

    response = await client.post(
        "/maintenance/clear", json={"password": "not-the-password", "stock": True, "journal": True}, headers=admin_headers
    )
    # 403, not 401: the admin must not be logged out by a typo
    assert response.status_code == 403
    assert await count(sessions, StockItem) == before
    assert await count(sessions, ActivityEvent) > 0


async def test_only_an_admin_may_clear(client, worker, material, receive, sessions):
    _, headers = worker
    await receive(6000)
    response = await clear(client, headers, stock=True)
    assert response.status_code == 403
    assert await count(sessions, StockItem) == 1


async def test_needs_a_token(client):
    assert (await client.post("/maintenance/clear", json={"password": "x", "stock": True})).status_code == 401


async def test_nothing_chosen_or_catalog_alone_is_refused(client, admin, material, sessions):
    _, headers = admin
    assert (await clear(client, headers)).status_code == 422
    assert (await clear(client, headers, catalog=True, journal=True)).status_code == 422
    assert (await client.post("/maintenance/clear", json={"stock": True}, headers=headers)).status_code == 422
    assert await count(sessions, Material) == 1


async def test_clear_stock_keeps_catalog_and_journal(client, admin, worker, material, receive, sessions):
    admin_user, admin_headers = admin
    await fill(client, worker[1], material, receive)
    journal_before = await count(sessions, ActivityEvent)

    response = await clear(client, admin_headers, stock=True)
    assert response.status_code == 200, response.text
    deleted = response.json()["deleted"]
    assert deleted["stock_items"] == 4  # two received, a piece and a remainder
    assert deleted["cut_operations"] == 1 and deleted["products"] == 1 and deleted["assemblies"] == 1
    assert "activity_log" not in deleted and "materials" not in deleted

    assert await count(sessions, StockItem) == 0
    assert await count(sessions, Product) == 0
    assert await count(sessions, Material) == 1
    assert len((await client.get("/locations/", headers=admin_headers)).json()) == 1

    # The journal is kept, with one more entry about the clearing
    entries = await events(sessions)
    assert len(entries) == journal_before + 1
    assert all(e.stock_item_id is None and e.cut_operation_id is None and e.product_id is None for e in entries)
    reset = entries[-1]
    assert (reset.action, reset.user_id, reset.details["groups"]) == ("reset", admin_user.id, ["stock"])
    # The text of older entries survives: the product name is in details
    assert any(e.details and e.details.get("product_name") == "Мотор" for e in entries)


async def test_clear_everything_keeps_users_and_numbering(client, admin, worker, material, receive, sessions):
    _, admin_headers = admin
    _, worker_headers = worker
    await fill(client, worker_headers, material, receive)
    async with sessions() as db:
        last_id = await db.scalar(select(func.max(StockItem.id)))

    response = await clear(client, admin_headers, stock=True, journal=True, catalog=True)
    assert response.status_code == 200, response.text
    assert await count(sessions, Material) == 0
    assert await count(sessions, User) == 2

    # Only the entry about the clearing is left in the journal
    journal = (await client.get("/activity/", headers=admin_headers)).json()
    assert [e["action"] for e in journal["items"]] == ["reset"]
    assert journal["items"][0]["details"]["groups"] == ["stock", "journal", "catalog"]

    # Work goes on, and a new piece does not get the number of a deleted one
    new_material = (await client.post("/materials/", json={"name": "Профиль"}, headers=worker_headers)).json()
    response = await client.post(
        "/stock-items/", json={"material_id": new_material["id"], "length_mm": 3000}, headers=worker_headers
    )
    assert response.status_code == 201, response.text
    assert response.json()[0]["id"] > last_id


async def test_clear_journal_only(client, admin, material, receive, sessions):
    _, admin_headers = admin
    await receive(6000)
    response = await clear(client, admin_headers, journal=True)
    assert response.status_code == 200
    assert response.json()["deleted"] == {"activity_log": 1}
    assert await count(sessions, StockItem) == 1
    assert [e.action for e in await events(sessions)] == ["reset"]
