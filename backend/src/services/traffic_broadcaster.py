"""D-13: single global SSE snapshot broadcaster.

One background task (update_snapshot_loop, started in main.py's lifespan)
periodically recomputes the full live snapshot (top talkers over a 5-minute
rolling window per D-12, plus raw active connections) into a single
module-level dict. Every connected SSE client reads from this shared state
on each tick rather than re-querying the DB per client — D-13's "one
channel, full snapshot, fan-out" design.
"""

import asyncio
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.device import Device
from src.models.traffic_flow import TrafficFlow

# D-12: rolling window for "top talkers" ranking — smooths bursty traffic
# so the ranking doesn't flicker/reorder on every update.
_ROLLING_WINDOW = timedelta(minutes=5)

# Caps the raw active_connections list to bound SSE payload size.
_MAX_ACTIVE_CONNECTIONS = 100

_latest_snapshot: dict = {}


def get_latest_snapshot() -> dict:
    return _latest_snapshot


async def _compute_snapshot(db: AsyncSession) -> dict:
    """Computes the live snapshot from current TrafficFlow rows within the
    D-12 rolling window.

    Device resolution uses Device.last_known_mac only (not the full MAC
    history) — acceptable here because the rolling window (5 minutes) is far
    shorter than any realistic MAC-rotation interval, unlike the historical
    queries in routes/traffic.py's bandwidth/destinations endpoints, which
    must resolve a device's full MAC history.
    """
    window_start = datetime.now(timezone.utc) - _ROLLING_WINDOW

    flow_rows = (
        (
            await db.execute(
                select(TrafficFlow).where(TrafficFlow.time >= window_start).order_by(TrafficFlow.time.desc())
            )
        )
        .scalars()
        .all()
    )

    device_rows = (await db.execute(select(Device))).scalars().all()
    device_by_mac = {d.last_known_mac: d for d in device_rows if d.last_known_mac}

    bytes_by_mac: dict[str, float] = {}
    for flow in flow_rows:
        bytes_by_mac[flow.device_mac] = bytes_by_mac.get(flow.device_mac, 0.0) + flow.bytes

    top_talkers = []
    for device_mac, summed_bytes in bytes_by_mac.items():
        device = device_by_mac.get(device_mac)
        top_talkers.append(
            {
                "device_id": device.id if device else None,
                "device_name": device.name if device else device_mac,
                "bytes": summed_bytes,
            }
        )
    top_talkers.sort(key=lambda talker: talker["bytes"], reverse=True)

    active_connections = [
        {
            "device_mac": flow.device_mac,
            "dst_ip": flow.dst_ip,
            "dst_hostname": flow.dst_hostname,
            "dst_port": flow.dst_port,
            "protocol": flow.protocol,
            "bytes": flow.bytes,
        }
        for flow in flow_rows[:_MAX_ACTIVE_CONNECTIONS]
    ]

    return {
        "top_talkers": top_talkers,
        "active_connections": active_connections,
        "computed_at": datetime.now(timezone.utc).isoformat(),
    }


async def update_snapshot_loop(stop_event: asyncio.Event, session_factory) -> None:
    """Background loop started in main.py's lifespan — recomputes the
    snapshot every 7s (D-11: same cadence as capture's FLUSH_INTERVAL)."""
    global _latest_snapshot
    while not stop_event.is_set():
        async with session_factory() as db:
            _latest_snapshot = await _compute_snapshot(db)
        try:
            await asyncio.wait_for(stop_event.wait(), timeout=7)
        except asyncio.TimeoutError:
            pass
