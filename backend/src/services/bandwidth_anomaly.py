from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.modules.device_identity.models import Device, DeviceMacHistory
from src.modules.traffic.models import BandwidthMetric

# D-09/RESEARCH.md Open Question 2 — provisional defaults, tunable without a
# code-structure change since they're named constants, not magic numbers.
ROLLING_WINDOW_DAYS = 14
ANOMALY_THRESHOLD_MULTIPLIER = 3.0
MIN_SAMPLE_DAYS = 7


async def _resolve_device_macs(db: AsyncSession, device_id: int) -> set[str]:
    """Resolves the full set of MACs a device has ever been associated
    with, querying device_identity's Device/DeviceMacHistory directly via
    the same `db` session check_bandwidth_anomaly was already given.

    Deliberately NOT routed through DeviceLookupInterface (T-05-11's
    general retrofit rule) — this function is called from capture.py's
    queue_daily_scans, which already holds an open `db` session mid-request
    and queries Device/SecurityAlert directly in the same transaction; the
    route-level DeviceLookupInterface instance uses its own independently
    constructed session factory, which would not see uncommitted state
    from this caller's transaction. Pre-retrofit behavior (an inline
    Device/DeviceMacHistory query) is preserved exactly for this same-session
    consumer; only routes.py's per-request consumers go through
    DeviceLookupInterface.lookup().
    """
    device = (await db.execute(select(Device).where(Device.id == device_id))).scalar_one_or_none()
    if device is None:
        return set()

    history_macs = (
        (await db.execute(select(DeviceMacHistory.mac).where(DeviceMacHistory.device_id == device_id)))
        .scalars()
        .all()
    )
    macs = set(history_macs)
    if device.last_known_mac:
        macs.add(device.last_known_mac)
    return macs


async def check_bandwidth_anomaly(db: AsyncSession, device_id: int) -> bool:
    """D-09: bandwidth-spike anomaly — a device's most-recent trailing 24h of
    traffic exceeds ANOMALY_THRESHOLD_MULTIPLIER times its own rolling
    historical average. Pure read+compute query, no side effects (no alert
    insert, no status write) — callers act on the returned bool.

    Pitfall 5: requires at least MIN_SAMPLE_DAYS distinct prior days of
    BandwidthMetric data before evaluating; returns False below that
    threshold regardless of how large the most recent reading is, to avoid a
    noisy/meaningless threshold against a near-empty baseline.

    Uses a trailing 24h window ending "now" for the "most recent" bucket
    (not a calendar-day bucket keyed off row.time.date()), so the comparison
    is always a full 24h of traffic against the baseline regardless of what
    time of day this runs — calendar-day bucketing would otherwise compare a
    partial "today" against full prior days, producing both false negatives
    (a late-day spike rolling into a new calendar day right before the scan)
    and false positives (a few hours of activity right before the scan
    compared against multi-day full-day averages).

    Remaining days are still grouped by calendar day in Python
    (row.time.date()), not SQL time_bucket — keeps this portable across
    Postgres/SQLite, mirroring network_bandwidth's existing dual-path
    precedent in traffic.py.
    """
    macs = await _resolve_device_macs(db, device_id)

    now = datetime.now(timezone.utc)
    most_recent_window_start = now - timedelta(hours=24)
    window_start = now - timedelta(days=ROLLING_WINDOW_DAYS)
    rows = (
        (
            await db.execute(
                select(BandwidthMetric)
                .where(BandwidthMetric.device_mac.in_(macs))
                .where(BandwidthMetric.time >= window_start)
            )
        )
        .scalars()
        .all()
    )

    most_recent_total = 0.0
    daily_totals: dict[object, float] = {}
    baseline_days: set[object] = set()
    for row in rows:
        total_bytes = row.bytes_rx + row.bytes_tx
        # SQLite (used in tests) returns naive datetimes even for a
        # DateTime(timezone=True) column; Postgres returns aware ones.
        # Normalize to aware UTC before comparing against most_recent_window_start.
        row_time = row.time if row.time.tzinfo else row.time.replace(tzinfo=timezone.utc)
        if row_time >= most_recent_window_start:
            most_recent_total += total_bytes
        else:
            day_key = row.time.date()
            daily_totals[day_key] = daily_totals.get(day_key, 0.0) + total_bytes
            baseline_days.add(day_key)

    # Sample-size guard counts complete baseline days plus the trailing 24h
    # bucket itself, mirroring the prior len(daily_totals) semantics before
    # the most-recent bucket was split out.
    if len(baseline_days) + 1 < MIN_SAMPLE_DAYS:
        return False

    if not daily_totals:
        return False

    rolling_average = sum(daily_totals.values()) / len(daily_totals)

    return most_recent_total > rolling_average * ANOMALY_THRESHOLD_MULTIPLIER
