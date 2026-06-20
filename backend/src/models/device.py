import enum
from datetime import datetime

from sqlalchemy import Boolean
from sqlalchemy import DateTime
from sqlalchemy import Enum as SAEnum
from sqlalchemy import String, func
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
