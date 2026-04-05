import secrets
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, get_db, require_admin
from app.core.security import create_access_token, hash_password, verify_password
from app.core.user_expiry import deactivate_expired_users
from app.models.user import User
from app.schemas.auth import (
    BootstrapRequest,
    ChangePasswordRequest,
    LoginRequest,
    RecoverPasswordRequest,
    RecoverPasswordResponse,
    RegisterRequest,
    TokenResponse,
    UserPublic,
)

router = APIRouter(prefix="/auth", tags=["auth"])


def _user_public(u: User) -> UserPublic:
    return UserPublic.model_validate(u)


@router.post("/login", response_model=TokenResponse)
def login(body: LoginRequest, db: Session = Depends(get_db)) -> TokenResponse:
    deactivate_expired_users(db)
    user = db.query(User).filter(User.username == body.username).first()
    if user is None or not verify_password(body.password, user.password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Tên đăng nhập hoặc mật khẩu không đúng",
        )
    if user.status != "active":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Tài khoản đã bị vô hiệu hóa",
        )
    token = create_access_token(
        subject=user.username,
        user_id=user.user_id,
        role=user.role,
    )
    return TokenResponse(
        access_token=token,
        user=_user_public(user),
    )


@router.post("/register", response_model=UserPublic)
def register(
    body: RegisterRequest,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
) -> UserPublic:
    if db.query(User).filter(User.username == body.username).first():
        raise HTTPException(status_code=400, detail="Username đã tồn tại")
    if db.query(User).filter(User.cccd == body.cccd).first():
        raise HTTPException(status_code=400, detail="CCCD đã tồn tại")

    user = User(
        username=body.username,
        password=hash_password(body.password),
        fullname=body.fullname,
        cccd=body.cccd,
        email=body.email,
        phone=body.phone,
        creat_at=date.today(),
        expired_at=body.expired_at,
        status="active",
        role=body.role,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return _user_public(user)


@router.post("/bootstrap", response_model=UserPublic)
def bootstrap_first_admin(body: BootstrapRequest, db: Session = Depends(get_db)) -> UserPublic:
    if db.query(User).count() > 0:
        raise HTTPException(status_code=403, detail="Bootstrap disabled: users already exist")

    exp = body.expired_at if body.expired_at is not None else date(2099, 12, 31)
    user = User(
        username=body.username,
        password=hash_password(body.password),
        fullname=body.fullname,
        cccd=body.cccd,
        email=body.email,
        phone=body.phone,
        creat_at=date.today(),
        expired_at=exp,
        status="active",
        role="admin",
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return _user_public(user)


@router.get("/me", response_model=UserPublic)
def read_me(db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> UserPublic:
    deactivate_expired_users(db)
    u = db.query(User).filter(User.user_id == user.user_id).first()
    if u is None:
        raise HTTPException(status_code=404, detail="User not found")
    return _user_public(u)


@router.post("/recover-password", response_model=RecoverPasswordResponse)
def recover_password(body: RecoverPasswordRequest, db: Session = Depends(get_db)) -> RecoverPasswordResponse:
    """Verify username + CCCD. Passwords are hashed (bcrypt) — cannot return old plaintext; issue new temp password."""
    user = db.query(User).filter(User.username == body.username.strip()).first()
    if user is None or user.cccd != body.cccd:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Tên đăng nhập hoặc CCCD không đúng",
        )
    temp = secrets.token_urlsafe(10)[:14]
    user.password = hash_password(temp)
    db.add(user)
    db.commit()
    return RecoverPasswordResponse(
        message=(
            "Mật khẩu trong hệ thống được mã hóa (bcrypt) nên không thể hiển thị mật khẩu cũ. "
            "Sau khi xác thực username và CCCD, hệ thống đã đặt mật khẩu tạm thời mới sau đây."
        ),
        temporary_password=temp,
    )


@router.post("/change-password")
def change_password(
    body: ChangePasswordRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict:
    if body.new_password != body.confirm_password:
        raise HTTPException(status_code=400, detail="Mật khẩu mới và xác nhận không khớp")
    if not verify_password(body.current_password, user.password):
        raise HTTPException(status_code=400, detail="Mật khẩu hiện tại không đúng")
    if body.new_password == body.current_password:
        raise HTTPException(status_code=400, detail="Mật khẩu mới phải khác mật khẩu hiện tại")
    user.password = hash_password(body.new_password)
    db.add(user)
    db.commit()
    return {"ok": True, "message": "Đổi mật khẩu thành công"}
