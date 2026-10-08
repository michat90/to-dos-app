from typing import AsyncGenerator
from httpx import ASGITransport, AsyncClient
from unittest.mock import AsyncMock
import pytest_asyncio
import pytest
import fakeredis.aioredis
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.redis import get_redis
from app.db.database import get_db
from app.db.models.project import Base
from app.main import app

TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

engine_test = create_async_engine(TEST_DATABASE_URL, connect_args={
                                  "check_same_thread": False})
TestingSessionLocal = async_sessionmaker(
    bind=engine_test, class_=AsyncSession, expire_on_commit=False
)


@pytest_asyncio.fixture(scope="function", autouse=True)
async def prepare_database():
    async with engine_test.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with engine_test.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


# 1. Fixture udostępniający sesję dla testów (np. test_unit_of_work.py)
@pytest_asyncio.fixture(scope="function")
async def override_get_db_session() -> AsyncGenerator[AsyncSession, None]:
    async with TestingSessionLocal() as session:
        yield session


# 2. Nadpisanie zależności FastAPI dla routów HTTP
async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
    async with TestingSessionLocal() as session:
        yield session


app.dependency_overrides[get_db] = override_get_db


# 3. Fixture dostarczający wirtualnego klienta HTTP
@pytest_asyncio.fixture(scope="function")
async def client() -> AsyncGenerator[AsyncClient, None]:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac


@pytest_asyncio.fixture(loop_scope="function")
async def fake_redis():
    """Tworzy asynchronicznego klienta FakeRedis w pamięci dla każdego testu."""
    client = fakeredis.aioredis.FakeRedis()
    yield client
    await client.aclose()


@pytest.fixture
def mock_uow() -> AsyncMock:
    """Tworzy mocka UnitOfWork dla asynchronicznego kontekstu (async with)."""
    uow = AsyncMock()
    uow.__aenter__.return_value = uow
    return uow


@pytest_asyncio.fixture(loop_scope="function")
async def client(override_get_db_session, fake_redis):
    # Używamy zdefiniowanej u Ciebie fixtury override_get_db_session
    async def _override_get_db():
        yield override_get_db_session

    async def _override_get_redis():
        yield fake_redis

    # Nadpisujemy kluczowe zależności FastAPI
    app.dependency_overrides[get_db] = _override_get_db
    app.dependency_overrides[get_redis] = _override_get_redis

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        yield ac

    app.dependency_overrides.clear()
