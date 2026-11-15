"""Cutting: the length calculation, the cut itself and choosing what to cut from."""
import pytest

from app.core.errors import DomainError
from app.repo.cutting import plan_cut


# --- plan_cut: pure calculation, no database ---
@pytest.mark.parametrize(
    "source, pieces, kerf, cuts, kerf_loss, remainder",
    [
        # No kerf (the default): lengths simply add up
        (7000, [3000, 3000], 0, 2, 0, 1000),
        (7000, [3500, 3500], 0, 1, 0, 0),
        (7000, [7000], 0, 0, 0, 0),
        (7000, [1000], 0, 1, 0, 6000),
        # With kerf: every cut consumes material
        (6000, [2500, 2500], 3, 2, 6, 994),
        (6000, [2998, 2999], 3, 1, 3, 0),
        # Leftover narrower than the blade is consumed by the last cut
        (6000, [5999], 3, 1, 1, 0),
        (6000, [5997], 3, 1, 3, 0),
    ],
)
def test_plan_cut(source, pieces, kerf, cuts, kerf_loss, remainder):
    plan = plan_cut(source, pieces, kerf)
    assert (plan.cuts, plan.kerf_loss_mm, plan.remainder_mm) == (cuts, kerf_loss, remainder)
    # Nothing is lost or invented
    assert sum(pieces) + plan.kerf_loss_mm + plan.remainder_mm == source


@pytest.mark.parametrize(
    "source, pieces, kerf",
    [
        (7000, [4000, 4000], 0),
        (7000, [7001], 0),
        (6000, [3000, 3000], 3),  # fits only without kerf
    ],
)
def test_plan_cut_rejects_pieces_that_do_not_fit(source, pieces, kerf):
    with pytest.raises(DomainError):
        plan_cut(source, pieces, kerf)


# --- POST /cuts/ ---
async def test_cut_into_used_pieces_and_remainder(client, worker, receive):
    """The owner's main scenario: 7 m into 3 m + 3 m used, 1 m back to stock."""
    user, headers = worker
    (pipe,) = await receive(7000)

    response = await client.post(
        "/cuts/",
        json={"source_item_id": pipe["id"], "pieces": [{"length_mm": 3000, "used": True}] * 2},
        headers=headers,
    )
    assert response.status_code == 201, response.text
    cut = response.json()

    assert cut["source_item"]["status"] == "cut"
    assert cut["kerf_loss_mm"] == 0
    assert cut["user_id"] == user.id
    assert [(r["length_mm"], r["status"]) for r in cut["results"]] == [
        (3000, "used"),
        (3000, "used"),
        (1000, "in_stock"),
    ]
    # Every result points back to the pipe it was cut from
    assert all(r["parent_id"] == pipe["id"] for r in cut["results"])
    assert all(r["cut_operation_id"] == cut["id"] for r in cut["results"])


async def test_piece_can_go_back_to_stock(client, worker, receive):
    _, headers = worker
    (pipe,) = await receive(7000)
    response = await client.post(
        "/cuts/",
        json={"source_item_id": pipe["id"], "pieces": [{"length_mm": 2000}, {"length_mm": 2000, "used": True}]},
        headers=headers,
    )
    statuses = [r["status"] for r in response.json()["results"]]
    assert statuses == ["in_stock", "used", "in_stock"]


async def test_short_remainder_becomes_scrap(client, worker, receive):
    _, headers = worker
    (pipe,) = await receive(7000)
    response = await client.post(
        "/cuts/", json={"source_item_id": pipe["id"], "pieces": [{"length_mm": 6800}]}, headers=headers
    )
    remainder = response.json()["results"][-1]
    # 200 mm is below the 300 mm minimum of the material
    assert (remainder["length_mm"], remainder["status"]) == (200, "scrap")
    assert remainder["location"] is None


