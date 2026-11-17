"""Assemblies: cuts and piece goods for one product, planned and finished in one transaction."""
import asyncio
import uuid

from sqlalchemy import select

from app.models.Alchemy_models import ActivityEvent, CutOperation, Movement


def key() -> str:
    return uuid.uuid4().hex


async def make_product(client, headers, name="Мотор 600", quantity=5):
    response = await client.post("/products/", json={"name": name, "quantity": quantity}, headers=headers)
    assert response.status_code == 200, response.text
    return response.json()


async def plan(client, headers, materials=(), products=()):
    response = await client.post(
        "/assemblies/plan", json={"materials": list(materials), "products": list(products)}, headers=headers
    )
    assert response.status_code == 200, response.text
    return response.json()


def cuts_of(planned: dict) -> list[dict]:
    """Turn a plan into the cuts the browser sends to finish the assembly."""
    return [
        {"source_item_id": cut["item"]["id"], "pieces": [{"length_mm": p["length_mm"], "used": p["used"]} for p in cut["pieces"]]}
        for material in planned["materials"]
        for cut in material["cuts"]
    ]


async def finish(client, headers, planned=None, products=(), client_key=None, **extra):
    body = {
        "client_key": client_key or key(),
        "cuts": cuts_of(planned) if planned else [],
        "products": list(products),
        **extra,
    }
    return await client.post("/assemblies/", json=body, headers=headers)


async def items(client, headers, material_id):
    response = await client.get(f"/stock-items/?material_id={material_id}", headers=headers)
    return {item["id"]: item for item in response.json()}


def line(material, *pieces):
    return {"material_id": material["id"], "pieces": [dict(length_mm=l, quantity=q, used=u) for l, q, u in pieces]}


# --- 1. Only piece goods ---
async def test_assembly_of_goods_only(client, worker):
    _, headers = worker
    motor = await make_product(client, headers, quantity=3)
    remote = await make_product(client, headers, name="Пульт", quantity=10)
    goods = [{"product_id": motor["id"], "quantity": 1}, {"product_id": remote["id"], "quantity": 2}]

    planned = await plan(client, headers, products=goods)
    assert planned["ok"] is True
    assert [(p["product"]["name"], p["quantity"], p["available"]) for p in planned["products"]] == [
        ("Мотор 600", 1, 3), ("Пульт", 2, 10),
    ]

    response = await finish(client, headers, products=goods, name="Ворота №1")
    assert response.status_code == 201, response.text
    assembly = response.json()
    assert assembly["name"] == "Ворота №1"
    assert assembly["cuts"] == []
    assert sorted((g["product"]["name"], g["quantity"]) for g in assembly["goods"]) == [("Мотор 600", 1), ("Пульт", 2)]
    left = {p["name"]: p["quantity"] for p in (await client.get("/products/", headers=headers)).json()}
    assert left == {"Мотор 600": 2, "Пульт": 8}


# --- 2. Only material to cut; 6. several lengths; 7. remainder back to stock ---
async def test_assembly_of_cuts_only_with_several_lengths(client, worker, material, receive):
    _, headers = worker
    source = (await receive(7000))[0]
    planned = await plan(client, headers, materials=[line(material, (3000, 1, True), (1500, 2, True))])
    assert planned["ok"] is True
    [cut] = planned["materials"][0]["cuts"]
    assert cut["item"]["id"] == source["id"]
    assert cut["remainder_mm"] == 1000 and cut["remainder_fate"] == "stock"

    response = await finish(client, headers, planned)
    assert response.status_code == 201, response.text
    [operation] = response.json()["cuts"]
    results = sorted((r["length_mm"], r["status"]) for r in operation["results"])
    assert results == [(1000, "in_stock"), (1500, "used"), (1500, "used"), (3000, "used")]

    stock = await items(client, headers, material["id"])
    assert stock[source["id"]]["status"] == "cut"
    # The remainder is a new stock item with its own number
    remainder = next(r for r in operation["results"] if r["length_mm"] == 1000)
    assert remainder["id"] != source["id"] and remainder["code"].startswith("T-")


