"""REST endpoints for map groups and invitation membership."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, get_db
from app.core.map_access import can_manage_group, can_view_group, is_user_active
from app.models.map_group import MapGroup, MapGroupMembership
from app.models.map_location import LocationUsing
from app.models.user import User
from app.schemas.map_groups import GroupCreate, GroupPatch, GroupPublic


router = APIRouter(prefix="/map-groups", tags=["map-groups"])


def _is_admin(user: User) -> bool:
    return user.role == "admin"


def _owner_or_404(db: Session, group: MapGroup) -> User:
    owner = db.get(User, group.owner_user_id)
    if owner is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy chủ sở hữu nhóm")
    return owner


def _group_public(
    db: Session,
    group: MapGroup,
    actor: User,
) -> GroupPublic:
    owner = _owner_or_404(db, group)
    if _is_admin(actor):
        access_role = "admin"
    elif actor.user_id == group.owner_user_id:
        access_role = "owner"
    else:
        access_role = "member"
    return GroupPublic(
        group_id=group.group_id,
        name=group.name,
        owner_user_id=group.owner_user_id,
        owner_username=owner.username,
        created_by_user_id=group.created_by_user_id,
        created_at=group.created_at,
        updated_at=group.updated_at,
        access_role=access_role,
        can_manage=can_manage_group(actor, group),
    )


def _manageable_group_or_404(
    db: Session,
    group_id: int,
    actor: User,
) -> MapGroup:
    group = db.get(MapGroup, group_id)
    if group is None or not can_manage_group(actor, group):
        raise HTTPException(status_code=404, detail="Không tìm thấy nhóm")
    return group


def _duplicate_name(
    db: Session,
    owner_user_id: int,
    name: str,
    *,
    exclude_group_id: int | None = None,
) -> bool:
    query = db.query(MapGroup).filter(
        MapGroup.owner_user_id == owner_user_id,
        func.lower(MapGroup.name) == name.lower(),
    )
    if exclude_group_id is not None:
        query = query.filter(MapGroup.group_id != exclude_group_id)
    return query.first() is not None


@router.get("", response_model=list[GroupPublic])
def list_groups(
    db: Session = Depends(get_db),
    actor: User = Depends(get_current_user),
) -> list[GroupPublic]:
    """List every admin group or visible owner/accepted-member groups."""
    if _is_admin(actor):
        groups = db.query(MapGroup).order_by(MapGroup.group_id.asc()).all()
    else:
        if not is_user_active(actor):
            raise HTTPException(status_code=403, detail="Tài khoản không còn hiệu lực")
        member_group_ids = [
            group_id
            for (group_id,) in db.query(MapGroupMembership.group_id)
            .filter(
                MapGroupMembership.user_id == actor.user_id,
                MapGroupMembership.status == "accepted",
            )
            .all()
        ]
        groups = (
            db.query(MapGroup)
            .filter(
                (MapGroup.owner_user_id == actor.user_id)
                | (MapGroup.group_id.in_(member_group_ids))
            )
            .order_by(MapGroup.group_id.asc())
            .all()
        )
        groups = [group for group in groups if can_view_group(db, actor, group)]
    return [_group_public(db, group, actor) for group in groups]


@router.post("", response_model=GroupPublic, status_code=status.HTTP_201_CREATED)
def create_group(
    body: GroupCreate,
    db: Session = Depends(get_db),
    actor: User = Depends(get_current_user),
) -> GroupPublic:
    """Create a group for self, or for an exact owner username as admin."""
    if _is_admin(actor):
        owner = (
            db.query(User).filter(User.username == body.owner_username).first()
            if body.owner_username
            else actor
        )
        if owner is None:
            raise HTTPException(status_code=404, detail="Không tìm thấy owner")
    else:
        if not is_user_active(actor):
            raise HTTPException(status_code=403, detail="Tài khoản không còn hiệu lực")
        if body.owner_username and body.owner_username != actor.username:
            raise HTTPException(status_code=403, detail="Không được tạo nhóm cho user khác")
        owner = actor

    if _duplicate_name(db, owner.user_id, body.name):
        raise HTTPException(status_code=409, detail="Tên nhóm đã tồn tại")

    group = MapGroup(
        name=body.name,
        owner_user_id=owner.user_id,
        created_by_user_id=actor.user_id,
    )
    db.add(group)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="Tên nhóm đã tồn tại") from exc
    db.refresh(group)
    return _group_public(db, group, actor)


@router.patch("/{group_id}", response_model=GroupPublic)
def rename_group(
    group_id: int,
    body: GroupPatch,
    db: Session = Depends(get_db),
    actor: User = Depends(get_current_user),
) -> GroupPublic:
    """Rename a managed group while preserving per-owner uniqueness."""
    group = _manageable_group_or_404(db, group_id, actor)
    if _duplicate_name(
        db,
        group.owner_user_id,
        body.name,
        exclude_group_id=group.group_id,
    ):
        raise HTTPException(status_code=409, detail="Tên nhóm đã tồn tại")
    group.name = body.name
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="Tên nhóm đã tồn tại") from exc
    db.refresh(group)
    return _group_public(db, group, actor)


@router.delete("/{group_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_empty_group(
    group_id: int,
    db: Session = Depends(get_db),
    actor: User = Depends(get_current_user),
) -> None:
    """Delete an empty managed group; map cascade belongs to Phase 4."""
    group = _manageable_group_or_404(db, group_id, actor)
    has_active_maps = (
        db.query(LocationUsing.location_id)
        .filter(LocationUsing.group_id == group.group_id)
        .first()
        is not None
    )
    if has_active_maps:
        raise HTTPException(
            status_code=409,
            detail="Nhóm còn bản đồ đang sử dụng; cần archive trước khi xóa",
        )
    db.delete(group)
    db.commit()
