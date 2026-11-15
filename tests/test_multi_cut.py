"""Cutting pieces out of several stock items: the packing, the plan and the batch cut."""
import pytest

from app.repo import activity
from app.repo.cutting import pack_pieces, plan_cut


def pipes(*lengths):
    """Free stock as (id, length) pairs with ids 1, 2, 3..."""
    return [(index, length) for index, length in enumerate(lengths, start=1)]


def packed_lengths(items, pieces, kerf=0, min_usable=300):
    """Run the packing and show, per item id, the piece lengths it received."""
    assignment, unplaced = pack_pieces(items, pieces, kerf, min_usable)
    return (
        {item_id: [pieces[i] for i in indexes] for item_id, indexes in assignment.items()},
        [pieces[i] for i in unplaced],
    )


# --- pack_pieces: pure calculation ---
def test_ten_three_metre_pieces_take_five_seven_metre_pipes():
    """The owner's example: ten pieces of 3 m out of 7 m pipes."""
    placed, unplaced = packed_lengths(pipes(*[7000] * 6), [3000] * 10)
    assert placed == {1: [3000, 3000], 2: [3000, 3000], 3: [3000, 3000], 4: [3000, 3000], 5: [3000, 3000]}
    assert unplaced == []  # the sixth pipe stays untouched


def test_pieces_that_fit_one_pipe_use_one_pipe():
    placed, _ = packed_lengths(pipes(7000, 7000), [3000, 3000, 1000])
    assert placed == {1: [3000, 3000, 1000]}


def test_mixed_lengths_are_packed_tightly():
    placed, unplaced = packed_lengths(pipes(7000, 7000), [4000, 3000, 4000, 3000])
    assert sorted(sorted(p) for p in placed.values()) == [[3000, 4000], [3000, 4000]]
    assert unplaced == []


def test_exact_offcut_is_used_before_a_whole_pipe():
    placed, _ = packed_lengths(pipes(7000, 3000), [3000])
    assert placed == {2: [3000]}


def test_short_offcuts_are_used_before_whole_pipes():
    placed, _ = packed_lengths(pipes(7000, 4000), [3000])
    assert placed == {2: [3000]}  # 1000 mm left, still usable


def test_an_item_that_would_leave_scrap_is_avoided_when_there_is_a_choice():
    """3100 for a 3000 piece would waste 100 mm; the 7000 pipe leaves a usable remainder."""
    placed, _ = packed_lengths(pipes(7000, 7000, 3000, 3100), [3000, 3000, 3000])
    assert placed == {3: [3000], 1: [3000, 3000]}


def test_an_item_that_leaves_scrap_is_used_when_nothing_else_fits():
    placed, unplaced = packed_lengths(pipes(3100), [3000])
    assert placed == {1: [3000]} and unplaced == []


def test_older_pipe_is_taken_first_among_equal_ones():
    placed, _ = packed_lengths([(7, 7000), (3, 7000), (5, 7000)], [1000])
    assert list(placed) == [3]


def test_piece_longer_than_everything_is_reported_and_the_rest_is_placed():
    placed, unplaced = packed_lengths(pipes(7000), [8000, 3000])
    assert placed == {1: [3000]}
    assert unplaced == [8000]


def test_pieces_left_over_when_the_stock_runs_out():
    placed, unplaced = packed_lengths(pipes(7000), [3000] * 3)
    assert placed == {1: [3000, 3000]}
    assert unplaced == [3000]


def test_no_stock_at_all():
    assert packed_lengths([], [1000, 2000]) == ({}, [1000, 2000])


def test_kerf_reduces_how_many_pieces_fit():
    # Seven pieces of 1000 mm need six cuts: 7018 mm with a 3 mm blade, more than 7000
    placed, unplaced = packed_lengths(pipes(7000, 7000), [1000] * 7, kerf=3)
    assert sorted(len(p) for p in placed.values()) == [1, 6]
    assert unplaced == []


@pytest.mark.parametrize(
    "stock, pieces, kerf",
    [
        ([7000] * 6, [3000] * 10, 0),
        ([7000, 7000, 3000, 3100, 4000], [3000, 2500, 1200, 3000, 800, 3000], 0),
        ([7000, 6000, 5000], [2400, 2400, 1100, 1100, 900, 3300, 600], 3),
        ([7000], [8000, 7000, 1], 0),
        ([1000, 1000], [1000, 1000, 1000], 5),
    ],
)
def test_packing_is_always_consistent(stock, pieces, kerf):
    """Every piece ends up in exactly one place, and every item can really hold what it got."""
    items = pipes(*stock)
    assignment, unplaced = pack_pieces(items, pieces, kerf, 300)

    placed = [i for indexes in assignment.values() for i in indexes]
    assert sorted(placed + unplaced) == list(range(len(pieces)))

    lengths = dict(items)
    for item_id, indexes in assignment.items():
        plan_cut(lengths[item_id], [pieces[i] for i in indexes], kerf)  # raises if it does not fit