async def test_pieces_marked_for_stock_stay_in_stock(client, worker, material, receive):
    _, headers = worker
    await receive(6000)
    planned = await plan(client, headers, materials=[line(material, (2000, 1, True), (2000, 2, False))])
    response = await finish(client, headers, planned)
    statuses = sorted(r["status"] for r in response.json()["cuts"][0]["results"])
    assert statuses == ["in_stock", "in_stock", "used"]


async def test_pieces_spread_over_several_items(client, worker, material, receive):
    _, headers = worker
    await receive(3000, count=2)
    planned = await plan(client, headers, materials=[line(material, (2500, 2, True))])
    assert planned["ok"] is True and len(planned["materials"][0]["cuts"]) == 2
    response = await finish(client, headers, planned)
    assert len(response.json()["cuts"]) == 2


async def test_kerf_and_short_remainder_are_planned(client, worker):
    _, headers = worker
    material = (await client.post(
        "/materials/", json={"name": "Профиль", "kerf_mm": 5, "min_usable_length_mm": 500}, headers=headers
    )).json()
    response = await client.post("/stock-items/", json={"material_id": material["id"], "length_mm": 3000}, headers=headers)
    assert response.status_code == 201, response.text
    planned = await plan(client, headers, materials=[line(material, (1400, 2, True))])
    [cut] = planned["materials"][0]["cuts"]
    # 1400 + 5 + 1400, then one more cut of 5: 190 mm left, shorter than 500
    assert cut["kerf_loss_mm"] == 10 and cut["remainder_mm"] == 190 and cut["remainder_fate"] == "scrap"


# --- 3. Material and goods together ---
async def test_assembly_of_cuts_and_goods(client, worker, material, receive):
    user, headers = worker
    await receive(6000)
    motor = await make_product(client, headers, quantity=2)
    goods = [{"product_id": motor["id"], "quantity": 1}]
    planned = await plan(client, headers, materials=[line(material, (2000, 2, True))], products=goods)
    assert planned["ok"] is True

    response = await finish(client, headers, planned, products=goods)
    assert response.status_code == 201
    assembly = response.json()
    assert len(assembly["cuts"]) == 1 and assembly["goods"][0]["quantity"] == 1
    assert assembly["user"]["id"] == user.id


# --- 4. Not enough of a product; 8. failure in the middle of finishing ---
async def test_not_enough_goods_is_shown_and_refused(client, worker, material, receive, sessions):
    _, headers = worker
    source = (await receive(6000))[0]
    motor = await make_product(client, headers, quantity=1)
    goods = [{"product_id": motor["id"], "quantity": 2}]
    planned = await plan(client, headers, materials=[line(material, (2000, 1, True))], products=goods)
    assert planned["ok"] is False
    assert planned["products"][0]["available"] == 1

    # The cut is applied first, then taking the goods fails. Nothing of it may stay.
    response = await finish(client, headers, planned, products=goods)
    assert response.status_code == 400
    assert "1 left" in response.json()["detail"]

    stock = await items(client, headers, material["id"])
    assert [i["status"] for i in stock.values()] == ["in_stock"] and source["id"] in stock
    assert (await client.get("/products/", headers=headers)).json()[0]["quantity"] == 1
    async with sessions() as db:
        assert (await db.execute(select(CutOperation))).scalars().all() == []
        assert (await db.execute(select(Movement))).scalars().all() == []
        # Only what happened before the assembly: stock received, the motor created
        before = ("receive", "product_receive")
        assert (await db.execute(select(ActivityEvent).where(ActivityEvent.action.notin_(before)))).scalars().all() == []
    assert (await client.get("/assemblies/", headers=headers)).json() == []


