"""Warehouse operations leave the right entries in the activity journal."""
import pytest

from app.repo import activity


@pytest.fixture
def journal(sessions):
    """Read the journal oldest first, as plain tuples that are easy to compare."""

    async def _read(**filters):
        async with sessions() as db:
            events = await activity.list_events(db, **filters)
        return list(reversed(events))

    return _read


def summary(events):
    return [(e.action, e.quantity, e.length_mm) for e in events]


async def cut(client, headers, source_id, pieces, **extra):
    response = await client.post(
        "/cuts/", json={"source_item_id": source_id, "pieces": pieces, **extra}, headers=headers
    )
    assert response.status_code == 201, response.text
    return response.json()


# --- Receiving ---
async def test_receipt_is_one_entry_for_the_whole_delivery(worker, material, receive, journal):
    user, _ = worker
    pieces = await receive(7000, count=30)

    (event,) = await journal()
    assert (event.action, event.quantity, event.length_mm) == ("receive", 30, 210_000)
    assert event.user.id == user.id
    assert event.material.id == material["id"]
    assert event.stock_item is None  # thirty pieces, not one
    assert event.details == {"piece_length_mm": 7000, "item_ids": [p["id"] for p in pieces]}


async def test_receipt_of_a_single_piece_points_at_it(receive, journal):
    (pipe,) = await receive(7000)
    (event,) = await journal()
    assert event.stock_item.id == pipe["id"]


async def test_rejected_receipt_leaves_no_entry(client, worker, material, journal):
    response = await client.post(
        "/stock-items/", json={"material_id": material["id"], "length_mm": 7000, "location_id": 999}, headers=worker[1]
    )
    assert response.status_code == 404
    assert await journal() == []


# --- Cutting ---
async def test_cut_with_used_pieces(client, admin, receive, journal):
    """Received by the worker, cut by the admin: the cut entries belong to the admin."""
    admin_user, admin_headers = admin
    (pipe,) = await receive(7000)
    done = await cut(client, admin_headers, pipe["id"], [{"length_mm": 3000, "used": True}] * 2)

    events = await journal()
    assert summary(events) == [("receive", 1, 7000), ("cut", 1, 7000), ("use", 2, 6000)]

    cut_event, use_event = events[1], events[2]
    assert {cut_event.user.id, use_event.user.id} == {admin_user.id}
    assert cut_event.stock_item.id == pipe["id"]
    assert cut_event.cut_operation_id == use_event.cut_operation_id == done["id"]
    assert cut_event.details == {"pieces_mm": [3000, 3000], "remainder_mm": 1000}


async def test_cut_that_only_returns_pieces_to_stock_uses_nothing(client, worker, receive, journal):
    (pipe,) = await receive(7000)
    await cut(client, worker[1], pipe["id"], [{"length_mm": 3000}, {"length_mm": 2000}])
    assert summary(await journal(action=activity.USE)) == []
    assert summary(await journal(action=activity.CUT)) == [("cut", 1, 7000)]


async def test_only_used_pieces_count_as_used(client, worker, receive, journal):
    (pipe,) = await receive(7000)
    await cut(client, worker[1], pipe["id"], [{"length_mm": 3000, "used": True}, {"length_mm": 2000}])
    assert summary(await journal(action=activity.USE)) == [("use", 1, 3000)]


async def test_scrap_remainder_is_recorded(client, worker, receive, journal):
    (pipe,) = await receive(7000)
    done = await cut(client, worker[1], pipe["id"], [{"length_mm": 6800, "used": True}])

    (scrap,) = await journal(action=activity.SCRAP)
    assert (scrap.quantity, scrap.length_mm) == (1, 200)
    assert scrap.stock_item.id == done["results"][-1]["id"]
    assert scrap.cut_operation_id == done["id"]


async def test_kept_remainder_is_not_scrap(client, worker, receive, journal):
    (pipe,) = await receive(7000)
    await cut(client, worker[1], pipe["id"], [{"length_mm": 3000, "used": True}])
    assert await journal(action=activity.SCRAP) == []


async def test_forced_scrap_of_a_long_remainder_is_recorded(client, worker, receive, journal):
    (pipe,) = await receive(7000)
    await cut(client, worker[1], pipe["id"], [{"length_mm": 3000, "used": True}], scrap_remainder=True)
    assert summary(await journal(action=activity.SCRAP)) == [("scrap", 1, 4000)]


async def test_failed_cut_leaves_no_entry(client, worker, receive, journal):
    (pipe,) = await receive(7000)
    response = await client.post(
        "/cuts/", json={"source_item_id": pipe["id"], "pieces": [{"length_mm": 4000}] * 2}, headers=worker[1]
    )
    assert response.status_code == 400
    assert summary(await journal()) == [("receive", 1, 7000)]


