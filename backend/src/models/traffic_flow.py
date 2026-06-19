from datetime import datetime

from sqlalchemy import DateTime, Float, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from src.models.base import Base


class TrafficFlow(Base):
    """Time-series table (TimescaleDB hypertable) for per-destination traffic flows.

    D-05: separate from `bandwidth_metrics` (the simple per-device-per-time
    rollup) — this table is the 5-tuple flow-level detail (device_mac, dst_ip,
    dst_port, protocol) feeding the per-device destination breakdown (TRAF-03).

    `dst_hostname` always stores the raw DNS-sniffed hostname (D-08) — never
    the grouped registered domain. Registered-domain grouping (D-10) happens
    at query/serialization time only, in domain_grouping.py.
    """

    __tablename__ = "traffic_flows"

    time: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        primary_key=True,
    )
    device_mac: Mapped[str] = mapped_column(String(17), nullable=False, primary_key=True)
    dst_ip: Mapped[str] = mapped_column(String(45), nullable=False, primary_key=True)
    dst_port: Mapped[int | None] = mapped_column(Integer, nullable=True, primary_key=True)
    protocol: Mapped[int] = mapped_column(Integer, nullable=False, primary_key=True)
    bytes: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    dst_hostname: Mapped[str | None] = mapped_column(String(255), nullable=True)
