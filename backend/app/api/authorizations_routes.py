"""
REST API bảng ``device_authorization`` (quyền user trên thiết bị).

- **GET**: bắt buộc đúng một query ``user_id`` **hoặc** ``device_id`` — liệt kê authorization tương ứng.
- **POST**: tạo bản ghi mới (khóa chính ghép ``device_id`` + ``user_id``); trùng → 409.

Đây là lớp phân quyền **thực** so với cột legacy ``device.user_device_asignment_id``.
"""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.deps import get_db, require_admin
from app.models.device_authorization import DeviceAuthorization
from app.models.user import User
from app.schemas.authorizations import AuthorizationCreate, AuthorizationPublic

router = APIRouter(prefix="/authorizations", tags=["authorizations"])


@router.get("", response_model=list[AuthorizationPublic])
def list_authorizations(
    user_id: int | None = Query(None),
    device_id: int | None = Query(None),
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
) -> list[AuthorizationPublic]:
    """Lọc theo user hoặc theo thiết bị (không cho cả hai null/ cả hai cùng lúc)."""
    if (user_id is None) == (device_id is None):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cần đúng một tham số: user_id hoặc device_id",
        )
    q = db.query(DeviceAuthorization)
    if user_id is not None:
        rows = (
            q.filter(DeviceAuthorization.user_id == user_id)
            .order_by(DeviceAuthorization.device_id.asc())
            .all()
        )
    else:
        rows = (
            q.filter(DeviceAuthorization.device_id == device_id)
            .order_by(DeviceAuthorization.user_id.asc())
            .all()
        )
    return [AuthorizationPublic.model_validate(r) for r in rows]


@router.post("", response_model=AuthorizationPublic, status_code=status.HTTP_201_CREATED)
def create_authorization(
    body: AuthorizationCreate,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
) -> AuthorizationPublic:
    """Gán quyền user–device; ``granted_by`` thường là username admin (chuỗi)."""
    row = DeviceAuthorization(
        device_id=body.device_id,
        user_id=body.user_id,
        granted_at=body.granted_at,
        granted_by=body.granted_by,
        expired_at=body.expired_at,
    )
    db.add(row)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        # Khóa chính (device_id, user_id) trùng
        raise HTTPException(
            status_code=409,
            detail="Authorization already exists for this user/device",
        )
    db.refresh(row)
    return AuthorizationPublic.model_validate(row)
