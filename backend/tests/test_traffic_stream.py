import json
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from src.models.bandwidth import BandwidthMetric
from src.modules.device_identity.models import Device, DeviceType
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


async def test_traffic_ingest_coerces_null_dst_port_to_zero(client, test_db):
    """A flow with dst_port=None (e.g. ICMP, which has no port) must not hit
    traffic_flows' NOT NULL PK constraint on dst_port — the ingest route
    coerces None to the 0 sentinel before persisting (live-traffic regression:
    real ICMP packets through capture's traffic_sniff.py surfaced this as a
    Postgres IntegrityError before the fix)."""
    payload = {
        "interval_start": "2026-06-19T12:00:00Z",
        "interval_end": "2026-06-19T12:00:07Z",
        "flows": [
            {
                "src_mac": "52:55:55:ba:0d:04",
                "dst_ip": "151.101.0.223",
                "dst_port": None,
                "protocol": 1,
                "bytes": 118,
                "dst_hostname": None,
            }
        ],
    }
    response = await client.post("/api/capture/traffic", json=payload)
    assert response.status_code == 201

    session_maker = async_sessionmaker(test_db, expire_on_commit=False)
    async with session_maker() as db:
        flow_rows = (await db.execute(select(TrafficFlow))).scalars().all()
        assert len(flow_rows) == 1
        assert flow_rows[0].dst_port == 0
        assert flow_rows[0].protocol == 1


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


async def test_compute_snapshot_ranks_top_talkers_descending_by_bytes(test_db):
    """_compute_snapshot's top_talkers list is sorted descending by summed
    bytes over the rolling window."""
    from src.services.traffic_broadcaster import _compute_snapshot

    session_maker = async_sessionmaker(test_db, expire_on_commit=False)
    now = datetime.now(timezone.utc)
    async with session_maker() as db:
        device_low = Device(
            identity_key="host:low",
            name="Low Talker",
            type=DeviceType.LAPTOP,
            last_known_mac="aa:aa:aa:aa:aa:aa",
        )
        device_high = Device(
            identity_key="host:high",
            name="High Talker",
            type=DeviceType.LAPTOP,
            last_known_mac="bb:bb:bb:bb:bb:bb",
        )
        db.add_all([device_low, device_high])
        await db.flush()

        db.add(TrafficFlow(time=now, device_mac="aa:aa:aa:aa:aa:aa", dst_ip="1.1.1.1", dst_port=443, protocol=6, bytes=100))
        db.add(TrafficFlow(time=now, device_mac="bb:bb:bb:bb:bb:bb", dst_ip="2.2.2.2", dst_port=443, protocol=6, bytes=900))
        await db.commit()

        snapshot = await _compute_snapshot(db)
        macs_in_order = [talker["device_name"] for talker in snapshot["top_talkers"]]
        assert macs_in_order == ["High Talker", "Low Talker"]


async def test_compute_snapshot_excludes_stale_rows_outside_rolling_window(test_db):
    """A TrafficFlow row older than the 5-minute rolling window is excluded
    from the top_talkers ranking (proves the rolling window, D-12)."""
    from src.services.traffic_broadcaster import _compute_snapshot

    session_maker = async_sessionmaker(test_db, expire_on_commit=False)
    now = datetime.now(timezone.utc)
    stale_time = now - timedelta(minutes=10)
    async with session_maker() as db:
        device = Device(
            identity_key="host:onlyone",
            name="Only Device",
            type=DeviceType.LAPTOP,
            last_known_mac="cc:cc:cc:cc:cc:cc",
        )
        db.add(device)
        await db.flush()

        db.add(TrafficFlow(time=stale_time, device_mac="cc:cc:cc:cc:cc:cc", dst_ip="3.3.3.3", dst_port=443, protocol=6, bytes=99999))
        db.add(TrafficFlow(time=now, device_mac="cc:cc:cc:cc:cc:cc", dst_ip="4.4.4.4", dst_port=443, protocol=6, bytes=50))
        await db.commit()

        snapshot = await _compute_snapshot(db)
        assert len(snapshot["top_talkers"]) == 1
        assert snapshot["top_talkers"][0]["bytes"] == 50


async def test_update_snapshot_loop_survives_transient_compute_error(monkeypatch):
    """update_snapshot_loop must not die for the process lifetime if a single
    tick's _compute_snapshot raises (e.g. a transient DB error) — every SSE
    client's live feed depends on this loop running forever (code review
    finding, live-traffic regression class)."""
    import asyncio

    import src.services.traffic_broadcaster as broadcaster_module

    call_count = 0

    async def flaky_compute_snapshot(db):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise RuntimeError("transient DB error")
        return {"top_talkers": [], "active_connections": [], "computed_at": "now"}

    monkeypatch.setattr(broadcaster_module, "_compute_snapshot", flaky_compute_snapshot)

    class _FakeSession:
        async def __aenter__(self):
            return None

        async def __aexit__(self, *exc_info):
            return False

    def fake_session_factory():
        return _FakeSession()

    stop_event = asyncio.Event()

    async def stop_after_two_ticks():
        while call_count < 2:
            await asyncio.sleep(0.01)
        stop_event.set()

    await asyncio.gather(
        broadcaster_module.update_snapshot_loop(stop_event, fake_session_factory),
        stop_after_two_ticks(),
    )

    assert call_count == 2
    assert broadcaster_module.get_latest_snapshot() == {
        "top_talkers": [],
        "active_connections": [],
        "computed_at": "now",
    }


async def test_stream_event_generator_yields_one_snapshot_event(monkeypatch):
    """Calling the SSE route's event_generator function directly (mocking
    request.is_disconnected() to return True after the first iteration)
    yields exactly one {"event": "snapshot", ...} dict whose data field is
    valid JSON matching get_latest_snapshot()'s shape."""
    from src.routes.traffic import traffic_stream
    from src.services import traffic_broadcaster

    fake_snapshot = {"top_talkers": [], "active_connections": [], "computed_at": "2026-06-19T12:00:00Z"}
    monkeypatch.setattr(traffic_broadcaster, "_latest_snapshot", fake_snapshot)

    class FakeRequest:
        def __init__(self):
            self._calls = 0

        async def is_disconnected(self):
            self._calls += 1
            return self._calls > 1

    response = await traffic_stream(FakeRequest())
    events = []
    async for event in response.body_iterator:
        events.append(event)

    assert len(events) >= 1
    first = events[0]
    assert first["event"] == "snapshot"
    assert json.loads(first["data"]) == fake_snapshot
