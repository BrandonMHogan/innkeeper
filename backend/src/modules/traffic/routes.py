"""GET /api/modules/traffic/* — SSE live feed (TRAF-01) and historical
bandwidth/destinations query routes (TRAF-02..04). Every route is gated
behind the existing session-cookie auth (Depends(require_auth)) per ASVS
V4/V12 plus Depends(require_module_enabled("traffic")) (T-05-12) — no new
auth surface is introduced (T-03-09: accepted, single-user/household threat
model).

Relocated from src/routes/traffic.py (Plan 04). The pre-retrofit inline
MAC-union helper is deleted entirely — every device-MAC resolution call
site goes directly through the constructor-injected DeviceLookupInterface's
lookup() (T-05-11), consuming the MAC-rotation-aware union exposed on
DeviceInfo.macs per Plan 03's documented contract (05-03-SUMMARY.md),
instead of querying Device/DeviceMacHistory directly.
"""

import asyncio
import json
from datetime import datetime, timezone
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from sse_starlette.sse import EventSourceResponse

from src.auth import require_auth
from src.database import get_db
from src.host.dependencies import require_module_enabled
from src.modules.device_identity.interfaces import DeviceLookupInterface
from src.modules.traffic.broadcaster import get_latest_snapshot
from src.modules.traffic.models import BandwidthMetric, TrafficFlow
from src.services.domain_grouping import registered_domain

router = APIRouter()

# T-03-10: hardcoded literal SQL identifiers selected only by a
# Literal-typed `view` parameter — FastAPI/Pydantic validates `view` against
# this exact set before the value ever reaches the SQL string, so no raw
# user input is ever interpolated into a query.
_CONTINUOUS_AGGREGATE_VIEWS = {
    "daily": "traffic.bandwidth_daily",
    "weekly": "traffic.bandwidth_weekly",
    "monthly": "traffic.bandwidth_monthly",
}

# Matches the bucket width used by each continuous aggregate's time_bucket()
# call in migrations/0001_initial.py — used for the SQLite-compatible
# fallback query (portable GROUP BY over raw bandwidth_metrics rows) when the
# continuous aggregates don't exist (e.g. the test fixture's SQLite dialect).
_VIEW_BUCKET_DAYS = {"daily": 1, "weekly": 7, "monthly": 30}

# Module-level accessor pair (mirrors devices/routes.py's
# set_device_identity()/get_device_identity() pattern, Plan 03) — the
# constructor-injected DeviceLookupInterface instance the ModuleLoader
# resolved at startup is wired into route handlers here, since it's resolved
# once at load() time, not per-request.
_device_lookup: DeviceLookupInterface | None = None


def set_device_lookup(instance: DeviceLookupInterface) -> None:
    """Called once by TrafficModule's constructor at ModuleLoader wiring
    time (D-08) — injects the resolved DeviceLookupInterface instance for
    every route handler in this file to use."""
    global _device_lookup
    _device_lookup = instance


def get_device_lookup() -> DeviceLookupInterface:
    if _device_lookup is None:
        raise RuntimeError("DeviceLookupInterface not wired — ModuleLoader must run before requests are served")
    return _device_lookup


@router.get("/stream")
async def traffic_stream(
    request: Request,
    _: None = Depends(require_auth),
    __: None = Depends(require_module_enabled("traffic")),
):
    """D-13: single global SSE channel — polls the shared in-memory
    snapshot (updated by broadcaster.update_snapshot_loop) every 1s,
    yielding a new event only when the snapshot has changed since the last
    tick sent to this client."""

    async def event_generator():
        last_sent = None
        while True:
            if await request.is_disconnected():
                break
            snapshot = get_latest_snapshot()
            if snapshot != last_sent:
                yield {"event": "snapshot", "data": json.dumps(snapshot)}
                last_sent = dict(snapshot)
            await asyncio.sleep(1)

    return EventSourceResponse(event_generator(), ping=15)


