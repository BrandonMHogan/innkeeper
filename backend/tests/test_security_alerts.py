from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from src.models.security_alert import SecurityAlert, SecurityAlertType
from src.services.discovery import record_observation
from src.services.identity_resolver import Observation


async def test_record_observation_new_identity_fires_unknown_device_alert(test_db):
    session_maker = async_sessionmaker(test_db, expire_on_commit=False)
    async with session_maker() as db:
        await record_observation(
            db,
            Observation(
                mac="aa:bb:cc:dd:ee:ff",
                hostname="new-gadget",
                source="dhcp",
                observed_at=datetime.now(timezone.utc),
            ),
        )

        alerts = (
            (
                await db.execute(
                    select(SecurityAlert).where(SecurityAlert.type == SecurityAlertType.UNKNOWN_DEVICE)
                )
            )
            .scalars()
            .all()
        )
        assert len(alerts) == 1
        assert alerts[0].device_id is None


async def test_record_observation_existing_identity_does_not_refire_alert(test_db):
    session_maker = async_sessionmaker(test_db, expire_on_commit=False)
    async with session_maker() as db:
        observation = Observation(
            mac="aa:bb:cc:dd:ee:ff",
            hostname="new-gadget",
            source="dhcp",
            observed_at=datetime.now(timezone.utc),
        )
        await record_observation(db, observation)
        await record_observation(db, observation)

        alerts = (
            (
                await db.execute(
                    select(SecurityAlert).where(SecurityAlert.type == SecurityAlertType.UNKNOWN_DEVICE)
                )
            )
            .scalars()
            .all()
        )
        assert len(alerts) == 1