async def test_exact_fit_leaves_no_remainder(client, worker, receive):
    _, headers = worker
    (pipe,) = await receive(7000)
    response = await client.post(
        "/cuts/", json={"source_item_id": pipe["id"], "pieces": [{"length_mm": 3500}] * 2}, headers=headers
    )
    assert [r["length_mm"] for r in response.json()["results"]] == [3500, 3500]


async def test_remainder_stays_at_the_location_of_the_source(client, worker, receive):
    _, headers = worker
    location = (await client.post("/locations/", json={"name": "Стеллаж A"}, headers=headers)).json()
    (pipe,) = await receive(7000, location_id=location["id"])
    response = await client.post(
        "/cuts/", json={"source_item_id": pipe["id"], "pieces": [{"length_mm": 3000, "used": True}]}, headers=headers
    )
    remainder = response.json()["results"][-1]
    assert remainder["location"]["id"] == location["id"]


async def test_pieces_that_do_not_fit_change_nothing(client, worker, receive):
    _, headers = worker
    (pipe,) = await receive(7000)
    response = await client.post(
        "/cuts/", json={"source_item_id": pipe["id"], "pieces": [{"length_mm": 4000}] * 2}, headers=headers
    )
    assert response.status_code == 400
    assert "do not fit" in response.json()["detail"]

    items = (await client.get("/stock-items/", headers=headers)).json()
    assert [(i["id"], i["status"]) for i in items] == [(pipe["id"], "in_stock")]


async def test_a_piece_cannot_be_cut_twice(client, worker, receive):
    _, headers = worker
    (pipe,) = await receive(7000)
    body = {"source_item_id": pipe["id"], "pieces": [{"length_mm": 1000}]}
    assert (await client.post("/cuts/", json=body, headers=headers)).status_code == 201
    assert (await client.post("/cuts/", json=body, headers=headers)).status_code == 400


async def test_used_piece_cannot_be_cut(client, worker, receive):
    _, headers = worker
    (pipe,) = await receive(7000)
    cut = (
        await client.post(
            "/cuts/", json={"source_item_id": pipe["id"], "pieces": [{"length_mm": 3000, "used": True}]}, headers=headers
        )
    ).json()
    used_piece = cut["results"][0]
    response = await client.post(
        "/cuts/", json={"source_item_id": used_piece["id"], "pieces": [{"length_mm": 1000}]}, headers=headers
    )
    assert response.status_code == 400


async def test_unknown_source_is_404(client, worker):
    _, headers = worker
    response = await client.post(
        "/cuts/", json={"source_item_id": 999, "pieces": [{"length_mm": 1000}]}, headers=headers
    )
    assert response.status_code == 404


@pytest.mark.parametrize("pieces", [[], [{"length_mm": 0}], [{"length_mm": -5}]])
async def test_invalid_pieces_are_rejected(client, worker, receive, pieces):
    _, headers = worker
    (pipe,) = await receive(7000)
    response = await client.post("/cuts/", json={"source_item_id": pipe["id"], "pieces": pieces}, headers=headers)
    assert response.status_code == 422


async def test_history_follows_the_chain_of_cuts(client, worker, receive):
    _, headers = worker
    (pipe,) = await receive(7000)
    first = (
        await client.post("/cuts/", json={"source_item_id": pipe["id"], "pieces": [{"length_mm": 3000}]}, headers=headers)
    ).json()
    remainder = first["results"][-1]  # 4000 mm
    second = (
        await client.post(
            "/cuts/", json={"source_item_id": remainder["id"], "pieces": [{"length_mm": 1000}]}, headers=headers
        )
    ).json()
    small = second["results"][0]

    history = (await client.get(f"/stock-items/{small['id']}/history", headers=headers)).json()
    assert [a["id"] for a in history["ancestors"]] == [remainder["id"], pipe["id"]]

    history = (await client.get(f"/stock-items/{pipe['id']}/history", headers=headers)).json()
    assert len(history["children"]) == 2


