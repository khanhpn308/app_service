"""REST endpoints for map groups and invitation membership."""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, status
from slowapi.util import get_remote_address
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, get_db
from app.core.map_access import can_manage_group, can_view_group, is_user_active
from app.core.map_archive import LocationArchiveError
from app.core.map_lifecycle import MapLifecycleError, archive_and_delete_group
from app.core.rate_limit import limiter
from app.core.security import decode_token
from app.models.map_group import MapGroup, MapGroupMembership
from app.models.user import User
from app.schemas.map_groups import (
    GroupCreate,
    GroupPatch,
    GroupPublic,
    InvitationCreate,
    InvitationPatch,
    InvitationPublic,
    MembershipPublic,
)


router = APIRouter(tags=["map-groups"])
group_router = APIRouter(prefix="/map-groups")
invitation_router = APIRouter(prefix="/map-group-invitations")


def _is_admin(user: User) -> bool:
    return (user.role or "").lower() == "admin"


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _invite_rate_key(request: Request) -> str:
    authorization = request.headers.get("authorization", "")
    if authorization.lower().startswith("bearer "):
        try:
            payload = decode_token(authorization[7:].strip())
            identity = payload.get("uid") or payload.get("sub")
            if identity is not None:
                return f"map-invite-user:{identity}"
        except Exception:
            pass
    return f"map-invite-ip:{get_remote_address(request)}"


def _owner_or_404(db: Session, group: MapGroup) -> User:
    owner = db.get(User, group.owner_user_id)
    if owner is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy chủ sở hữu nhóm")
    return owner

def _user_by_exact_username(db: Session, username: str) -> User | None:
    """Preserve exact username semantics even on case-insensitive MySQL collations."""
    user = db.query(User).filter(User.username == username).first()
    return user if user is not None and user.username == username else None


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


@group_router.get("", response_model=list[GroupPublic])
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


@group_router.post("", response_model=GroupPublic, status_code=status.HTTP_201_CREATED)
def create_group(
    body: GroupCreate,
    db: Session = Depends(get_db),
    actor: User = Depends(get_current_user),
) -> GroupPublic:
    """Create a group for self, or for an exact owner username as admin."""
    if _is_admin(actor):
        owner = (
            _user_by_exact_username(db, body.owner_username)
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


@group_router.patch("/{group_id}", response_model=GroupPublic)
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


@group_router.delete("/{group_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_group(
    group_id: int,
    db: Session = Depends(get_db),
    actor: User = Depends(get_current_user),
) -> None:
    """Archive every active map and hard-delete a managed group atomically."""
    group = _manageable_group_or_404(db, group_id, actor)
    try:
        archive_and_delete_group(
            db,
            group.group_id,
            deleted_by=actor,
        )
        db.commit()
    except MapLifecycleError as error:
        db.rollback()
        raise HTTPException(status_code=404, detail="Không tìm thấy nhóm") from error
    except (LocationArchiveError, IntegrityError) as error:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="Không thể archive toàn bộ bản đồ của nhóm",
        ) from error