@router.get("/bandwidth/network")
async def network_bandwidth(
    view: Literal["daily", "weekly", "monthly"],
    _: None = Depends(require_auth),
    __: None = Depends(require_module_enabled("traffic")),
    db: AsyncSession = Depends(get_db),
):
    """TRAF-04: network-wide bandwidth totals as daily/weekly/monthly
    buckets. Reads the corresponding continuous aggregate
    (traffic.bandwidth_daily/weekly/monthly) on Postgres; falls back to an
    equivalent portable GROUP BY over raw bandwidth_metrics rows on any
    other dialect (e.g. SQLite in tests, where the materialized
    continuous-aggregate views don't exist).

    Declared before /bandwidth/{device_id} — FastAPI matches routes in
    declaration order, and a literal path segment must be registered ahead
    of a sibling path-parameter route or "/bandwidth/network" would be
    captured by {device_id} (with "network" failing int parsing).
    """
    dialect_name = db.bind.dialect.name

    if dialect_name == "postgresql":
        view_table = _CONTINUOUS_AGGREGATE_VIEWS[view]
        result = await db.execute(
            text(f"SELECT bucket, sum(bytes_rx) AS bytes_rx, sum(bytes_tx) AS bytes_tx FROM {view_table} GROUP BY bucket ORDER BY bucket")
        )
        buckets = [{"bucket": row.bucket, "bytes_rx": row.bytes_rx, "bytes_tx": row.bytes_tx} for row in result]
        return {"view": view, "buckets": buckets}

    # Non-Postgres fallback (SQLite test fixture): bucket raw rows in
    # Python by a fixed-width time delta, mirroring each cagg's time_bucket
    # width (1 day / 1 week / 1 month-as-30-days).
    rows = (await db.execute(select(BandwidthMetric))).scalars().all()
    bucket_days = _VIEW_BUCKET_DAYS[view]
    bucket_totals: dict[datetime, dict[str, float]] = {}
    for row in rows:
        epoch_days = row.time.timestamp() / 86400
        bucket_index = int(epoch_days // bucket_days)
        bucket_key = bucket_index
        if bucket_key not in bucket_totals:
            bucket_totals[bucket_key] = {"bytes_rx": 0.0, "bytes_tx": 0.0}
        bucket_totals[bucket_key]["bytes_rx"] += row.bytes_rx
        bucket_totals[bucket_key]["bytes_tx"] += row.bytes_tx

    buckets = [
        {
            "bucket": datetime.fromtimestamp(bucket_index * bucket_days * 86400, tz=timezone.utc),
            "bytes_rx": totals["bytes_rx"],
            "bytes_tx": totals["bytes_tx"],
        }
        for bucket_index, totals in sorted(bucket_totals.items())
    ]
    return {"view": view, "buckets": buckets}


@router.get("/bandwidth/{device_id}")
async def device_bandwidth(
    device_id: int,
    start: datetime,
    end: datetime,
    _: None = Depends(require_auth),
    __: None = Depends(require_module_enabled("traffic")),
    db: AsyncSession = Depends(get_db),
):
    """TRAF-02: historical bandwidth for a device over any time range,
    aggregating across the device's full MAC history (not just its current
    last_known_mac) — closes 03-RESEARCH.md Pitfall 1 / Open Question 1.

    Queries raw bandwidth_metrics rows directly (no per-device continuous
    aggregate) — acceptable for this phase's scope since per-device ranges
    are bounded by what a single household generates.
    """
    device_info = await get_device_lookup().lookup(str(device_id))
    if device_info is None:
        raise HTTPException(status_code=404, detail="Device not found")
    macs = device_info.macs

    rows = (
        (
            await db.execute(
                select(BandwidthMetric)
                .where(BandwidthMetric.device_mac.in_(macs))
                .where(BandwidthMetric.time >= start)
                .where(BandwidthMetric.time <= end)
                .order_by(BandwidthMetric.time)
            )
        )
        .scalars()
        .all()
    )

    return {
        "device_id": device_id,
        "start": start,
        "end": end,
        "points": [{"time": row.time, "bytes_rx": row.bytes_rx, "bytes_tx": row.bytes_tx} for row in rows],
    }


@router.get("/devices/{device_id}/destinations")
async def device_destinations(
    device_id: int,
    _: None = Depends(require_auth),
    __: None = Depends(require_module_enabled("traffic")),
    db: AsyncSession = Depends(get_db),
):
    """TRAF-03: per-device destination breakdown, grouped by registered
    domain (D-10) with raw-IP fallback (D-09) — resolves the device's full
    MAC history (same fix as device_bandwidth)."""
    device_info = await get_device_lookup().lookup(str(device_id))
    if device_info is None:
        raise HTTPException(status_code=404, detail="Device not found")
    macs = device_info.macs

    rows = (
        (await db.execute(select(TrafficFlow).where(TrafficFlow.device_mac.in_(macs)))).scalars().all()
    )

    totals: dict[str, float] = {}
    for row in rows:
        label = registered_domain(row.dst_hostname) if row.dst_hostname else row.dst_ip
        totals[label] = totals.get(label, 0.0) + row.bytes

    destinations = [
        {"label": label, "bytes": total_bytes}
        for label, total_bytes in sorted(totals.items(), key=lambda item: item[1], reverse=True)
    ]
    return {"device_id": device_id, "destinations": destinations}
