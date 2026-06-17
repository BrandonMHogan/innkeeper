from httpx import ASGITransport, AsyncClient


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
