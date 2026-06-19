async def test_destinations_groups_subdomains_under_registered_domain(seeded_traffic_db):
    """GET /api/traffic/devices/{device_id}/destinations with seeded
    TrafficFlow rows for www.netflix.com and api.netflix.com returns a
    single grouped entry for "netflix.com" with bytes summed from both raw
    hostnames (proves D-10 grouping is applied at serialization, not
    capture, time)."""
    client, device_id = seeded_traffic_db

    response = await client.get(f"/api/traffic/devices/{device_id}/destinations")
    assert response.status_code == 200
    body = response.json()
    by_label = {entry["label"]: entry["bytes"] for entry in body["destinations"]}
    assert by_label["netflix.com"] == 1000.0 + 500.0


async def test_destinations_falls_back_to_raw_ip_when_no_hostname(seeded_traffic_db):
    """A flow with no dst_hostname falls back to the raw dst_ip as its
    label (D-09). Also proves destinations resolve the device's full MAC
    history, since this flow was written under the device's old (rotated)
    MAC."""
    client, device_id = seeded_traffic_db

    response = await client.get(f"/api/traffic/devices/{device_id}/destinations")
    assert response.status_code == 200
    body = response.json()
    labels = {entry["label"] for entry in body["destinations"]}
    assert "8.8.8.8" in labels
