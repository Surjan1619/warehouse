"""Stock page overview: GET /stock-items/summary and GET /stock-items/page."""
import pytest


async def add_material(client, headers, name):
    response = await client.post("/materials/", json={"name": name}, headers=headers)
    assert response.status_code == 201, response.text
    return response.json()


async def summary(client, headers, **params):
    response = await client.get("/stock-items/summary", params=params, headers=headers)
    assert response.status_code == 200, response.text
    return response.json()


async def page(client, headers, **params):
    response = await client.get("/stock-items/page", params=params, headers=headers)
    assert response.status_code == 200, response.text
    return response.json()


# --- Summary ---
async def test_summary_counts_pieces_and_length_per_material(client, worker, material, receive):
    _, headers = worker
    other = await add_material(client, headers, "Вал 70")
    await receive(7000, count=3)
    await receive(1500)
    await client.post("/stock-items/", json={"material_id": other["id"], "length_mm": 6000}, headers=headers)

    rows = await summary(client, headers, status="in_stock")
    # Ordered by material name: "Вал 70" before "Труба 40x20"
    assert [(r["material"]["name"], r["count"], r["total_length_mm"], r["min_length_mm"], r["max_length_mm"]) for r in rows] == [
        ("Вал 70", 1, 6000, 6000, 6000),
        ("Труба 40x20", 4, 22500, 1500, 7000),
    ]


async def test_summary_follows_the_status(client, worker, receive):
    _, headers = worker
    first, _ = await receive(7000, count=2)
    await client.post(
        "/cuts/", json={"source_item_id": first["id"], "pieces": [{"length_mm": 3000, "used": True}]}, headers=headers
    )

    [in_stock] = await summary(client, headers, status="in_stock")
    assert (in_stock["count"], in_stock["total_length_mm"]) == (2, 11000)  # untouched pipe + 4000 remainder
    [cut] = await summary(client, headers, status="cut")
    assert (cut["count"], cut["total_length_mm"]) == (1, 7000)
    [everything] = await summary(client, headers)
    assert everything["count"] == 4


async def test_summary_leaves_out_materials_without_such_pieces(client, worker, material):
    _, headers = worker
    await add_material(client, headers, "Пустой")
    assert await summary(client, headers, status="in_stock") == []


async def test_summary_by_location(client, worker, receive):
    _, headers = worker
    location = (await client.post("/locations/", json={"name": "Стеллаж 1"}, headers=headers)).json()
    await receive(7000, location_id=location["id"])
    await receive(5000)
    [row] = await summary(client, headers, status="in_stock", location_id=location["id"])
    assert (row["count"], row["total_length_mm"]) == (1, 7000)


async def test_summary_rejects_an_unknown_status(client, worker):
    _, headers = worker
    assert (await client.get("/stock-items/summary?status=bogus", headers=headers)).status_code == 422


# --- Paged list ---
async def test_pages_split_the_list_and_report_the_total(client, worker, material, receive):
    _, headers = worker
    await receive(1000, count=3)
    await receive(3000, count=2)

    first = await page(client, headers, status="in_stock", material_id=material["id"], limit=2)
    second = await page(client, headers, status="in_stock", material_id=material["id"], limit=2, offset=2)
    third = await page(client, headers, status="in_stock", material_id=material["id"], limit=2, offset=4)

    assert first["total"] == second["total"] == third["total"] == 5
    assert [len(p["items"]) for p in (first, second, third)] == [2, 2, 1]
    ids = [item["id"] for p in (first, second, third) for item in p["items"]]
    assert len(set(ids)) == 5  # no piece shown twice, none skipped


async def test_page_puts_the_longest_first_and_equal_lengths_oldest_first(client, worker, material, receive):
    _, headers = worker
    short = await receive(1000)
    long_pair = await receive(7000, count=2)
    middle = await receive(3000)

    items = (await page(client, headers, material_id=material["id"]))["items"]
    assert [item["id"] for item in items] == [
        long_pair[0]["id"], long_pair[1]["id"], middle[0]["id"], short[0]["id"]
    ]


async def test_page_keeps_materials_apart(client, worker, material, receive):
    _, headers = worker
    other = await add_material(client, headers, "Вал 70")
    await receive(7000)
    await client.post("/stock-items/", json={"material_id": other["id"], "length_mm": 6000}, headers=headers)

    result = await page(client, headers, material_id=other["id"])
    assert result["total"] == 1
    assert result["items"][0]["material"]["id"] == other["id"]


async def test_page_past_the_end_is_empty(client, worker, material, receive):
    _, headers = worker
    await receive(7000)
    result = await page(client, headers, material_id=material["id"], offset=50)
    assert result == {"items": [], "total": 1}


@pytest.mark.parametrize("params", [{"limit": 0}, {"limit": 201}, {"offset": -1}, {"status": "bogus"}])
async def test_page_rejects_bad_parameters(client, worker, params):
    _, headers = worker
    assert (await client.get("/stock-items/page", params=params, headers=headers)).status_code == 422


async def test_overview_needs_a_token(client):
    assert (await client.get("/stock-items/summary")).status_code == 401
    assert (await client.get("/stock-items/page")).status_code == 401
