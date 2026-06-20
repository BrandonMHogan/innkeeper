import os

os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
os.environ.setdefault("SESSION_SECRET", "test-secret-not-for-production")

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from src.models.base import Base

# Every model module must be imported somewhere before Base.metadata.create_all
# runs, or SQLAlchemy never registers its table — models only reachable via
# an indirect import chain (e.g. through src.main) would silently vanish from
# create_all if a test exercises test_db without ever importing src.main
# first. Import them all explicitly here so test_db is self-sufficient.
from src.models import (  # noqa: F401
    app_settings,
    arp_event,
    bandwidth,
    device,
    device_mac_history,
    dhcp_event,
    discovered_identity,
    mdns_event,
    pending_scan_request,
    port_scan_result,
    security_alert,
    traffic_flow,
)


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


async def _login(client):
    await client.post("/api/auth/setup", json={"password": "correct-password"})
    login_response = await client.post("/api/auth/login", json={"password": "correct-password"})
    assert login_response.status_code == 200


@pytest.fixture
async def seeded_traffic_db(test_db, client):
    """Extends test_db with a Device that has rotated through two MACs
    (DeviceMacHistory rows for both), plus BandwidthMetric/TrafficFlow rows
    written under both MACs across a synthetic time range — used by
    test_bandwidth_query.py, test_traffic_destinations.py, and
    test_bandwidth_aggregates.py to prove MAC-rotation-aware aggregation
    (03-RESEARCH.md Pitfall 1 / Open Question 1) and arbitrary time-range
    correctness (TRAF-02).

    Yields (client, device_id) — client is an already-authenticated
    AsyncClient (get_db already overridden to test_db, session cookie set
    via the same _login helper test_devices.py uses); device_id is the
    seeded Device's primary key, needed by tests to call the device-scoped
    query routes.
    """
    from datetime import datetime, timedelta, timezone

    from src.models.bandwidth import BandwidthMetric
    from src.models.device import Device, DeviceType
    from src.models.device_mac_history import DeviceMacHistory
    from src.models.traffic_flow import TrafficFlow

    session_maker = async_sessionmaker(test_db, expire_on_commit=False)
    now = datetime.now(timezone.utc)
    old_mac = "11:11:11:11:11:11"
    current_mac = "22:22:22:22:22:22"

    async with session_maker() as db:
        device = Device(
            identity_key="host:rotated-device",
            name="Rotated Device",
            type=DeviceType.PHONE,
            last_known_mac=current_mac,
        )
        db.add(device)
        await db.flush()

        db.add_all(
            [
                DeviceMacHistory(device_id=device.id, mac=old_mac, first_seen=now - timedelta(days=10), last_seen=now - timedelta(days=5)),
                DeviceMacHistory(device_id=device.id, mac=current_mac, first_seen=now - timedelta(days=5), last_seen=now),
            ]
        )

        # BandwidthMetric rows under both MACs, spread across a year-wide
        # synthetic time range (proves "any time range" / TRAF-02).
        db.add_all(
            [
                BandwidthMetric(time=now - timedelta(days=400), device_mac=old_mac, bytes_rx=100.0, bytes_tx=200.0),
                BandwidthMetric(time=now - timedelta(days=8), device_mac=old_mac, bytes_rx=300.0, bytes_tx=400.0),
                BandwidthMetric(time=now - timedelta(days=2), device_mac=current_mac, bytes_rx=500.0, bytes_tx=600.0),
                BandwidthMetric(time=now - timedelta(hours=1), device_mac=current_mac, bytes_rx=700.0, bytes_tx=800.0),
            ]
        )

        # TrafficFlow rows for destination-grouping tests (D-10): two raw
        # hostnames under the same registered domain, both under the
        # current MAC.
        db.add_all(
            [
                TrafficFlow(
                    time=now - timedelta(hours=1),
                    device_mac=current_mac,
                    dst_ip="93.184.216.34",
                    dst_port=443,
                    protocol=6,
                    bytes=1000.0,
                    dst_hostname="www.netflix.com",
                ),
                TrafficFlow(
                    time=now - timedelta(hours=2),
                    device_mac=current_mac,
                    dst_ip="93.184.216.35",
                    dst_port=443,
                    protocol=6,
                    bytes=500.0,
                    dst_hostname="api.netflix.com",
                ),
                TrafficFlow(
                    time=now - timedelta(days=6),
                    device_mac=old_mac,
                    dst_ip="8.8.8.8",
                    dst_port=53,
                    protocol=17,
                    bytes=50.0,
                    dst_hostname=None,
                ),
            ]
        )

        await db.commit()
        device_id = device.id

    await _login(client)
    yield client, device_id
