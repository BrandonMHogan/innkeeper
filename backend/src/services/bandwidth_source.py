from datetime import datetime
from typing import Protocol

from sqlalchemy.ext.asyncio import AsyncSession

from src.models.bandwidth import BandwidthMetric


class BandwidthSource(Protocol):
    """D-07: swappable bandwidth-writing interface.

    One source today (passive capture); a future Phase 7 UniFi adapter will
    implement this same Protocol without requiring changes to callers — this
    is the swappability D-07 requires, matching PROJECT.md's existing
    adapter-pattern decision for router integrations.
    """

    async def write_rollup(
        self,
        db: AsyncSession,
        device_mac: str,
        bytes_rx: float,
        bytes_tx: float,
        observed_at: datetime,
    ) -> None: ...


class PassiveCaptureBandwidthSource:
    """The only source today; Phase 7's UniFi adapter will implement the same
    BandwidthSource Protocol without requiring changes to callers — that is
    the swappability D-07 requires.
    """

    async def write_rollup(
        self,
        db: AsyncSession,
        device_mac: str,
        bytes_rx: float,
        bytes_tx: float,
        observed_at: datetime,
    ) -> None:
        db.add(
            BandwidthMetric(
                time=observed_at,
                device_mac=device_mac,
                bytes_rx=bytes_rx,
                bytes_tx=bytes_tx,
            )
        )
        await db.commit()
