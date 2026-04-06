"""
Model ORM: bảng ``device`` — thiết bị IoT (định danh tĩnh, không lưu telemetry realtime).

- **device_id**: khóa chính (thường do admin nhập khi đăng ký thiết bị).
- **user_device_asignment_id**: cột legacy (chữ *asignment* sai chính tả trong schema cũ); NOT NULL nhưng
  **không** thay thế bảng ``device_authorization``. Giá trị thường ``0`` nếu không dùng.
- **location / device_type**: hiển thị/phân loại; dữ liệu sống từ MQTT không lưu ở đây (xem ``db_migrate`` đã bỏ cột last_reading*).
"""

from sqlalchemy import Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class Device(Base):
    """Thiết bị — một dòng một thiết bị vật lý / logical."""

    __tablename__ = "device"

    device_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    devicename: Mapped[str | None] = mapped_column(String(45), nullable=True)
    password: Mapped[str | None] = mapped_column(String(45), nullable=True)
    status: Mapped[str | None] = mapped_column(String(10), nullable=True)
    # Legacy NOT NULL column from original schema (name is misspelled "asignment").
    # Not used for RBAC: which user may access which device is in `device_authorization`.
    # New devices typically store 0 here; keep the column for DB compatibility.
    user_device_asignment_id: Mapped[int] = mapped_column(Integer, nullable=False)
    # Static display / classification only. Live telemetry comes from MQTT/payload, not stored here.
    location: Mapped[str | None] = mapped_column(String(255), nullable=True)
    device_type: Mapped[str | None] = mapped_column(String(45), nullable=True)
