from datetime import datetime

from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from src.models.device import Device, DeviceType
from src.models.discovered_identity import DiscoveredIdentity
from src.services.identity_resolver import MDNS_PLACEHOLDER_MAC


async def _login(client):
    await client.post("/api/auth/setup", json={"password": "correct-password"})
    login_response = await client.post("/api/auth/login", json={"password": "correct-password"})
    assert login_response.status_code == 200


async def _seed_identity(test_db, **overrides) -> int:
    session_maker = async_sessionmaker(test_db, expire_on_commit=False)
    async with session_maker() as db:
        identity = DiscoveredIdentity(
            identity_key=overrides.get("identity_key", "host:unknown-device"),
            mac=overrides.get("mac", "aa:bb:cc:dd:ee:ff"),
            hostname=overrides.get("hostname", "unknown-device"),
            first_seen=overrides.get("first_seen", datetime(2026, 1, 1)),
            last_seen=overrides.get("last_seen", datetime(2026, 1, 2)),
        )
        db.add(identity)
        await db.commit()
        await db.refresh(identity)
        return identity.id


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


async def test_register_device(client, test_db):
    await _login(client)
    identity_id = await _seed_identity(test_db)

    response = await client.post(
        "/api/devices/",
        json={
            "identity_id": identity_id,
            "name": "Brandon's MacBook",
            "owner": "Brandon",
            "type": "laptop",
            "trusted": True,
        },
    )
    assert response.status_code == 201

    session_maker = async_sessionmaker(test_db, expire_on_commit=False)
    async with session_maker() as db:
        devices = (await db.execute(select(Device))).scalars().all()
        assert len(devices) == 1
        assert devices[0].identity_key == "host:unknown-device"

        identities = (await db.execute(select(DiscoveredIdentity))).scalars().all()
        assert len(identities) == 0


async def test_register_device_rejects_invalid_type(client, test_db):
    await _login(client)
    identity_id = await _seed_identity(test_db)

    response = await client.post(
        "/api/devices/",
        json={
            "identity_id": identity_id,
            "name": "Brandon's MacBook",
            "owner": "Brandon",
            "type": "not-a-real-type",
            "trusted": True,
        },
    )
    assert response.status_code == 422


async def test_merge_device(client, test_db):
    await _login(client)
    device_id = await _seed_device(test_db)
    identity_id = await _seed_identity(test_db, mac="99:88:77:66:55:44")

    response = await client.post(
        f"/api/devices/{identity_id}/merge",
        json={"target_device_id": device_id},
    )
    assert response.status_code == 200

    session_maker = async_sessionmaker(test_db, expire_on_commit=False)
    async with session_maker() as db:
        device = (await db.execute(select(Device).where(Device.id == device_id))).scalar_one()
        assert device.last_known_mac == "99:88:77:66:55:44"

        identities = (await db.execute(select(DiscoveredIdentity))).scalars().all()
        assert len(identities) == 0


async def test_register_device_with_placeholder_mac_does_not_persist_placeholder(client, test_db):
    await _login(client)
    identity_id = await _seed_identity(
        test_db,
        mac=MDNS_PLACEHOLDER_MAC,
        hostname="mdns-only-speaker",
        identity_key="host:mdns-only-speaker",
    )

    response = await client.post(
        "/api/devices/",
        json={
            "identity_id": identity_id,
            "name": "MDNS Only Speaker",
            "owner": "Brandon",
            "type": "other",
            "trusted": False,
        },
    )
    assert response.status_code == 201

    session_maker = async_sessionmaker(test_db, expire_on_commit=False)
    async with session_maker() as db:
        devices = (await db.execute(select(Device))).scalars().all()
        assert len(devices) == 1
        assert devices[0].last_known_mac is None


async def test_merge_device_with_placeholder_mac_does_not_overwrite_last_known_mac(client, test_db):
    await _login(client)
    device_id = await _seed_device(test_db, last_known_mac="11:22:33:44:55:66")
    identity_id = await _seed_identity(
        test_db, mac=MDNS_PLACEHOLDER_MAC, hostname="mdns-only-thing"
    )

    response = await client.post(
        f"/api/devices/{identity_id}/merge",
        json={"target_device_id": device_id},
    )
    assert response.status_code == 200

    session_maker = async_sessionmaker(test_db, expire_on_commit=False)
    async with session_maker() as db:
        device = (await db.execute(select(Device).where(Device.id == device_id))).scalar_one()
        assert device.last_known_mac == "11:22:33:44:55:66"


async def test_unknown_device_listed(client, test_db):
    await _login(client)
    await _seed_identity(test_db)

    response = await client.get("/api/devices/")
    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert body[0]["unknown"] is True


async def test_unknown_identity_includes_inference_payload(client, test_db):
    await _login(client)
    await _seed_identity(test_db, mac="B8:E9:37:00:00:01")  # Sonos OUI
    await _seed_device(test_db)

    response = await client.get("/api/devices/")
    assert response.status_code == 200
    body = response.json()

    unknown = next(d for d in body if d["unknown"] is True)
    assert unknown["vendor"] == "Sonos"
    assert "type_guess" in unknown
    assert "name_guess" in unknown
    assert "raw_signals" in unknown
    assert set(unknown["raw_signals"].keys()) == {"mac", "raw_vendor", "mdns_service_type", "dhcp_vendor_class"}

    registered = next(d for d in body if d["unknown"] is False)
    assert "vendor" not in registered
    assert "type_guess" not in registered
    assert "name_guess" not in registered
    assert "raw_signals" not in registered


async def test_devices_requires_auth(client):
    response = await client.get("/api/devices/")
    assert response.status_code == 401


async def test_list_devices_canonical_path_no_redirect(client, test_db):
    """GET /api/devices/ (canonical, trailing slash) returns 200 with no
    redirect; GET /api/devices (no trailing slash, the old broken frontend
    literal) still returns 307 to the exact canonical Location (CR-02)."""
    from src.database import get_db
    from src.main import app

    session_maker = async_sessionmaker(test_db, expire_on_commit=False)

    async def override_get_db():
        async with session_maker() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(
            transport=transport, base_url="http://test", follow_redirects=False
        ) as raw_client:
            await raw_client.post("/api/auth/setup", json={"password": "correct-password"})
            login_response = await raw_client.post(
                "/api/auth/login", json={"password": "correct-password"}
            )
            assert login_response.status_code == 200

            canonical_response = await raw_client.get("/api/devices/")
            assert canonical_response.status_code == 200

            redirect_response = await raw_client.get("/api/devices")
            assert redirect_response.status_code == 307
            assert redirect_response.headers["location"] == "http://test/api/devices/"
    finally:
        app.dependency_overrides.clear()
