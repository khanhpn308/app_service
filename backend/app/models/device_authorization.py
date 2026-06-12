"""
Model ORM: bảng ``device_authorization`` — quan hệ nhiều-nhiều User ↔ Device.

Khóa chính ghép (**device_id**, **user_id**).

- **granted_at / granted_by**: audit — ai cấp quyền, khi nào (``granted_by`` là chuỗi, ví dụ username admin).
- **expired_at**: hết hạn quyền trên thiết bị (khác với ``user.expired_at`` — hết hạn tài khoản).
"""

from datetime import date, datetime

from sqlalchemy import Date, DateTime, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class DeviceAuthorization(Base):
    """Một dòng = user ``user_id`` được phép truy cập thiết bị ``device_id`` trong khoảng thời gian."""

    __tablename__ = "device_authorization"

    device_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("device.device_id", ondelete="CASCADE", onupdate="CASCADE"), primary_key=True
    )
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("user.user_id", ondelete="CASCADE", onupdate="CASCADE"), primary_key=True
    )
    granted_at: Mapped[date | None] = mapped_column(Date, nullable=True)
    granted_by: Mapped[str | None] = mapped_column(String(45), nullable=True)
    expired_at: Mapped[date | None] = mapped_column(Date, nullable=True)
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime, nullable=True, server_default=func.now(), onupdate=func.now()
    )