# --- POST /cuts/suggest ---
async def suggest(client, headers, material, pieces, **extra):
    response = await client.post(
        "/cuts/suggest", json={"material_id": material["id"], "pieces": pieces, **extra}, headers=headers
    )
    assert response.status_code == 200, response.text
    return response.json()


async def test_suggest_puts_the_smallest_remainder_first(client, worker, material, receive):
    _, headers = worker
    await receive(7000, count=3)
    await receive(3000)
    await receive(3100)
    await receive(4000, count=2)
    await receive(2000)  # too short, must not be offered

    found = await suggest(client, headers, material, [3000])

    assert found["required_mm"] == 3000
    assert [
        (c["item"]["length_mm"], c["count"], c["remainder_mm"], c["remainder_fate"]) for c in found["candidates"]
    ] == [
        (3000, 1, 0, "none"),
        (3100, 1, 100, "scrap"),
        (4000, 2, 1000, "stock"),
        (7000, 3, 4000, "stock"),
    ]


async def test_suggest_groups_identical_pieces_and_offers_the_oldest(client, worker, material, receive):
    _, headers = worker
    pipes = await receive(7000, count=3)
    found = await suggest(client, headers, material, [1000])

    (group,) = found["candidates"]
    assert group["item"]["id"] == pipes[0]["id"]
    assert group["item_ids"] == [p["id"] for p in pipes]


async def test_suggest_keeps_locations_apart(client, worker, material, receive):
    _, headers = worker
    location = (await client.post("/locations/", json={"name": "Стеллаж A"}, headers=headers)).json()
    await receive(7000)
    await receive(7000, location_id=location["id"])
    found = await suggest(client, headers, material, [1000])
    assert len(found["candidates"]) == 2


async def test_suggest_when_nothing_is_long_enough(client, worker, material, receive):
    _, headers = worker
    await receive(7000)
    found = await suggest(client, headers, material, [4000, 4000])
    assert found == {"required_mm": 8000, "candidates": [], "longest_available_mm": 7000}


async def test_suggest_with_empty_stock(client, worker, material):
    _, headers = worker
    found = await suggest(client, headers, material, [1000])
    assert found["candidates"] == [] and found["longest_available_mm"] is None


async def test_suggest_ignores_pieces_that_are_not_free(client, worker, material, receive):
    _, headers = worker
    pipe, spare = await receive(7000, count=2)
    await client.post(
        "/cuts/", json={"source_item_id": pipe["id"], "pieces": [{"length_mm": 3000, "used": True}]}, headers=headers
    )
    found = await suggest(client, headers, material, [3000])
    # Offered: the 4000 mm remainder and the untouched pipe; not the cut pipe or the used piece
    assert [c["item"]["length_mm"] for c in found["candidates"]] == [4000, 7000]
    assert found["candidates"][1]["item"]["id"] == spare["id"]


async def test_suggest_takes_kerf_into_account(client, worker, material, receive):
    _, headers = worker
    await receive(4000)
    await receive(7000)
    # Four pieces of 1000 mm need three cuts between them: 4009 mm with a 3 mm blade
    found = await suggest(client, headers, material, [1000] * 4, kerf_mm=3)
    assert found["required_mm"] == 4009
    assert [c["item"]["length_mm"] for c in found["candidates"]] == [7000]


async def test_suggest_changes_nothing(client, worker, material, receive):
    _, headers = worker
    await receive(7000)
    await suggest(client, headers, material, [3000])
    items = (await client.get("/stock-items/", headers=headers)).json()
    assert [(i["length_mm"], i["status"]) for i in items] == [(7000, "in_stock")]


async def test_suggest_rejects_bad_input(client, worker, material):
    _, headers = worker
    bad_length = await client.post(
        "/cuts/suggest", json={"material_id": material["id"], "pieces": [0]}, headers=headers
    )
    unknown_material = await client.post("/cuts/suggest", json={"material_id": 999, "pieces": [5]}, headers=headers)
    assert bad_length.status_code == 422
    assert unknown_material.status_code == 404