def _membership_public(
    db: Session,
    membership: MapGroupMembership,
) -> MembershipPublic:
    user = db.get(User, membership.user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy thành viên")
    return MembershipPublic(
        group_id=membership.group_id,
        user_id=membership.user_id,
        username=user.username,
        fullname=user.fullname,
        status=membership.status,
        invited_by_user_id=membership.invited_by_user_id,
        invited_at=membership.invited_at,
        responded_at=membership.responded_at,
    )


@group_router.get("/{group_id}/members", response_model=list[MembershipPublic])
def list_group_members(
    group_id: int,
    db: Session = Depends(get_db),
    actor: User = Depends(get_current_user),
) -> list[MembershipPublic]:
    """List invitation and membership states for group managers."""
    group = _manageable_group_or_404(db, group_id, actor)
    memberships = (
        db.query(MapGroupMembership)
        .filter(MapGroupMembership.group_id == group.group_id)
        .order_by(MapGroupMembership.invited_at.asc(), MapGroupMembership.user_id.asc())
        .all()
    )
    return [_membership_public(db, membership) for membership in memberships]


@group_router.post(
    "/{group_id}/invitations",
    response_model=MembershipPublic,
    status_code=status.HTTP_201_CREATED,
)
@limiter.limit("100/hour", key_func=_invite_rate_key)
def invite_group_member(
    request: Request,
    group_id: int,
    body: InvitationCreate,
    db: Session = Depends(get_db),
    actor: User = Depends(get_current_user),
) -> MembershipPublic:
    """Invite an exact active username or re-open a rejected invitation."""
    group = _manageable_group_or_404(db, group_id, actor)
    target = _user_by_exact_username(db, body.username)
    if target is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy người dùng")
    if target.user_id in {group.owner_user_id, actor.user_id}:
        raise HTTPException(status_code=409, detail="Không thể tự mời vào nhóm")
    if not is_user_active(target):
        raise HTTPException(status_code=409, detail="Tài khoản được mời không còn hiệu lực")

    membership = db.get(
        MapGroupMembership,
        (group.group_id, target.user_id),
    )
    if membership is not None and membership.status != "rejected":
        raise HTTPException(status_code=409, detail="Lời mời hoặc thành viên đã tồn tại")

    invited_at = _utcnow()
    if membership is None:
        membership = MapGroupMembership(
            group_id=group.group_id,
            user_id=target.user_id,
            status="pending",
            invited_by_user_id=actor.user_id,
            invited_at=invited_at,
        )
        db.add(membership)
    else:
        membership.status = "pending"
        membership.invited_by_user_id = actor.user_id
        membership.invited_at = invited_at
        membership.responded_at = None
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="Lời mời hoặc thành viên đã tồn tại",
        ) from exc
    db.refresh(membership)
    return _membership_public(db, membership)


@group_router.delete(
    "/{group_id}/members/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def remove_group_member(
    group_id: int,
    user_id: int,
    db: Session = Depends(get_db),
    actor: User = Depends(get_current_user),
) -> None:
    """Let only a group manager cancel or remove a membership."""
    group = _manageable_group_or_404(db, group_id, actor)
    membership = db.get(MapGroupMembership, (group.group_id, user_id))
    if membership is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy thành viên")
    db.delete(membership)
    db.commit()


def _invitation_public(
    db: Session,
    membership: MapGroupMembership,
) -> InvitationPublic:
    group = db.get(MapGroup, membership.group_id)
    if group is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy nhóm")
    owner = _owner_or_404(db, group)
    return InvitationPublic(
        group_id=group.group_id,
        group_name=group.name,
        owner_username=owner.username,
        status=membership.status,
        invited_at=membership.invited_at,
        responded_at=membership.responded_at,
    )


@invitation_router.get("", response_model=list[InvitationPublic])
def list_my_pending_invitations(
    db: Session = Depends(get_db),
    actor: User = Depends(get_current_user),
) -> list[InvitationPublic]:
    """List pending invitations for the authenticated active user."""
    if not is_user_active(actor):
        raise HTTPException(status_code=403, detail="Tài khoản không còn hiệu lực")
    memberships = (
        db.query(MapGroupMembership)
        .filter(
            MapGroupMembership.user_id == actor.user_id,
            MapGroupMembership.status == "pending",
        )
        .order_by(MapGroupMembership.invited_at.asc())
        .all()
    )
    return [_invitation_public(db, membership) for membership in memberships]


@invitation_router.patch("/{group_id}", response_model=InvitationPublic)
def respond_to_invitation(
    group_id: int,
    body: InvitationPatch,
    db: Session = Depends(get_db),
    actor: User = Depends(get_current_user),
) -> InvitationPublic:
    """Accept or reject the actor's own pending invitation."""
    if not is_user_active(actor):
        raise HTTPException(status_code=403, detail="Tài khoản không còn hiệu lực")
    membership = db.get(MapGroupMembership, (group_id, actor.user_id))
    if membership is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy lời mời")
    if membership.status != "pending":
        raise HTTPException(status_code=409, detail="Lời mời đã được phản hồi")

    group = db.get(MapGroup, group_id)
    if group is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy nhóm")
    owner = _owner_or_404(db, group)
    if body.status == "accepted" and not is_user_active(owner):
        raise HTTPException(status_code=409, detail="Owner của nhóm không còn hiệu lực")

    membership.status = body.status
    membership.responded_at = _utcnow()
    db.commit()
    db.refresh(membership)
    return _invitation_public(db, membership)


router.include_router(group_router)
router.include_router(invitation_router)
