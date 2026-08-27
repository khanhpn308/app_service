"""Shared authorization rules for map groups."""

from datetime import date

from sqlalchemy.orm import Session

from app.models.map_group import MapGroup, MapGroupMembership
from app.models.user import User


ACTIVE_STATUS = "active"
ADMIN_ROLE = "admin"
ACCEPTED_MEMBERSHIP = "accepted"


def _is_admin(user: User) -> bool:
    return (user.role or "").lower() == ADMIN_ROLE


def is_user_active(user: User, *, today: date | None = None) -> bool:
    """Return whether an account may use non-admin map capabilities."""
    if (user.status or "").lower() != ACTIVE_STATUS:
        return False

    current_day = today or date.today()
    return user.expired_at is None or user.expired_at > current_day


def can_manage_group(
    user: User,
    group: MapGroup,
    *,
    today: date | None = None,
) -> bool:
    """Admins manage every group; active owners manage their own group."""
    if _is_admin(user):
        return True
    return (
        is_user_active(user, today=today)
        and user.user_id == group.owner_user_id
    )


def can_config_anchor(
    user: User,
    group: MapGroup,
    *,
    today: date | None = None,
) -> bool:
    """Admins bypass the flag; regular users must be active owners with the flag."""
    if _is_admin(user):
        return True
    return (
        is_user_active(user, today=today)
        and user.user_id == group.owner_user_id
        and user.can_config_anchor == "yes"
    )


def can_view_group(
    db: Session,
    user: User,
    group: MapGroup,
    *,
    today: date | None = None,
) -> bool:
    """Apply owner-state visibility and accepted-membership rules."""
    if _is_admin(user):
        return True
    if not is_user_active(user, today=today):
        return False

    owner = (
        user
        if user.user_id == group.owner_user_id
        else db.get(User, group.owner_user_id)
    )
    if owner is None or not is_user_active(owner, today=today):
        return False
    if user.user_id == group.owner_user_id:
        return True

    membership = db.get(
        MapGroupMembership,
        (group.group_id, user.user_id),
    )
    return (
        membership is not None
        and membership.status == ACCEPTED_MEMBERSHIP
    )
