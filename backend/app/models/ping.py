"""Persistence models for application-level ESP32 ping sequence tracking."""

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    ForeignKey,
    Index,
    Integer,
    UniqueConstraint,
    and_,
    column,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


def _autoincrement_bigint():
    """Use BIGINT on MySQL and an SQLite-compatible integer primary key in tests."""

    return BigInteger().with_variant(Integer, "sqlite")


class PingPayload(Base):
    """One validated ping received from an ESP32 Node."""

    __tablename__ = "ping_payload"
    __table_args__ = (
        CheckConstraint("cycle_id >= 1", name="ck_ping_payload_cycle_id"),
        CheckConstraint(
            and_(column("order") >= 1, column("order") <= 4294967295),
            name="ck_ping_payload_order",
        ),
        CheckConstraint(
            "node_timestamp_ms >= 0", name="ck_ping_payload_node_timestamp_ms"
        ),
        Index("idx_ping_payload_device_id_id", "device_id", "id"),
        Index(
            "idx_ping_payload_device_cycle_order", "device_id", "cycle_id", "order"
        ),
        {
            "mysql_charset": "utf8mb4",
            "mysql_collate": "utf8mb4_0900_ai_ci",
            "sqlite_autoincrement": True,
        },
    )

    id: Mapped[int] = mapped_column(
        _autoincrement_bigint(), primary_key=True, autoincrement=True
    )
    device_id: Mapped[int] = mapped_column(
        ForeignKey(
            "device.device_id",
            name="fk_ping_payload_device",
            ondelete="CASCADE",
            onupdate="CASCADE",
        ),
        nullable=False,
    )
    cycle_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    order: Mapped[int] = mapped_column(BigInteger, nullable=False)
    node_timestamp_ms: Mapped[int] = mapped_column(BigInteger, nullable=False)


class MissingPingPayload(Base):
    """A missing ping order inferred within one device reset cycle."""

    __tablename__ = "missing_ping_payload"
    __table_args__ = (
        CheckConstraint("cycle_id >= 1", name="ck_missing_ping_payload_cycle_id"),
        CheckConstraint(
            "payload_id >= 1 AND payload_id <= 4294967295",
            name="ck_missing_ping_payload_payload_id",
        ),
        UniqueConstraint(
            "device_id",
            "cycle_id",
            "payload_id",
            name="uq_missing_ping_payload_device_cycle_payload",
        ),
        Index("idx_missing_ping_payload_device_id_id", "device_id", "id"),
        {
            "mysql_charset": "utf8mb4",
            "mysql_collate": "utf8mb4_0900_ai_ci",
            "sqlite_autoincrement": True,
        },
    )

    id: Mapped[int] = mapped_column(
        _autoincrement_bigint(), primary_key=True, autoincrement=True
    )
    payload_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    device_id: Mapped[int] = mapped_column(
        ForeignKey(
            "device.device_id",
            name="fk_missing_ping_payload_device",
            ondelete="CASCADE",
            onupdate="CASCADE",
        ),
        nullable=False,
    )
    cycle_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
