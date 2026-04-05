from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, Integer, Numeric, String
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
    location: Mapped[str | None] = mapped_column(String(255), nullable=True)
    device_type: Mapped[str | None] = mapped_column(String(45), nullable=True)
    last_reading_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True)
    last_reading_value: Mapped[Decimal | None] = mapped_column(Numeric(12, 4), nullable=True)
    last_reading_unit: Mapped[str | None] = mapped_column(String(32), nullable=True)
