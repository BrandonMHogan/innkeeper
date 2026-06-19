from datetime import datetime

from sqlalchemy import DateTime, Float, String, func
from sqlalchemy.orm import Mapped, mapped_column

from src.models.base import Base


class BandwidthMetric(Base):
    """Time-series table (TimescaleDB hypertable) for per-device bandwidth.

    Not written to in Phase 1 (Phase 3 populates it) but the schema must exist
    now per D-16 to avoid an expensive migration rewrite later.
    """

    __tablename__ = "bandwidth_metrics"

    time: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        primary_key=True,
    )
    device_mac: Mapped[str] = mapped_column(String(17), nullable=False, primary_key=True)
    bytes_rx: Mapped[float] = mapped_column(Float, default=0.0)
    bytes_tx: Mapped[float] = mapped_column(Float, default=0.0)
