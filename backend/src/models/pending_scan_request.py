from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, func
from sqlalchemy.orm import Mapped, mapped_column

from src.models.base import Base


class PendingScanRequest(Base):
    """D-03/RESEARCH.md Open Question 3 — DB-backed queue letting the
    browser's on-demand "Scan" button reach the privileged capture container,
    which never accepts inbound HTTP. Survives an API restart mid-request
    (unlike an in-memory queue). claimed_at is set by the capture-side
    poll-and-claim loop in a later wave.
    """

    __tablename__ = "pending_scan_requests"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    device_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("device_identity.devices.id"), nullable=False
    )
    requested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    claimed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
