"""Receiving pieces into stock and who is recorded as their author."""


async def test_receive_creates_separate_numbered_pieces(client, worker, receive):
    _, headers = worker
    pieces = await receive(7000, count=3)

    assert [p["code"] for p in pieces] == ["T-000001", "T-000002", "T-000003"]
    assert all(p["length_mm"] == 7000 and p["status"] == "in_stock" for p in pieces)
    assert len((await client.get("/stock-items/", headers=headers)).json()) == 3


async def test_received_pieces_record_who_received_them(client, admin, worker, material):
    admin_user, admin_headers = admin
    worker_user, worker_headers = worker
    body = {"material_id": material["id"], "length_mm": 7000, "count": 2}

    by_worker = (await client.post("/stock-items/", json=body, headers=worker_headers)).json()
    by_admin = (await client.post("/stock-items/", json=body, headers=admin_headers)).json()

    assert [p["created_by"] for p in by_worker] == [{"id": worker_user.id, "username": "worker"}] * 2
    assert [p["created_by"] for p in by_admin] == [{"id": admin_user.id, "username": "admin"}] * 2


async def test_author_is_shown_in_the_list_and_on_the_piece(client, worker, receive):
    user, headers = worker
    (pipe,) = await receive(7000)

    listed = (await client.get("/stock-items/", headers=headers)).json()
    single = (await client.get(f"/stock-items/{pipe['id']}", headers=headers)).json()

    assert listed[0]["created_by"]["username"] == "worker"
    assert single["created_by"]["id"] == user.id


async def test_pieces_from_a_cut_belong_to_whoever_cut(client, admin, worker, receive):
    """The worker received the pipe, the admin cut it: the new pieces are the admin's."""
    admin_user, admin_headers = admin
    worker_user, _ = worker
    (pipe,) = await receive(7000)

    cut = (
        await client.post(
            "/cuts/",
            json={"source_item_id": pipe["id"], "pieces": [{"length_mm": 3000, "used": True}]},
            headers=admin_headers,
        )
    ).json()

    assert cut["source_item"]["created_by"]["id"] == worker_user.id
    assert {r["created_by"]["id"] for r in cut["results"]} == {admin_user.id}


async def test_author_exposes_no_private_fields(client, worker, receive):
    (pipe,) = await receive(7000)
    assert set(pipe["created_by"]) == {"id", "username"}


async def test_receive_validates_input(client, worker, material):
    _, headers = worker
    base = {"material_id": material["id"], "length_mm": 7000, "count": 1}

    async def post(**changes):
        return (await client.post("/stock-items/", json={**base, **changes}, headers=headers)).status_code

    assert await post(length_mm=0) == 422
    assert await post(count=0) == 422
    assert await post(count=501) == 422
    assert await post(material_id=999) == 404
    assert await post(location_id=999) == 404


async def test_list_filters(client, worker, receive):
    _, headers = worker
    await receive(7000, count=2)
    (short,) = await receive(2000)
    await client.post(f"/stock-items/{short['id']}/scrap", headers=headers)

    async def count(query):
        return len((await client.get(f"/stock-items/{query}", headers=headers)).json())

    assert await count("") == 3
    assert await count("?status=in_stock") == 2
    assert await count("?status=scrap") == 1
    assert await count("?min_length_mm=3000") == 2
    assert (await client.get("/stock-items/?status=bogus", headers=headers)).status_code == 422
