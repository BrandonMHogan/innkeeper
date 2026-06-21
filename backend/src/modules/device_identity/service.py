"""upsert_discovered_identity/upsert_device_mac_history/record_observation —
moved verbatim from src/services/discovery.py into the device_identity
support module, per Plan 03 Task 1's action.

The only behavioral addition vs. the pre-retrofit version: record_observation
publishes a "new_device" event via the shared event_bus singleton at the
exact point a genuinely-new identity is written (inside
upsert_discovered_identity's is_new_identity branch). Signature, return
type, and commit timing are otherwise byte-identical to the pre-retrofit
discovery.py — this function is on the capture container's hot ingest path
(T-05-08) and must not silently change contract.
"""

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.security_alert import SecurityAlert, SecurityAlertType
from src.modules.device_identity.event_bus_singleton import event_bus
from src.modules.device_identity.identity_resolver import (
    MDNS_PLACEHOLDER_MAC,
    HostnameFallbackResolver,
    IdentityResolver,
    Observation,
)
from src.modules.device_identity.models import Device, DeviceMacHistory, DiscoveredIdentity
from src.services.security_status import SecurityStatus


async def upsert_discovered_identity(
    db: AsyncSession,
    identity_key: str,
    mac: str,
    hostname: str | None,
    seen_at: datetime,
    mdns_service_type: str | None = None,
    dhcp_vendor_class: str | None = None,
) -> None:
    """Dialect-aware upsert avoiding the select-then-insert race (Pitfall 5).

    Postgres (production) uses pg_insert().on_conflict_do_update(); SQLite
    (the in-memory test fixture) uses the equivalent sqlite_insert() path —
    both support the same ON CONFLICT DO UPDATE semantics in SQLAlchemy 2.0.

    SEC-02/D-13: a pre-check distinguishes a brand-new identity from an
    update to an existing one — only the former fires exactly one
    unknown_device SecurityAlert (device_id=None, since no Device row
    exists yet for an unregistered identity) and exactly one "new_device"
    event_bus publish.
    """
    dialect_name = db.bind.dialect.name if db.bind is not None else db.get_bind().dialect.name

    is_new_identity = (
        await db.execute(select(DiscoveredIdentity.id).where(DiscoveredIdentity.identity_key == identity_key))
    ).scalar_one_or_none() is None

    if dialect_name == "postgresql":
        stmt = (
            pg_insert(DiscoveredIdentity)
            .values(
                identity_key=identity_key,
                mac=mac,
                hostname=hostname,
                mdns_service_type=mdns_service_type,
                dhcp_vendor_class=dhcp_vendor_class,
                first_seen=seen_at,
                last_seen=seen_at,
            )
            .on_conflict_do_update(
                index_elements=[DiscoveredIdentity.identity_key],
                set_={
                    "mac": mac,
                    "hostname": hostname,
                    "mdns_service_type": mdns_service_type,
                    "dhcp_vendor_class": dhcp_vendor_class,
                    "last_seen": seen_at,
                },
            )
        )
    else:
        stmt = (
            sqlite_insert(DiscoveredIdentity)
            .values(
                identity_key=identity_key,
                mac=mac,
                hostname=hostname,
                mdns_service_type=mdns_service_type,
                dhcp_vendor_class=dhcp_vendor_class,
                first_seen=seen_at,
                last_seen=seen_at,
            )
            .on_conflict_do_update(
                index_elements=["identity_key"],
                set_={
                    "mac": mac,
                    "hostname": hostname,
                    "mdns_service_type": mdns_service_type,
                    "dhcp_vendor_class": dhcp_vendor_class,
                    "last_seen": seen_at,
                },
            )
        )

    await db.execute(stmt)
    await db.commit()

    if is_new_identity:
        db.add(
            SecurityAlert(
                device_id=None,
                type=SecurityAlertType.UNKNOWN_DEVICE,
                severity=SecurityStatus.WARNING,
                message="Unknown device joined the network",
            )
        )
        await db.commit()

        await event_bus.publish(
            "new_device",
            {"identity_key": identity_key, "mac": mac, "hostname": hostname},
        )


async def upsert_device_mac_history(
    db: AsyncSession,
    device_id: int,
    mac: str,
    seen_at: datetime,
) -> None:
    """Upsert a DeviceMacHistory row for (device_id, mac) — closes the
    MAC-rotation blind spot (03-RESEARCH.md Pitfall 1).

    Dialect-aware upsert, same pg_insert/sqlite_insert .on_conflict_do_update()
    pattern as upsert_discovered_identity above — do not introduce a third
    upsert style into this file. If a row for this (device_id, mac) pair
    already exists, updates its last_seen; otherwise inserts a new row with
    first_seen=last_seen=seen_at.
    """
    dialect_name = db.bind.dialect.name if db.bind is not None else db.get_bind().dialect.name

    if dialect_name == "postgresql":
        stmt = (
            pg_insert(DeviceMacHistory)
            .values(device_id=device_id, mac=mac, first_seen=seen_at, last_seen=seen_at)
            .on_conflict_do_update(
                index_elements=[DeviceMacHistory.device_id, DeviceMacHistory.mac],
                set_={"last_seen": seen_at},
            )
        )
    else:
        stmt = (
            sqlite_insert(DeviceMacHistory)
            .values(device_id=device_id, mac=mac, first_seen=seen_at, last_seen=seen_at)
            .on_conflict_do_update(
                index_elements=["device_id", "mac"],
                set_={"last_seen": seen_at},
            )
        )

    await db.execute(stmt)
    await db.commit()


async def record_observation(
    db: AsyncSession,
    observation: Observation,
    resolver: "IdentityResolver | None" = None,
) -> None:
    """Resolve an observation's identity key and persist it.

    Pitfall 2: if a registered Device row already exists for this MAC, the
    observation updates that row's identity_key/last_known_mac/last_seen in
    place instead of also writing a DiscoveredIdentity row — this prevents a
    registered device's hostname/MAC change from spawning a phantom unknown
    card. This fast path only applies when observation.mac is a real,
    device-specific MAC: a placeholder-MAC observation (CR-05) skips the
    Device-branch lookup entirely, since the placeholder is shared across
    every hostname-bearing mDNS observation and must never be used to match
    an existing Device by last_known_mac — doing so would let any mDNS
    observation hijack any other registered device that happens to also
    carry the shared placeholder.
    """
    resolver = resolver or HostnameFallbackResolver()
    identity_key = resolver.resolve(observation)

    if observation.mac == MDNS_PLACEHOLDER_MAC:
        await upsert_discovered_identity(
            db,
            identity_key=identity_key,
            mac=observation.mac,
            hostname=observation.hostname,
            seen_at=observation.observed_at,
            mdns_service_type=observation.mdns_service_type,
            dhcp_vendor_class=observation.dhcp_vendor_class,
        )
        return

    result = await db.execute(select(Device).where(Device.last_known_mac == observation.mac))
    device = result.scalar_one_or_none()

    if device is not None:
        device.identity_key = identity_key
        device.last_known_mac = observation.mac
        device.last_seen = observation.observed_at
        await db.commit()
        await upsert_device_mac_history(db, device.id, observation.mac, observation.observed_at)
        return

    await upsert_discovered_identity(
        db,
        identity_key=identity_key,
        mac=observation.mac,
        hostname=observation.hostname,
        seen_at=observation.observed_at,
        mdns_service_type=observation.mdns_service_type,
        dhcp_vendor_class=observation.dhcp_vendor_class,
    )
