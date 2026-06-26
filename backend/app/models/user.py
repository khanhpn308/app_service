"""
Model ORM: bảng MySQL ``user`` (tên trùng từ khóa SQL nên trong DB thường quote).

Cột quan trọng:
    - **user_id**: khóa chính.
    - **username**: đăng nhập, map JWT ``sub``.
    - **password**: bcrypt hash (cần VARCHAR đủ dài, ví dụ 255).
    - **cccd**: số định danh 12 chữ số (VARCHAR — giữ số 0 đứng đầu; trước đây là Numeric gây mất số 0).
    - **expired_at / status**: hết hạn tài khoản — đồng bộ với ``user_expiry.deactivate_expired_users``.
    - **role**: ``admin`` hoặc ``user`` (RBAC đơn giản).

Lưu ý: ``creat_at`` là tên cột lịch sử (typo *creat* thay vì *created*).
"""

from datetime import date, datetime

from sqlalchemy import Date, DateTime, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class User(Base):
    """Ánh xạ bảng ``user`` — người dùng hệ thống."""

    __tablename__ = "user"

    user_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String(45), unique=True, nullable=False)
    # Bcrypt hash (~60 chars). DB column should be VARCHAR(255); VARCHAR(45) cannot store a bcrypt hash.
    password: Mapped[str] = mapped_column(String(255), nullable=False)
    fullname: Mapped[str] = mapped_column(String(45), nullable=False)
    # VARCHAR(12) để giữ số 0 đứng đầu (CCCD VN thường bắt đầu bằng 0). Numeric làm mất số 0.
    cccd: Mapped[str] = mapped_column(String(12), unique=True, nullable=False)
    email: Mapped[str | None] = mapped_column(String(45), nullable=True)
    # VARCHAR để giữ số 0 đầu / dấu +, định dạng số điện thoại quốc tế (trước đây là INT).
    phone: Mapped[str | None] = mapped_column(String(20), nullable=True)
    creat_at: Mapped[object] = mapped_column("creat_at", Date, nullable=False)
    expired_at: Mapped[date | None] = mapped_column("expired_at", Date, nullable=True)
    status: Mapped[str] = mapped_column(String(10), nullable=False)
    role: Mapped[str] = mapped_column(String(10), nullable=False)
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime, nullable=True, server_default=func.now(), onupdate=func.now()
    )
