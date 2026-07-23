"""Transactional lifecycle operations for map groups and owners."""

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.core.map_archive import DeleteReason, archive_location
from app.models.device_authorization import DeviceAuthorization
from app.models.map_group import MapGroup, MapGroupMembership
from app.models.map_location import LocationUsing
from app.models.user import User


class MapLifecycleError(RuntimeError):
    """Raised when a lifecycle target disappears during a transaction."""


def archive_and_delete_group(
    db: Session,
    group_id: int,
    *,
    deleted_by: User,
    reason: DeleteReason = DeleteReason.GROUP_DELETED,
) -> None:
    """Archive all active maps, remove memberships and delete one locked group."""
    group = db.execute(
        select(MapGroup)
        .where(MapGroup.group_id == group_id)
        .with_for_update()
    ).scalar_one_or_none()
    if group is None:
        raise MapLifecycleError("The map group no longer exists.")

    location_ids = db.execute(
        select(LocationUsing.location_id)
        .where(LocationUsing.group_id == group.group_id)
        .order_by(LocationUsing.location_id.asc())
        .with_for_update()
    ).scalars().all()
    for location_id in location_ids:
        archive_location(
            db,
            location_id,
            deleted_by=deleted_by,
            reason=reason,
        )

    db.query(MapGroupMembership).filter(
        MapGroupMembership.group_id == group.group_id
    ).delete(synchronize_session=False)
    db.delete(group)
    db.flush()


def delete_user_with_map_lifecycle(
    db: Session,
    user_id: int,
    *,
    deleted_by: User,
) -> None:
    """Archive owned maps, delete owned groups and remove map references to a user."""
    target = db.execute(
        select(User).where(User.user_id == user_id).with_for_update()
    ).scalar_one_or_none()
    if target is None:
        raise MapLifecycleError("The user no longer exists.")

    owned_group_ids = db.execute(
        select(MapGroup.group_id)
        .where(MapGroup.owner_user_id == target.user_id)
        .order_by(MapGroup.group_id.asc())
        .with_for_update()
    ).scalars().all()
    for group_id in owned_group_ids:
        archive_and_delete_group(
            db,
            group_id,
            deleted_by=deleted_by,
            reason=DeleteReason.OWNER_DELETED,
        )

    db.query(MapGroupMembership).filter(
        MapGroupMembership.user_id == target.user_id
    ).delete(synchronize_session=False)
    db.execute(
        update(MapGroupMembership)
        .where(MapGroupMembership.invited_by_user_id == target.user_id)
        .values(invited_by_user_id=None)
    )
    db.execute(
        update(MapGroup)
        .where(MapGroup.created_by_user_id == target.user_id)
        .values(created_by_user_id=None)
    )
    db.execute(
        update(LocationUsing)
        .where(LocationUsing.created_by_user_id == target.user_id)
        .values(created_by_user_id=None)
    )
    db.query(DeviceAuthorization).filter(
        DeviceAuthorization.user_id == target.user_id
    ).delete(synchronize_session=False)
    db.delete(target)
    db.flush()
