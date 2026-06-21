from datetime import datetime, timedelta, timezone

from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

import src.routes.capture as capture_module
from src.models.bandwidth import BandwidthMetric
from src.modules.device_identity.models import Device, DeviceType
from src.models.pending_scan_request import PendingScanRequest
from src.models.port_scan_result import PortScanResult
from src.models.security_alert import SecurityAlert, SecurityAlertType
from src.routes.capture import _detect_default_gateway
from src.services.security_status import SecurityStatus


async def test_arp_ingest(client):
    """POST /api/capture/arp from loopback (httpx test client default) succeeds."""
    payload = {
        "src_mac": "aa:bb:cc:dd:ee:ff",
        "src_ip": "192.168.1.50",
        "dst_ip": "192.168.1.1",
    }
    response = await client.post("/api/capture/arp", json=payload)
    assert response.status_code == 201


async def test_dhcp_ingest(client, test_db):
    """POST /api/capture/dhcp from loopback succeeds and creates a fused identity."""
    from sqlalchemy import select
    from sqlalchemy.ext.asyncio import async_sessionmaker

    from src.modules.device_identity.models import DiscoveredIdentity

    payload = {
        "src_mac": "aa:bb:cc:dd:ee:ff",
        "hostname": "my-laptop",
        "requested_ip": "192.168.1.50",
        "vendor_class_id": None,
    }
    response = await client.post("/api/capture/dhcp", json=payload)
    assert response.status_code == 201

    session_maker = async_sessionmaker(test_db, expire_on_commit=False)
    async with session_maker() as db:
        result = await db.execute(select(DiscoveredIdentity))
        rows = result.scalars().all()
        assert len(rows) == 1
        assert rows[0].identity_key == "host:my-laptop"


async def test_mdns_ingest(client):
    """POST /api/capture/mdns from loopback succeeds."""
    payload = {
        "hostname": "iphone.local",
        "addresses": "192.168.1.60",
        "service_type": "_airplay._tcp.local.",
    }
    response = await client.post("/api/capture/mdns", json=payload)
    assert response.status_code == 201


async def test_mdns_ingest_without_hostname_does_not_collide(client, test_db):
    """Two distinct hostname-less mDNS observations must not collapse into
    a single placeholder-MAC identity (CR-01 regression)."""
    from sqlalchemy import select
    from sqlalchemy.ext.asyncio import async_sessionmaker

    from src.modules.device_identity.models import DiscoveredIdentity

    payload_one = {
        "hostname": None,
        "addresses": "192.168.1.61",
        "service_type": "_airplay._tcp.local.",
    }
    payload_two = {
        "hostname": None,
        "addresses": "192.168.1.62",
        "service_type": "_googlecast._tcp.local.",
    }

    response_one = await client.post("/api/capture/mdns", json=payload_one)
    assert response_one.status_code == 201

    response_two = await client.post("/api/capture/mdns", json=payload_two)
    assert response_two.status_code == 201

    session_maker = async_sessionmaker(test_db, expire_on_commit=False)
    async with session_maker() as db:
        result = await db.execute(select(DiscoveredIdentity))
        rows = result.scalars().all()
        assert len(rows) == 0


async def test_mdns_ingest_with_hostname_still_resolves_identity(client, test_db):
    """A hostname-bearing mDNS observation still resolves to a fused
    hostname-keyed identity (guard clause does not regress the legitimate
    fusion path)."""
    from sqlalchemy import select
    from sqlalchemy.ext.asyncio import async_sessionmaker

    from src.modules.device_identity.models import DiscoveredIdentity

    payload = {
        "hostname": "iphone.local",
        "addresses": "192.168.1.60",
        "service_type": "_airplay._tcp.local.",
    }
    response = await client.post("/api/capture/mdns", json=payload)
    assert response.status_code == 201

    session_maker = async_sessionmaker(test_db, expire_on_commit=False)
    async with session_maker() as db:
        result = await db.execute(select(DiscoveredIdentity))
        rows = result.scalars().all()
        assert len(rows) == 1
        assert rows[0].identity_key == "host:iphone.local"


async def test_arp_ingest_rejects_non_loopback(test_db):
    """POST /api/capture/arp from a non-loopback peer address returns 403.

    Uses httpx's ASGITransport `client` tuple param to set a non-default
    peer address for this one test, exercising the real code path (no
    dependency override needed).
    """
    from sqlalchemy.ext.asyncio import async_sessionmaker

    from src.database import get_db
    from src.main import app

    session_maker = async_sessionmaker(test_db, expire_on_commit=False)

    async def override_get_db():
        async with session_maker() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db
    try:
        transport = ASGITransport(app=app, client=("203.0.113.5", 12345))
        async with AsyncClient(transport=transport, base_url="http://test") as non_loopback_client:
            payload = {
                "src_mac": "aa:bb:cc:dd:ee:ff",
                "src_ip": "192.168.1.50",
                "dst_ip": "192.168.1.1",
            }
            response = await non_loopback_client.post("/api/capture/arp", json=payload)
            assert response.status_code == 403
    finally:
        app.dependency_overrides.clear()


