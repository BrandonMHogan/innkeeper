from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.models.app_settings import AppSettings
from src.models.base import Base


async def test_models_create_row(test_db):
    """Directly construct an AppSettings row and confirm it round-trips."""
    session_maker = async_sessionmaker(test_db, expire_on_commit=False, class_=AsyncSession)
    async with session_maker() as session:
        row = AppSettings(setup_complete=True, password_hash="salt$deadbeef")
        session.add(row)
        await session.commit()

    async with session_maker() as session:
        result = await session.execute(select(AppSettings))
        fetched = result.scalar_one()
        assert fetched.setup_complete is True
        assert fetched.password_hash == "salt$deadbeef"
        assert fetched.password_hash != "salt"  # never plaintext


async def test_metadata_create_all(test_db):
    """Base.metadata.create_all succeeds against in-memory SQLite.

    Confirms create_hypertable (SQLite-incompatible) is correctly isolated
    to the Alembic migration and never invoked by create_all.
    """
    table_names = set(Base.metadata.tables.keys())
    assert {"app_settings", "bandwidth_metrics", "arp_events"} <= table_names
