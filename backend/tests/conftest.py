import os

os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
os.environ.setdefault("SESSION_SECRET", "test-secret-not-for-production")

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from src.models.base import Base


@pytest.fixture
async def test_db():
    """In-memory SQLite for tests — no Docker/Postgres needed.

    TimescaleDB-specific SQL (create_hypertable) only runs via Alembic
    migrations, never via Base.metadata.create_all, so it's naturally
    skipped here — no special-casing required.
    """
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest.fixture
async def client(test_db):
    """FastAPI AsyncClient with the get_db dependency overridden to use test_db."""
    from src.database import get_db
    from src.main import app

    session_maker = async_sessionmaker(test_db, expire_on_commit=False)

    async def override_get_db():
        async with session_maker() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c
    app.dependency_overrides.clear()
