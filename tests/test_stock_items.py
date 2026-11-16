"""Receiving pieces into stock and who is recorded as their author."""
import pytest



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


# --- Search by number ---
async def find(client, headers, number, **params):
    return await client.get("/stock-items/", params={"number": number, **params}, headers=headers)


@pytest.mark.parametrize(
    "written",
    ["T-000002", "t-000002", "T000002", "T-2", "t2", "2", "000002", " T-000002 ", "Т-000002", "№ 2", "#2"],
)
async def test_piece_is_found_however_its_number_is_written(client, worker, receive, written):
    pieces = await receive(7000, count=3)
    response = await find(client, worker[1], written)
    assert response.status_code == 200, response.text
    assert [p["id"] for p in response.json()] == [pieces[1]["id"]]


async def test_search_returns_the_whole_piece(client, worker, receive):
    (pipe,) = await receive(7000)
    (found,) = (await find(client, worker[1], pipe["code"])).json()
    assert found == pipe


async def test_unknown_number_gives_an_empty_list(client, worker, receive):
    await receive(7000)
    response = await find(client, worker[1], "T-000999")
    assert response.status_code == 200 and response.json() == []


async def test_search_finds_pieces_that_are_no_longer_in_stock(client, worker, receive):
    """Someone holding an offcut or a used piece must still be able to look it up."""
    _, headers = worker
    (pipe,) = await receive(7000)
    cut = (
        await client.post(
            "/cuts/", json={"source_item_id": pipe["id"], "pieces": [{"length_mm": 6900, "used": True}]}, headers=headers
        )
    ).json()
    used, scrap = cut["results"]

    statuses = {}
    for item in (pipe, used, scrap):
        (found,) = (await find(client, headers, item["code"])).json()
        statuses[found["id"]] = found["status"]

    assert statuses == {pipe["id"]: "cut", used["id"]: "used", scrap["id"]: "scrap"}


async def test_search_can_be_combined_with_other_filters(client, worker, receive):
    (pipe,) = await receive(7000)
    assert len((await find(client, worker[1], pipe["code"], status="in_stock")).json()) == 1
    assert (await find(client, worker[1], pipe["code"], status="scrap")).json() == []


async def test_search_matches_the_exact_number_only(client, worker, receive):
    """Number 1 must not also bring up 10, 11 and 12."""
    await receive(7000, count=12)
    assert [p["code"] for p in (await find(client, worker[1], "1")).json()] == ["T-000001"]


@pytest.mark.parametrize("written", ["", "T-", "abc", "12a", "T-12-3", "1.5", "0", "T-000000", "99999999999", "٣"])
async def test_malformed_number_is_rejected(client, worker, receive, written):
    await receive(7000)
    response = await find(client, worker[1], written)
    assert response.status_code == 422, response.text


async def test_number_longer_than_the_field_allows_is_rejected(client, worker):
    assert (await find(client, worker[1], "1" * 31)).status_code == 422


async def test_search_requires_login(client):
    assert (await client.get("/stock-items/", params={"number": "1"})).status_code == 401


# --- Correcting the length: PATCH /stock-items/{id} with length_mm ---
async def test_worker_can_correct_the_length_of_a_received_piece(client, worker, receive):
    _, headers = worker
    [pipe] = await receive(7000)
    response = await client.patch(f"/stock-items/{pipe['id']}", json={"length_mm": 6950}, headers=headers)
    assert response.status_code == 200, response.text
    assert response.json()["length_mm"] == 6950
    # The new length is what cutting works with
    response = await client.post(
        "/cuts/", json={"source_item_id": pipe["id"], "pieces": [{"length_mm": 3000}]}, headers=headers
    )
    assert sorted(p["length_mm"] for p in response.json()["results"]) == [3000, 3950]


async def test_admin_can_correct_the_length(client, admin, receive):
    _, headers = admin
    [pipe] = await receive(7000)
    response = await client.patch(f"/stock-items/{pipe['id']}", json={"length_mm": 6000}, headers=headers)
    assert response.status_code == 200, response.text


async def test_length_of_a_reserved_piece_can_be_corrected(client, worker, receive):
    _, headers = worker
    order = (await client.post("/orders/", json={"number": "З-1", "customer_name": "Иванов"}, headers=headers)).json()
    [pipe] = await receive(7000)
    await client.post(f"/stock-items/{pipe['id']}/assign", json={"order_id": order["id"]}, headers=headers)
    response = await client.patch(f"/stock-items/{pipe['id']}", json={"length_mm": 6500}, headers=headers)
    assert response.status_code == 200, response.text
    assert response.json()["status"] == "reserved"


async def test_length_of_a_cut_source_cannot_be_corrected(client, worker, receive):
    _, headers = worker
    [pipe] = await receive(7000)
    await client.post("/cuts/", json={"source_item_id": pipe["id"], "pieces": [{"length_mm": 3000}]}, headers=headers)
    response = await client.patch(f"/stock-items/{pipe['id']}", json={"length_mm": 6000}, headers=headers)
    assert response.status_code == 400
    assert (await client.get(f"/stock-items/{pipe['id']}", headers=headers)).json()["length_mm"] == 7000


async def test_length_of_a_piece_from_a_cut_cannot_be_corrected(client, worker, receive):
    _, headers = worker
    [pipe] = await receive(7000)
    cut = (
        await client.post("/cuts/", json={"source_item_id": pipe["id"], "pieces": [{"length_mm": 3000}]}, headers=headers)
    ).json()
    remainder = next(p for p in cut["results"] if p["length_mm"] == 4000)
    response = await client.patch(f"/stock-items/{remainder['id']}", json={"length_mm": 3900}, headers=headers)
    assert response.status_code == 400
    assert "cancel the cut" in response.json()["detail"]


async def test_length_of_a_scrapped_piece_cannot_be_corrected(client, worker, receive):
    _, headers = worker
    [pipe] = await receive(7000)
    await client.post(f"/stock-items/{pipe['id']}/scrap", headers=headers)
    response = await client.patch(f"/stock-items/{pipe['id']}", json={"length_mm": 6000}, headers=headers)
    assert response.status_code == 400


async def test_length_can_be_corrected_after_the_cut_is_cancelled(client, worker, receive):
    _, headers = worker
    [pipe] = await receive(7000)
    cut = (
        await client.post("/cuts/", json={"source_item_id": pipe["id"], "pieces": [{"length_mm": 3000}]}, headers=headers)
    ).json()
    await client.post(f"/cuts/{cut['id']}/cancel", headers=headers)
    response = await client.patch(f"/stock-items/{pipe['id']}", json={"length_mm": 6900}, headers=headers)
    assert response.status_code == 200, response.text


@pytest.mark.parametrize("length", [0, -5, None, "abc"])
async def test_bad_length_is_rejected(client, worker, receive, length):
    _, headers = worker
    [pipe] = await receive(7000)
    response = await client.patch(f"/stock-items/{pipe['id']}", json={"length_mm": length}, headers=headers)
    assert response.status_code == 422
    assert (await client.get(f"/stock-items/{pipe['id']}", headers=headers)).json()["length_mm"] == 7000


async def test_note_can_still_be_changed_without_the_length(client, worker, receive):
    _, headers = worker
    [pipe] = await receive(7000)
    response = await client.patch(f"/stock-items/{pipe['id']}", json={"note": "кривая"}, headers=headers)
    assert response.status_code == 200, response.text
    assert response.json()["note"] == "кривая" and response.json()["length_mm"] == 7000
