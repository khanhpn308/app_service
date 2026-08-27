from datetime import date, timedelta

from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.core.map_archive import DeleteReason, archive_location
from app.models.anchor import Anchor, AnchorConfigDelivery, AnchorConfigOutbox
from app.models.base import Base
from app.models.device import Device
from app.models.map_group import MapGroup
from app.models.map_location import LocationDeleted, LocationUsing
from app.models.user import User
from app.services.anchor_delivery_service import (
    reconcile_gateway_change,
    reconcile_pending_locations,
)


def _db():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    return Session(engine)


def _seed(db: Session):
    owner = User(
        username="owner", password="unused", fullname="Owner", cccd="000000000001",
        creat_at=date.today(), expired_at=date.today() + timedelta(days=30),
        status="active", role="user", can_config_anchor="no",
    )
    db.add(owner)
    db.flush()
    group = MapGroup(name="Factory", owner_user_id=owner.user_id, created_by_user_id=owner.user_id)
    db.add(group)
    db.flush()
    location = LocationUsing(
        location="Floor_1", image_data=b"x", mime_type="image/webp", original_filename="map.webp",
        checksum_sha256="a" * 64, file_size_bytes=1, width=100, height=100,
        group_id=group.group_id, owner_user_id=owner.user_id, created_by_user_id=owner.user_id,
    )
    db.add(location)
    db.flush()
    anchor = Anchor(
        hardware_id="A-1", name="Alpha", name_key="alpha", x=10, y=20, z=0,
        location_id=location.location_id, status="active",
        created_by_user_id=owner.user_id, updated_by_user_id=owner.user_id,
    )
    db.add(anchor)
    db.commit()
    return owner, group, location, anchor


def test_archiving_map_soft_deletes_anchors_and_creates_empty_snapshot_without_permission_flag():
    db = _db()
    owner, _, location, anchor = _seed(db)

    archive_location(db, location.location_id, deleted_by=owner, reason=DeleteReason.MAP_DELETED)
    db.commit()

    assert db.get(LocationUsing, location.location_id) is None
    assert db.get(LocationDeleted, location.location_id) is not None
    kept = db.get(Anchor, anchor.anchor_id)
    assert kept.status == "inactive"
    assert kept.deleted_at is not None
    assert kept.name_key is None
    snapshot = db.query(AnchorConfigOutbox).one()
    assert snapshot.reason == "map_deleted"
    assert snapshot.payload["anchors"] == []


def test_gateway_change_reconciles_completed_latest_snapshot_and_old_location():
    db = _db()
    owner, _, location, _ = _seed(db)
    second_group = MapGroup(name="Second", owner_user_id=owner.user_id, created_by_user_id=owner.user_id)
    db.add(second_group)
    db.flush()
    second = LocationUsing(
        location="Floor_2", image_data=b"x", mime_type="image/webp", original_filename="two.webp",
        checksum_sha256="b" * 64, file_size_bytes=1, width=100, height=100,
        group_id=second_group.group_id, owner_user_id=owner.user_id, created_by_user_id=owner.user_id,
    )
    db.add(second)
    old = AnchorConfigOutbox(
        location_id=location.location_id, location=location.location,
        payload={"revision": 1, "anchors": []}, reason="update", status="completed",
    )
    new = AnchorConfigOutbox(
        location_id=second.location_id, location=second.location,
        payload={"revision": 2, "anchors": []}, reason="update", status="completed",
    )
    gateway = Device(
        device_id=101, devicename="Gateway", status="active", user_device_asignment_id=0,
        location="Floor_1", device_type="gateway", topic="gw/up", publish_topic="gw/down",
    )
    db.add_all([old, new, gateway])
    db.flush()
    old.payload["revision"] = old.revision
    new.payload["revision"] = new.revision
    db.commit()

    reconcile_gateway_change(db, gateway)
    db.commit()
    first = db.query(AnchorConfigDelivery).one()
    assert first.status == "pending"
    assert db.get(AnchorConfigOutbox, old.revision).status == "pending"

    gateway.location = "Floor_2"
    gateway.publish_topic = "gw/new-down"
    reconcile_gateway_change(db, gateway, old_location="Floor_1")
    db.commit()
    assert first.status == "superseded"
    second_delivery = db.query(AnchorConfigDelivery).filter_by(revision=new.revision).one()
    assert (second_delivery.status, second_delivery.publish_topic) == ("pending", "gw/new-down")

    gateway.status = "inactive"
    reconcile_gateway_change(db, gateway, old_location="Floor_2")
    db.commit()
    assert second_delivery.status == "superseded"


def test_periodic_reconciliation_targets_gateway_added_after_snapshot_completed():
    db = _db()
    _, _, location, _ = _seed(db)
    outbox = AnchorConfigOutbox(
        location_id=location.location_id, location=location.location,
        payload={"revision": 1, "anchors": []}, reason="update", status="completed",
    )
    db.add(outbox)
    db.flush()
    outbox.payload["revision"] = outbox.revision
    db.add(Device(
        device_id=101, devicename="Late", status="active", user_device_asignment_id=0,
        location="floor_1", device_type="gateway", topic="late/up", publish_topic="late/down",
    ))
    db.commit()

    assert reconcile_pending_locations(db) == 1
    db.commit()
    assert db.query(AnchorConfigDelivery).one().status == "pending"
    assert db.get(AnchorConfigOutbox, outbox.revision).status == "pending"

