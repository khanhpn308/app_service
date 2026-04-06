"""
Seed dữ liệu khởi đầu: admin mặc định và vài thiết bị demo.

Chạy từ ``main.lifespan`` sau khi schema sẵn sàng. Mật khẩu admin mặc định phải đổi sau khi vào production.

Hàm ``ensure_*`` idempotent: nếu dữ liệu đã có thì thoát sớm (tránh duplicate).
"""

from datetime import date
from decimal import Decimal

from sqlalchemy.exc import IntegrityError
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.models.device import Device
from app.models.user import User

DEFAULT_ADMIN_USERNAME = "AD00000"
# Default password for first-time setup; change after login in production.
DEFAULT_ADMIN_PASSWORD = "khanhxx007"
DEFAULT_ADMIN_CCCD = Decimal("888888888888")


def ensure_default_admin(db: Session) -> None:
    """Tạo user admin cố định nếu chưa tồn tại (bỏ qua lỗi race/IntegrityError)."""
    existing = (
        db.query(User).filter(User.username == DEFAULT_ADMIN_USERNAME).first()
    )
    if existing is not None:
        return

    user = User(
        username=DEFAULT_ADMIN_USERNAME,
        password=hash_password(DEFAULT_ADMIN_PASSWORD),
        fullname="System Administrator",
        cccd=DEFAULT_ADMIN_CCCD,
        email="admin@local",
        phone=None,
        creat_at=date.today(),
        expired_at=date(2099, 12, 31),
        status="active",
        role="admin",
    )
    db.add(user)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()


def ensure_default_devices(db: Session) -> None:
    """Thêm vài ``device`` mẫu khi bảng đang trống; bỏ qua nếu schema lỗi thời (OperationalError)."""
    try:
        if db.query(Device).count() > 0:
            return
    except OperationalError:
        # If schema doesn't match (e.g., missing columns in an old DB volume),
        # don't crash the whole app at startup. The migration step should fix schema.
        db.rollback()
        return
    seeds = [
        Device(device_id=1, devicename="Motor DEV001", password="dev001", status="active", user_device_asignment_id=0),
        Device(device_id=2, devicename="Motor DEV002", password="dev002", status="active", user_device_asignment_id=0),
        Device(device_id=3, devicename="Motor DEV003", password="dev003", status="active", user_device_asignment_id=0),
    ]
    for d in seeds:
        db.add(d)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
