from datetime import datetime

from sqlalchemy import DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column

from src.models.base import Base


class DiscoveredIdentity(Base):
    """Fused, unregistered identity row — one per resolved identity key (D-01..D-03).

    Unique on identity_key so the discovery service can use a dialect-aware
    upsert (ON CONFLICT DO UPDATE) instead of a racy select-then-insert
    (Pitfall 5).
    """

    __tablename__ = "discovered_identities"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    identity_key: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    mac: Mapped[str] = mapped_column(String(17), nullable=False)
    hostname: Mapped[str | None] = mapped_column(String(255), nullable=True)
    mdns_service_type: Mapped[str | None] = mapped_column(String(255), nullable=True)
    dhcp_vendor_class: Mapped[str | None] = mapped_column(String(255), nullable=True)
    first_seen: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    last_seen: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
