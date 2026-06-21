"""Device, DiscoveredIdentity, DeviceMacHistory — relocated verbatim from
src/models/{device,discovered_identity,device_mac_history}.py into the
device_identity support module's own Postgres schema (D-11/D-12).

Each model gains `__table_args__ = {"schema": "device_identity"}`. The
DeviceMacHistory FK to Device is updated to the schema-qualified
`device_identity.devices.id` target. No other field, type, or default
changes — this is a pure relocation, per Plan 03 Task 1's action.
"""

import enum
from datetime import datetime

from sqlalchemy import Boolean
from sqlalchemy import DateTime
from sqlalchemy import Enum as SAEnum
from sqlalchemy import ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column

from src.models.base import Base
from src.services.security_status import SecurityStatus


class DeviceType(str, enum.Enum):
    PHONE = "phone"
    LAPTOP = "laptop"
    DESKTOP = "desktop"
    TABLET = "tablet"
    IOT = "iot_smart_home"
    TV = "tv_streaming"
    CONSOLE = "game_console"
    ROUTER = "router_network"
    OTHER = "other"


class Device(Base):
    """Registry row — D-04: identity is locked once registered."""

    __tablename__ = "devices"
    __table_args__ = {"schema": "device_identity"}

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    identity_key: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    owner: Mapped[str] = mapped_column(String(100), nullable=False, default="")
    type: Mapped[DeviceType] = mapped_column(
        SAEnum(DeviceType, name="devicetype", values_callable=lambda enum_cls: [e.value for e in enum_cls]),
        nullable=False,
    )
    trusted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    last_known_mac: Mapped[str | None] = mapped_column(String(17), nullable=True)
    first_seen: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    last_seen: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())

    # D-06/D-07: derived/cached security status — never user-set, recomputed
    # by the scan-ingest/threat-match/bandwidth-anomaly write paths. Defaults
    # to GOOD so a never-scanned device isn't shown as "at risk" (Pitfall 3).
    security_status: Mapped[str] = mapped_column(
        SAEnum(SecurityStatus, name="securitystatus", values_callable=lambda enum_cls: [e.value for e in enum_cls]),
        nullable=False,
        server_default=SecurityStatus.GOOD.value,
    )
    # Nullable — no scan yet. The "not yet scanned" UI affordance reads this
    # timestamp directly; it is never encoded into security_status itself.
    last_scanned_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # Current IP target for the capture container's on-demand/daily port
    # scan (Plan 04-03) — distinct from last_known_mac, which identifies the
    # device, not where to point nmap.
    last_known_ip: Mapped[str | None] = mapped_column(String(45), nullable=True)


class DiscoveredIdentity(Base):
    """Fused, unregistered identity row — one per resolved identity key (D-01..D-03).

    Unique on identity_key so the discovery service can use a dialect-aware
    upsert (ON CONFLICT DO UPDATE) instead of a racy select-then-insert
    (Pitfall 5).
    """

    __tablename__ = "discovered_identities"
    __table_args__ = {"schema": "device_identity"}

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    identity_key: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    mac: Mapped[str] = mapped_column(String(17), nullable=False)
    hostname: Mapped[str | None] = mapped_column(String(255), nullable=True)
    mdns_service_type: Mapped[str | None] = mapped_column(String(255), nullable=True)
    dhcp_vendor_class: Mapped[str | None] = mapped_column(String(255), nullable=True)
    first_seen: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    last_seen: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


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
    __table_args__ = {"schema": "device_identity"}

    device_id: Mapped[int] = mapped_column(
        ForeignKey("device_identity.devices.id"), nullable=False, primary_key=True
    )
    mac: Mapped[str] = mapped_column(String(17), nullable=False, primary_key=True)
    first_seen: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    last_seen: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