async def test_same_product_twice_is_summed(client, worker):
    _, headers = worker
    motor = await make_product(client, headers, quantity=3)
    goods = [{"product_id": motor["id"], "quantity": 2}, {"product_id": motor["id"], "quantity": 2}]
    planned = await plan(client, headers, products=goods)
    assert planned["ok"] is False
    assert [(p["quantity"], p["available"]) for p in planned["products"]] == [(4, 3)]
    assert (await finish(client, headers, products=goods)).status_code == 400


# --- 5. Not enough length ---
async def test_piece_longer_than_any_item_is_unplaced(client, worker, material, receive):
    _, headers = worker
    await receive(2000)
    planned = await plan(client, headers, materials=[line(material, (2500, 1, True), (1000, 1, True))])
    assert planned["ok"] is False
    [m] = planned["materials"]
    assert [p["length_mm"] for p in m["unplaced"]] == [2500]
    assert m["longest_available_mm"] == 2000


async def test_material_with_no_stock_is_unplaced(client, worker, material):
    _, headers = worker
    planned = await plan(client, headers, materials=[line(material, (500, 3, True))])
    assert planned["ok"] is False
    assert len(planned["materials"][0]["unplaced"]) == 3
    assert planned["materials"][0]["longest_available_mm"] is None


async def test_piece_that_does_not_fit_the_chosen_item_rolls_back(client, worker, material, receive):
    _, headers = worker
    source = (await receive(2000))[0]
    motor = await make_product(client, headers, quantity=5)
    body = {
        "client_key": key(),
        "products": [{"product_id": motor["id"], "quantity": 1}],
        "cuts": [{"source_item_id": source["id"], "pieces": [{"length_mm": 2500, "used": True}]}],
    }
    response = await client.post("/assemblies/", json=body, headers=headers)
    assert response.status_code == 400
    assert (await client.get("/products/", headers=headers)).json()[0]["quantity"] == 5
    assert (await items(client, headers, material["id"]))[source["id"]]["status"] == "in_stock"


# --- The plan went stale before finishing ---
async def test_item_taken_meanwhile_is_refused(client, worker, material, receive):
    _, headers = worker
    source = (await receive(6000))[0]
    planned = await plan(client, headers, materials=[line(material, (2000, 1, True))])
    # Someone else cuts the same piece first
    other = await client.post(
        "/cuts/", json={"source_item_id": source["id"], "pieces": [{"length_mm": 1000}]}, headers=headers
    )
    assert other.status_code == 201, other.text
    response = await finish(client, headers, planned)
    assert response.status_code == 409
    assert "refresh the plan" in response.json()["detail"]


# --- 9. Pressing "finish" twice ---
async def test_repeated_submit_saves_once(client, worker, material, receive):
    _, headers = worker
    await receive(6000)
    motor = await make_product(client, headers, quantity=5)
    goods = [{"product_id": motor["id"], "quantity": 2}]
    planned = await plan(client, headers, materials=[line(material, (2000, 1, True))], products=goods)
    same_key = key()

    first = await finish(client, headers, planned, products=goods, client_key=same_key)
    second = await finish(client, headers, planned, products=goods, client_key=same_key)
    assert first.status_code == 201 and second.status_code == 200
    assert first.json()["id"] == second.json()["id"]
    assert (await client.get("/products/", headers=headers)).json()[0]["quantity"] == 3
    assert len((await client.get("/assemblies/", headers=headers)).json()) == 1


async def test_simultaneous_submits_save_once(client, worker, material, receive):
    _, headers = worker
    await receive(6000)
    motor = await make_product(client, headers, quantity=5)
    goods = [{"product_id": motor["id"], "quantity": 2}]
    planned = await plan(client, headers, materials=[line(material, (2000, 1, True))], products=goods)
    same_key = key()

    responses = await asyncio.gather(*(
        finish(client, headers, planned, products=goods, client_key=same_key) for _ in range(3)
    ))
    assert sorted(r.status_code for r in responses) == [200, 200, 201], [r.text for r in responses]
    assert len({r.json()["id"] for r in responses}) == 1
    assert (await client.get("/products/", headers=headers)).json()[0]["quantity"] == 3


