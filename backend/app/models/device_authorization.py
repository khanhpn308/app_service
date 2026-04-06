"""
Model ORM: bảng ``device_authorization`` — quan hệ nhiều-nhiều User ↔ Device.

Khóa chính ghép (**device_id**, **user_id**).

- **granted_at / granted_by**: audit — ai cấp quyền, khi nào (``granted_by`` là chuỗi, ví dụ username admin).
- **expired_at**: hết hạn quyền trên thiết bị (khác với ``user.expired_at`` — hết hạn tài khoản).
"""

from datetime import date

from sqlalchemy import Date, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class DeviceAuthorization(Base):
    """Một dòng = user ``user_id`` được phép truy cập thiết bị ``device_id`` trong khoảng thời gian."""

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
