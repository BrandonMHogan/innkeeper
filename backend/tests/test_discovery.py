from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from src.models.device import Device, DeviceType
from src.models.discovered_identity import DiscoveredIdentity
from src.services.discovery import record_observation
from src.services.identity_resolver import MDNS_PLACEHOLDER_MAC, Observation


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


async def test_placeholder_mac_observation_does_not_hijack_registered_device(test_db):
    session_maker = async_sessionmaker(test_db, expire_on_commit=False)
    async with session_maker() as db:
        device = Device(
            identity_key="host:living-room-speaker",
            name="Living Room Speaker",
            owner="Brandon",
            type=DeviceType.OTHER,
            trusted=False,
            last_known_mac=MDNS_PLACEHOLDER_MAC,
        )
        db.add(device)
        await db.commit()

        await record_observation(
            db,
            Observation(
                mac=MDNS_PLACEHOLDER_MAC,
                hostname="someone-elses-phone",
                source="mdns",
                observed_at=datetime.utcnow(),
            ),
        )

        devices = (await db.execute(select(Device))).scalars().all()
        assert len(devices) == 1
        assert devices[0].identity_key == "host:living-room-speaker"
        assert devices[0].name == "Living Room Speaker"
        assert devices[0].last_known_mac == MDNS_PLACEHOLDER_MAC

        identities = (await db.execute(select(DiscoveredIdentity))).scalars().all()
        assert len(identities) == 1
        assert identities[0].identity_key == "host:someone-elses-phone"


async def test_record_observation_non_placeholder_mac_still_matches_device(test_db):
    session_maker = async_sessionmaker(test_db, expire_on_commit=False)
    async with session_maker() as db:
        device = Device(
            identity_key="mac:aa:bb:cc:dd:ee:ff",
            name="Real Device",
            owner="Brandon",
            type=DeviceType.OTHER,
            trusted=False,
            last_known_mac="aa:bb:cc:dd:ee:ff",
        )
        db.add(device)
        await db.commit()

        await record_observation(
            db,
            Observation(
                mac="aa:bb:cc:dd:ee:ff",
                hostname="renamed",
                source="dhcp",
                observed_at=datetime.utcnow(),
            ),
        )

        devices = (await db.execute(select(Device))).scalars().all()
        assert len(devices) == 1
        assert devices[0].identity_key == "host:renamed"


async def test_upsert_persists_mdns_dhcp_signals(test_db):
    session_maker = async_sessionmaker(test_db, expire_on_commit=False)

    # Use a fresh session per phase — selecting mid-session on the same
    # identity map would return a stale cached instance rather than a
    # row re-read from the DB, since the upsert's Core on_conflict_do_update
    # statement bypasses ORM attribute refresh for already-loaded instances.
    async with session_maker() as db:
        await record_observation(
            db,
            Observation(
                mac="aa:bb:cc:dd:ee:ff",
                hostname="signal-device",
                source="mdns",
                observed_at=datetime.utcnow(),
                mdns_service_type="_airplay._tcp",
            ),
        )

    async with session_maker() as db:
        result = await db.execute(select(DiscoveredIdentity))
        rows = result.scalars().all()
        assert len(rows) == 1
        assert rows[0].mdns_service_type == "_airplay._tcp"
        assert rows[0].dhcp_vendor_class is None

    # Upsert overwrites signal columns with each new observation's values
    # (same overwrite semantics as the existing mac/hostname columns) —
    # a DHCP-only observation carries no mDNS signal, so this call
    # correctly clears mdns_service_type while setting dhcp_vendor_class.
    async with session_maker() as db:
        await record_observation(
            db,
            Observation(
                mac="aa:bb:cc:dd:ee:ff",
                hostname="signal-device",
                source="dhcp",
                observed_at=datetime.utcnow(),
                dhcp_vendor_class="dhcpcd-9.4.1:Linux",
            ),
        )

    async with session_maker() as db:
        result = await db.execute(select(DiscoveredIdentity))
        rows = result.scalars().all()
        assert len(rows) == 1
        assert rows[0].dhcp_vendor_class == "dhcpcd-9.4.1:Linux"


async def test_upsert_arp_only_observation_leaves_signal_columns_none(test_db):
    session_maker = async_sessionmaker(test_db, expire_on_commit=False)
    async with session_maker() as db:
        await record_observation(
            db,
            Observation(
                mac="aa:bb:cc:dd:ee:ff",
                hostname=None,
                source="arp",
                observed_at=datetime.utcnow(),
            ),
        )

        result = await db.execute(select(DiscoveredIdentity))
        rows = result.scalars().all()
        assert len(rows) == 1
        assert rows[0].mdns_service_type is None
        assert rows[0].dhcp_vendor_class is None


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
