from datetime import datetime

from sqlalchemy import String, func
from sqlalchemy.orm import Mapped, mapped_column

from src.models.base import Base


class ArpEvent(Base):
    """Capture ingest row — one ARP packet observation POSTed by the capture service."""

    __tablename__ = "arp_events"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    src_mac: Mapped[str] = mapped_column(String(17), nullable=False)
    src_ip: Mapped[str] = mapped_column(String(45), nullable=False)
    dst_ip: Mapped[str] = mapped_column(String(45), nullable=False)
    received_at: Mapped[datetime] = mapped_column(nullable=False, server_default=func.now())
