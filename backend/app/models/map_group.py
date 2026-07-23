"""SQLAlchemy models for map sharing groups and invitation membership."""

from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Integer, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class MapGroup(Base):
    """A named map collection owned by exactly one user."""

    __tablename__ = "map_group"
    __table_args__ = (
        UniqueConstraint("owner_user_id", "name", name="uq_map_group_owner_name"),
        Index("idx_map_group_owner", "owner_user_id"),
        {"mysql_charset": "utf8mb4", "mysql_collate": "utf8mb4_0900_ai_ci"},
    )

    group_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
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
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now(), onupdate=func.now()
    )


class MapGroupMembership(Base):
    """Invitation state and accepted membership for a user in a map group."""

    __tablename__ = "map_group_membership"
    __table_args__ = (
        CheckConstraint(
            "status IN ('pending', 'accepted', 'rejected')",
            name="ck_map_group_membership_status",
        ),
        Index("idx_map_group_membership_user_status", "user_id", "status"),
        {"mysql_charset": "utf8mb4", "mysql_collate": "utf8mb4_0900_ai_ci"},
    )

    group_id: Mapped[int] = mapped_column(
        ForeignKey("map_group.group_id", ondelete="CASCADE", onupdate="CASCADE"),
        primary_key=True,
    )
    user_id: Mapped[int] = mapped_column(
        ForeignKey("user.user_id", ondelete="CASCADE", onupdate="CASCADE"),
        primary_key=True,
    )
    status: Mapped[str] = mapped_column(
        String(10), nullable=False, server_default="pending"
    )
    invited_by_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("user.user_id", ondelete="SET NULL", onupdate="CASCADE"),
        nullable=True,
    )
    invited_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now()
    )
    responded_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
