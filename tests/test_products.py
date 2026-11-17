"""Piece goods: product types (admin only) and restocking / taking out of stock."""
import pytest
from sqlalchemy import select

from app.models.Alchemy_models import Movement


async def make_product(client, headers, name="Мотор 600", quantity=5, **extra):
    response = await client.post("/products/", json={"name": name, "quantity": quantity, **extra}, headers=headers)
    assert response.status_code == 200, response.text
    return response.json()


# --- Product types: only an admin creates and deletes them ---
async def test_admin_creates_and_deletes_a_type(client, admin):
    _, headers = admin
    response = await client.post("/products/types", json={"name": "Моторы"}, headers=headers)
    assert response.status_code == 200, response.text
    type_id = response.json()["id"]
    assert (await client.delete(f"/products/types/{type_id}", headers=headers)).status_code == 200


async def test_worker_cannot_create_a_type(client, worker):
    _, headers = worker
    response = await client.post("/products/types", json={"name": "Моторы"}, headers=headers)
    assert response.status_code == 403
    assert (await client.get("/products/types", headers=headers)).json() == []


async def test_worker_cannot_delete_a_type(client, worker, admin):
    _, admin_headers = admin
    _, worker_headers = worker
    type_id = (await client.post("/products/types", json={"name": "Моторы"}, headers=admin_headers)).json()["id"]
    assert (await client.delete(f"/products/types/{type_id}", headers=worker_headers)).status_code == 403
    assert len((await client.get("/products/types", headers=admin_headers)).json()) == 1


async def test_worker_sees_types_and_uses_them_for_products(client, worker, admin):
    _, admin_headers = admin
    _, worker_headers = worker
    type_id = (await client.post("/products/types", json={"name": "Моторы"}, headers=admin_headers)).json()["id"]
    assert [t["name"] for t in (await client.get("/products/types", headers=worker_headers)).json()] == ["Моторы"]
    product = await make_product(client, worker_headers, product_type_id=type_id)
    assert product["product_type"]["name"] == "Моторы"


# --- Restocking and taking out of stock ---
async def test_receive_adds_to_the_quantity(client, worker):
    _, headers = worker
    product = await make_product(client, headers, quantity=5)
    response = await client.post(f"/products/{product['id']}/receive", json={"quantity": 3}, headers=headers)
    assert response.status_code == 200, response.text
    assert response.json()["quantity"] == 8


async def test_issue_takes_from_the_quantity(client, worker):
    _, headers = worker
    product = await make_product(client, headers, quantity=5)
    response = await client.post(f"/products/{product['id']}/issue", json={"quantity": 2}, headers=headers)
    assert response.status_code == 200, response.text
    assert response.json()["quantity"] == 3
    listed = (await client.get("/products/", headers=headers)).json()
    assert listed[0]["quantity"] == 3


async def test_issue_of_everything_leaves_zero(client, worker):
    _, headers = worker
    product = await make_product(client, headers, quantity=4)
    response = await client.post(f"/products/{product['id']}/issue", json={"quantity": 4}, headers=headers)
    assert response.json()["quantity"] == 0


async def test_issue_of_more_than_there_is_changes_nothing(client, worker):
    _, headers = worker
    product = await make_product(client, headers, quantity=2)
    response = await client.post(f"/products/{product['id']}/issue", json={"quantity": 3}, headers=headers)
    assert response.status_code == 400
    assert "2 left" in response.json()["detail"]
    assert (await client.get("/products/", headers=headers)).json()[0]["quantity"] == 2


async def test_product_without_quantity_counts_as_zero(client, worker):
    _, headers = worker
    product = await make_product(client, headers, quantity=None)
    assert (await client.post(f"/products/{product['id']}/issue", json={"quantity": 1}, headers=headers)).status_code == 400
    response = await client.post(f"/products/{product['id']}/receive", json={"quantity": 2}, headers=headers)
    assert response.json()["quantity"] == 2


async def test_movements_record_who_changed_what(client, sessions, worker):
    user, headers = worker
    product = await make_product(client, headers, quantity=5)
    await client.post(f"/products/{product['id']}/receive", json={"quantity": 3}, headers=headers)
    await client.post(f"/products/{product['id']}/issue", json={"quantity": 2}, headers=headers)
    # A refused issue leaves no trace
    await client.post(f"/products/{product['id']}/issue", json={"quantity": 100}, headers=headers)

    async with sessions() as db:
        rows = (await db.execute(select(Movement).order_by(Movement.id))).scalars().all()
    assert [(m.change_type, m.quantity_changed, m.user_id) for m in rows] == [
        ("receive", 3, user.id),
        ("issue", -2, user.id),
    ]


