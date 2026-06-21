import enum
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, func
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column

from src.models.base import Base
from src.services.security_status import SecurityStatus


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
