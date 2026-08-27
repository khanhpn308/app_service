"""Atomic Anchor mutations and deterministic delta/full outbox production."""

from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.models.anchor import Anchor, AnchorConfigDelivery, AnchorConfigOutbox
from app.models.map_location import LocationUsing
from app.models.user import User
from app.schemas.anchors import AnchorCreate, AnchorPatch


class AnchorConflictError(ValueError):
    """A MAC Address, legacy hardware ID, or active name already exists."""


@dataclass(frozen=True)
class AnchorMutation:
    anchor: Anchor | None
    revision: int | None


def _name_key(name: str) -> str:
    key = name.casefold()
    if len(key) > 100:
        raise AnchorConflictError("Anchor name normalization is too long")
    return key


def _assert_unique(
    db: Session,
    *,
    location_id: int,
    mac_address: str | None = None,
    hardware_id: str | None = None,
    name: str | None = None,
    exclude_anchor_id: int | None = None,
) -> None:
    if mac_address is not None:
        query = db.query(Anchor).filter(
            or_(
                Anchor.mac_address == mac_address,
                Anchor.hardware_id == mac_address,
            )
        )
        if exclude_anchor_id is not None:
            query = query.filter(Anchor.anchor_id != exclude_anchor_id)
        if query.first() is not None:
            raise AnchorConflictError("MAC Address đã tồn tại")
    if hardware_id is not None:
        query = db.query(Anchor).filter(Anchor.hardware_id == hardware_id)
        if exclude_anchor_id is not None:
            query = query.filter(Anchor.anchor_id != exclude_anchor_id)
        if query.first() is not None:
            raise AnchorConflictError("Hardware ID đã tồn tại")
    if name is not None:
        query = db.query(Anchor).filter(
            Anchor.location_id == location_id,
            Anchor.name_key == _name_key(name),
            Anchor.status == "active",
        )
        if exclude_anchor_id is not None:
            query = query.filter(Anchor.anchor_id != exclude_anchor_id)
        if query.first() is not None:
            raise AnchorConflictError("Tên Anchor đã tồn tại trong map")


def _supersede_previous(
    db: Session,
    location_id: int,
    now: datetime,
    target_gateway_id: int | None,
) -> None:
    old_revisions = [
        revision
        for (revision,) in db.query(AnchorConfigOutbox.revision)
        .filter(
            AnchorConfigOutbox.location_id == location_id,
            AnchorConfigOutbox.status.in_(("pending", "failed")),
        )
        .all()
    ]
    if not old_revisions:
        return
    deliveries = db.query(AnchorConfigDelivery).filter(
        AnchorConfigDelivery.revision.in_(old_revisions),
        AnchorConfigDelivery.status != "applied",
    )
    if target_gateway_id is not None:
        deliveries = deliveries.filter(
            AnchorConfigDelivery.gateway_id == target_gateway_id
        )
    deliveries.update({"status": "superseded"}, synchronize_session=False)
    for revision in old_revisions:
        states = [
            state for (state,) in db.query(AnchorConfigDelivery.status)
            .filter(AnchorConfigDelivery.revision == revision)
            .all()
        ]
        old = db.get(AnchorConfigOutbox, revision)
        if states and all(state == "superseded" for state in states):
            old.status = "superseded"
            old.superseded_at = now
        elif states and all(state in {"applied", "superseded"} for state in states):
            old.status = "completed"
            old.completed_at = now.replace(tzinfo=None)
        elif not states and target_gateway_id is None:
            old.status = "superseded"
            old.superseded_at = now


def _anchor_payload(anchor: Anchor) -> dict:
    return {
        "id": anchor.anchor_id,
        "mac_address": anchor.mac_address,
        "name": anchor.name,
        "x": float(anchor.x),
        "y": float(anchor.y),
        "z": float(anchor.z),
    }


def _delta_payload(anchor: Anchor, action: str) -> dict:
    if action == "delete":
        return {
            "action": "delete",
            "id": anchor.anchor_id,
            "mac_address": anchor.mac_address,
        }
    return {"action": "upsert", **_anchor_payload(anchor)}


def _write_outbox(
    db: Session,
    location: LocationUsing,
    actor: User,
    reason: str,
    *,
    operation: str,
    anchors: list[dict],
    target_gateway_id: int | None = None,
) -> AnchorConfigOutbox:
    generated_at = datetime.now(timezone.utc)
    _supersede_previous(
        db, location.location_id, generated_at, target_gateway_id
    )
    outbox = AnchorConfigOutbox(
        location_id=location.location_id,
        location=location.location,
        target_gateway_id=target_gateway_id,
        payload={},
        reason=reason,
        status="pending",
        created_by_user_id=actor.user_id,
    )
    db.add(outbox)
    db.flush()
    outbox.payload = {
        "schema": "anchor_config.v1",
        "operation": operation,
        "location_id": location.location_id,
        "location": location.location,
        "revision": outbox.revision,
        "generated_at": generated_at.isoformat().replace("+00:00", "Z"),
        "anchors": anchors,
    }
    from app.services.anchor_delivery_service import reconcile_latest_snapshot

    reconcile_latest_snapshot(db, outbox)
    return outbox


