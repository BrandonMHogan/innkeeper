from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from src.models.base import Base


class AppSettings(Base):
    """Single-row table for application configuration (password hash, setup state)."""

    __tablename__ = "app_settings"

    id: Mapped[int] = mapped_column(primary_key=True)
    password_hash: Mapped[str | None] = mapped_column(String(256), nullable=True)
    setup_complete: Mapped[bool] = mapped_column(default=False)
