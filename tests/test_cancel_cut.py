"""Undoing a cut made by mistake: POST /cuts/{id}/cancel."""


async def make_cut(client, headers, source_id, *lengths, used=False, **piece_extra):
    body = {"source_item_id": source_id, "pieces": [{"length_mm": l, "used": used, **piece_extra} for l in lengths]}
    response = await client.post("/cuts/", json=body, headers=headers)
    assert response.status_code == 201, response.text
    return response.json()


async def get_item(client, headers, item_id):
    response = await client.get(f"/stock-items/{item_id}", headers=headers)
    assert response.status_code == 200, response.text
    return response.json()


async def make_order(client, headers, number="З-1"):
    response = await client.post("/orders/", json={"number": number, "customer_name": "Иванов"}, headers=headers)
    assert response.status_code == 201, response.text
    return response.json()


async def test_cancel_returns_the_source_and_cancels_the_pieces(client, worker, receive):
    user, headers = worker
    [pipe] = await receive(7000)
    cut = await make_cut(client, headers, pipe["id"], 3000, 3000)

    response = await client.post(f"/cuts/{cut['id']}/cancel", headers=headers)
    assert response.status_code == 200, response.text
    cancelled = response.json()
    assert cancelled["cancelled_at"].endswith("+00:00")
    assert cancelled["cancelled_by_id"] == user.id
    assert cancelled["source_item"]["status"] == "in_stock"
    assert cancelled["source_item"]["length_mm"] == 7000
    assert [piece["status"] for piece in cancelled["results"]] == ["cancelled"] * 3

    # The pipe can be cut again, the cancelled pieces are not offered
    response = await client.post(
        "/cuts/suggest", json={"material_id": pipe["material"]["id"], "pieces": [1000]}, headers=headers
    )
    assert [c["item"]["id"] for c in response.json()["candidates"]] == [pipe["id"]]
    await make_cut(client, headers, pipe["id"], 2000)


async def test_cancelled_pieces_leave_the_stock_list(client, worker, receive):
    _, headers = worker
    [pipe] = await receive(7000)
    cut = await make_cut(client, headers, pipe["id"], 3000)
    await client.post(f"/cuts/{cut['id']}/cancel", headers=headers)

    in_stock = (await client.get("/stock-items/?status=in_stock", headers=headers)).json()
    assert [item["id"] for item in in_stock] == [pipe["id"]]
    cancelled = (await client.get("/stock-items/?status=cancelled", headers=headers)).json()
    assert sorted(item["length_mm"] for item in cancelled) == [3000, 4000]


async def test_cut_with_used_pieces_and_scrap_can_be_cancelled(client, worker, receive):
    _, headers = worker
    [pipe] = await receive(7000)
    cut = await make_cut(client, headers, pipe["id"], 6800, used=True)  # 200 mm remainder is scrap
    assert sorted(p["status"] for p in cut["results"]) == ["scrap", "used"]

    response = await client.post(f"/cuts/{cut['id']}/cancel", headers=headers)
    assert response.status_code == 200, response.text
    assert sorted(p["status"] for p in response.json()["results"]) == ["cancelled", "cancelled"]
    assert (await get_item(client, headers, pipe["id"]))["status"] == "in_stock"


async def test_a_cut_cannot_be_cancelled_twice(client, worker, receive):
    _, headers = worker
    [pipe] = await receive(7000)
    cut = await make_cut(client, headers, pipe["id"], 3000)
    assert (await client.post(f"/cuts/{cut['id']}/cancel", headers=headers)).status_code == 200
    response = await client.post(f"/cuts/{cut['id']}/cancel", headers=headers)
    assert response.status_code == 409


async def test_a_piece_cut_further_blocks_the_cancel_until_that_cut_is_cancelled(client, worker, receive):
    _, headers = worker
    [pipe] = await receive(7000)
    first = await make_cut(client, headers, pipe["id"], 3000)
    remainder = next(p for p in first["results"] if p["length_mm"] == 4000)
    second = await make_cut(client, headers, remainder["id"], 1000)

    response = await client.post(f"/cuts/{first['id']}/cancel", headers=headers)
    assert response.status_code == 409
    assert remainder["code"] in response.json()["detail"]
    # Nothing changed
    assert (await get_item(client, headers, pipe["id"]))["status"] == "cut"
    assert (await get_item(client, headers, remainder["id"]))["status"] == "cut"

    # Cancelling in reverse order works
    assert (await client.post(f"/cuts/{second['id']}/cancel", headers=headers)).status_code == 200
    assert (await get_item(client, headers, remainder["id"]))["status"] == "in_stock"
    assert (await client.post(f"/cuts/{first['id']}/cancel", headers=headers)).status_code == 200
    assert (await get_item(client, headers, pipe["id"]))["status"] == "in_stock"
    assert (await get_item(client, headers, remainder["id"]))["status"] == "cancelled"


