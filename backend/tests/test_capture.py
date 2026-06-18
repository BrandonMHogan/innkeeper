from httpx import ASGITransport, AsyncClient

import src.routes.capture as capture_module
from src.routes.capture import _detect_default_gateway


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

    from src.models.discovered_identity import DiscoveredIdentity

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

    from src.models.discovered_identity import DiscoveredIdentity

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

    from src.models.discovered_identity import DiscoveredIdentity

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