# --- POST /cuts/plan ---
async def get_plan(client, headers, material, pieces, **extra):
    response = await client.post(
        "/cuts/plan", json={"material_id": material["id"], "pieces": pieces, **extra}, headers=headers
    )
    assert response.status_code == 200, response.text
    return response.json()


async def test_plan_for_ten_pieces(client, worker, material, receive):
    _, headers = worker
    stock = await receive(7000, count=6)
    plan = await get_plan(client, headers, material, [{"length_mm": 3000, "used": True}] * 10)

    assert [c["item"]["id"] for c in plan["cuts"]] == [p["id"] for p in stock[:5]]
    assert all(c["pieces"] == [{"length_mm": 3000, "used": True, "order_id": None, "location_id": None, "note": None}] * 2
               for c in plan["cuts"])
    assert all((c["remainder_mm"], c["remainder_fate"]) == (1000, "stock") for c in plan["cuts"])
    assert plan["unplaced"] == []


async def test_plan_keeps_what_each_piece_is_for(client, worker, material, receive):
    """"Used" and "back to stock" must survive the reshuffling of pieces."""
    _, headers = worker
    await receive(7000, count=2)
    plan = await get_plan(
        client,
        headers,
        material,
        [{"length_mm": 4000, "used": True}, {"length_mm": 4000, "used": False}, {"length_mm": 2500, "used": True}],
    )
    flags = sorted((p["length_mm"], p["used"]) for c in plan["cuts"] for p in c["pieces"])
    assert flags == [(2500, True), (4000, False), (4000, True)]


async def test_plan_puts_the_fullest_items_first(client, worker, material, receive):
    _, headers = worker
    await receive(7000, count=2)
    plan = await get_plan(client, headers, material, [{"length_mm": 6500}, {"length_mm": 3000}])
    assert [c["remainder_mm"] for c in plan["cuts"]] == [500, 4000]


async def test_plan_marks_remainders_that_become_scrap(client, worker, material, receive):
    _, headers = worker
    await receive(7000)
    plan = await get_plan(client, headers, material, [{"length_mm": 6900}])
    assert (plan["cuts"][0]["remainder_mm"], plan["cuts"][0]["remainder_fate"]) == (100, "scrap")


async def test_plan_reports_pieces_that_cannot_be_cut(client, worker, material, receive):
    _, headers = worker
    await receive(7000)
    plan = await get_plan(client, headers, material, [{"length_mm": 8000}, {"length_mm": 3000}] )
    assert [p["length_mm"] for p in plan["unplaced"]] == [8000]
    assert len(plan["cuts"]) == 1
    assert plan["longest_available_mm"] == 7000


async def test_plan_only_uses_free_pieces_of_the_material(client, worker, material, receive):
    _, headers = worker
    other = (await client.post("/materials/", json={"name": "Профиль 55"}, headers=headers)).json()
    await client.post("/stock-items/", json={"material_id": other["id"], "length_mm": 7000}, headers=headers)
    (scrapped,) = await receive(7000)
    await client.post(f"/stock-items/{scrapped['id']}/scrap", headers=headers)

    plan = await get_plan(client, headers, material, [{"length_mm": 3000}])
    assert plan == {"cuts": [], "unplaced": plan["unplaced"], "longest_available_mm": None}
    assert len(plan["unplaced"]) == 1


async def test_plan_changes_nothing(client, worker, material, receive, sessions):
    _, headers = worker
    await receive(7000, count=2)
    await get_plan(client, headers, material, [{"length_mm": 3000}] * 4)

    items = (await client.get("/stock-items/", headers=headers)).json()
    assert [(i["length_mm"], i["status"]) for i in items] == [(7000, "in_stock")] * 2
    async with sessions() as db:
        assert [e.action for e in await activity.list_events(db)] == ["receive"]


async def test_plan_rejects_bad_input(client, worker, material):
    _, headers = worker

    async def status(**body):
        return (await client.post("/cuts/plan", json=body, headers=headers)).status_code

    assert await status(material_id=material["id"], pieces=[]) == 422
    assert await status(material_id=material["id"], pieces=[{"length_mm": 0}]) == 422
    assert await status(material_id=999, pieces=[{"length_mm": 5}]) == 404
    assert (await client.post("/cuts/plan", json={})).status_code == 401


