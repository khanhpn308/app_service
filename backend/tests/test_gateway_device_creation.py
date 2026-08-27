from datetime import date, timedelta

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.api.devices_routes import router
from app.core.deps import get_db, require_admin
from app.models.anchor import AnchorConfigDelivery, AnchorConfigOutbox
from app.models.base import Base
from app.models.device import Device
from app.models.map_group import MapGroup
from app.models.map_location import LocationUsing
from app.models.user import User


class FakeMqtt:
    def __init__(self):
        self.subscribed: list[str] = []

    def subscribe_topic(self, topic: str) -> None:
        self.subscribed.append(topic)

    def unsubscribe_topic(self, _topic: str) -> None:
        pass


def _api():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    db = Session(engine)
    admin = User(
        username="admin",
        password="unused",
        fullname="Admin",
        cccd="000000000001",
        creat_at=date.today(),
        expired_at=date.today() + timedelta(days=30),
        status="active",
        role="admin",
        can_config_anchor="no",
    )
    db.add(admin)
    db.commit()
    app = FastAPI()
    app.include_router(router, prefix="/api")
    app.state.mqtt = FakeMqtt()
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[require_admin] = lambda: admin
    return TestClient(app), db, app.state.mqtt


def _gateway_body(device_id: int) -> dict:
    return {
        "device_id": device_id,
        "devicename": f"Gateway {device_id}",
        "password": "secret123",
        "status": "active",
        "user_device_asignment_id": 0,
        "location": "Floor_1",
        "device_type": "gateway",
    }


def _seed_map(db: Session) -> LocationUsing:
    admin = db.query(User).filter_by(username="admin").one()
    group = MapGroup(
        name="Factory",
        owner_user_id=admin.user_id,
        created_by_user_id=admin.user_id,
    )
    db.add(group)
    db.flush()
    location = LocationUsing(
        location="Floor_1",
        image_data=b"image",
        mime_type="image/webp",
        original_filename="floor.webp",
        checksum_sha256="a" * 64,
        file_size_bytes=5,
        width=100,
        height=100,
        group_id=group.group_id,
        owner_user_id=admin.user_id,
        created_by_user_id=admin.user_id,
    )
    db.add(location)
    db.commit()
    return location


def test_create_gateway_assigns_default_topics_and_subscribes_uplink_immediately():
    client, db, mqtt = _api()

    response = client.post("/api/devices", json=_gateway_body(101))

    assert response.status_code == 201
    assert response.json()["topic"] == "gateway/101/backend_receive"
    assert response.json()["publish_topic"] == "gateway/101/backend_send"
    row = db.get(Device, 101)
    assert (row.topic, row.publish_topic) == (
        "gateway/101/backend_receive",
        "gateway/101/backend_send",
    )
    assert mqtt.subscribed == ["gateway/101/backend_receive"]


def test_create_gateway_preserves_explicit_topics():
    client, _, mqtt = _api()
    body = {
        **_gateway_body(102),
        "topic": "custom/gateway/up",
        "publish_topic": "custom/gateway/down",
    }

    response = client.post("/api/devices", json=body)

    assert response.status_code == 201
    assert response.json()["topic"] == "custom/gateway/up"
    assert response.json()["publish_topic"] == "custom/gateway/down"
    assert mqtt.subscribed == ["custom/gateway/up"]


def test_create_gateway_bootstraps_only_that_gateway_with_full_replace():
    client, db, _ = _api()
    location = _seed_map(db)
    db.add(Device(
        device_id=100,
        devicename="Existing Gateway",
        status="active",
        user_device_asignment_id=0,
        location="Floor_1",
        device_type="gateway",
        topic="gateway/100/backend_receive",
        publish_topic="gateway/100/backend_send",
    ))
    db.commit()

    response = client.post("/api/devices", json=_gateway_body(101))

    assert response.status_code == 201
    outbox = db.query(AnchorConfigOutbox).one()
    assert outbox.location_id == location.location_id
    assert outbox.target_gateway_id == 101
    assert outbox.reason == "gateway_bootstrap"
    assert outbox.payload["operation"] == "replace"
    deliveries = db.query(AnchorConfigDelivery).all()
    assert [row.gateway_id for row in deliveries] == [101]
    assert deliveries[0].payload["gateway_id"] == 101


def test_create_gateway_rejects_duplicate_active_publish_topic():
    client, db, _ = _api()
    first = {
        **_gateway_body(101),
        "publish_topic": "shared/down",
    }
    second = {
        **_gateway_body(102),
        "publish_topic": "shared/down",
    }

    assert client.post("/api/devices", json=first).status_code == 201
    duplicate = client.post("/api/devices", json=second)

    assert duplicate.status_code == 409
    assert duplicate.json()["detail"] == "Gateway publish topic already in use"
    assert db.get(Device, 102) is None


def test_update_gateway_topic_rejects_duplicate_and_bootstraps_after_valid_change():
    client, db, _ = _api()
    _seed_map(db)
    assert client.post("/api/devices", json={
        **_gateway_body(101), "publish_topic": "gateway/101/down",
    }).status_code == 201
    assert client.post("/api/devices", json={
        **_gateway_body(102), "publish_topic": "gateway/102/down",
    }).status_code == 201
    before = db.query(AnchorConfigOutbox).count()

    duplicate = client.put(
        "/api/devices/102/topic",
        json={"publish_topic": "gateway/101/down"},
    )
    assert duplicate.status_code == 409
    db.refresh(db.get(Device, 102))
    assert db.get(Device, 102).publish_topic == "gateway/102/down"
    assert db.query(AnchorConfigOutbox).count() == before

    changed = client.put(
        "/api/devices/102/topic",
        json={"publish_topic": "gateway/102/new-down"},
    )
    assert changed.status_code == 200
    latest = db.query(AnchorConfigOutbox).order_by(
        AnchorConfigOutbox.revision.desc()
    ).first()
    assert latest.target_gateway_id == 102
    assert latest.reason == "gateway_bootstrap"
    assert latest.payload["operation"] == "replace"


def test_patch_gateway_rejects_duplicate_publish_topic():
    client, db, _ = _api()
    assert client.post("/api/devices", json={
        **_gateway_body(101), "publish_topic": "gateway/101/down",
    }).status_code == 201
    assert client.post("/api/devices", json={
        **_gateway_body(102), "publish_topic": "gateway/102/down",
    }).status_code == 201

    duplicate = client.patch(
        "/api/devices/102",
        json={"publish_topic": "gateway/101/down"},
    )

    assert duplicate.status_code == 409
    db.refresh(db.get(Device, 102))
    assert db.get(Device, 102).publish_topic == "gateway/102/down"