async def test_arp_ingest_accepts_detected_gateway(monkeypatch, test_db):
    """A request whose peer IP matches the detected gateway is trusted.

    Monkeypatches the module's _TRUSTED_HOSTS set directly to include a
    known fake gateway IP, then proves a request from that exact peer
    address is accepted — exercising the membership-check logic without
    depending on the real host's actual route table.
    """
    from sqlalchemy.ext.asyncio import async_sessionmaker

    from src.database import get_db
    from src.main import app

    fake_gateway = "10.99.0.1"
    monkeypatch.setattr(capture_module, "_TRUSTED_HOSTS", frozenset({"127.0.0.1", "::1", fake_gateway}))

    session_maker = async_sessionmaker(test_db, expire_on_commit=False)

    async def override_get_db():
        async with session_maker() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db
    try:
        transport = ASGITransport(app=app, client=(fake_gateway, 12345))
        async with AsyncClient(transport=transport, base_url="http://test") as gateway_client:
            payload = {
                "src_mac": "aa:bb:cc:dd:ee:ff",
                "src_ip": "192.168.1.50",
                "dst_ip": "192.168.1.1",
            }
            response = await gateway_client.post("/api/capture/arp", json=payload)
            assert response.status_code == 201
    finally:
        app.dependency_overrides.clear()


def test_detect_default_gateway_fails_safe_on_bad_path(monkeypatch):
    """_detect_default_gateway() returns None (never raises) when the
    configured /proc/net/route path doesn't exist."""
    monkeypatch.setattr(capture_module, "_PROC_NET_ROUTE_PATH", "/nonexistent/path/route")
    assert _detect_default_gateway() is None


async def _seed_device(test_db, **overrides) -> int:
    session_maker = async_sessionmaker(test_db, expire_on_commit=False)
    async with session_maker() as db:
        device = Device(
            identity_key=overrides.get("identity_key", "host:registered-device"),
            name=overrides.get("name", "Registered Device"),
            owner=overrides.get("owner", "Brandon"),
            type=overrides.get("type", DeviceType.ROUTER),
            trusted=overrides.get("trusted", False),
            last_known_mac=overrides.get("last_known_mac", "11:22:33:44:55:66"),
            last_known_ip=overrides.get("last_known_ip"),
        )
        db.add(device)
        await db.commit()
        await db.refresh(device)
        return device.id


async def _seed_daily_bandwidth(test_db, mac: str, daily_totals: list[float]):
    now = datetime.now(timezone.utc)
    session_maker = async_sessionmaker(test_db, expire_on_commit=False)
    async with session_maker() as db:
        num_days = len(daily_totals)
        for i, total in enumerate(daily_totals):
            days_ago = num_days - 1 - i
            db.add(
                BandwidthMetric(
                    time=now - timedelta(days=days_ago),
                    device_mac=mac,
                    bytes_rx=total / 2,
                    bytes_tx=total / 2,
                )
            )
        await db.commit()


async def test_scan_ingest_rejects_non_loopback(test_db):
    from sqlalchemy.ext.asyncio import async_sessionmaker

    from src.database import get_db
    from src.main import app

    device_id = await _seed_device(test_db)

    session_maker = async_sessionmaker(test_db, expire_on_commit=False)

    async def override_get_db():
        async with session_maker() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db
    try:
        transport = ASGITransport(app=app, client=("203.0.113.5", 12345))
        async with AsyncClient(transport=transport, base_url="http://test") as non_loopback_client:
            response = await non_loopback_client.post(
                "/api/capture/scan", json={"device_id": device_id, "open_ports": [22]}
            )
            assert response.status_code == 403
    finally:
        app.dependency_overrides.clear()


async def test_scan_ingest_flags_risky_port_and_sets_critical(client, test_db):
    device_id = await _seed_device(test_db, type=DeviceType.ROUTER)

    response = await client.post("/api/capture/scan", json={"device_id": device_id, "open_ports": [22, 23]})
    assert response.status_code == 201

    session_maker = async_sessionmaker(test_db, expire_on_commit=False)
    async with session_maker() as db:
        results = (await db.execute(select(PortScanResult))).scalars().all()
        assert len(results) == 1
        assert results[0].open_ports == [22, 23]

        device = (await db.execute(select(Device).where(Device.id == device_id))).scalar_one()
        assert device.last_scanned_at is not None
        assert device.security_status == "critical"


