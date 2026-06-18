from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from src.models.device import Device, DeviceType
from src.models.discovered_identity import DiscoveredIdentity
from src.services.discovery import record_observation
from src.services.identity_resolver import Observation


async def test_record_observation_creates_discovered_identity(test_db):
    session_maker = async_sessionmaker(test_db, expire_on_commit=False)
    async with session_maker() as db:
        observation = Observation(
            mac="aa:bb:cc:dd:ee:ff",
            hostname="foo",
            source="dhcp",
            observed_at=datetime.utcnow(),
        )
        await record_observation(db, observation)

        result = await db.execute(select(DiscoveredIdentity))
        rows = result.scalars().all()
        assert len(rows) == 1
        assert rows[0].identity_key == "host:foo"


async def test_first_last_seen_tracking(test_db):
    session_maker = async_sessionmaker(test_db, expire_on_commit=False)
    async with session_maker() as db:
        first_seen_at = datetime(2026, 1, 1, 10, 0, 0)
        last_seen_at = datetime(2026, 1, 1, 12, 0, 0)

        await record_observation(
            db,
            Observation(mac="aa:bb:cc:dd:ee:ff", hostname="bar", source="dhcp", observed_at=first_seen_at),
        )
        await record_observation(
            db,
            Observation(mac="aa:bb:cc:dd:ee:ff", hostname="bar", source="dhcp", observed_at=last_seen_at),
        )

        result = await db.execute(select(DiscoveredIdentity))
        rows = result.scalars().all()
        assert len(rows) == 1
        assert rows[0].first_seen == first_seen_at
        assert rows[0].last_seen == last_seen_at


async def test_registered_identity_key_change_no_phantom(test_db):
    session_maker = async_sessionmaker(test_db, expire_on_commit=False)
    async with session_maker() as db:
        device = Device(
            identity_key="mac:aa:bb:cc:dd:ee:ff",
            name="Brandon's Phone",
            owner="Brandon",
            type=DeviceType.PHONE,
            trusted=False,
            last_known_mac="aa:bb:cc:dd:ee:ff",
        )
        db.add(device)
        await db.commit()

        await record_observation(
            db,
            Observation(
                mac="aa:bb:cc:dd:ee:ff",
                hostname="renamed-phone",
                source="dhcp",
                observed_at=datetime.utcnow(),
            ),
        )

        identities = (await db.execute(select(DiscoveredIdentity))).scalars().all()
        assert len(identities) == 0

        devices = (await db.execute(select(Device))).scalars().all()
        assert len(devices) == 1
        assert devices[0].identity_key == "host:renamed-phone"


async def test_concurrent_same_identity_no_duplicate(test_db):
    session_maker = async_sessionmaker(test_db, expire_on_commit=False)
    async with session_maker() as db:
        observation = Observation(
            mac="aa:bb:cc:dd:ee:ff",
            hostname="dup-device",
            source="dhcp",
            observed_at=datetime.utcnow(),
        )
        await record_observation(db, observation)
        await record_observation(db, observation)

        result = await db.execute(select(DiscoveredIdentity))
        rows = result.scalars().all()
        assert len(rows) == 1
