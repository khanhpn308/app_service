"""SQLAlchemy models for active and archived WebP floorplans."""

from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    LargeBinary,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.mysql import MEDIUMBLOB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


def _image_blob_type():
    return LargeBinary().with_variant(MEDIUMBLOB(), "mysql")


class LocationUsing(Base):
    """An active floorplan; only this table is queried by GPS views."""

    __tablename__ = "locations_using"
    __table_args__ = (
        UniqueConstraint("location", name="uq_locations_using_location"),
        CheckConstraint("width = 800", name="ck_locations_using_width"),
        CheckConstraint(
            "height BETWEEN 1 AND 8000", name="ck_locations_using_height"
        ),
        CheckConstraint(
            "file_size_bytes BETWEEN 1 AND 5242880",
            name="ck_locations_using_file_size",
        ),
        Index("idx_locations_using_group", "group_id"),
        Index("idx_locations_using_owner", "owner_user_id"),
        {
            "mysql_charset": "utf8mb4",
            "mysql_collate": "utf8mb4_0900_ai_ci",
            "sqlite_autoincrement": True,
        },
    )

    location_id: Mapped[int] = mapped_column(
        Integer, primary_key=True, autoincrement=True
    )
    location: Mapped[str] = mapped_column(String(255), nullable=False)
    image_data: Mapped[bytes] = mapped_column(_image_blob_type(), nullable=False)
    mime_type: Mapped[str] = mapped_column(
        String(50), nullable=False, server_default="image/webp"
    )
    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    checksum_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    file_size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    width: Mapped[int] = mapped_column(Integer, nullable=False)
    height: Mapped[int] = mapped_column(Integer, nullable=False)
    group_id: Mapped[int] = mapped_column(
        ForeignKey("map_group.group_id", ondelete="RESTRICT", onupdate="CASCADE"),
        nullable=False,
    )
    owner_user_id: Mapped[int] = mapped_column(
        ForeignKey("user.user_id", ondelete="RESTRICT", onupdate="CASCADE"),
        nullable=False,
    )
    created_by_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("user.user_id", ondelete="SET NULL", onupdate="CASCADE"),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now()
    )


class LocationDeleted(Base):
    """Immutable archive row with snapshots and no foreign-key dependencies."""

    __tablename__ = "locations_deleted"
    __table_args__ = (
        CheckConstraint("width = 800", name="ck_locations_deleted_width"),
        CheckConstraint(
            "height BETWEEN 1 AND 8000", name="ck_locations_deleted_height"
        ),
        CheckConstraint(
            "delete_reason IN ('map_deleted', 'group_deleted', 'owner_deleted')",
            name="ck_locations_deleted_reason",
        ),
        Index("idx_locations_deleted_location", "location"),
        Index("idx_locations_deleted_owner", "owner_user_id_snapshot"),
        Index("idx_locations_deleted_deleted_at", "deleted_at"),
        {"mysql_charset": "utf8mb4", "mysql_collate": "utf8mb4_0900_ai_ci"},
    )

    location_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    location: Mapped[str] = mapped_column(String(255), nullable=False)
    image_data: Mapped[bytes] = mapped_column(_image_blob_type(), nullable=False)
    mime_type: Mapped[str] = mapped_column(String(50), nullable=False)
    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    checksum_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    file_size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    width: Mapped[int] = mapped_column(Integer, nullable=False)
    height: Mapped[int] = mapped_column(Integer, nullable=False)
    group_id_snapshot: Mapped[int] = mapped_column(Integer, nullable=False)
    group_name_snapshot: Mapped[str] = mapped_column(String(100), nullable=False)
    owner_user_id_snapshot: Mapped[int] = mapped_column(Integer, nullable=False)
    owner_username_snapshot: Mapped[str] = mapped_column(String(45), nullable=False)
    created_by_user_id_snapshot: Mapped[int | None] = mapped_column(
        Integer, nullable=True
    )
    created_by_username_snapshot: Mapped[str | None] = mapped_column(
        String(45), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    deleted_by_user_id_snapshot: Mapped[int] = mapped_column(Integer, nullable=False)
    deleted_by_username_snapshot: Mapped[str] = mapped_column(
        String(45), nullable=False
    )
    deleted_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now()
    )
    delete_reason: Mapped[str] = mapped_column(String(20), nullable=False)
