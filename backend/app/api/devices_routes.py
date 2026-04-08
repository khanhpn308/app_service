"""
REST API thiết bị IoT (bảng ``device``) và liên kết phân quyền (``device_authorization``).

Quy ước:
    - **Admin**: CRUD đầy đủ, xem mọi thiết bị, cột ``user_device_asignment_id`` trong chi tiết.
    - **User thường**: chỉ xem thiết bị có trong ``device_authorization`` và chưa hết ``expired_at``
      (hoặc ``expired_at`` null).

Viết tắt:
    - **RBAC** ở đây kết hợp ``role`` + bảng quan hệ user–device.
"""

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, get_db, require_admin
from app.models.device import Device
from app.models.device_authorization import DeviceAuthorization
from app.models.user import User
from app.schemas.devices import (
    DeviceAuthorizedUser,
    DeviceCreate,
    DeviceDetailPublic,
    DeviceTopicPublic,
    DeviceTopicUpdate,
    DevicePublic,
    DeviceUpdate,
)

router = APIRouter(prefix="/devices", tags=["devices"])


def _sync_topic_runtime(request: Request, old_topic: str, new_topic: str) -> None:
    """Đồng bộ subscribe/unsubscribe topic trên MQTT subscriber runtime."""
    mqtt = getattr(request.app.state, "mqtt", None)
    if mqtt is None:
        return
    if old_topic and old_topic != new_topic:
        mqtt.unsubscribe_topic(old_topic)
    if new_topic and new_topic != old_topic:
        mqtt.subscribe_topic(new_topic)


@router.get("", response_model=list[DevicePublic])
def list_devices_admin(
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
) -> list[DevicePublic]:
    """Admin: danh sách toàn bộ thiết bị (sắp theo ``device_id``)."""
    rows = db.query(Device).order_by(Device.device_id.asc()).all()
    return [DevicePublic.model_validate(r) for r in rows]


@router.post("", response_model=DevicePublic, status_code=status.HTTP_201_CREATED)
def create_device(
    body: DeviceCreate,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
) -> DevicePublic:
    """Admin: tạo thiết bị mới; 409 nếu trùng khóa chính ``device_id``."""
    row = Device(
        device_id=body.device_id,
        devicename=body.devicename,
        password=body.password,
        status=body.status,
        user_device_asignment_id=body.user_device_asignment_id,
        location=body.location,
        device_type=body.device_type,
        topic=body.topic,
    )
    db.add(row)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Device already exists")
    db.refresh(row)
    return DevicePublic.model_validate(row)


@router.patch("/{device_id}", response_model=DevicePublic)
def patch_device(
    device_id: int,
    body: DeviceUpdate,
    request: Request,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
) -> DevicePublic:
    """Admin: cập nhật một phần trường tĩnh trên thiết bị."""
    row = db.query(Device).filter(Device.device_id == device_id).first()
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Device not found")

    data = body.model_dump(exclude_unset=True)
    old_topic = (row.topic or "").strip()
    for key, val in data.items():
        setattr(row, key, val)

    db.commit()
    db.refresh(row)

    if "topic" in data:
        new_topic = (row.topic or "").strip()
        _sync_topic_runtime(request, old_topic, new_topic)
    return DevicePublic.model_validate(row)


@router.get("/topics", response_model=list[DeviceTopicPublic])
def list_device_topics(
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
) -> list[DeviceTopicPublic]:
    """Admin: danh sách topic đã lưu theo từng thiết bị."""
    rows = db.query(Device).order_by(Device.device_id.asc()).all()
    return [
        DeviceTopicPublic(
            device_id=r.device_id,
            devicename=r.devicename,
            status=r.status,
            topic=r.topic,
        )
        for r in rows
    ]


@router.put("/{device_id}/topic", response_model=DeviceTopicPublic)
def update_device_topic(
    device_id: int,
    body: DeviceTopicUpdate,
    request: Request,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
) -> DeviceTopicPublic:
    """Admin: cập nhật topic thiết bị và đồng bộ subscribe runtime."""
    row = db.query(Device).filter(Device.device_id == device_id).first()
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Device not found")

    old_topic = (row.topic or "").strip()
    row.topic = (body.topic or "").strip() or None

    db.commit()
    db.refresh(row)

    new_topic = (row.topic or "").strip()
    _sync_topic_runtime(request, old_topic, new_topic)

    return DeviceTopicPublic(
        device_id=row.device_id,
        devicename=row.devicename,
        status=row.status,
        topic=row.topic,
    )


@router.get("/my", response_model=list[DevicePublic])
def list_devices_for_current_user(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[DevicePublic]:
    """User: thiết bị được phân quyền và còn hiệu lực (theo ngày ``expired_at``)."""
    today = date.today()
    q = (
        db.query(Device)
        .join(DeviceAuthorization, DeviceAuthorization.device_id == Device.device_id)
        .filter(DeviceAuthorization.user_id == user.user_id)
        .filter(or_(DeviceAuthorization.expired_at.is_(None), DeviceAuthorization.expired_at >= today))
        .order_by(Device.device_id.asc())
    )
    rows = q.all()
    return [DevicePublic.model_validate(r) for r in rows]


@router.delete("/{device_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_device(
    device_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
) -> None:
    """Admin: xóa thiết bị và mọi bản ghi ``device_authorization`` liên quan."""
    row = db.query(Device).filter(Device.device_id == device_id).first()
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Device not found")
    db.query(DeviceAuthorization).filter(DeviceAuthorization.device_id == device_id).delete(
        synchronize_session=False
    )
    db.delete(row)
    db.commit()


@router.get("/{device_id}", response_model=DeviceDetailPublic)
def get_device(
    device_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> DeviceDetailPublic:
    """
    Chi tiết thiết bị + danh sách user được phân quyền.

    User thường chỉ xem được nếu có authorization còn hạn; admin xem mọi thiết bị.
    ``user_device_asignment_id`` chỉ trả cho admin (tránh lộ legacy id cho user thường).
    """
    row = db.query(Device).filter(Device.device_id == device_id).first()
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Device not found")

    if user.role != "admin":
        today = date.today()
        auth = (
            db.query(DeviceAuthorization)
            .filter(
                DeviceAuthorization.device_id == device_id,
                DeviceAuthorization.user_id == user.user_id,
            )
            .first()
        )
        if auth is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Device not found")
        if auth.expired_at is not None and auth.expired_at < today:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Device not found")

    auth_rows = (
        db.query(DeviceAuthorization, User)
        .join(User, User.user_id == DeviceAuthorization.user_id)
        .filter(DeviceAuthorization.device_id == device_id)
        .order_by(User.user_id.asc())
        .all()
    )
    authorized_users = [
        DeviceAuthorizedUser(
            user_id=u.user_id,
            username=u.username,
            fullname=u.fullname,
            expired_at=a.expired_at,
        )
        for a, u in auth_rows
    ]

    detail = DeviceDetailPublic.model_validate(row)
    return detail.model_copy(
        update={
            "authorized_users": authorized_users,
            "user_device_asignment_id": row.user_device_asignment_id if user.role == "admin" else None,
        }
    )
