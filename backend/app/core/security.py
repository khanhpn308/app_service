"""
Bảo mật: mật khẩu (bcrypt) và JWT.

- **hash_password / verify_password**: bcrypt — salt tự động, không lưu plaintext.
- **create_access_token**: tạo JWT ký **đối xứng** bằng ``jwt_secret`` (thuật toán ``HS256``).
- **decode_token**: giải mã và kiểm tra chữ ký + hạn ``exp``.

Trường chuẩn JWT:
    - **sub** (subject): ở đây là **username** (chuỗi duy nhất đăng nhập).
    - **exp**: thời điểm hết hạn (UTC).
"""

from datetime import UTC, datetime, timedelta

import bcrypt
import jwt

from app.core.config import settings


def hash_password(plain: str) -> str:
    """Băm mật khẩu; trả chuỗi ASCII an toàn để lưu DB (VARCHAR)."""
    return bcrypt.hashpw(plain.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    """So khớp mật khẩu nhập với hash đã lưu; lỗi format trả ``False``."""
    try:
        return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))
    except ValueError:
        return False


def create_access_token(*, subject: str, user_id: int, role: str) -> str:
    """
    Tạo JWT access token (một loại, không refresh token trong project này).

    Args:
        subject: Username (``sub`` trong payload).
        user_id: Khóa chính ``user.user_id`` (``uid`` trong payload).
        role: ``admin`` hoặc ``user``.
    """
    secret = settings.jwt_secret
    expire = datetime.now(tz=UTC) + timedelta(minutes=settings.jwt_expire_minutes)
    payload = {
        "sub": subject,
        "uid": user_id,
        "role": role,
        "exp": expire,
    }
    return jwt.encode(payload, secret, algorithm=settings.jwt_algorithm)


def decode_token(token: str) -> dict:
    """Giải mã JWT; ném exception nếu hết hạn hoặc secret không khớp."""
    return jwt.decode(
        token,
        settings.jwt_secret,
        algorithms=[settings.jwt_algorithm],
    )
