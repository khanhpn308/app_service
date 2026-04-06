"""
Kết nối SQLAlchemy tới MySQL.

- **engine**: pool kết nối, ``pool_pre_ping`` tránh dùng connection đã chết.
- **SessionLocal**: factory session ORM (mỗi request thường lấy một session qua ``get_db`` trong ``deps.py``).

Hàm ``_pymysql_connect`` dùng PyMySQL trực tiếp (tránh lỗi encode/mật khẩu đặc biệt trong URL).
"""

import time

import pymysql
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import sessionmaker

from app.core.config import settings


def _pymysql_connect():
    """Tạo raw connection PyMySQL — khớp test thủ công, tránh quirks của URL."""
    return pymysql.connect(
        host=settings.db_host,
        port=settings.db_port,
        user=settings.db_user,
        password=settings.db_password,
        database=settings.db_name,
        charset="utf8mb4",
    )


def get_engine() -> Engine:
    """Xây SQLAlchemy Engine với ``creator`` tùy chỉnh (không dùng chuỗi URL đầy đủ)."""
    return create_engine(
        "mysql+pymysql://",
        creator=_pymysql_connect,
        pool_size=20,
        max_overflow=10,
        pool_pre_ping=True,
    )


engine = get_engine()
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def db_ping() -> float:
    """
    Kiểm tra DB còn sống và đo độ trễ (ms).

    Returns:
        Thời gian round-trip ``SELECT 1`` tính bằng millisecond, làm tròn 2 chữ số thập phân.
    """
    started_at = time.perf_counter()
    with engine.connect() as conn:
        conn.execute(text("SELECT 1"))
    latency_ms = (time.perf_counter() - started_at) * 1000
    return round(latency_ms, 2)
