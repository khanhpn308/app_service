"""
Seed dữ liệu khởi đầu: admin mặc định và vài thiết bị demo.

Chạy từ ``main.lifespan`` sau khi schema sẵn sàng. Mật khẩu admin mặc định phải đổi sau khi vào production.

Hàm ``ensure_*`` idempotent: nếu dữ liệu đã có thì thoát sớm (tránh duplicate).
"""

import os
from datetime import date
from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.core.map_image_validator import validate_map_image
from app.models.device import Device
from app.models.map_group import MapGroup
from app.models.map_location import LocationDeleted, LocationUsing
from app.models.user import User

DEFAULT_ADMIN_USERNAME = "AD00000"
# Default password for first-time setup; change after login in production.
DEFAULT_ADMIN_PASSWORD = "khanhxx007"
DEFAULT_ADMIN_CCCD = "888888888888"
SYSTEM_MAP_GROUP_NAME = "System Debug Maps"
SYSTEM_FLOORPLANS = (
    ("Floor_1", "Floor_1.webp"),
    ("Floor_2", "Floor_2.webp"),
    ("Floor_3", "Floor_3.webp"),
    ("Floor_4", "Floor_4.webp"),
)


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
    # Mật khẩu thiết bị được hash bcrypt (giống user) — dùng cho WS ESP32 auth.
    seeds = [
        Device(device_id=1, devicename="Motor DEV001", password=hash_password("dev001"), status="active", user_device_asignment_id=0),
        Device(device_id=2, devicename="Motor DEV002", password=hash_password("dev002"), status="active", user_device_asignment_id=0),
        Device(device_id=3, devicename="Motor DEV003", password=hash_password("dev003"), status="active", user_device_asignment_id=0),
    ]
    for d in seeds:
        db.add(d)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()


def _default_floorplan_dir() -> Path:
    configured = os.getenv("FLOORPLAN_SEED_DIR")
    candidates = [
        Path(configured) if configured else None,
        Path("/app/seed_floorplans"),
        Path(__file__).resolve().parents[3] / "src" / "assets" / "floorplans",
    ]
    for candidate in candidates:
        if candidate is not None and candidate.is_dir():
            return candidate
    raise FileNotFoundError(
        "Không tìm thấy thư mục seed floorplan; đặt FLOORPLAN_SEED_DIR."
    )


def ensure_default_maps(
    db: Session,
    *,
    floorplan_dir: Path | None = None,
) -> None:
    """Seed four system WebPs once across both active and archive tables."""
    admin = db.execute(
        select(User)
        .where(User.username == DEFAULT_ADMIN_USERNAME)
        .with_for_update()
    ).scalar_one_or_none()
    if admin is None:
        raise RuntimeError("Default admin must exist before seeding system maps.")

    group = db.execute(
        select(MapGroup).where(
            MapGroup.owner_user_id == admin.user_id,
            func.lower(MapGroup.name) == SYSTEM_MAP_GROUP_NAME.lower(),
        )
    ).scalar_one_or_none()
    if group is None:
        group = MapGroup(
            name=SYSTEM_MAP_GROUP_NAME,
            owner_user_id=admin.user_id,
            created_by_user_id=admin.user_id,
        )
        db.add(group)
        db.flush()

    source_dir = Path(floorplan_dir) if floorplan_dir else _default_floorplan_dir()
    for location, filename in SYSTEM_FLOORPLANS:
        normalized = location.lower()
        active_exists = db.execute(
            select(LocationUsing.location_id).where(
                func.lower(LocationUsing.location) == normalized
            )
        ).first()
        archived_exists = db.execute(
            select(LocationDeleted.location_id).where(
                func.lower(LocationDeleted.location) == normalized
            )
        ).first()
        if active_exists is not None or archived_exists is not None:
            continue

        content = (source_dir / filename).read_bytes()
        metadata = validate_map_image(
            content,
            filename=filename,
            content_type="image/webp",
        )
        db.add(
            LocationUsing(
                location=location,
                image_data=content,
                mime_type=metadata.mime_type,
                original_filename=filename,
                checksum_sha256=metadata.checksum_sha256,
                file_size_bytes=metadata.file_size_bytes,
                width=metadata.width,
                height=metadata.height,
                group_id=group.group_id,
                owner_user_id=admin.user_id,
                created_by_user_id=admin.user_id,
            )
        )
    db.commit()