# --- POST /cuts/batch ---
async def cut_batch(client, headers, cuts):
    return await client.post("/cuts/batch", json={"cuts": cuts}, headers=headers)


def as_batch(plan):
    return [{"source_item_id": c["item"]["id"], "pieces": c["pieces"]} for c in plan["cuts"]]


async def test_plan_can_be_carried_out_as_is(client, worker, material, receive):
    """Plan ten pieces, cut them, and check what is left on the shelf."""
    user, headers = worker
    await receive(7000, count=6)
    plan = await get_plan(client, headers, material, [{"length_mm": 3000, "used": True}] * 10)

    response = await cut_batch(client, headers, as_batch(plan))
    assert response.status_code == 201, response.text
    operations = response.json()
    assert len(operations) == 5 and all(o["user_id"] == user.id for o in operations)

    async def count(status):
        items = (await client.get(f"/stock-items/?status={status}", headers=headers)).json()
        return sorted(i["length_mm"] for i in items)

    assert await count("used") == [3000] * 10
    assert await count("cut") == [7000] * 5
    assert await count("in_stock") == [1000] * 5 + [7000]


async def test_batch_writes_the_journal_for_every_cut(client, worker, material, receive, sessions):
    _, headers = worker
    await receive(7000, count=2)
    plan = await get_plan(client, headers, material, [{"length_mm": 3000, "used": True}] * 4)
    await cut_batch(client, headers, as_batch(plan))

    async with sessions() as db:
        events = await activity.list_events(db)
    totals = {}
    for e in events:
        quantity, length = totals.get(e.action, (0, 0))
        totals[e.action] = (quantity + e.quantity, length + e.length_mm)
    assert totals == {"receive": (2, 14_000), "cut": (2, 14_000), "use": (4, 12_000)}


async def test_batch_is_all_or_nothing(client, worker, material, receive, sessions):
    """The second cut does not fit, so the first one must be undone as well."""
    _, headers = worker
    first, second = await receive(7000, count=2)
    response = await cut_batch(
        client,
        headers,
        [
            {"source_item_id": first["id"], "pieces": [{"length_mm": 3000, "used": True}]},
            {"source_item_id": second["id"], "pieces": [{"length_mm": 8000}]},
        ],
    )
    assert response.status_code == 400

    items = (await client.get("/stock-items/", headers=headers)).json()
    assert [(i["id"], i["status"]) for i in items] == [(first["id"], "in_stock"), (second["id"], "in_stock")]
    async with sessions() as db:
        assert [e.action for e in await activity.list_events(db)] == ["receive"]


async def test_batch_fails_cleanly_when_the_stock_changed_after_planning(client, worker, material, receive):
    """Someone else cut one of the planned pipes in the meantime."""
    _, headers = worker
    await receive(7000, count=2)
    plan = await get_plan(client, headers, material, [{"length_mm": 3000, "used": True}] * 4)
    taken = plan["cuts"][1]["item"]["id"]
    await client.post("/cuts/", json={"source_item_id": taken, "pieces": [{"length_mm": 500}]}, headers=headers)

    response = await cut_batch(client, headers, as_batch(plan))
    assert response.status_code == 400

    untouched = plan["cuts"][0]["item"]["id"]
    item = (await client.get(f"/stock-items/{untouched}", headers=headers)).json()
    assert item["status"] == "in_stock"


async def test_same_pipe_twice_in_one_batch_is_rejected(client, worker, receive):
    _, headers = worker
    (pipe,) = await receive(7000)
    cut = {"source_item_id": pipe["id"], "pieces": [{"length_mm": 1000}]}
    response = await cut_batch(client, headers, [cut, cut])
    assert response.status_code == 400
    assert (await client.get(f"/stock-items/{pipe['id']}", headers=headers)).json()["status"] == "in_stock"


async def test_batch_rejects_bad_input(client, worker, receive):
    _, headers = worker
    (pipe,) = await receive(7000)

    assert (await cut_batch(client, headers, [])).status_code == 422
    assert (await cut_batch(client, headers, [{"source_item_id": pipe["id"], "pieces": []}])).status_code == 422
    assert (await cut_batch(client, headers, [{"source_item_id": 999, "pieces": [{"length_mm": 5}]}])).status_code == 404
    assert (await client.post("/cuts/batch", json={"cuts": []})).status_code == 401
