from datetime import date

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, get_db, require_admin
from app.models.device import Device
from app.models.device_authorization import DeviceAuthorization
from app.models.user import User
from app.schemas.devices import DeviceCreate, DeviceDetailPublic, DevicePublic

router = APIRouter(prefix="/devices", tags=["devices"])


@router.get("", response_model=list[DevicePublic])
def list_devices_admin(
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
) -> list[DevicePublic]:
    rows = db.query(Device).order_by(Device.device_id.asc()).all()
    return [DevicePublic.model_validate(r) for r in rows]


@router.post("", response_model=DevicePublic, status_code=status.HTTP_201_CREATED)
def create_device(
    body: DeviceCreate,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
) -> DevicePublic:
    row = Device(
        device_id=body.device_id,
        devicename=body.devicename,
        password=body.password,
        status=body.status,
        user_device_asignment_id=body.user_device_asignment_id,
    )
    db.add(row)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Device already exists")
    db.refresh(row)
    return DevicePublic.model_validate(row)


@router.get("/my", response_model=list[DevicePublic])
def list_devices_for_current_user(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[DevicePublic]:
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


@router.get("/{device_id}", response_model=DeviceDetailPublic)
def get_device(
    device_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> DeviceDetailPublic:
    """Admin: any device. User: only if authorized and not expired."""
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

    return DeviceDetailPublic.model_validate(row)

