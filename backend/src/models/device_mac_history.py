from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column

from src.models.base import Base


class DeviceMacHistory(Base):
    """Every MAC a Device has ever used — closes the MAC-rotation blind spot.

    03-RESEARCH.md Pitfall 1 / Open Question 1: bandwidth_metrics and
    traffic_flows are both keyed by raw device_mac, with no historical
    "all MACs this device has ever had" table. A query that filters only on
    Device.last_known_mac silently misses every row written under a
    previous MAC (e.g. iOS/Android private MAC rotation). This table is the
    fix: a row exists for every (device_id, mac) pair this device has ever
    been observed under, so historical bandwidth/traffic_flows queries can
    join across the device's full MAC history, not just its current MAC.

    Plain Postgres table (not a hypertable) — small lookup table, not
    time-series.
    """

    __tablename__ = "device_mac_history"

    device_id: Mapped[int] = mapped_column(ForeignKey("devices.id"), nullable=False, primary_key=True)
    mac: Mapped[str] = mapped_column(String(17), nullable=False, primary_key=True)
    first_seen: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    last_seen: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
