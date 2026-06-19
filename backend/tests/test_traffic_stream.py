from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from src.models.bandwidth import BandwidthMetric
from src.models.traffic_flow import TrafficFlow


def _rollup_payload() -> dict:
    return {
        "interval_start": "2026-06-19T12:00:00Z",
        "interval_end": "2026-06-19T12:00:07Z",
        "flows": [
            {
                "src_mac": "aa:bb:cc:dd:ee:ff",
                "dst_ip": "93.184.216.34",
                "dst_port": 443,
                "protocol": 6,
                "bytes": 1500,
                "dst_hostname": "example.com",
            },
            {
                "src_mac": "aa:bb:cc:dd:ee:ff",
                "dst_ip": "93.184.216.35",
                "dst_port": 443,
                "protocol": 6,
                "bytes": 500,
                "dst_hostname": "other.example.com",
            },
            {
                "src_mac": "11:22:33:44:55:66",
                "dst_ip": "8.8.8.8",
                "dst_port": 53,
                "protocol": 17,
                "bytes": 100,
                "dst_hostname": None,
            },
        ],
    }


async def test_traffic_ingest_accepts_rollup_from_loopback(client):
    """POST /api/capture/traffic from loopback (test client default) returns
    201 with {"ok": True}."""
    response = await client.post("/api/capture/traffic", json=_rollup_payload())
    assert response.status_code == 201
    assert response.json() == {"ok": True}


async def test_traffic_ingest_writes_flow_and_bandwidth_rows(client, test_db):
    """After the POST, one TrafficFlow row exists per distinct 5-tuple, and
    one BandwidthMetric row exists per distinct src_mac with bytes_tx summed
    from that mac's flows (bytes_rx stays 0.0 — known v1 limitation)."""
    response = await client.post("/api/capture/traffic", json=_rollup_payload())
    assert response.status_code == 201

    session_maker = async_sessionmaker(test_db, expire_on_commit=False)
    async with session_maker() as db:
        flow_rows = (await db.execute(select(TrafficFlow))).scalars().all()
        assert len(flow_rows) == 3

        bandwidth_rows = (await db.execute(select(BandwidthMetric))).scalars().all()
        assert len(bandwidth_rows) == 2

        by_mac = {row.device_mac: row for row in bandwidth_rows}
        assert by_mac["aa:bb:cc:dd:ee:ff"].bytes_tx == 2000
        assert by_mac["aa:bb:cc:dd:ee:ff"].bytes_rx == 0.0
        assert by_mac["11:22:33:44:55:66"].bytes_tx == 100


async def test_traffic_ingest_rejects_non_loopback(test_db):
    """POST /api/capture/traffic from a non-loopback peer address returns 403,
    matching the existing /arp /dhcp /mdns trust boundary."""
    from httpx import ASGITransport, AsyncClient
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
            response = await non_loopback_client.post("/api/capture/traffic", json=_rollup_payload())
            assert response.status_code == 403
    finally:
        app.dependency_overrides.clear()
