from datetime import datetime

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, func
from sqlalchemy.orm import Mapped, mapped_column

from src.models.base import Base


class PortScanResult(Base):
    """History table — one row per port scan (on-demand or daily), per
    04-RESEARCH.md Open Question 1. Not a hypertable (plain relational table,
    per STATE.md note); the derived Device.security_status only ever reads
    the latest row, so D-06/D-07's "no opaque history-dependent scoring"
    intent is preserved even though history is retained here.
    """

    __tablename__ = "port_scan_results"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    device_id: Mapped[int] = mapped_column(Integer, ForeignKey("devices.id"), nullable=False)
    scanned_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    # JSON (not Postgres ARRAY) so the SQLite test fixture can also create
    # this column — portability over Postgres-specific typing.
    open_ports: Mapped[list[int]] = mapped_column(JSON, nullable=False, default=list)