def _delta_event(
    db: Session,
    location: LocationUsing,
    actor: User,
    reason: str,
    anchor: Anchor,
    action: str,
) -> AnchorConfigOutbox:
    db.flush()
    return _write_outbox(
        db,
        location,
        actor,
        reason,
        operation="delta",
        anchors=[_delta_payload(anchor, action)],
    )


def _replace_event(
    db: Session,
    location: LocationUsing,
    actor: User,
    reason: str,
    *,
    target_gateway_id: int | None = None,
) -> AnchorConfigOutbox:
    db.flush()
    anchors = (
        db.query(Anchor)
        .filter(
            Anchor.location_id == location.location_id,
            Anchor.status == "active",
        )
        .order_by(Anchor.anchor_id.asc())
        .all()
    )
    return _write_outbox(
        db,
        location,
        actor,
        reason,
        operation="replace",
        anchors=[_anchor_payload(anchor) for anchor in anchors],
        target_gateway_id=target_gateway_id,
    )


def create_anchor(
    db: Session,
    location: LocationUsing,
    actor: User,
    data: AnchorCreate,
) -> AnchorMutation:
    _assert_unique(
        db,
        location_id=location.location_id,
        mac_address=data.mac_address,
        hardware_id=data.hardware_id,
        name=data.name,
    )
    legacy_identity = data.hardware_id or data.mac_address
    anchor = Anchor(
        hardware_id=legacy_identity,
        mac_address=data.mac_address,
        name=data.name,
        name_key=_name_key(data.name),
        x=Decimal(str(data.x)),
        y=Decimal(str(data.y)),
        z=Decimal(str(data.z)),
        location_id=location.location_id,
        status="active",
        created_by_user_id=actor.user_id,
        updated_by_user_id=actor.user_id,
    )
    db.add(anchor)
    outbox = _delta_event(db, location, actor, "create", anchor, "upsert")
    return AnchorMutation(anchor=anchor, revision=outbox.revision)


def update_anchor(
    db: Session,
    anchor: Anchor,
    location: LocationUsing,
    actor: User,
    data: AnchorPatch,
) -> AnchorMutation:
    changes = data.model_dump(exclude_unset=True)
    changed = False
    if "mac_address" in changes:
        mac_address = changes["mac_address"]
        if anchor.mac_address is not None and anchor.mac_address != mac_address:
            raise AnchorConflictError("MAC Address không thể thay đổi")
        if anchor.mac_address != mac_address:
            _assert_unique(
                db,
                location_id=anchor.location_id,
                mac_address=mac_address,
                exclude_anchor_id=anchor.anchor_id,
            )
            anchor.mac_address = mac_address
            changed = True
    if "name" in changes and anchor.name != changes["name"]:
        _assert_unique(
            db,
            location_id=anchor.location_id,
            name=changes["name"],
            exclude_anchor_id=anchor.anchor_id,
        )
        anchor.name = changes["name"]
        anchor.name_key = _name_key(changes["name"])
        changed = True
    for coordinate in ("x", "y", "z"):
        if coordinate in changes:
            value = Decimal(str(changes[coordinate]))
            if getattr(anchor, coordinate) != value:
                setattr(anchor, coordinate, value)
                changed = True
    if not changed:
        return AnchorMutation(anchor=anchor, revision=None)
    anchor.updated_by_user_id = actor.user_id
    db.add(anchor)
    outbox = _delta_event(db, location, actor, "update", anchor, "upsert")
    return AnchorMutation(anchor=anchor, revision=outbox.revision)


def delete_anchor(
    db: Session,
    anchor: Anchor,
    location: LocationUsing,
    actor: User,
) -> AnchorMutation:
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    anchor.status = "inactive"
    anchor.name_key = None
    anchor.deleted_at = now
    anchor.deleted_by_user_id = actor.user_id
    anchor.updated_by_user_id = actor.user_id
    db.add(anchor)
    outbox = _delta_event(db, location, actor, "delete", anchor, "delete")
    return AnchorMutation(anchor=anchor, revision=outbox.revision)


def resync_location(
    db: Session,
    location: LocationUsing,
    actor: User,
    gateway_id: int,
) -> AnchorConfigOutbox:
    """Create a new full snapshot without changing Anchor rows."""
    return _replace_event(
        db,
        location,
        actor,
        "resync",
        target_gateway_id=gateway_id,
    )


def bootstrap_gateway(
    db: Session,
    location: LocationUsing,
    actor: User,
    gateway_id: int,
) -> AnchorConfigOutbox:
    """Create a full snapshot targeted only to a newly configured Gateway."""
    return _replace_event(
        db,
        location,
        actor,
        "gateway_bootstrap",
        target_gateway_id=gateway_id,
    )


def archive_location_anchors(
    db: Session,
    location: LocationUsing,
    actor: User,
    *,
    reason: str,
) -> AnchorConfigOutbox | None:
    """Soft-delete all active Anchors and emit one empty lifecycle snapshot."""
    anchors = db.query(Anchor).filter(
        Anchor.location_id == location.location_id,
        Anchor.status == "active",
    ).all()
    if not anchors:
        return None
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    for anchor in anchors:
        anchor.status = "inactive"
        anchor.name_key = None
        anchor.deleted_at = now
        anchor.deleted_by_user_id = actor.user_id
        anchor.updated_by_user_id = actor.user_id
    db.flush()
    return _replace_event(db, location, actor, reason)