# --- 10. History and author ---
async def test_history_keeps_author_and_links(client, worker, material, receive, sessions):
    user, headers = worker
    await receive(6000)
    motor = await make_product(client, headers, quantity=5)
    goods = [{"product_id": motor["id"], "quantity": 2}]
    planned = await plan(client, headers, materials=[line(material, (2000, 1, True))], products=goods)
    assembly = (await finish(client, headers, planned, products=goods, name="Ворота")).json()
    assert assembly["created_at"].endswith("+00:00")

    async with sessions() as db:
        operation = (await db.execute(select(CutOperation))).scalar_one()
        movement = (await db.execute(select(Movement))).scalar_one()
        events = (await db.execute(select(ActivityEvent).order_by(ActivityEvent.id))).scalars().all()
    assert (operation.assembly_id, operation.user_id) == (assembly["id"], user.id)
    assert (movement.assembly_id, movement.user_id, movement.change_type, movement.quantity_changed) == (
        assembly["id"], user.id, "issue", -2,
    )
    assembled = [e for e in events if e.action == "assemble"]
    assert len(assembled) == 1 and assembled[0].user_id == user.id
    assert assembled[0].details == {
        "assembly_id": assembly["id"], "name": "Ворота", "cut_operation_ids": [operation.id],
        "products": [{"product_id": motor["id"], "name": "Мотор 600", "quantity": 2}],
    }
    issued = [e for e in events if e.action == "product_issue"]
    assert [(e.product_id, e.quantity, e.user_id, e.details["assembly_id"]) for e in issued] == [
        (motor["id"], 2, user.id, assembly["id"]),
    ]
    # The cut is journalled as before
    assert {"cut", "use"} <= {e.action for e in events}

    detail = (await client.get(f"/assemblies/{assembly['id']}", headers=headers)).json()
    assert detail["id"] == assembly["id"] and len(detail["cuts"]) == 1


async def test_cut_of_an_assembly_can_be_cancelled(client, worker, material, receive):
    _, headers = worker
    source = (await receive(6000))[0]
    planned = await plan(client, headers, materials=[line(material, (2000, 1, True))])
    assembly = (await finish(client, headers, planned)).json()
    cut_id = assembly["cuts"][0]["id"]
    assert (await client.post(f"/cuts/{cut_id}/cancel", headers=headers)).status_code == 200
    assert (await items(client, headers, material["id"]))[source["id"]]["status"] == "in_stock"


# --- Validation ---
async def test_empty_assembly_is_refused(client, worker):
    _, headers = worker
    response = await client.post("/assemblies/", json={"client_key": key()}, headers=headers)
    assert response.status_code == 422


async def test_unknown_product_or_material_is_404(client, worker):
    _, headers = worker
    response = await client.post("/assemblies/plan", json={"products": [{"product_id": 999, "quantity": 1}]}, headers=headers)
    assert response.status_code == 404
    response = await client.post(
        "/assemblies/plan", json={"materials": [{"material_id": 999, "pieces": [{"length_mm": 100}]}]}, headers=headers
    )
    assert response.status_code == 404
    assert (await client.get("/assemblies/999", headers=headers)).status_code == 404


async def test_bad_lines_are_rejected(client, worker, material):
    _, headers = worker
    for body in (
        {"products": [{"product_id": 1, "quantity": 0}]},
        {"materials": [{"material_id": material["id"], "pieces": [{"length_mm": 0}]}]},
        {"materials": [{"material_id": material["id"], "pieces": [{"length_mm": 100, "quantity": 0}]}]},
        {"materials": [{"material_id": material["id"], "pieces": []}]},
    ):
        assert (await client.post("/assemblies/plan", json=body, headers=headers)).status_code == 422
    assert (await client.post("/assemblies/", json={"client_key": "short", "products": []}, headers=headers)).status_code == 422


async def test_assemblies_need_a_token(client):
    assert (await client.post("/assemblies/plan", json={})).status_code == 401
    assert (await client.get("/assemblies/")).status_code == 401
