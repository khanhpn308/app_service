from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class TestLog(Base):
    __tablename__ = "test_logs"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    protocol: Mapped[str] = mapped_column(String(32), nullable=False)
    version: Mapped[int | None] = mapped_column(Integer, nullable=True)
    message_len: Mapped[int | None] = mapped_column(Integer, nullable=True)
    message: Mapped[str | None] = mapped_column(Text, nullable=True)
    node_id_len: Mapped[int | None] = mapped_column(Integer, nullable=True)
    node_id: Mapped[str] = mapped_column(String(128), nullable=False)
    device_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    gateway_id_len: Mapped[int | None] = mapped_column(Integer, nullable=True)
    gateway_id: Mapped[str] = mapped_column(String(128), nullable=False)
    event_timestamp_ms: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    gateway_timestamp_ms: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    mark_time_ms: Mapped[int] = mapped_column(BigInteger, nullable=False)
    delay_gateway_to_server_ms: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    rssi: Mapped[int | None] = mapped_column(Integer, nullable=True)
    src_mac: Mapped[str | None] = mapped_column(String(17), nullable=True)
    topic: Mapped[str | None] = mapped_column(String(255), nullable=True)
    raw_hex: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=func.current_timestamp(),
    )
