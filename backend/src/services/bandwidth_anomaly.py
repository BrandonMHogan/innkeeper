from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.bandwidth import BandwidthMetric
from src.routes.traffic import _resolve_device_macs

# D-09/RESEARCH.md Open Question 2 — provisional defaults, tunable without a
# code-structure change since they're named constants, not magic numbers.
ROLLING_WINDOW_DAYS = 14
ANOMALY_THRESHOLD_MULTIPLIER = 3.0
MIN_SAMPLE_DAYS = 7


async def check_bandwidth_anomaly(db: AsyncSession, device_id: int) -> bool:
    """D-09: bandwidth-spike anomaly — a device's most-recent day of traffic
    exceeds ANOMALY_THRESHOLD_MULTIPLIER times its own rolling historical
    average. Pure read+compute query, no side effects (no alert insert, no
    status write) — callers act on the returned bool.

    Pitfall 5: requires at least MIN_SAMPLE_DAYS distinct prior days of
    BandwidthMetric data before evaluating; returns False below that
    threshold regardless of how large the most recent reading is, to avoid a
    noisy/meaningless threshold against a near-empty baseline.

    Groups rows by calendar day in Python (row.time.date()), not SQL
    time_bucket — keeps this portable across Postgres/SQLite, mirroring
    network_bandwidth's existing dual-path precedent in traffic.py.
    """
    macs = await _resolve_device_macs(db, device_id)

    window_start = datetime.now(timezone.utc) - timedelta(days=ROLLING_WINDOW_DAYS)
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

    daily_totals: dict[object, float] = {}
    for row in rows:
        day_key = row.time.date()
        daily_totals[day_key] = daily_totals.get(day_key, 0.0) + row.bytes_rx + row.bytes_tx

    if len(daily_totals) < MIN_SAMPLE_DAYS:
        return False

    most_recent_day = max(daily_totals.keys())
    most_recent_total = daily_totals.pop(most_recent_day)

    if not daily_totals:
        return False

    rolling_average = sum(daily_totals.values()) / len(daily_totals)

    return most_recent_total > rolling_average * ANOMALY_THRESHOLD_MULTIPLIER
