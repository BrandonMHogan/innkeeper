from datetime import datetime, timedelta, timezone


async def test_device_bandwidth_sums_across_full_mac_history(seeded_traffic_db):
    """GET /api/modules/traffic/bandwidth/{device_id} returns a total that sums
    bytes across both MACs a device has ever used, not just its current
    last_known_mac (proves the MAC-rotation fix, Pitfall 1/Open Question 1)."""
    client, device_id = seeded_traffic_db

    now = datetime.now(timezone.utc)
    start = now - timedelta(days=20)
    end = now
    response = await client.get(
        f"/api/modules/traffic/bandwidth/{device_id}",
        params={"start": start.isoformat(), "end": end.isoformat()},
    )
    assert response.status_code == 200
    body = response.json()
    total_tx = sum(point["bytes_tx"] for point in body["points"])
    total_rx = sum(point["bytes_rx"] for point in body["points"])
    # Within the 20-day window: old_mac row at -8d (400 tx), current_mac
    # rows at -2d (600 tx) and -1h (800 tx). The -400d old_mac row is
    # outside the window.
    assert total_tx == 400.0 + 600.0 + 800.0
    assert total_rx == 300.0 + 500.0 + 700.0


async def test_device_bandwidth_supports_arbitrary_wide_time_range(seeded_traffic_db):
    """GET /api/modules/traffic/bandwidth/{device_id} with a year-wide range returns
    successfully with no error and no implicit truncation (TRAF-02)."""
    client, device_id = seeded_traffic_db

    now = datetime.now(timezone.utc)
    start = now - timedelta(days=500)
    end = now
    response = await client.get(
        f"/api/modules/traffic/bandwidth/{device_id}",
        params={"start": start.isoformat(), "end": end.isoformat()},
    )
    assert response.status_code == 200
    body = response.json()
    # All four seeded BandwidthMetric rows (including the -400d one) fall
    # within this year-wide range — proves no implicit truncation.
    assert len(body["points"]) == 4


async def test_device_bandwidth_404_for_missing_device(client):
    from tests.conftest import _login

    await _login(client)
    now = datetime.now(timezone.utc)
    response = await client.get(
        "/api/modules/traffic/bandwidth/999999",
        params={"start": (now - timedelta(days=1)).isoformat(), "end": now.isoformat()},
    )
    assert response.status_code == 404
