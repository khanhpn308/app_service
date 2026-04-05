from datetime import date

from sqlalchemy import Date, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class DeviceAuthorization(Base):
    __tablename__ = "device_authorization"

    device_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("device.device_id"), primary_key=True
    )
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("user.user_id"), primary_key=True
    )
    granted_at: Mapped[date | None] = mapped_column(Date, nullable=True)
    granted_by: Mapped[str | None] = mapped_column(String(45), nullable=True)
    expired_at: Mapped[date | None] = mapped_column(Date, nullable=True)
