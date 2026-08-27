"""REST CRUD and scoped management search for map Anchors."""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import String, cast, func, or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, get_db
from app.core.map_access import can_config_anchor, can_view_group, is_user_active
from app.models.anchor import Anchor, AnchorConfigOutbox
from app.models.device import Device
from app.models.map_group import MapGroup
from app.models.map_location import LocationUsing
from app.models.user import User
from app.schemas.anchors import (
    AnchorConfigResyncResponse,
    AnchorConfigStatusResponse,
    AnchorCreate,
    AnchorDeleteResponse,
    AnchorManageResponse,
    AnchorMutationResponse,
    AnchorPatch,
    AnchorPublic,
)
from app.core.config import settings
from app.services.anchor_delivery_service import (
    get_location_sync_status,
    reconcile_latest_snapshot,
)
from app.services.anchor_service import (
    AnchorConflictError,
    create_anchor,
    delete_anchor,
    update_anchor,
    resync_location,
)

router = APIRouter(tags=["anchors"])


def _is_admin(user: User) -> bool:
    return (user.role or "").lower() == "admin"


def _location_context(
    db: Session,
    location_id: int,
    actor: User,
    *,
    mutation: bool = False,
) -> tuple[LocationUsing, MapGroup]:
    location = db.get(LocationUsing, location_id)
    if location is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy bản đồ")
    group = db.get(MapGroup, location.group_id)
    if group is None or not can_view_group(db, actor, group):
        raise HTTPException(status_code=404, detail="Không tìm thấy bản đồ")
    if mutation and not can_config_anchor(actor, group):
        raise HTTPException(status_code=403, detail="Không có quyền cấu hình Anchor")
    return location, group


def _active_anchor_context(
    db: Session,
    anchor_id: int,
    actor: User,
    *,
    mutation: bool = False,
) -> tuple[Anchor, LocationUsing, MapGroup]:
    anchor = db.get(Anchor, anchor_id)
    if anchor is None or anchor.status != "active":
        raise HTTPException(status_code=404, detail="Không tìm thấy Anchor")
    location, group = _location_context(
        db, anchor.location_id, actor, mutation=mutation
    )
    return anchor, location, group


def _public(anchor: Anchor, location: LocationUsing) -> AnchorPublic:
    return AnchorPublic(
        anchor_id=anchor.anchor_id,
        mac_address=anchor.mac_address,
        hardware_id=anchor.hardware_id,
        name=anchor.name,
        x=float(anchor.x),
        y=float(anchor.y),
        z=float(anchor.z),
        location_id=location.location_id,
        location=location.location,
        group_id=location.group_id,
        status=anchor.status,
        created_by_user_id=anchor.created_by_user_id,
        created_at=anchor.created_at,
        updated_at=anchor.updated_at,
    )


def _commit_mutation(db: Session, operation):
    try:
        result = operation()
        db.commit()
        if result.anchor is not None:
            db.refresh(result.anchor)
        return result
    except AnchorConflictError as error:
        db.rollback()
        raise HTTPException(status_code=409, detail=str(error)) from error
    except IntegrityError as error:
        db.rollback()
        raise HTTPException(status_code=409, detail="Anchor bị trùng dữ liệu") from error
    except Exception:
        db.rollback()
        raise


@router.get(
    "/locations/{location_id}/anchors", response_model=list[AnchorPublic]
)
def list_location_anchors(
    location_id: int,
    db: Session = Depends(get_db),
    actor: User = Depends(get_current_user),
) -> list[AnchorPublic]:
    location, _ = _location_context(db, location_id, actor)
    rows = (
        db.query(Anchor)
        .filter(Anchor.location_id == location_id, Anchor.status == "active")
        .order_by(Anchor.anchor_id.asc())
        .all()
    )
    return [_public(row, location) for row in rows]


@router.post(
    "/locations/{location_id}/anchors",
    response_model=AnchorMutationResponse,
    status_code=status.HTTP_201_CREATED,
)
def post_anchor(
    location_id: int,
    body: AnchorCreate,
    db: Session = Depends(get_db),
    actor: User = Depends(get_current_user),
) -> AnchorMutationResponse:
    location, _ = _location_context(db, location_id, actor, mutation=True)
    result = _commit_mutation(
        db, lambda: create_anchor(db, location, actor, body)
    )
    return AnchorMutationResponse(
        data=_public(result.anchor, location),
        config_revision=result.revision,
        sync_status="pending" if result.revision is not None else "unchanged",
    )


