"""PortScanResult, SecurityAlert, SecurityAlertType, PendingScanRequest —
relocated verbatim from src/models/{port_scan_result,security_alert,
pending_scan_request}.py (Plan 05), each gaining
__table_args__ = {"schema": "security"} (D-11/D-14) and a ForeignKey
re-pointed at "device_identity.devices.id" since Device now lives in the
device_identity schema (Plan 03).

Mirrors Plan 04's traffic/models.py relocation pattern exactly.
"""

import enum
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, JSON, String, func
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column

from src.models.base import Base
from src.services.security_status import SecurityStatus


class PortScanResult(Base):
    """History table — one row per port scan (on-demand or daily), per
    04-RESEARCH.md Open Question 1. Not a hypertable (plain relational table,
    per STATE.md note); the derived Device.security_status only ever reads
    the latest row, so D-06/D-07's "no opaque history-dependent scoring"
    intent is preserved even though history is retained here.
    """

    __tablename__ = "port_scan_results"
    __table_args__ = {"schema": "security"}

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    device_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("device_identity.devices.id"), nullable=False
    )
    scanned_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    # JSON (not Postgres ARRAY) so the SQLite test fixture can also create
    # this column — portability over Postgres-specific typing.
    open_ports: Mapped[list[int]] = mapped_column(JSON, nullable=False, default=list)


class SecurityAlertType(str, enum.Enum):
    UNKNOWN_DEVICE = "unknown_device"
    MALICIOUS_IP = "malicious_ip"
    SUSPICIOUS_TRAFFIC = "suspicious_traffic"
    UNEXPECTED_PORT = "unexpected_port"


class SecurityAlert(Base):
    """D-11: canonical durable alert record — shaped so Phase 5's event bus
    (PLUG-03) can subscribe to/poll it directly, not throwaway work. Delivery
    (push) is explicitly out of scope this phase (D-13); this table's job
    stops at "detected, classified, and durably recorded."
    """

    __tablename__ = "security_alerts"
    __table_args__ = {"schema": "security"}

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    # Nullable — unregistered/unknown-device alerts have no Device row to
    # reference (e.g. SEC-02's unknown-device-join alert).
    device_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("device_identity.devices.id"), nullable=True
    )
    type: Mapped[str] = mapped_column(
        SAEnum(SecurityAlertType, name="securityalerttype", values_callable=lambda enum_cls: [e.value for e in enum_cls]),
        nullable=False,
    )
    # Reuses the same SecurityStatus enum as Device.security_status (D-06) —
    # deliberately not a parallel severity enum.
    severity: Mapped[str] = mapped_column(
        SAEnum(SecurityStatus, name="securitystatus", values_callable=lambda enum_cls: [e.value for e in enum_cls]),
        nullable=False,
    )
    message: Mapped[str] = mapped_column(String(500), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    acknowledged: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)


class PendingScanRequest(Base):
    """D-03/RESEARCH.md Open Question 3 — DB-backed queue letting the
    browser's on-demand "Scan" button reach the privileged capture container,
    which never accepts inbound HTTP. Survives an API restart mid-request
    (unlike an in-memory queue). claimed_at is set by the capture-side
    poll-and-claim loop in a later wave.
    """

    __tablename__ = "pending_scan_requests"
    __table_args__ = {"schema": "security"}

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    device_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("device_identity.devices.id"), nullable=False
    )
    requested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    claimed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
