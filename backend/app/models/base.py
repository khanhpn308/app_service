"""
Lớp cơ sở cho mọi model SQLAlchemy 2.0 (DeclarativeBase).

``Base.metadata.create_all`` trong ``main.lifespan`` dùng metadata này để tạo bảng thiếu.
Không đặt logic chung ở đây — chỉ anchor cho ORM.
"""

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Registry metadata cho tất cả bảng trong package ``app.models``."""

    pass
