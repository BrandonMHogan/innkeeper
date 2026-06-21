from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.ext.asyncio import async_sessionmaker

from src.modules.device_identity.identity_resolver import Observation
from src.modules.device_identity.models import Device, DeviceMacHistory, DeviceType
from src.modules.device_identity.service import record_observation


async def test_query_all_macs_for_device(test_db):
    """Inserting two DeviceMacHistory rows for the same device_id with
    different macs, then querying all macs for that device_id, returns both.
    """
    session_maker = async_sessionmaker(test_db, expire_on_commit=False)
    async with session_maker() as session:
        device = Device(
            identity_key="host:testdevice",
            name="Test Device",
            owner="tester",
            type=DeviceType.LAPTOP,
            last_known_mac="aa:bb:cc:dd:ee:01",
        )
        session.add(device)
        await session.commit()

        now = datetime.now(timezone.utc)
        session.add(DeviceMacHistory(device_id=device.id, mac="aa:bb:cc:dd:ee:01", first_seen=now, last_seen=now))
        session.add(DeviceMacHistory(device_id=device.id, mac="aa:bb:cc:dd:ee:02", first_seen=now, last_seen=now))
        await session.commit()

        result = await session.execute(
            select(DeviceMacHistory.mac).where(DeviceMacHistory.device_id == device.id)
        )
        macs = {row[0] for row in result.all()}
        assert macs == {"aa:bb:cc:dd:ee:01", "aa:bb:cc:dd:ee:02"}


async def test_upsert_same_device_mac_pair_no_integrity_error(test_db):
    """Inserting a DeviceMacHistory row, then upserting another row for the
    same (device_id, mac) pair with a later seen_at, does not raise an
    integrity error — composite PK is (device_id, mac), so an update path
    is needed, not a second insert.
    """
    session_maker = async_sessionmaker(test_db, expire_on_commit=False)
    async with session_maker() as session:
        device = Device(
            identity_key="host:testdevice2",
            name="Test Device 2",
            owner="tester",
            type=DeviceType.LAPTOP,
            last_known_mac="aa:bb:cc:dd:ee:03",
        )
        session.add(device)
        await session.commit()

        first_seen = datetime(2026, 1, 1, tzinfo=timezone.utc)
        later_seen = datetime(2026, 1, 2, tzinfo=timezone.utc)

        stmt = sqlite_insert(DeviceMacHistory).values(
            device_id=device.id, mac="aa:bb:cc:dd:ee:03", first_seen=first_seen, last_seen=first_seen
        )
        await session.execute(stmt)
        await session.commit()

        # Second "insert" for the same (device_id, mac) pair upserts instead
        # of raising an IntegrityError.
        stmt = (
            sqlite_insert(DeviceMacHistory)
            .values(device_id=device.id, mac="aa:bb:cc:dd:ee:03", first_seen=first_seen, last_seen=later_seen)
            .on_conflict_do_update(
                index_elements=["device_id", "mac"],
                set_={"last_seen": later_seen},
            )
        )
        await session.execute(stmt)
        await session.commit()

        result = await session.execute(
            select(DeviceMacHistory).where(
                DeviceMacHistory.device_id == device.id,
                DeviceMacHistory.mac == "aa:bb:cc:dd:ee:03",
            )
        )
        rows = result.scalars().all()
        assert len(rows) == 1
        assert rows[0].last_seen.replace(tzinfo=timezone.utc) == later_seen


async def test_record_observation_writes_mac_history_for_registered_device(test_db):
    """record_observation's Device-branch fast path upserts a DeviceMacHistory
    row whenever last_known_mac changes — closes the MAC-rotation blind spot.
    """
    session_maker = async_sessionmaker(test_db, expire_on_commit=False)
    async with session_maker() as db:
        device = Device(
            identity_key="mac:aa:bb:cc:dd:ee:04",
            name="Rotating Device",
            owner="tester",
            type=DeviceType.PHONE,
            last_known_mac="aa:bb:cc:dd:ee:04",
        )
        db.add(device)
        await db.commit()

        first_seen_at = datetime(2026, 1, 1, tzinfo=timezone.utc)
        await record_observation(
            db,
            Observation(mac="aa:bb:cc:dd:ee:04", hostname=None, source="arp", observed_at=first_seen_at),
        )

        result = await db.execute(select(DeviceMacHistory).where(DeviceMacHistory.device_id == device.id))
        macs = {row.mac for row in result.scalars().all()}
        assert macs == {"aa:bb:cc:dd:ee:04"}
