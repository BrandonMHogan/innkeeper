from datetime import datetime

from sqlalchemy import DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column

from src.models.base import Base


class DhcpEvent(Base):
    """Capture ingest row — one DHCP packet observation POSTed by the capture service."""

    __tablename__ = "dhcp_events"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    src_mac: Mapped[str] = mapped_column(String(17), nullable=False)
    hostname: Mapped[str | None] = mapped_column(String(255), nullable=True)
    requested_ip: Mapped[str | None] = mapped_column(String(45), nullable=True)
    vendor_class_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
