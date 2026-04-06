"""
Phụ thuộc FastAPI (dependency injection) dùng chung cho route.

- **get_db**: cấp ``Session`` SQLAlchemy; đóng session sau request.
- **get_current_user**: đọc JWT từ header ``Authorization: Bearer``, tra user trong DB.
- **require_admin**: bảo vệ route chỉ dành cho ``user.role == "admin"``.

Viết tắt:
    - **HTTPBearer**: scheme HTTP Bearer (RFC 6750) — FastAPI lấy token từ header.
"""

from collections.abc import Generator

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.db import SessionLocal
from app.core.security import decode_token
from app.models.user import User

security = HTTPBearer(auto_error=False)


def get_db() -> Generator[Session, None, None]:
    """
    Yield một session DB; ``finally`` đảm bảo ``close()`` sau khi response trả về.

    Dùng: ``db: Session = Depends(get_db)`` trên mọi route cần truy vấn ORM.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_current_user(
    db: Session = Depends(get_db),
    creds: HTTPAuthorizationCredentials | None = Depends(security),
) -> User:
    """
    Xác thực JWT và trả về bản ghi ``User`` hiện tại.

    Payload JWT (xem ``security.create_access_token``):
        - ``sub``: username (không phải user_id).
        - ``uid``, ``role``: tiện cho client; server vẫn load user từ DB theo ``sub``.

    Raises:
        HTTPException 401 nếu thiếu token, token sai/hết hạn, hoặc user không tồn tại.
    """
    if creds is None or not creds.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
        )
    try:
        payload = decode_token(creds.credentials)
    except Exception as exc:  # noqa: BLE001 — jwt decode: trả 401 thống nhất
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        ) from exc
    username = payload.get("sub")
    if not username:
        raise HTTPException(status_code=401, detail="Invalid token payload")
    user = db.query(User).filter(User.username == username).first()
    if user is None:
        raise HTTPException(status_code=401, detail="User not found")
    return user


def require_admin(user: User = Depends(get_current_user)) -> User:
    """
    Giống ``get_current_user`` nhưng trả 403 nếu ``role`` không phải ``admin``.

    Dùng cho quản lý user/thiết bị/phân quyền hàng loạt.
    """
    if user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin role required",
        )
    return user
