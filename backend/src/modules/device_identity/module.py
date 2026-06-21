"""DeviceIdentityModule — DeviceLookupInterface implementation +
register()/merge() write methods, instantiated via the ModuleLoader's
constructor-injection factory (D-08).

Devices (Plan 03 Task 2) calls register()/merge() instead of writing
directly to device_identity.* tables — D-16/Pitfall 4/T-05-07: a module may
only query its own schema directly, everything else goes through a
requires-resolved interface/write-method, enforced by code-review
convention (D-13) since this is a single-process app, not Postgres grants.
"""

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.modules.device_identity.identity_resolver import MDNS_PLACEHOLDER_MAC
from src.modules.device_identity.interfaces import DeviceInfo, DeviceLookupInterface
from src.modules.device_identity.models import Device, DeviceMacHistory, DiscoveredIdentity


class DeviceIdentityModule:
    """Implements DeviceLookupInterface; exposes register()/merge() for the
    Devices feature module's write paths. requires=[] per the manifest, so
    the constructor takes no injected dependencies — `deps` is accepted for
    factory-signature consistency with every other module."""

    def __init__(self, db_session_factory) -> None:
        self._db_session_factory = db_session_factory

    async def lookup(self, identifier: str) -> DeviceInfo | None:
        """Resolves `identifier` (a MAC or an identity_key) to a DeviceInfo,
        or None if no registered Device matches. `macs` is the union of the
        device's current last_known_mac plus its full DeviceMacHistory —
        the MAC-rotation-aware union logic moved here per RESEARCH.md
        Pattern 6, out of routes/traffic.py::_resolve_device_macs."""
        async with self._db_session_factory() as db:
            device = await self._find_device(db, identifier)
            if device is None:
                return None
            return await self._to_device_info(db, device)

    async def register(
        self,
        db: AsyncSession,
        identity_id: int,
        name: str,
        owner: str,
        device_type: str,
        trusted: bool,
    ) -> Device:
        """Registers a DiscoveredIdentity as a new Device — byte-identical
        behavior to the pre-retrofit routes/devices.py::register_device,
        moved behind this method so Devices' routes.py never writes
        directly to device_identity.* tables."""
        result = await db.execute(select(DiscoveredIdentity).where(DiscoveredIdentity.id == identity_id))
        identity = result.scalar_one_or_none()
        if identity is None:
            raise ValueError("Discovered identity not found")

        device = Device(
            identity_key=identity.identity_key,
            name=name,
            owner=owner,
            type=device_type,
            trusted=trusted,
            last_known_mac=None if identity.mac == MDNS_PLACEHOLDER_MAC else identity.mac,
            first_seen=identity.first_seen,
            last_seen=identity.last_seen,
        )
        db.add(device)
        await db.delete(identity)
        await db.commit()
        return device

    async def merge(self, db: AsyncSession, identity_id: int, target_device_id: int) -> Device:
        """Merges a DiscoveredIdentity into an existing Device — byte-identical
        behavior to the pre-retrofit routes/devices.py::merge_device."""
        identity_result = await db.execute(select(DiscoveredIdentity).where(DiscoveredIdentity.id == identity_id))
        identity = identity_result.scalar_one_or_none()
        if identity is None:
            raise ValueError("Discovered identity not found")

        device_result = await db.execute(select(Device).where(Device.id == target_device_id))
        device = device_result.scalar_one_or_none()
        if device is None:
            raise ValueError("Target device not found")

        if identity.mac != MDNS_PLACEHOLDER_MAC:
            device.last_known_mac = identity.mac
        device.last_seen = max(identity.last_seen, device.last_seen)
        await db.delete(identity)
        await db.commit()
        return device

    async def list_all(self, db: AsyncSession) -> tuple[list[Device], list[DiscoveredIdentity]]:
        """Returns (registered devices, unknown identities) — the combined
        list GET /api/modules/devices/ serializes. Lives here so Devices'
        routes.py never issues select(Device)/select(DiscoveredIdentity)
        directly (T-05-07)."""
        devices = (await db.execute(select(Device))).scalars().all()
        identities = (await db.execute(select(DiscoveredIdentity))).scalars().all()
        return list(devices), list(identities)

    async def _find_device(self, db: AsyncSession, identifier: str) -> Device | None:
        by_mac = (await db.execute(select(Device).where(Device.last_known_mac == identifier))).scalar_one_or_none()
        if by_mac is not None:
            return by_mac
        return (
            await db.execute(select(Device).where(Device.identity_key == identifier))
        ).scalar_one_or_none()

    async def _to_device_info(self, db: AsyncSession, device: Device) -> DeviceInfo:
        history_macs = (
            (await db.execute(select(DeviceMacHistory.mac).where(DeviceMacHistory.device_id == device.id)))
            .scalars()
            .all()
        )
        macs = set(history_macs)
        if device.last_known_mac:
            macs.add(device.last_known_mac)
        return DeviceInfo(
            device_id=device.id,
            name=device.name,
            type=device.type.value if hasattr(device.type, "value") else device.type,
            macs=macs,
        )


def create(deps: dict[type, object]) -> DeviceIdentityModule:
    """Constructor-injection factory satisfying provides=[DeviceLookupInterface],
    requires=[] (D-08). Imports the live async session factory lazily to
    avoid a circular import between src.database and the module package at
    import time."""
    from sqlalchemy.ext.asyncio import async_sessionmaker

    from src.database import engine

    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    return DeviceIdentityModule(session_factory)
