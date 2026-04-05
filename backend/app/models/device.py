from sqlalchemy import Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class Device(Base):
    __tablename__ = "device"

    device_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    devicename: Mapped[str | None] = mapped_column(String(45), nullable=True)
    password: Mapped[str | None] = mapped_column(String(45), nullable=True)
    status: Mapped[str | None] = mapped_column(String(10), nullable=True)
    # Required by current MySQL schema (NOT NULL). Semantics unclear; keep as int.
    user_device_asignment_id: Mapped[int] = mapped_column(Integer, nullable=False)
