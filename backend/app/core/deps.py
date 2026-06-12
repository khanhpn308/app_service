"""
Phụ thuộc FastAPI (dependency injection) dùng chung cho route.

- **get_db**: cấp ``Session`` SQLAlchemy; đóng session sau request.
- **get_current_user**: đọc JWT từ header ``Authorization: Bearer``, tra user trong DB.
- **require_admin**: bảo vệ route chỉ dành cho ``user.role == "admin"``.

Viết tắt:
    - **HTTPBearer**: scheme HTTP Bearer (RFC 6750) — FastAPI lấy token từ header.
"""

from collections.abc import Generator

from fastapi import Depends, HTTPException, WebSocket, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.db import SessionLocal
from app.core.security import decode_token, verify_password
from app.models.device import Device
from app.models.user import User

security = HTTPBearer(auto_error=False)


def get_db() -> Generator[Session, None, None]:
    """
    Yield một session DB; rollback nếu request lỗi, luôn ``close()`` sau khi xong.

    Rollback ở đây bảo vệ mọi route: nếu handler raise (kể cả commit fail), session
    được đưa về trạng thái sạch trước khi trả connection về pool.

    Dùng: ``db: Session = Depends(get_db)`` trên mọi route cần truy vấn ORM.
    """
    db = SessionLocal()
    try:
        yield db
    except Exception:
        db.rollback()
        raise
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


def _ws_extract_token(websocket: WebSocket) -> str | None:
    """Lấy JWT từ WebSocket: ưu tiên query ``?access_token=``, fallback header Bearer.

    Frontend không gửi được custom header trong WebSocket handshake của trình duyệt nên
    token thường nằm ở query. Header chỉ dùng được cho client không phải browser.
    """
    token = websocket.query_params.get("access_token")
    if token:
        return token
    auth = websocket.headers.get("authorization") or websocket.headers.get("Authorization")
    if auth and auth.lower().startswith("bearer "):
        return auth[7:].strip()
    return None


async def authenticate_ws_user(websocket: WebSocket) -> User | None:
    """Xác thực WebSocket client (frontend) bằng JWT.

    Trả về ``User`` nếu hợp lệ; nếu không, ``close`` socket với code 1008 (policy violation)
    và trả ``None`` để caller dừng. Truy vấn DB chạy trong thread để không block event loop.
    """
    token = _ws_extract_token(websocket)
    if not token:
        await websocket.close(code=1008)
        return None
    try:
        payload = decode_token(token)
    except Exception:  # noqa: BLE001 — token sai/hết hạn: từ chối thống nhất
        await websocket.close(code=1008)
        return None
    username = payload.get("sub")
    if not isinstance(username, str) or not username.strip():
        await websocket.close(code=1008)
        return None

    import anyio

    def _load() -> User | None:
        with SessionLocal() as db:
            return db.query(User).filter(User.username == username).first()

    user = await anyio.to_thread.run_sync(_load)
    if user is None:
        await websocket.close(code=1008)
        return None
    return user


async def authenticate_ws_device(websocket: WebSocket, device_id: str) -> Device | None:
    """Xác thực kết nối uplink từ thiết bị (ESP32) bằng device credential.

    Credential lấy từ query ``?device_password=`` (hoặc header ``x-device-password``), so khớp
    với ``device.password`` đã hash. Trả ``Device`` nếu hợp lệ, ngược lại ``close(1008)`` + ``None``.
    """
    pwd = websocket.query_params.get("device_password") or websocket.headers.get("x-device-password")
    if not pwd:
        await websocket.close(code=1008)
        return None

    import anyio

    def _load() -> Device | None:
        with SessionLocal() as db:
            try:
                did = int(device_id)
            except (TypeError, ValueError):
                return None
            return db.query(Device).filter(Device.device_id == did).first()

    device = await anyio.to_thread.run_sync(_load)
    if device is None or not device.password or not verify_password(pwd, device.password):
        await websocket.close(code=1008)
        return None
    return device
