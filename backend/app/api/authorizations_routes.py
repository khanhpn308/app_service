from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.deps import get_db, require_admin
from app.models.device_authorization import DeviceAuthorization
from app.models.user import User
from app.schemas.authorizations import AuthorizationCreate, AuthorizationPublic

router = APIRouter(prefix="/authorizations", tags=["authorizations"])


@router.get("", response_model=list[AuthorizationPublic])
def list_authorizations(
    user_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
) -> list[AuthorizationPublic]:
    rows = (
        db.query(DeviceAuthorization)
        .filter(DeviceAuthorization.user_id == user_id)
        .order_by(DeviceAuthorization.device_id.asc())
        .all()
    )
    return [AuthorizationPublic.model_validate(r) for r in rows]


@router.post("", response_model=AuthorizationPublic, status_code=status.HTTP_201_CREATED)
def create_authorization(
    body: AuthorizationCreate,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
) -> AuthorizationPublic:
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
        # Primary key is (device_id, user_id) => duplicate assignment
        raise HTTPException(
            status_code=409,
            detail="Authorization already exists for this user/device",
        )
    db.refresh(row)
    return AuthorizationPublic.model_validate(row)

