import enum
from datetime import datetime

from sqlalchemy import Boolean
from sqlalchemy import DateTime
from sqlalchemy import Enum as SAEnum
from sqlalchemy import String, func
from sqlalchemy.orm import Mapped, mapped_column

from src.models.base import Base


class DeviceType(str, enum.Enum):
    PHONE = "phone"
    LAPTOP = "laptop"
    DESKTOP = "desktop"
    TABLET = "tablet"
    IOT = "iot_smart_home"
    TV = "tv_streaming"
    CONSOLE = "game_console"
    ROUTER = "router_network"
    OTHER = "other"


class Device(Base):
    """Registry row — D-04: identity is locked once registered."""

    __tablename__ = "devices"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    identity_key: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    owner: Mapped[str] = mapped_column(String(100), nullable=False, default="")
    type: Mapped[DeviceType] = mapped_column(
        SAEnum(DeviceType, name="devicetype", values_callable=lambda enum_cls: [e.value for e in enum_cls]),
        nullable=False,
    )
    trusted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    last_known_mac: Mapped[str | None] = mapped_column(String(17), nullable=True)
    first_seen: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    last_seen: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
