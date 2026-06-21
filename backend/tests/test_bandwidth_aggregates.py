from datetime import datetime, timedelta, timezone

from sqlalchemy.ext.asyncio import async_sessionmaker

from src.modules.traffic.models import BandwidthMetric
from tests.conftest import _login


async def _seed_network_bandwidth(test_db):
    """Seeds raw BandwidthMetric rows across several days for two devices —
    used to verify network_bandwidth's daily/weekly/monthly views against a
    portable (SQLite-compatible) GROUP BY, since the real continuous
    aggregates only exist on Postgres/TimescaleDB."""
    session_maker = async_sessionmaker(test_db, expire_on_commit=False)
    now = datetime.now(timezone.utc)
    async with session_maker() as db:
        db.add_all(
            [
                BandwidthMetric(time=now - timedelta(days=1), device_mac="aa:aa:aa:aa:aa:aa", bytes_rx=10.0, bytes_tx=20.0),
                BandwidthMetric(time=now - timedelta(days=1, hours=2), device_mac="bb:bb:bb:bb:bb:bb", bytes_rx=30.0, bytes_tx=40.0),
                BandwidthMetric(time=now - timedelta(days=10), device_mac="aa:aa:aa:aa:aa:aa", bytes_rx=50.0, bytes_tx=60.0),
                BandwidthMetric(time=now - timedelta(days=40), device_mac="aa:aa:aa:aa:aa:aa", bytes_rx=70.0, bytes_tx=80.0),
            ]
        )
        await db.commit()


async def test_network_bandwidth_daily_view_matches_seeded_sums(client, test_db):
    await _seed_network_bandwidth(test_db)
    await _login(client)
    response = await client.get("/api/modules/traffic/bandwidth/network", params={"view": "daily"})
    assert response.status_code == 200
    body = response.json()
    total_tx = sum(bucket["bytes_tx"] for bucket in body["buckets"])
    assert total_tx == 20.0 + 40.0 + 60.0 + 80.0


async def test_network_bandwidth_weekly_view_matches_seeded_sums(client, test_db):
    await _seed_network_bandwidth(test_db)
    await _login(client)
    response = await client.get("/api/modules/traffic/bandwidth/network", params={"view": "weekly"})
    assert response.status_code == 200
    body = response.json()
    total_tx = sum(bucket["bytes_tx"] for bucket in body["buckets"])
    assert total_tx == 20.0 + 40.0 + 60.0 + 80.0


async def test_network_bandwidth_monthly_view_matches_seeded_sums(client, test_db):
    await _seed_network_bandwidth(test_db)
    await _login(client)
    response = await client.get("/api/modules/traffic/bandwidth/network", params={"view": "monthly"})
    assert response.status_code == 200
    body = response.json()
    total_tx = sum(bucket["bytes_tx"] for bucket in body["buckets"])
    assert total_tx == 20.0 + 40.0 + 60.0 + 80.0


async def test_network_bandwidth_rejects_invalid_view(client, test_db):
    await _login(client)
    response = await client.get("/api/modules/traffic/bandwidth/network", params={"view": "hourly"})
    assert response.status_code == 422