async def test_unknown_product_is_404(client, worker):
    _, headers = worker
    assert (await client.post("/products/999/issue", json={"quantity": 1}, headers=headers)).status_code == 404
    assert (await client.post("/products/999/receive", json={"quantity": 1}, headers=headers)).status_code == 404


@pytest.mark.parametrize("quantity", [0, -1, 100001, "abc", None])
async def test_bad_quantity_is_rejected(client, worker, quantity):
    _, headers = worker
    product = await make_product(client, headers, quantity=5)
    for action in ("receive", "issue"):
        response = await client.post(f"/products/{product['id']}/{action}", json={"quantity": quantity}, headers=headers)
        assert response.status_code == 422
    assert (await client.get("/products/", headers=headers)).json()[0]["quantity"] == 5


async def test_quantity_changes_need_a_token(client, worker):
    _, headers = worker
    product = await make_product(client, headers)
    assert (await client.post(f"/products/{product['id']}/issue", json={"quantity": 1})).status_code == 401
    assert (await client.post(f"/products/{product['id']}/receive", json={"quantity": 1})).status_code == 401


# --- Deleting a product ---
async def test_product_without_movements_can_be_deleted(client, worker):
    _, headers = worker
    product = await make_product(client, headers)
    assert (await client.delete(f"/products/{product['id']}", headers=headers)).status_code == 200
    assert (await client.get("/products/", headers=headers)).json() == []


async def test_product_with_movements_is_kept(client, worker):
    _, headers = worker
    product = await make_product(client, headers)
    await client.post(f"/products/{product['id']}/issue", json={"quantity": 1}, headers=headers)
    response = await client.delete(f"/products/{product['id']}", headers=headers)
    assert response.status_code == 409
    assert len((await client.get("/products/", headers=headers)).json()) == 1


# --- Journal: every change of piece goods is an entry ---
async def journal(client, admin_headers, **params):
    response = await client.get("/activity/", params=params, headers=admin_headers)
    assert response.status_code == 200, response.text
    return response.json()["items"]


async def test_receive_and_issue_are_journalled(client, worker, admin):
    user, headers = worker
    _, admin_headers = admin
    type_id = (await client.post("/products/types", json={"name": "Моторы"}, headers=admin_headers)).json()["id"]
    product = await make_product(client, headers, quantity=5, product_type_id=type_id)
    await client.post(f"/products/{product['id']}/receive", json={"quantity": 3}, headers=headers)
    await client.post(f"/products/{product['id']}/issue", json={"quantity": 2}, headers=headers)
    # Refused: leaves no entry
    await client.post(f"/products/{product['id']}/issue", json={"quantity": 100}, headers=headers)

    entries = list(reversed(await journal(client, admin_headers)))
    assert [(e["action"], e["quantity"], e["user"]["id"], e["details"]["quantity_after"]) for e in entries] == [
        ("product_receive", 5, user.id, 5),
        ("product_receive", 3, user.id, 8),
        ("product_issue", 2, user.id, 6),
    ]
    assert entries[0]["details"]["new"] is True
    assert entries[2]["product"] == {"id": product["id"], "name": "Мотор 600", "product_type": {"id": type_id, "name": "Моторы"}}
    assert entries[2]["details"]["product_type"] == "Моторы"

    issues = await journal(client, admin_headers, action="product_issue")
    assert len(issues) == 1


async def test_new_product_without_quantity_is_not_journalled(client, worker, admin):
    _, headers = worker
    _, admin_headers = admin
    await make_product(client, headers, quantity=0)
    assert await journal(client, admin_headers) == []


async def test_journal_keeps_the_name_of_a_deleted_product(client, worker, admin):
    _, headers = worker
    _, admin_headers = admin
    product = await make_product(client, headers, name="Ручка", quantity=2)
    assert (await client.delete(f"/products/{product['id']}", headers=headers)).status_code == 200
    [entry] = await journal(client, admin_headers)
    assert entry["product"] is None
    assert entry["details"]["product_name"] == "Ручка"
