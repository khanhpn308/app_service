from datetime import date, timedelta

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.api.anchors_routes import router
from app.core.deps import get_current_user, get_db
from app.models.anchor import AnchorConfigDelivery, AnchorConfigOutbox
from app.models.base import Base
from app.models.device import Device
from app.models.map_group import MapGroup
from app.models.map_location import LocationUsing
from app.models.user import User
from app.services.anchor_delivery_service import handle_gateway_uplink


@pytest.fixture
def api():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    db = Session(engine)
    actor = {"user": None}
    app = FastAPI()
    app.include_router(router, prefix="/api")
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_current_user] = lambda: actor["user"]
    with TestClient(app) as client:
        yield client, db, actor
    db.close()


def _seed(db: Session):
    owner = User(
        username="owner", password="unused", fullname="Owner", cccd="000000000001",
        creat_at=date.today(), expired_at=date.today() + timedelta(days=30),
        status="active", role="user", can_config_anchor="yes",
    )
    outsider = User(
        username="outsider", password="unused", fullname="Out", cccd="000000000002",
        creat_at=date.today(), expired_at=date.today() + timedelta(days=30),
        status="active", role="user", can_config_anchor="yes",
    )
    db.add_all([owner, outsider])
    db.flush()
    group = MapGroup(name="Factory", owner_user_id=owner.user_id, created_by_user_id=owner.user_id)
    db.add(group)
    db.flush()
    location = LocationUsing(
        location="Floor_1", image_data=b"x", mime_type="image/webp",
        original_filename="map.webp", checksum_sha256="a" * 64,
        file_size_bytes=1, width=100, height=100, group_id=group.group_id,
        owner_user_id=owner.user_id, created_by_user_id=owner.user_id,
    )
    db.add(location)
    db.flush()
    db.add(Device(
        device_id=101, devicename="Gateway", status="active", user_device_asignment_id=0,
        location="floor_1", device_type="gateway", topic="gw/up", publish_topic="gw/down",
    ))
    db.commit()
    return owner, outsider, location


def test_status_and_targeted_resync_are_scoped_and_return_gateway_contract(api):
    client, db, actor = api
    owner, outsider, location = _seed(db)
    actor["user"] = owner

    legacy = client.post(f"/api/locations/{location.location_id}/anchor-config-resync")
    assert legacy.status_code == 410
    assert db.query(AnchorConfigOutbox).count() == 0
    resync = client.post(
        f"/api/locations/{location.location_id}/gateways/101/anchor-config-resync"
    )
    assert resync.status_code == 202
    assert resync.json()["gateway_id"] == 101
    assert resync.json()["sync_status"] == "pending"
    outbox = db.query(AnchorConfigOutbox).one()
    assert outbox.target_gateway_id == 101
    assert outbox.payload["operation"] == "replace"
    delivery = db.query(AnchorConfigDelivery).one()
    assert delivery.gateway_id == 101
    assert delivery.payload["gateway_id"] == 101
    status = client.get(f"/api/locations/{location.location_id}/anchor-config-status")
    assert status.status_code == 200
    assert status.json()["aggregate"] == "pending"
    assert status.json()["gateways"][0]["gateway_id"] == 101

    actor["user"] = outsider
    assert client.get(f"/api/locations/{location.location_id}/anchor-config-status").status_code == 404
    assert client.post(
        f"/api/locations/{location.location_id}/gateways/101/anchor-config-resync"
    ).status_code == 404


def test_mqtt_ack_requires_matching_gateway_topic_location_and_schema(api):
    _, db, _ = api
    owner, _, location = _seed(db)
    outbox = AnchorConfigOutbox(
        location_id=location.location_id, location=location.location,
        payload={"schema": "anchor_config.v1", "revision": 1, "anchors": []},
        reason="resync", status="pending", created_by_user_id=owner.user_id,
    )
    db.add(outbox)
    db.flush()
    outbox.payload["revision"] = outbox.revision
    db.add(AnchorConfigDelivery(
        revision=outbox.revision, gateway_id=101, publish_topic="gw/down",
        payload=outbox.payload, status="published"
    ))
    db.commit()
    payload = {
        "type": "anchor_config_ack", "schema": "anchor_config_ack.v1",
        "gateway_id": 101, "location_id": location.location_id,
        "location": " floor_1 ", "revision": outbox.revision,
        "status": "applied", "error": None,
    }

    assert handle_gateway_uplink(db, payload, mqtt_topic="wrong") is False
    assert handle_gateway_uplink(db, {**payload, "schema": "bad"}, mqtt_topic="gw/up") is False
    assert handle_gateway_uplink(db, {**payload, "location": "other"}, mqtt_topic="gw/up") is False
    assert handle_gateway_uplink(db, payload, mqtt_topic="gw/up") is True
    db.commit()
    assert db.query(AnchorConfigDelivery).one().status == "applied"
