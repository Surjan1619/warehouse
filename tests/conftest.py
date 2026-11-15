"""
Shared fixtures.

Tests run against a separate PostgreSQL database named "<main database>_test"
on the same server, so the working data is never touched. The database is
created on first use, its tables are rebuilt once per test run from the ORM
models, and every table is emptied before each test.
"""
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.core.config import settings
from app.core.db import get_db
from app.core.jwt import create_access_token
from app.main import app
from app.models.Alchemy_models import Base
from app.repo.crud import create_user

MAIN_URL = make_url(settings.DATABASE_URL)
TEST_DATABASE = f"{MAIN_URL.database}_test"
TEST_URL = MAIN_URL.set(database=TEST_DATABASE)

# Not a real credential: test users exist only inside the test database
TEST_PASSWORD = "test-password"


@pytest_asyncio.fixture(scope="session")
async def engine():
    # Guard against ever dropping tables of the working database
    assert TEST_URL.database.endswith("_test")

    # CREATE DATABASE cannot run inside a transaction, hence AUTOCOMMIT
    server = create_async_engine(MAIN_URL, isolation_level="AUTOCOMMIT", poolclass=NullPool)
    async with server.connect() as conn:
        exists = await conn.scalar(
            text("SELECT 1 FROM pg_database WHERE datname = :name"), {"name": TEST_DATABASE}
        )
        if not exists:
            await conn.execute(text(f'CREATE DATABASE "{TEST_DATABASE}"'))
    await server.dispose()

    # NullPool: no connection outlives the event loop that opened it
    test_engine = create_async_engine(TEST_URL, poolclass=NullPool)
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    yield test_engine
    await test_engine.dispose()


@pytest_asyncio.fixture
async def sessions(engine):
    """Session factory bound to the test database, emptied before the test."""
    tables = ", ".join(f'"{name}"' for name in Base.metadata.tables)
    async with engine.begin() as conn:
        await conn.execute(text(f"TRUNCATE {tables} RESTART IDENTITY CASCADE"))
    return async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


@pytest_asyncio.fixture
async def client(sessions):
    """HTTP client for the application, wired to the test database."""

    async def override_get_db():
        async with sessions() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as http:
        yield http
    app.dependency_overrides.clear()


@pytest.fixture
def make_user(sessions):
    """Create a user and return it together with ready-to-use auth headers."""

    async def _make(username: str, role: str = "worker", is_active: bool = True):
        async with sessions() as db:
            user = await create_user(db, username=username, role=role, plain_password=TEST_PASSWORD)
            if not is_active:
                user.is_active = False
                await db.commit()
        headers = {"Authorization": f"Bearer {create_access_token(subject=str(user.id))}"}
        return user, headers

    return _make


@pytest_asyncio.fixture
async def admin(make_user):
    return await make_user("admin", role="admin")


@pytest_asyncio.fixture
async def worker(make_user):
    return await make_user("worker", role="worker")


@pytest_asyncio.fixture
async def material(client, worker):
    """A material with no kerf and the default 300 mm minimum usable remainder."""
    _, headers = worker
    response = await client.post("/materials/", json={"name": "Труба 40x20"}, headers=headers)
    assert response.status_code == 201, response.text
    return response.json()


@pytest.fixture
def receive(client, worker, material):
    """Put pieces of the test material into stock and return them."""
    _, headers = worker

    async def _receive(length_mm: int, count: int = 1, **extra):
        body = {"material_id": material["id"], "length_mm": length_mm, "count": count, **extra}
        response = await client.post("/stock-items/", json=body, headers=headers)
        assert response.status_code == 201, response.text
        return response.json()

    return _receive
