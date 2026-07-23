"""
REST API quản lý người dùng (chủ yếu **admin**).

- **GET /users**: danh sách user kèm ``authorized_devices`` (thiết bị đã gán qua ``device_authorization``).
- **PATCH /users/{id}**: đổi ``status`` (active/deactive).
- **DELETE /users/{id}**: xóa user (không cho xóa chính mình).

``deactivate_expired_users`` được gọi trước khi liệt kê để đồng bộ hết hạn tài khoản.
"""

from collections import defaultdict

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.deps import get_db, require_admin
from app.core.map_archive import LocationArchiveError
from app.core.map_lifecycle import (
    MapLifecycleError,
    delete_user_with_map_lifecycle,
)
from app.core.user_expiry import deactivate_expired_users
from app.models.device import Device
from app.models.device_authorization import DeviceAuthorization
from app.models.user import User
from app.schemas.auth import UserPublic, UserStatusPatch
from app.schemas.authorizations import AuthorizedDeviceBrief

router = APIRouter(prefix="/users", tags=["users"])


@router.get("", response_model=list[UserPublic])
def list_users(
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
    limit: int = Query(default=500, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
) -> list[UserPublic]:
    """Danh sách user (phân trang); join authorization chỉ cho user trong trang."""
    deactivate_expired_users(db)
    rows = (
        db.query(User)
        .order_by(User.user_id.asc())
        .limit(limit)
        .offset(offset)
        .all()
    )
    user_ids = [u.user_id for u in rows]
    # Chỉ lấy authorization của các user trong trang hiện tại (tránh quét toàn bảng).
    pairs = (
        db.query(DeviceAuthorization.user_id, Device.device_id, Device.devicename)
        .join(Device, Device.device_id == DeviceAuthorization.device_id)
        .filter(DeviceAuthorization.user_id.in_(user_ids))
        .order_by(DeviceAuthorization.user_id.asc(), DeviceAuthorization.device_id.asc())
        .all()
    ) if user_ids else []
    by_user: dict[int, list[AuthorizedDeviceBrief]] = defaultdict(list)
    for uid, did, name in pairs:
        by_user[uid].append(AuthorizedDeviceBrief(device_id=did, devicename=name))
    out: list[UserPublic] = []
    for u in rows:
        base = UserPublic.model_validate(u)
        out.append(base.model_copy(update={"authorized_devices": by_user.get(u.user_id, [])}))
    return out


@router.patch("/{user_id}", response_model=UserPublic)
def patch_user_status(
    user_id: int,
    body: UserStatusPatch,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
) -> UserPublic:
    """Cập nhật trạng thái tài khoản (active/deactive)."""
    target = db.query(User).filter(User.user_id == user_id).first()
    if target is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy người dùng")
    target.status = body.status
    db.add(target)
    db.commit()
    db.refresh(target)
    return UserPublic.model_validate(target)


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_user(
    user_id: int,
    db: Session = Depends(get_db),
    current: User = Depends(require_admin),
) -> None:
    """Xóa user theo khóa; chặn xóa tài khoản đang đăng nhập."""
    if user_id == current.user_id:
        raise HTTPException(status_code=400, detail="Không thể xóa chính tài khoản đang đăng nhập")
    target = db.query(User).filter(User.user_id == user_id).first()
    if target is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy người dùng")
    try:
        delete_user_with_map_lifecycle(
            db,
            target.user_id,
            deleted_by=current,
        )
        db.commit()
    except MapLifecycleError as error:
        db.rollback()
        raise HTTPException(status_code=404, detail="Không tìm thấy người dùng") from error
    except (LocationArchiveError, IntegrityError) as error:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="Không thể archive dữ liệu bản đồ của người dùng",
        ) from error