async def test_scan_ingest_clean_scan_keeps_status_elevated_with_old_unacked_alert(client, test_db):
    """WR-04: an old unacknowledged malicious-IP alert must keep
    Device.security_status elevated even when the newest scan result
    itself is completely clean (no risky/unexpected ports) — D-07's
    "each signal source independently contributes" precedent, exercised
    end-to-end through the real ingest_scan_result route rather than only
    via derive_status' own unit tests."""
    device_id = await _seed_device(test_db)

    session_maker = async_sessionmaker(test_db, expire_on_commit=False)
    async with session_maker() as db:
        db.add(
            SecurityAlert(
                device_id=device_id,
                type=SecurityAlertType.MALICIOUS_IP,
                severity=SecurityStatus.CRITICAL,
                message="Old device contacted a known-malicious address",
                acknowledged=False,
            )
        )
        await db.commit()

    response = await client.post("/api/capture/scan", json={"device_id": device_id, "open_ports": [80]})
    assert response.status_code == 201

    session_maker = async_sessionmaker(test_db, expire_on_commit=False)
    async with session_maker() as db:
        device = (await db.execute(select(Device).where(Device.id == device_id))).scalar_one()
        assert device.security_status == "critical"


async def test_scan_ingest_rejects_oversized_payload(client, test_db):
    device_id = await _seed_device(test_db)

    response = await client.post(
        "/api/capture/scan", json={"device_id": device_id, "open_ports": list(range(1, 1002))}
    )
    assert response.status_code == 413


async def test_pending_scans_only_returns_devices_with_known_ip(client, test_db):
    device_with_ip = await _seed_device(
        test_db, identity_key="host:with-ip", last_known_mac="aa:aa:aa:aa:aa:aa", last_known_ip="192.168.1.50"
    )
    device_without_ip = await _seed_device(
        test_db, identity_key="host:no-ip", last_known_mac="bb:bb:bb:bb:bb:bb", last_known_ip=None
    )

    session_maker = async_sessionmaker(test_db, expire_on_commit=False)
    async with session_maker() as db:
        db.add_all(
            [
                PendingScanRequest(device_id=device_with_ip),
                PendingScanRequest(device_id=device_without_ip),
            ]
        )
        await db.commit()

    response = await client.get("/api/capture/pending-scans")
    assert response.status_code == 200
    body = response.json()
    assert body["pending"] == [{"device_id": device_with_ip, "ip": "192.168.1.50"}]

    session_maker = async_sessionmaker(test_db, expire_on_commit=False)
    async with session_maker() as db:
        rows = (await db.execute(select(PendingScanRequest))).scalars().all()
        claimed = {r.device_id: r.claimed_at for r in rows}
        assert claimed[device_with_ip] is not None
        assert claimed[device_without_ip] is None


async def test_queue_daily_scans_creates_one_request_per_device_no_duplicates(client, test_db):
    device_id_1 = await _seed_device(test_db, identity_key="host:one", last_known_mac="aa:aa:aa:aa:aa:aa")
    device_id_2 = await _seed_device(test_db, identity_key="host:two", last_known_mac="bb:bb:bb:bb:bb:bb")

    response = await client.post("/api/capture/queue-daily-scans")
    assert response.status_code == 201
    assert response.json()["queued_count"] == 2

    response_two = await client.post("/api/capture/queue-daily-scans")
    assert response_two.status_code == 201
    assert response_two.json()["queued_count"] == 0

    session_maker = async_sessionmaker(test_db, expire_on_commit=False)
    async with session_maker() as db:
        rows = (await db.execute(select(PendingScanRequest))).scalars().all()
        assert len(rows) == 2
        assert {r.device_id for r in rows} == {device_id_1, device_id_2}


async def test_queue_daily_scans_rejects_non_loopback(test_db):
    from sqlalchemy.ext.asyncio import async_sessionmaker

    from src.database import get_db
    from src.main import app

    session_maker = async_sessionmaker(test_db, expire_on_commit=False)

    async def override_get_db():
        async with session_maker() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db
    try:
        transport = ASGITransport(app=app, client=("203.0.113.5", 12345))
        async with AsyncClient(transport=transport, base_url="http://test") as non_loopback_client:
            response = await non_loopback_client.post("/api/capture/queue-daily-scans")
            assert response.status_code == 403
    finally:
        app.dependency_overrides.clear()


async def test_arp_ingest_updates_device_last_known_ip(client, test_db):
    device_id = await _seed_device(test_db, last_known_mac="aa:bb:cc:dd:ee:ff", last_known_ip=None)

    payload = {
        "src_mac": "aa:bb:cc:dd:ee:ff",
        "src_ip": "192.168.1.77",
        "dst_ip": "192.168.1.1",
    }
    response = await client.post("/api/capture/arp", json=payload)
    assert response.status_code == 201

    session_maker = async_sessionmaker(test_db, expire_on_commit=False)
    async with session_maker() as db:
        device = (await db.execute(select(Device).where(Device.id == device_id))).scalar_one()
        assert device.last_known_ip == "192.168.1.77"


