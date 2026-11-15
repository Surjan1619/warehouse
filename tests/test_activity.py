"""The activity journal: writing entries and reading them back."""
from datetime import datetime, timedelta

import pytest
from sqlalchemy import func, select, update

from app.models.Alchemy_models import ActivityEvent, Material, StockItem
from app.repo import activity


@pytest.fixture
async def stock(sessions, worker):
    """A material and one piece of it, created directly in the database."""
    user, _ = worker
    async with sessions() as db:
        material = Material(name="Труба 40x20")
        db.add(material)
        await db.flush()
        item = StockItem(material_id=material.id, length_mm=7000, created_by_id=user.id)
        db.add(item)
        await db.commit()
        return material.id, item.id


async def count_events(sessions) -> int:
    async with sessions() as db:
        return await db.scalar(select(func.count()).select_from(ActivityEvent))


async def test_event_is_saved_with_all_its_fields(sessions, worker, stock):
    user, _ = worker
    material_id, item_id = stock
    async with sessions() as db:
        activity.add_event(
            db,
            activity.RECEIVE,
            user.id,
            material_id=material_id,
            stock_item_id=item_id,
            quantity=30,
            length_mm=210_000,
            details={"note": "первая поставка"},
        )
        await db.commit()

    async with sessions() as db:
        (event,) = await activity.list_events(db)

    assert event.action == "receive"
    assert event.user.username == "worker"
    assert event.material.name == "Труба 40x20"
    assert event.stock_item.id == item_id
    assert (event.quantity, event.length_mm) == (30, 210_000)
    assert event.details == {"note": "первая поставка"}
    assert isinstance(event.created_at, datetime)


async def test_defaults_describe_one_piece_of_unknown_length(sessions, worker):
    async with sessions() as db:
        activity.add_event(db, activity.CUT, worker[0].id)
        await db.commit()
    async with sessions() as db:
        (event,) = await activity.list_events(db)
    assert (event.quantity, event.length_mm, event.details) == (1, 0, None)
    assert event.material is None and event.stock_item is None


async def test_event_without_a_user_is_allowed(sessions):
    """System actions and tokens of deleted users must not break the journal."""
    async with sessions() as db:
        activity.add_event(db, activity.SCRAP, None)
        await db.commit()
    async with sessions() as db:
        (event,) = await activity.list_events(db)
    assert event.user is None


async def test_event_is_rolled_back_together_with_the_action(sessions, worker):
    """add_event does not commit: a failed action leaves no trace in the journal."""
    async with sessions() as db:
        activity.add_event(db, activity.RECEIVE, worker[0].id)
        await db.rollback()
    assert await count_events(sessions) == 0


async def test_nothing_is_written_until_the_caller_commits(sessions, worker):
    async with sessions() as db:
        activity.add_event(db, activity.RECEIVE, worker[0].id)
        await db.flush()
        assert await count_events(sessions) == 0  # another session does not see it yet
        await db.commit()
    assert await count_events(sessions) == 1


@pytest.mark.parametrize("action", ["", "delete", "RECEIVE", None])
async def test_unknown_action_is_rejected(sessions, worker, action):
    async with sessions() as db:
        with pytest.raises(ValueError):
            activity.add_event(db, action, worker[0].id)


@pytest.mark.parametrize("values", [{"quantity": -1}, {"length_mm": -1}])
async def test_negative_totals_are_rejected(sessions, worker, values):
    async with sessions() as db:
        with pytest.raises(ValueError):
            activity.add_event(db, activity.USE, worker[0].id, **values)


async def test_newest_entries_come_first(sessions, worker):
    async with sessions() as db:
        for action in (activity.RECEIVE, activity.CUT, activity.USE):
            activity.add_event(db, action, worker[0].id)
            await db.commit()
    async with sessions() as db:
        events = await activity.list_events(db)
    assert [e.action for e in events] == ["use", "cut", "receive"]


async def test_filters(sessions, admin, worker, stock):
    admin_user, _ = admin
    worker_user, _ = worker
    material_id, item_id = stock
    async with sessions() as db:
        activity.add_event(db, activity.RECEIVE, worker_user.id, material_id=material_id, quantity=3)
        activity.add_event(db, activity.CUT, worker_user.id, material_id=material_id, stock_item_id=item_id)
        activity.add_event(db, activity.CUT, admin_user.id)
        await db.commit()

    async def found(**filters):
        async with sessions() as db:
            return len(await activity.list_events(db, **filters))

    assert await found() == 3
    assert await found(user_id=worker_user.id) == 2
    assert await found(user_id=admin_user.id) == 1
    assert await found(action=activity.CUT) == 2
    assert await found(user_id=worker_user.id, action=activity.CUT) == 1
    assert await found(material_id=material_id) == 2
    assert await found(stock_item_id=item_id) == 1
    assert await found(action=activity.SCRAP) == 0


async def test_date_range_includes_the_start_and_excludes_the_end(sessions, worker):
    day = datetime(2026, 11, 10)
    moments = [day - timedelta(seconds=1), day, day + timedelta(hours=12), day + timedelta(days=1)]
    async with sessions() as db:
        for _ in moments:
            activity.add_event(db, activity.RECEIVE, worker[0].id)
        await db.commit()
        ids = (await db.scalars(select(ActivityEvent.id).order_by(ActivityEvent.id))).all()
        for event_id, moment in zip(ids, moments):
            await db.execute(update(ActivityEvent).where(ActivityEvent.id == event_id).values(created_at=moment))
        await db.commit()

    async with sessions() as db:
        inside = await activity.list_events(db, date_from=day, date_to=day + timedelta(days=1))
        since = await activity.list_events(db, date_from=day)
        before = await activity.list_events(db, date_to=day)

    assert sorted(e.created_at for e in inside) == [day, day + timedelta(hours=12)]
    assert len(since) == 3
    assert len(before) == 1


async def test_limit_and_offset(sessions, worker):
    async with sessions() as db:
        for _ in range(5):
            activity.add_event(db, activity.RECEIVE, worker[0].id)
        await db.commit()
    async with sessions() as db:
        first = await activity.list_events(db, limit=2)
        second = await activity.list_events(db, limit=2, offset=2)
        rest = await activity.list_events(db, limit=2, offset=4)
    ids = [e.id for e in first + second + rest]
    assert ids == sorted(ids, reverse=True) and len(ids) == 5
