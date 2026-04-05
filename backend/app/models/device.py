from sqlalchemy import Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class Device(Base):
    __tablename__ = "device"

    device_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    devicename: Mapped[str | None] = mapped_column(String(45), nullable=True)
    password: Mapped[str | None] = mapped_column(String(45), nullable=True)
    status: Mapped[str | None] = mapped_column(String(10), nullable=True)
    # Legacy NOT NULL column from original schema (name is misspelled "asignment").
    # Not used for RBAC: which user may access which device is in `device_authorization`.
    # New devices typically store 0 here; keep the column for DB compatibility.
    user_device_asignment_id: Mapped[int] = mapped_column(Integer, nullable=False)
    # Static display / classification only. Live telemetry comes from MQTT/payload, not stored here.
    location: Mapped[str | None] = mapped_column(String(255), nullable=True)
    device_type: Mapped[str | None] = mapped_column(String(45), nullable=True)
