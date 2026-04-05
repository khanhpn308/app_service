from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.deps import get_db, require_admin
from app.core.user_expiry import deactivate_expired_users
from app.models.user import User
from app.schemas.auth import UserPublic, UserStatusPatch

router = APIRouter(prefix="/users", tags=["users"])


@router.get("", response_model=list[UserPublic])
def list_users(
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
) -> list[UserPublic]:
    deactivate_expired_users(db)
    rows = db.query(User).order_by(User.user_id.asc()).all()
    return [UserPublic.model_validate(u) for u in rows]


@router.patch("/{user_id}", response_model=UserPublic)
def patch_user_status(
    user_id: int,
    body: UserStatusPatch,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
) -> UserPublic:
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
    if user_id == current.user_id:
        raise HTTPException(status_code=400, detail="Không thể xóa chính tài khoản đang đăng nhập")
    target = db.query(User).filter(User.user_id == user_id).first()
    if target is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy người dùng")
    db.delete(target)
    db.commit()