@router.get("/anchors/manage", response_model=AnchorManageResponse)
def manage_anchors(
    q: str | None = Query(default=None, max_length=100),
    group_id: int | None = None,
    location_id: int | None = None,
    limit: int = Query(default=25, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    actor: User = Depends(get_current_user),
) -> AnchorManageResponse:
    if not _is_admin(actor) and (
        not is_user_active(actor) or actor.can_config_anchor != "yes"
    ):
        raise HTTPException(status_code=403, detail="Không có quyền cấu hình Anchor")
    query = (
        db.query(Anchor, LocationUsing)
        .join(LocationUsing, LocationUsing.location_id == Anchor.location_id)
        .filter(Anchor.status == "active")
    )
    if not _is_admin(actor):
        query = query.join(
            MapGroup, MapGroup.group_id == LocationUsing.group_id
        ).filter(MapGroup.owner_user_id == actor.user_id)
    if group_id is not None:
        query = query.filter(LocationUsing.group_id == group_id)
    if location_id is not None:
        query = query.filter(LocationUsing.location_id == location_id)
    search = (q or "").strip()
    if search:
        lowered = f"%{search.lower()}%"
        clauses = (
            func.lower(Anchor.name).like(lowered),
            func.lower(Anchor.mac_address).like(lowered),
            func.lower(Anchor.hardware_id).like(lowered),
        )
        if search.isdigit():
            query = query.filter(
                or_(*clauses, cast(Anchor.anchor_id, String) == search)
            )
        else:
            query = query.filter(or_(*clauses))
    total = query.count()
    rows = (
        query.order_by(Anchor.anchor_id.asc()).limit(limit).offset(offset).all()
    )
    return AnchorManageResponse(
        data=[_public(anchor, location) for anchor, location in rows],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/anchors/{anchor_id}", response_model=AnchorPublic)
def get_anchor(
    anchor_id: int,
    db: Session = Depends(get_db),
    actor: User = Depends(get_current_user),
) -> AnchorPublic:
    anchor, location, _ = _active_anchor_context(db, anchor_id, actor)
    return _public(anchor, location)


@router.patch("/anchors/{anchor_id}", response_model=AnchorMutationResponse)
def patch_anchor(
    anchor_id: int,
    body: AnchorPatch,
    db: Session = Depends(get_db),
    actor: User = Depends(get_current_user),
) -> AnchorMutationResponse:
    anchor, location, _ = _active_anchor_context(
        db, anchor_id, actor, mutation=True
    )
    result = _commit_mutation(
        db, lambda: update_anchor(db, anchor, location, actor, body)
    )
    return AnchorMutationResponse(
        data=_public(result.anchor, location),
        config_revision=result.revision,
        sync_status="pending" if result.revision is not None else "unchanged",
    )


@router.delete("/anchors/{anchor_id}", response_model=AnchorDeleteResponse)
def remove_anchor(
    anchor_id: int,
    db: Session = Depends(get_db),
    actor: User = Depends(get_current_user),
) -> AnchorDeleteResponse:
    anchor, location, _ = _active_anchor_context(
        db, anchor_id, actor, mutation=True
    )
    result = _commit_mutation(
        db, lambda: delete_anchor(db, anchor, location, actor)
    )
    return AnchorDeleteResponse(
        deleted_anchor_id=anchor_id, config_revision=result.revision
    )


@router.get(
    "/locations/{location_id}/anchor-config-status",
    response_model=AnchorConfigStatusResponse,
)
def anchor_config_status(
    location_id: int,
    db: Session = Depends(get_db),
    actor: User = Depends(get_current_user),
) -> AnchorConfigStatusResponse:
    location, _ = _location_context(db, location_id, actor, mutation=True)
    latest = (
        db.query(AnchorConfigOutbox)
        .filter_by(location_id=location.location_id)
        .order_by(AnchorConfigOutbox.revision.desc())
        .first()
    )
    if latest is not None:
        reconcile_latest_snapshot(db, latest)
        db.commit()
    return AnchorConfigStatusResponse.model_validate(
        get_location_sync_status(
            db,
            location,
            offline_after_seconds=settings.gateway_offline_after_seconds,
        )
    )


@router.post(
    "/locations/{location_id}/anchor-config-resync",
    status_code=status.HTTP_410_GONE,
)
def deprecated_anchor_config_resync(
    location_id: int,
    db: Session = Depends(get_db),
    actor: User = Depends(get_current_user),
) -> None:
    _location_context(db, location_id, actor, mutation=True)
    raise HTTPException(
        status_code=status.HTTP_410_GONE,
        detail="Hãy chọn một Gateway để gửi lại cấu hình",
    )


@router.post(
    "/locations/{location_id}/gateways/{gateway_id}/anchor-config-resync",
    response_model=AnchorConfigResyncResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
def anchor_config_resync(
    location_id: int,
    gateway_id: int,
    db: Session = Depends(get_db),
    actor: User = Depends(get_current_user),
) -> AnchorConfigResyncResponse:
    location, _ = _location_context(db, location_id, actor, mutation=True)
    gateway = db.get(Device, gateway_id)
    if (
        gateway is None
        or str(gateway.device_type or "").strip().casefold() != "gateway"
        or str(gateway.status or "").strip().casefold() != "active"
        or str(gateway.location or "").strip().casefold()
        != str(location.location).strip().casefold()
    ):
        raise HTTPException(status_code=404, detail="Không tìm thấy Gateway trong map")
    try:
        outbox = resync_location(db, location, actor, gateway_id)
        db.commit()
    except Exception:
        db.rollback()
        raise
    return AnchorConfigResyncResponse(
        gateway_id=gateway_id,
        config_revision=outbox.revision,
    )