async def test_traffic_ingest_malicious_ip_creates_alert_and_critical_status(client, test_db, monkeypatch):
    device_id = await _seed_device(test_db, last_known_mac="aa:bb:cc:dd:ee:ff")

    class _FakeThreatIntel:
        def is_malicious(self, ip: str) -> bool:
            return ip == "198.51.100.99"

    monkeypatch.setattr(capture_module, "get_default_threat_intel_source", lambda: _FakeThreatIntel())

    payload = {
        "interval_start": datetime.now(timezone.utc).isoformat(),
        "interval_end": datetime.now(timezone.utc).isoformat(),
        "flows": [
            {
                "src_mac": "aa:bb:cc:dd:ee:ff",
                "dst_ip": "198.51.100.99",
                "dst_port": 443,
                "protocol": 6,
                "bytes": 1000,
                "dst_hostname": None,
            }
        ],
    }
    response = await client.post("/api/capture/traffic", json=payload)
    assert response.status_code == 201

    session_maker = async_sessionmaker(test_db, expire_on_commit=False)
    async with session_maker() as db:
        alerts = (
            (await db.execute(select(SecurityAlert).where(SecurityAlert.type == SecurityAlertType.MALICIOUS_IP)))
            .scalars()
            .all()
        )
        assert len(alerts) == 1
        assert alerts[0].device_id == device_id

        device = (await db.execute(select(Device).where(Device.id == device_id))).scalar_one()
        assert device.security_status == "critical"


async def test_queue_daily_scans_bandwidth_anomaly_creates_alert_and_warning_status(client, test_db):
    device_id = await _seed_device(test_db, last_known_mac="aa:bb:cc:dd:ee:ff")

    steady = [100.0] * 7
    spike = [1000.0]
    await _seed_daily_bandwidth(test_db, "aa:bb:cc:dd:ee:ff", steady + spike)

    response = await client.post("/api/capture/queue-daily-scans")
    assert response.status_code == 201

    session_maker = async_sessionmaker(test_db, expire_on_commit=False)
    async with session_maker() as db:
        alerts = (
            (
                await db.execute(
                    select(SecurityAlert).where(SecurityAlert.type == SecurityAlertType.SUSPICIOUS_TRAFFIC)
                )
            )
            .scalars()
            .all()
        )
        assert len(alerts) == 1
        assert alerts[0].device_id == device_id

        device = (await db.execute(select(Device).where(Device.id == device_id))).scalar_one()
        assert device.security_status == "warning"


async def test_queue_daily_scans_no_bandwidth_anomaly_no_alert(client, test_db):
    device_id = await _seed_device(test_db, last_known_mac="aa:bb:cc:dd:ee:ff")

    # Fewer than 7 distinct days — no anomaly evaluation possible.
    await _seed_daily_bandwidth(test_db, "aa:bb:cc:dd:ee:ff", [100.0, 100.0, 100.0])

    response = await client.post("/api/capture/queue-daily-scans")
    assert response.status_code == 201

    session_maker = async_sessionmaker(test_db, expire_on_commit=False)
    async with session_maker() as db:
        alerts = (
            (
                await db.execute(
                    select(SecurityAlert).where(SecurityAlert.type == SecurityAlertType.SUSPICIOUS_TRAFFIC)
                )
            )
            .scalars()
            .all()
        )
        assert len(alerts) == 0

        device = (await db.execute(select(Device).where(Device.id == device_id))).scalar_one()
        assert device.security_status != "warning"


async def test_queue_daily_scans_dedupes_suspicious_traffic_alert(client, test_db):
    await _seed_device(test_db, last_known_mac="aa:bb:cc:dd:ee:ff")

    steady = [100.0] * 7
    spike = [1000.0]
    await _seed_daily_bandwidth(test_db, "aa:bb:cc:dd:ee:ff", steady + spike)

    response_one = await client.post("/api/capture/queue-daily-scans")
    assert response_one.status_code == 201

    response_two = await client.post("/api/capture/queue-daily-scans")
    assert response_two.status_code == 201

    session_maker = async_sessionmaker(test_db, expire_on_commit=False)
    async with session_maker() as db:
        alerts = (
            (
                await db.execute(
                    select(SecurityAlert).where(SecurityAlert.type == SecurityAlertType.SUSPICIOUS_TRAFFIC)
                )
            )
            .scalars()
            .all()
        )
        assert len(alerts) == 1
