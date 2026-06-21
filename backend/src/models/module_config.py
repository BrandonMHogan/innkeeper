from sqlalchemy import Boolean, String
from sqlalchemy.orm import Mapped, mapped_column

from src.models.base import Base


class ModuleConfig(Base):
    """A module's enabled/disabled state, toggled without restarting the
    process (MOD-02). Modules default enabled — no row existing for a
    module_id means enabled, matching this column's default (see
    src/host/dependencies.py's is_module_enabled).
    """

    __tablename__ = "module_configs"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    module_id: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
