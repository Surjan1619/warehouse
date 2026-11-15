"""GET /activity/: the journal as the admin sees it."""
from datetime import datetime, timedelta, timezone

from sqlalchemy import select, update

from app.models.Alchemy_models import ActivityEvent


async def get_journal(client, headers, **params):
    response = await client.get("/activity/", params=params, headers=headers)
    assert response.status_code == 200, response.text
    return response.json()


async def cut(client, headers, source_id, pieces):
    response = await client.post("/cuts/", json={"source_item_id": source_id, "pieces": pieces}, headers=headers)
    assert response.status_code == 201, response.text
    return response.json()


# --- Access ---
async def test_journal_is_for_admins_only(client, admin, worker):
    assert (await client.get("/activity/")).status_code == 401
    assert (await client.get("/activity/", headers=worker[1])).status_code == 403
    assert (await client.get("/activity/", headers=admin[1])).status_code == 200


async def test_empty_journal(client, admin):
    assert await get_journal(client, admin[1]) == {"items": [], "total": 0}


# --- Content ---
async def test_entry_shows_who_did_what_with_what(client, admin, worker, material, receive):
    worker_user, _ = worker
    (pipe,) = await receive(7000)

    page = await get_journal(client, admin[1])
    (entry,) = page["items"]

    assert page["total"] == 1
    assert entry["action"] == "receive"
    assert entry["user"] == {"id": worker_user.id, "username": "worker"}
    assert entry["material"]["name"] == material["name"]
    assert entry["stock_item"] == {"id": pipe["id"], "code": pipe["code"], "length_mm": 7000}
    assert (entry["quantity"], entry["length_mm"]) == (1, 7000)
    assert entry["details"]["piece_length_mm"] == 7000


async def test_newest_entries_come_first(client, admin, worker, receive):
    (pipe,) = await receive(7000)
    await cut(client, worker[1], pipe["id"], [{"length_mm": 3000, "used": True}])

    page = await get_journal(client, admin[1])
    assert [e["action"] for e in page["items"]] == ["use", "cut", "receive"]


async def test_time_is_reported_in_utc_with_an_offset(client, admin, receive):
    """Without the offset a browser would read UTC as local time and show the wrong hour."""
    await receive(7000)
    (entry,) = (await get_journal(client, admin[1]))["items"]

    moment = datetime.fromisoformat(entry["created_at"])
    assert moment.utcoffset() == timedelta(0)
    assert abs(datetime.now(timezone.utc) - moment) < timedelta(minutes=1)


async def test_entry_never_exposes_password_data(client, admin, receive):
    await receive(7000)
    response = await client.get("/activity/", headers=admin[1])
    assert "password" not in response.text


# --- Filters ---
async def test_filter_by_worker_and_action(client, admin, worker, receive):
    admin_user, admin_headers = admin
    worker_user, worker_headers = worker
    first, second = await receive(7000, count=2)  # one "receive" by the worker
    await cut(client, worker_headers, first["id"], [{"length_mm": 3000, "used": True}])
    await cut(client, admin_headers, second["id"], [{"length_mm": 3000}])

    async def total(**params):
        return (await get_journal(client, admin_headers, **params))["total"]

    assert await total() == 4  # receive, cut + use, cut
    assert await total(user_id=worker_user.id) == 3
    assert await total(user_id=admin_user.id) == 1
    assert await total(action="cut") == 2
    assert await total(action="use") == 1
    assert await total(action="scrap") == 0
    assert await total(user_id=admin_user.id, action="use") == 0


async def test_filter_by_material_and_piece(client, admin, worker, material, receive):
    _, headers = worker
    other = (await client.post("/materials/", json={"name": "Профиль 55"}, headers=headers)).json()
    (pipe,) = await receive(7000)
    await client.post("/stock-items/", json={"material_id": other["id"], "length_mm": 6000}, headers=headers)
    await cut(client, headers, pipe["id"], [{"length_mm": 3000}])

    assert (await get_journal(client, admin[1], material_id=material["id"]))["total"] == 2
    assert (await get_journal(client, admin[1], material_id=other["id"]))["total"] == 1
    assert (await get_journal(client, admin[1], stock_item_id=pipe["id"]))["total"] == 2


async def test_filter_by_dates_given_in_the_viewers_time_zone(client, admin, sessions, receive):
    """
    A viewer at UTC+4 asks for 10 November. Their day runs from 20:00 UTC on
    the 9th to 20:00 UTC on the 10th, which is how the entries are stored.
    """
    stored_utc = [
        datetime(2026, 11, 9, 19, 59),  # 23:59 on the 9th locally: outside
        datetime(2026, 11, 9, 20, 0),   # 00:00 on the 10th locally: inside
        datetime(2026, 11, 10, 19, 59),  # 23:59 on the 10th locally: inside
        datetime(2026, 11, 10, 20, 0),  # 00:00 on the 11th locally: outside
    ]
    for _ in stored_utc:
        await receive(7000)
    async with sessions() as db:
        ids = (await db.scalars(select(ActivityEvent.id).order_by(ActivityEvent.id))).all()
        for event_id, moment in zip(ids, stored_utc):
            await db.execute(update(ActivityEvent).where(ActivityEvent.id == event_id).values(created_at=moment))
        await db.commit()

    page = await get_journal(
        client, admin[1], date_from="2026-11-10T00:00:00+04:00", date_to="2026-11-11T00:00:00+04:00"
    )

    assert page["total"] == 2
    assert [e["created_at"] for e in page["items"]] == [
        "2026-11-10T19:59:00+00:00",
        "2026-11-09T20:00:00+00:00",
    ]


async def test_open_ended_date_filters(client, admin, sessions, receive):
    await receive(7000)
    await receive(7000)
    async with sessions() as db:
        first_id = await db.scalar(select(ActivityEvent.id).order_by(ActivityEvent.id).limit(1))
        await db.execute(
            update(ActivityEvent).where(ActivityEvent.id == first_id).values(created_at=datetime(2020, 1, 1))
        )
        await db.commit()

    assert (await get_journal(client, admin[1], date_from="2026-01-01T00:00:00Z"))["total"] == 1
    assert (await get_journal(client, admin[1], date_to="2026-01-01T00:00:00Z"))["total"] == 1


# --- Paging ---
async def test_paging_walks_through_every_entry_once(client, admin, receive):
    for _ in range(5):
        await receive(7000)

    seen = []
    for offset in (0, 2, 4):
        page = await get_journal(client, admin[1], limit=2, offset=offset)
        assert page["total"] == 5  # the total ignores limit and offset
        seen += [e["id"] for e in page["items"]]

    assert seen == sorted(seen, reverse=True) and len(set(seen)) == 5


async def test_offset_past_the_end_is_empty(client, admin, receive):
    await receive(7000)
    page = await get_journal(client, admin[1], offset=10)
    assert page == {"items": [], "total": 1}


async def test_invalid_parameters_are_rejected(client, admin):
    async def status(**params):
        return (await client.get("/activity/", params=params, headers=admin[1])).status_code

    assert await status(limit=0) == 422
    assert await status(limit=201) == 422
    assert await status(offset=-1) == 422
    assert await status(action="delete") == 422
    assert await status(date_from="yesterday") == 422
    assert await status(limit=200) == 200
