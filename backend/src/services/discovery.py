from datetime import datetime

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.device import Device
from src.models.discovered_identity import DiscoveredIdentity
from src.services.identity_resolver import HostnameFallbackResolver, IdentityResolver, Observation


async def upsert_discovered_identity(
    db: AsyncSession,
    identity_key: str,
    mac: str,
    hostname: str | None,
    seen_at: datetime,
) -> None:
    """Dialect-aware upsert avoiding the select-then-insert race (Pitfall 5).

    Postgres (production) uses pg_insert().on_conflict_do_update(); SQLite
    (the in-memory test fixture) uses the equivalent sqlite_insert() path —
    both support the same ON CONFLICT DO UPDATE semantics in SQLAlchemy 2.0.
    """
    dialect_name = db.bind.dialect.name if db.bind is not None else db.get_bind().dialect.name

    if dialect_name == "postgresql":
        stmt = (
            pg_insert(DiscoveredIdentity)
            .values(
                identity_key=identity_key,
                mac=mac,
                hostname=hostname,
                first_seen=seen_at,
                last_seen=seen_at,
            )
            .on_conflict_do_update(
                index_elements=[DiscoveredIdentity.identity_key],
                set_={"mac": mac, "hostname": hostname, "last_seen": seen_at},
            )
        )
    else:
        stmt = (
            sqlite_insert(DiscoveredIdentity)
            .values(
                identity_key=identity_key,
                mac=mac,
                hostname=hostname,
                first_seen=seen_at,
                last_seen=seen_at,
            )
            .on_conflict_do_update(
                index_elements=["identity_key"],
                set_={"mac": mac, "hostname": hostname, "last_seen": seen_at},
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
    card.
    """
    resolver = resolver or HostnameFallbackResolver()
    identity_key = resolver.resolve(observation)

    result = await db.execute(select(Device).where(Device.last_known_mac == observation.mac))
    device = result.scalar_one_or_none()

    if device is not None:
        device.identity_key = identity_key
        device.last_known_mac = observation.mac
        device.last_seen = observation.observed_at
        await db.commit()
        return

    await upsert_discovered_identity(
        db,
        identity_key=identity_key,
        mac=observation.mac,
        hostname=observation.hostname,
        seen_at=observation.observed_at,
    )
