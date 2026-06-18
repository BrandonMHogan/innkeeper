from datetime import datetime

from sqlalchemy import String, func
from sqlalchemy.orm import Mapped, mapped_column

from src.models.base import Base


class MdnsEvent(Base):
    """Capture ingest row — one mDNS service observation POSTed by the capture service."""

    __tablename__ = "mdns_events"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    hostname: Mapped[str | None] = mapped_column(String(255), nullable=True)
    service_type: Mapped[str] = mapped_column(String(255), nullable=False)
    addresses: Mapped[str] = mapped_column(String(512), nullable=False)
    received_at: Mapped[datetime] = mapped_column(nullable=False, server_default=func.now())