async def test_journal_lengths_add_up_for_a_cut(client, worker, receive, journal):
    """Used + scrap + what went back to stock equals the length of the cut piece."""
    (pipe,) = await receive(7000)
    done = await cut(
        client, worker[1], pipe["id"], [{"length_mm": 3000, "used": True}, {"length_mm": 3900}]
    )
    events = {e.action: e for e in await journal()}
    back_to_stock = sum(r["length_mm"] for r in done["results"] if r["status"] == "in_stock")

    assert events["use"].length_mm + events["scrap"].length_mm + back_to_stock == events["cut"].length_mm


# --- Writing off and consuming by hand ---
async def test_scrapping_a_piece_is_recorded(client, worker, receive, journal):
    user, headers = worker
    (pipe,) = await receive(2000)
    assert (await client.post(f"/stock-items/{pipe['id']}/scrap", headers=headers)).status_code == 200

    (event,) = await journal(action=activity.SCRAP)
    assert (event.quantity, event.length_mm, event.user.id) == (1, 2000, user.id)
    assert event.stock_item.id == pipe["id"]


async def test_refused_scrap_leaves_no_entry(client, worker, receive, journal):
    (pipe,) = await receive(2000)
    await client.post(f"/stock-items/{pipe['id']}/scrap", headers=worker[1])
    again = await client.post(f"/stock-items/{pipe['id']}/scrap", headers=worker[1])
    assert again.status_code == 400
    assert len(await journal(action=activity.SCRAP)) == 1


async def test_using_a_reserved_piece_is_recorded(client, worker, receive, journal):
    _, headers = worker
    order = (await client.post("/orders/", json={"customer_name": "Клиент"}, headers=headers)).json()
    (pipe,) = await receive(3000)
    await client.post(f"/stock-items/{pipe['id']}/assign", json={"order_id": order["id"]}, headers=headers)
    assert await journal(action=activity.USE) == []  # reserving is not consuming

    await client.post(f"/stock-items/{pipe['id']}/use", headers=headers)
    (event,) = await journal(action=activity.USE)
    assert (event.length_mm, event.details) == (3000, {"order_id": order["id"]})


async def test_closing_an_order_records_its_pieces_as_used(client, admin, worker, receive, journal):
    admin_user, admin_headers = admin
    _, headers = worker
    order = (await client.post("/orders/", json={"customer_name": "Клиент"}, headers=headers)).json()
    for pipe in await receive(3000, count=2):
        await client.post(f"/stock-items/{pipe['id']}/assign", json={"order_id": order["id"]}, headers=headers)

    await client.patch(f"/orders/{order['id']}", json={"status": "done"}, headers=admin_headers)

    events = await journal(action=activity.USE)
    assert summary(events) == [("use", 1, 3000)] * 2
    assert {e.user.id for e in events} == {admin_user.id}


async def test_cancelling_an_order_uses_nothing(client, worker, receive, journal):
    _, headers = worker
    order = (await client.post("/orders/", json={"customer_name": "Клиент"}, headers=headers)).json()
    (pipe,) = await receive(3000)
    await client.post(f"/stock-items/{pipe['id']}/assign", json={"order_id": order["id"]}, headers=headers)
    await client.patch(f"/orders/{order['id']}", json={"status": "cancelled"}, headers=headers)
    assert await journal(action=activity.USE) == []


# --- The whole picture ---
async def test_totals_per_worker_can_be_summed_from_the_journal(client, admin, worker, material, receive, journal):
    """What the reports of step 1.5 will be built from."""
    admin_user, admin_headers = admin
    worker_user, worker_headers = worker
    pipes = await receive(7000, count=3)  # by the worker
    await cut(client, worker_headers, pipes[0]["id"], [{"length_mm": 3000, "used": True}] * 2)
    await cut(client, admin_headers, pipes[1]["id"], [{"length_mm": 6900, "used": True}])

    def totals(events):
        result = {}
        for e in events:
            quantity, length = result.get(e.action, (0, 0))
            result[e.action] = (quantity + e.quantity, length + e.length_mm)
        return result

    assert totals(await journal(user_id=worker_user.id)) == {
        "receive": (3, 21_000),
        "cut": (1, 7000),
        "use": (2, 6000),
    }
    assert totals(await journal(user_id=admin_user.id)) == {
        "cut": (1, 7000),
        "use": (1, 6900),
        "scrap": (1, 100),
    }
