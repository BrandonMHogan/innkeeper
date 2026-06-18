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
