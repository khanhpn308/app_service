"""Atomic archive operation for active floorplans."""

from enum import Enum

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.map_group import MapGroup
from app.models.map_location import LocationDeleted, LocationUsing
from app.models.user import User
from app.services.anchor_service import archive_location_anchors


class DeleteReason(str, Enum):
    MAP_DELETED = "map_deleted"
    GROUP_DELETED = "group_deleted"
    OWNER_DELETED = "owner_deleted"


class LocationArchiveError(RuntimeError):
    """Raised when an active location cannot be archived."""

    def __init__(self, code: str, message: str):
        self.code = code
        super().__init__(message)


def archive_location(
    db: Session,
    location_id: int,
    *,
    deleted_by: User,
    reason: DeleteReason,
) -> LocationDeleted:
    """Copy one locked active row to history, then delete it.

    The caller owns the surrounding transaction and must commit or roll back.
    """
    if not isinstance(reason, DeleteReason):
        raise LocationArchiveError(
            "invalid_delete_reason",
            "The archive delete reason is not supported.",
        )
    if deleted_by.user_id is None or not deleted_by.username:
        raise LocationArchiveError(
            "invalid_deleted_by",
            "A persisted user is required to archive a location.",
        )

    active = db.execute(
        select(LocationUsing)
        .where(LocationUsing.location_id == location_id)
        .with_for_update()
    ).scalar_one_or_none()
    if active is None:
        raise LocationArchiveError(
            "location_not_found",
            "The active location does not exist.",
        )

    group = db.get(MapGroup, active.group_id)
    owner = db.get(User, active.owner_user_id)
    creator = (
        db.get(User, active.created_by_user_id)
        if active.created_by_user_id is not None
        else None
    )
    if group is None or owner is None:
        raise LocationArchiveError(
            "archive_context_missing",
            "The active location is missing its group or owner.",
        )

    archive_location_anchors(
        db,
        active,
        deleted_by,
        reason=reason.value,
    )

    archived = LocationDeleted(
        location_id=active.location_id,
        location=active.location,
        image_data=active.image_data,
        mime_type=active.mime_type,
        original_filename=active.original_filename,
        checksum_sha256=active.checksum_sha256,
        file_size_bytes=active.file_size_bytes,
        width=active.width,
        height=active.height,
        group_id_snapshot=active.group_id,
        group_name_snapshot=group.name,
        owner_user_id_snapshot=active.owner_user_id,
        owner_username_snapshot=owner.username,
        created_by_user_id_snapshot=active.created_by_user_id,
        created_by_username_snapshot=creator.username if creator else None,
        created_at=active.created_at,
        deleted_by_user_id_snapshot=deleted_by.user_id,
        deleted_by_username_snapshot=deleted_by.username,
        delete_reason=reason.value,
    )
    db.add(archived)
    db.flush()
    db.delete(active)
    db.flush()
    return archived
