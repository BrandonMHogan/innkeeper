from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from src.models.device import Device, DeviceType
from src.models.pending_scan_request import PendingScanRequest
from src.models.port_scan_result import PortScanResult
from src.models.security_alert import SecurityAlert, SecurityAlertType
from src.services.security_status import SecurityStatus


async def _login(client):
    await client.post("/api/auth/setup", json={"password": "correct-password"})
    login_response = await client.post("/api/auth/login", json={"password": "correct-password"})
    assert login_response.status_code == 200


async def _seed_device(test_db, **overrides) -> int:
    session_maker = async_sessionmaker(test_db, expire_on_commit=False)
    async with session_maker() as db:
        device = Device(
            identity_key=overrides.get("identity_key", "host:registered-device"),
            name=overrides.get("name", "Registered Device"),
            owner=overrides.get("owner", "Brandon"),
            type=overrides.get("type", DeviceType.OTHER),
            trusted=overrides.get("trusted", False),
            last_known_mac=overrides.get("last_known_mac", "11:22:33:44:55:66"),
        )
        db.add(device)
        await db.commit()
        await db.refresh(device)
        return device.id


async def test_trigger_scan_creates_pending_request(client, test_db):
    await _login(client)
    device_id = await _seed_device(test_db)

    response = await client.post(f"/api/security/scan/{device_id}")
    assert response.status_code == 202

    session_maker = async_sessionmaker(test_db, expire_on_commit=False)
    async with session_maker() as db:
        rows = (await db.execute(select(PendingScanRequest))).scalars().all()
        assert len(rows) == 1
        assert rows[0].device_id == device_id
        assert rows[0].claimed_at is None


async def test_trigger_scan_nonexistent_device_404(client, test_db):
    await _login(client)
    response = await client.post("/api/security/scan/9999")
    assert response.status_code == 404


async def test_trigger_scan_requires_auth(client, test_db):
    response = await client.post("/api/security/scan/1")
    assert response.status_code == 401


async def test_list_alerts_only_unacknowledged(client, test_db):
    await _login(client)
    device_id = await _seed_device(test_db)

    session_maker = async_sessionmaker(test_db, expire_on_commit=False)
    async with session_maker() as db:
        db.add_all(
            [
                SecurityAlert(
                    device_id=device_id,
                    type=SecurityAlertType.UNEXPECTED_PORT,
                    severity=SecurityStatus.WARNING,
                    message="acked alert",
                    acknowledged=True,
                ),
                SecurityAlert(
                    device_id=device_id,
                    type=SecurityAlertType.MALICIOUS_IP,
                    severity=SecurityStatus.CRITICAL,
                    message="unacked alert",
                    acknowledged=False,
                ),
            ]
        )
        await db.commit()

    response = await client.get("/api/security/alerts")
    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert body[0]["message"] == "unacked alert"


async def test_ack_alert(client, test_db):
    await _login(client)
    device_id = await _seed_device(test_db)

    session_maker = async_sessionmaker(test_db, expire_on_commit=False)
    async with session_maker() as db:
        alert = SecurityAlert(
            device_id=device_id,
            type=SecurityAlertType.MALICIOUS_IP,
            severity=SecurityStatus.CRITICAL,
            message="needs ack",
        )
        db.add(alert)
        await db.commit()
        await db.refresh(alert)
        alert_id = alert.id

    response = await client.post(f"/api/security/alerts/{alert_id}/ack")
    assert response.status_code == 200

    list_response = await client.get("/api/security/alerts")
    assert list_response.json() == []


async def test_ack_alert_nonexistent_404(client, test_db):
    await _login(client)
    response = await client.post("/api/security/alerts/9999/ack")
    assert response.status_code == 404


async def test_ack_all_alerts(client, test_db):
    await _login(client)
    device_id = await _seed_device(test_db)

    session_maker = async_sessionmaker(test_db, expire_on_commit=False)
    async with session_maker() as db:
        db.add_all(
            [
                SecurityAlert(
                    device_id=device_id,
                    type=SecurityAlertType.MALICIOUS_IP,
                    severity=SecurityStatus.CRITICAL,
                    message="alert 1",
                ),
                SecurityAlert(
                    device_id=device_id,
                    type=SecurityAlertType.UNEXPECTED_PORT,
                    severity=SecurityStatus.WARNING,
                    message="alert 2",
                ),
            ]
        )
        await db.commit()

    response = await client.post("/api/security/alerts/ack-all")
    assert response.status_code == 200
    assert response.json() == {"acknowledged_count": 2}

    list_response = await client.get("/api/security/alerts")
    assert list_response.json() == []


async def test_get_scan_result_flags_ports(client, test_db):
    await _login(client)
    device_id = await _seed_device(test_db, type=DeviceType.ROUTER)

    session_maker = async_sessionmaker(test_db, expire_on_commit=False)
    async with session_maker() as db:
        db.add(
            PortScanResult(
                device_id=device_id,
                open_ports=[22, 23],
                scanned_at=datetime.now(timezone.utc),
            )
        )
        await db.commit()

    response = await client.get(f"/api/security/scan/{device_id}")
    assert response.status_code == 200
    body = response.json()
    assert body["scanned_at"] is not None
    ports_by_number = {p["port"]: p["flag"] for p in body["ports"]}
    assert ports_by_number[22] == "expected"
    assert ports_by_number[23] == "risky"


async def test_get_scan_result_never_scanned(client, test_db):
    await _login(client)
    device_id = await _seed_device(test_db)

    response = await client.get(f"/api/security/scan/{device_id}")
    assert response.status_code == 200
    assert response.json() == {"scanned_at": None, "ports": []}


async def test_get_scan_result_nonexistent_device_404(client, test_db):
    await _login(client)
    response = await client.get("/api/security/scan/9999")
    assert response.status_code == 404


async def test_get_scan_result_requires_auth(client, test_db):
    response = await client.get("/api/security/scan/1")
    assert response.status_code == 401
