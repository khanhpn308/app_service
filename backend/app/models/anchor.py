"""Persistence models for Anchor configuration snapshots and gateway delivery."""

from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    JSON,
    BigInteger,
    CheckConstraint,
    DECIMAL,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.mysql import DATETIME as MYSQL_DATETIME
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


def _datetime_6():
    """Use microsecond precision on MySQL while remaining portable to SQLite tests."""

    return DateTime().with_variant(MYSQL_DATETIME(fsp=6), "mysql")


class Anchor(Base):
    """An Anchor positioned on one active floor map with a canonical MAC identity."""

    __tablename__ = "anchor"
    __table_args__ = (
        UniqueConstraint("hardware_id", name="uq_anchor_hardware_id"),
        UniqueConstraint("mac_address", name="uq_anchor_mac_address"),
        UniqueConstraint(
            "location_id", "name_key", name="uq_anchor_location_name_key"
        ),
        CheckConstraint("x >= 0 AND x <= 100", name="ck_anchor_x"),
        CheckConstraint("y >= 0 AND y <= 100", name="ck_anchor_y"),
        Index("idx_anchor_location_status_id", "location_id", "status", "anchor_id"),
        Index("idx_anchor_created_by", "created_by_user_id"),
        Index("idx_anchor_updated_by", "updated_by_user_id"),
        Index("idx_anchor_deleted_by", "deleted_by_user_id"),
        {
            "mysql_charset": "utf8mb4",
            "mysql_collate": "utf8mb4_0900_ai_ci",
            "sqlite_autoincrement": True,
        },
    )

    anchor_id: Mapped[int] = mapped_column(
        Integer, primary_key=True, autoincrement=True
    )
    hardware_id: Mapped[str] = mapped_column(String(64), nullable=False)
    # Transitional canonical identity. Legacy rows keep their original hardware_id
    # until an operator supplies a valid MAC Address through the Anchor editor.
    mac_address: Mapped[str | None] = mapped_column(String(17), nullable=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    name_key: Mapped[str | None] = mapped_column(String(100), nullable=True)
    x: Mapped[Decimal] = mapped_column(
        DECIMAL(7, 4), nullable=False, server_default=text("50.0000")
    )
    y: Mapped[Decimal] = mapped_column(
        DECIMAL(7, 4), nullable=False, server_default=text("50.0000")
    )
    z: Mapped[Decimal] = mapped_column(
        DECIMAL(10, 3), nullable=False, server_default=text("0.000")
    )
    # Snapshot identifier: map lifecycle archives/deletes the active location while
    # inactive Anchor rows remain available for audit.
    location_id: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(
        Enum(
            "active",
            "inactive",
            name="anchor_status",
            create_constraint=True,
        ),
        nullable=False,
        server_default="active",
    )
    created_by_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("user.user_id", ondelete="SET NULL", onupdate="CASCADE"),
        nullable=True,
    )
    updated_by_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("user.user_id", ondelete="SET NULL", onupdate="CASCADE"),
        nullable=True,
    )
    deleted_by_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("user.user_id", ondelete="SET NULL", onupdate="CASCADE"),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        _datetime_6(), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        _datetime_6(), nullable=False, server_default=func.now(), onupdate=func.now()
    )
    deleted_at: Mapped[datetime | None] = mapped_column(_datetime_6(), nullable=True)


class AnchorConfigOutbox(Base):
    """Immutable full snapshot committed atomically with an Anchor mutation."""

    __tablename__ = "anchor_config_outbox"
    __table_args__ = (
        Index("idx_anchor_outbox_location_revision", "location_id", "revision"),
        Index("idx_anchor_outbox_status_revision", "status", "revision"),
        Index("idx_anchor_outbox_created_by", "created_by_user_id"),
        {"mysql_charset": "utf8mb4", "mysql_collate": "utf8mb4_0900_ai_ci"},
    )

    revision: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"),
        primary_key=True,
        autoincrement=True,
    )
    # Snapshot identifier only: deliberately no FK so parent map archival cannot erase it.
    location_id: Mapped[int] = mapped_column(Integer, nullable=False)
    location: Mapped[str] = mapped_column(String(255), nullable=False)
    # Null means a map-wide mutation; non-null targets bootstrap/resync to one Gateway.
    target_gateway_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    reason: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(
        Enum(
            "pending",
            "completed",
            "failed",
            "superseded",
            name="anchor_outbox_status",
            create_constraint=True,
        ),
        nullable=False,
        server_default="pending",
    )
    created_by_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("user.user_id", ondelete="SET NULL", onupdate="CASCADE"),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        _datetime_6(), nullable=False, server_default=func.now()
    )
    completed_at: Mapped[datetime | None] = mapped_column(_datetime_6(), nullable=True)
    superseded_at: Mapped[datetime | None] = mapped_column(
        _datetime_6(), nullable=True
    )


class AnchorConfigDelivery(Base):
    """Per-gateway delivery and acknowledgement state for one snapshot revision."""

    __tablename__ = "anchor_config_delivery"
    __table_args__ = (
        UniqueConstraint(
            "revision", "gateway_id", name="uq_anchor_delivery_revision_gateway"
        ),
        Index("idx_anchor_delivery_status_retry", "status", "next_attempt_at"),
        Index("idx_anchor_delivery_gateway_revision", "gateway_id", "revision"),
        {"mysql_charset": "utf8mb4", "mysql_collate": "utf8mb4_0900_ai_ci"},
    )

    delivery_id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"),
        primary_key=True,
        autoincrement=True,
    )
    revision: Mapped[int] = mapped_column(
        ForeignKey(
            "anchor_config_outbox.revision", ondelete="CASCADE", onupdate="CASCADE"
        ),
        nullable=False,
    )
    # Snapshot identifier only: deliberately no device FK so delivery audit survives.
    gateway_id: Mapped[int] = mapped_column(Integer, nullable=False)
    publish_topic: Mapped[str | None] = mapped_column(String(255), nullable=True)
    # Immutable wire payload composed specifically for this Gateway/revision.
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    status: Mapped[str] = mapped_column(
        Enum(
            "pending",
            "published",
            "applied",
            "rejected",
            "misconfigured",
            "superseded",
            name="anchor_delivery_status",
            create_constraint=True,
        ),
        nullable=False,
        server_default="pending",
    )
    attempt_count: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("0")
    )
    next_attempt_at: Mapped[datetime | None] = mapped_column(
        _datetime_6(), nullable=True
    )
    lease_until: Mapped[datetime | None] = mapped_column(_datetime_6(), nullable=True)
    leased_by: Mapped[str | None] = mapped_column(String(100), nullable=True)
    published_at: Mapped[datetime | None] = mapped_column(_datetime_6(), nullable=True)
    acked_at: Mapped[datetime | None] = mapped_column(_datetime_6(), nullable=True)
    last_error: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        _datetime_6(), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        _datetime_6(), nullable=False, server_default=func.now(), onupdate=func.now()
    )