async def test_any_cut_can_be_cancelled_not_only_the_last(client, worker, receive):
    _, headers = worker
    first_pipe, second_pipe = await receive(7000, count=2)
    first = await make_cut(client, headers, first_pipe["id"], 3000)
    await make_cut(client, headers, second_pipe["id"], 2000)

    assert (await client.post(f"/cuts/{first['id']}/cancel", headers=headers)).status_code == 200
    assert (await get_item(client, headers, first_pipe["id"]))["status"] == "in_stock"
    assert (await get_item(client, headers, second_pipe["id"]))["status"] == "cut"


async def test_a_reserved_source_is_reserved_again(client, worker, receive):
    _, headers = worker
    order = await make_order(client, headers)
    [pipe] = await receive(7000)
    await client.post(f"/stock-items/{pipe['id']}/assign", json={"order_id": order["id"]}, headers=headers)
    cut = await make_cut(client, headers, pipe["id"], 3000)

    await client.post(f"/cuts/{cut['id']}/cancel", headers=headers)
    source = await get_item(client, headers, pipe["id"])
    assert source["status"] == "reserved"
    assert source["order"]["id"] == order["id"]


async def test_a_reservation_for_a_closed_order_is_not_restored(client, worker, receive):
    _, headers = worker
    order = await make_order(client, headers)
    [pipe] = await receive(7000)
    await client.post(f"/stock-items/{pipe['id']}/assign", json={"order_id": order["id"]}, headers=headers)
    cut = await make_cut(client, headers, pipe["id"], 3000)
    response = await client.patch(f"/orders/{order['id']}", json={"status": "cancelled"}, headers=headers)
    assert response.status_code == 200, response.text

    await client.post(f"/cuts/{cut['id']}/cancel", headers=headers)
    source = await get_item(client, headers, pipe["id"])
    assert source["status"] == "in_stock"
    assert source["order"] is None


async def test_pieces_of_a_cancelled_cut_no_longer_count_for_the_order(client, worker, receive):
    _, headers = worker
    order = await make_order(client, headers)
    [pipe] = await receive(7000)
    cut = await make_cut(client, headers, pipe["id"], 3000, order_id=order["id"])

    await client.post(f"/cuts/{cut['id']}/cancel", headers=headers)
    detail = (await client.get(f"/orders/{order['id']}", headers=headers)).json()
    assert detail["items"] == []
    assert detail["total_length_mm"] == 0


async def test_each_cut_of_a_batch_is_cancelled_on_its_own(client, worker, receive):
    _, headers = worker
    first_pipe, second_pipe = await receive(7000, count=2)
    body = {
        "cuts": [
            {"source_item_id": first_pipe["id"], "pieces": [{"length_mm": 3000}, {"length_mm": 3000}]},
            {"source_item_id": second_pipe["id"], "pieces": [{"length_mm": 3000}]},
        ]
    }
    response = await client.post("/cuts/batch", json=body, headers=headers)
    assert response.status_code == 201, response.text
    first, _ = response.json()

    assert (await client.post(f"/cuts/{first['id']}/cancel", headers=headers)).status_code == 200
    assert (await get_item(client, headers, first_pipe["id"]))["status"] == "in_stock"
    assert (await get_item(client, headers, second_pipe["id"]))["status"] == "cut"


async def test_cancelled_cut_is_listed_with_its_mark(client, worker, receive):
    _, headers = worker
    [pipe] = await receive(7000)
    cut = await make_cut(client, headers, pipe["id"], 3000)
    await client.post(f"/cuts/{cut['id']}/cancel", headers=headers)
    again = await make_cut(client, headers, pipe["id"], 2000)

    cuts = (await client.get(f"/cuts/?source_item_id={pipe['id']}", headers=headers)).json()
    assert [(c["id"], c["cancelled_at"] is None) for c in cuts] == [(again["id"], True), (cut["id"], False)]


async def test_admin_can_cancel_a_cut_of_a_worker(client, worker, admin, receive):
    _, worker_headers = worker
    _, admin_headers = admin
    [pipe] = await receive(7000)
    cut = await make_cut(client, worker_headers, pipe["id"], 3000)
    assert (await client.post(f"/cuts/{cut['id']}/cancel", headers=admin_headers)).status_code == 200


async def test_unknown_cut_is_404(client, worker):
    _, headers = worker
    assert (await client.post("/cuts/999/cancel", headers=headers)).status_code == 404


async def test_cancel_needs_a_token(client, worker, receive):
    _, headers = worker
    [pipe] = await receive(7000)
    cut = await make_cut(client, headers, pipe["id"], 3000)
    assert (await client.post(f"/cuts/{cut['id']}/cancel")).status_code == 401
