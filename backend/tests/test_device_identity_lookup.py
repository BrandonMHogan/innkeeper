"""DeviceLookupInterface contract test — Plan 03 Task 1 Test 3.

Contract (documented in src/modules/device_identity/interfaces.py and this
plan's SUMMARY.md, since Plans 04/05 depend on it exactly as specified
here): lookup(identifier) accepts a MAC or an identity_key and returns a
DeviceInfo for a matching registered Device, or None if no Device matches.
None — not a raised exception — is the "not found" signal.
"""

from sqlalchemy.ext.asyncio import async_sessionmaker

from src.modules.device_identity.interfaces import DeviceInfo
from src.modules.device_identity.models import Device, DeviceMacHistory, DeviceType
from src.modules.device_identity.module import DeviceIdentityModule


async def test_lookup_resolves_registered_device_by_mac(test_db):
    session_maker = async_sessionmaker(test_db, expire_on_commit=False)
    async with session_maker() as db:
        device = Device(
            identity_key="host:lookup-test",
            name="Lookup Test Device",
            owner="tester",
            type=DeviceType.LAPTOP,
            last_known_mac="aa:bb:cc:dd:ee:ff",
        )
        db.add(device)
        await db.commit()
        device_id = device.id

    module = DeviceIdentityModule(session_maker)
    result = await module.lookup("aa:bb:cc:dd:ee:ff")

    assert result is not None
    assert isinstance(result, DeviceInfo)
    assert result.device_id == device_id
    assert result.name == "Lookup Test Device"
    assert "aa:bb:cc:dd:ee:ff" in result.macs


async def test_lookup_resolves_registered_device_by_identity_key(test_db):
    session_maker = async_sessionmaker(test_db, expire_on_commit=False)
    async with session_maker() as db:
        device = Device(
            identity_key="host:identity-key-lookup",
            name="Identity Key Device",
            owner="tester",
            type=DeviceType.LAPTOP,
            last_known_mac="11:22:33:44:55:66",
        )
        db.add(device)
        await db.commit()

    module = DeviceIdentityModule(session_maker)
    result = await module.lookup("host:identity-key-lookup")

    assert result is not None
    assert result.name == "Identity Key Device"


async def test_lookup_returns_none_for_unmatched_mac(test_db):
    session_maker = async_sessionmaker(test_db, expire_on_commit=False)
    module = DeviceIdentityModule(session_maker)

    result = await module.lookup("ff:ff:ff:ff:ff:ff")

    assert result is None


async def test_lookup_macs_includes_full_mac_history(test_db):
    """DeviceInfo.macs unions the device's current last_known_mac with every
    historical MAC from DeviceMacHistory — the MAC-rotation-aware union
    logic moved out of routes/traffic.py::_resolve_device_macs per
    RESEARCH.md Pattern 6."""
    session_maker = async_sessionmaker(test_db, expire_on_commit=False)
    async with session_maker() as db:
        device = Device(
            identity_key="host:rotated",
            name="Rotated Device",
            owner="tester",
            type=DeviceType.PHONE,
            last_known_mac="22:22:22:22:22:22",
        )
        db.add(device)
        await db.flush()
        db.add(DeviceMacHistory(device_id=device.id, mac="11:11:11:11:11:11"))
        db.add(DeviceMacHistory(device_id=device.id, mac="22:22:22:22:22:22"))
        await db.commit()

    module = DeviceIdentityModule(session_maker)
    result = await module.lookup("22:22:22:22:22:22")

    assert result is not None
    assert result.macs == {"11:11:11:11:11:11", "22:22:22:22:22:22"}
