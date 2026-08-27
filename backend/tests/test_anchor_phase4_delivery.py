import json
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.models.anchor import AnchorConfigDelivery, AnchorConfigOutbox
from app.models.base import Base
from app.models.device import Device
from app.models.map_group import MapGroup
from app.models.map_location import LocationUsing
from app.models.user import User
from app.services.anchor_delivery_service import (
    AnchorDispatcher,
    apply_gateway_ack,
    get_location_sync_status,
    reconcile_latest_snapshot,
)
from app.services.gateway_presence import GatewayPresence
from app.core.mqtt_subscriber import MqttSubscriber


def _database():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    return engine, Session(engine)


def _seed(db: Session):
    owner = User(
        username="owner",
        password="unused",
        fullname="Owner",
        cccd="000000000001",
        creat_at=date.today(),
        expired_at=date.today() + timedelta(days=30),
        status="active",
        role="user",
        can_config_anchor="yes",
    )
    db.add(owner)
    db.flush()
    group = MapGroup(
        name="Factory",
        owner_user_id=owner.user_id,
        created_by_user_id=owner.user_id,
    )
    db.add(group)
    db.flush()
    location = LocationUsing(
        location=" Floor_1 ",
        image_data=b"image",
        mime_type="image/webp",
        original_filename="map.webp",
        checksum_sha256="a" * 64,
        file_size_bytes=5,
        width=100,
        height=100,
        group_id=group.group_id,
        owner_user_id=owner.user_id,
        created_by_user_id=owner.user_id,
    )
    db.add(location)
    db.flush()
    outbox = AnchorConfigOutbox(
        location_id=location.location_id,
        location=location.location,
        payload={"schema": "anchor_config.v1", "revision": 1, "anchors": []},
        reason="resync",
        status="pending",
        created_by_user_id=owner.user_id,
    )
    db.add(outbox)
    db.flush()
    outbox.payload["revision"] = outbox.revision
    db.commit()
    return owner, location, outbox


def _gateway(db: Session, device_id: int, *, topic="gw/down", location="floor_1"):
    row = Device(
        device_id=device_id,
        devicename=f"Gateway {device_id}",
        password=None,
        status="active",
        user_device_asignment_id=0,
        location=location,
        device_type="gateway",
        topic=f"gw/{device_id}/up",
        publish_topic=topic,
    )
    db.add(row)
    db.commit()
    return row


def _delta_event(db: Session, location: LocationUsing, anchors: list[dict], reason="update"):
    outbox = AnchorConfigOutbox(
        location_id=location.location_id,
        location=location.location,
        payload={},
        reason=reason,
        status="pending",
    )
    db.add(outbox)
    db.flush()
    outbox.payload = {
        "schema": "anchor_config.v1",
        "operation": "delta",
        "location_id": location.location_id,
        "location": location.location,
        "revision": outbox.revision,
        "generated_at": "2026-08-09T10:00:00Z",
        "anchors": anchors,
    }
    db.commit()
    return outbox


def _upsert(anchor_id: int, name: str, x: float) -> dict:
    return {
        "action": "upsert",
        "id": anchor_id,
        "mac_address": f"12:21:AA:43:1A:{anchor_id:02X}",
        "name": name,
        "x": x,
        "y": 50.0,
        "z": 0.0,
    }


def test_reconcile_targets_every_matching_gateway_and_marks_missing_topic():
    _, db = _database()
    _, _, outbox = _seed(db)
    _gateway(db, 101, topic="same/down")
    _gateway(db, 102, topic="same/down", location=" FLOOR_1 ")
    _gateway(db, 103, topic=None)
    _gateway(db, 104, location="other")

    deliveries = reconcile_latest_snapshot(db, outbox)
    db.commit()

    assert [(row.gateway_id, row.status) for row in deliveries] == [
        (101, "misconfigured"),
        (102, "misconfigured"),
        (103, "misconfigured"),
    ]
    assert all(row.payload["operation"] == "replace" for row in deliveries)
    assert {row.payload["gateway_id"] for row in deliveries} == {101, 102, 103}
    assert {
        row.last_error for row in deliveries if row.gateway_id in {101, 102}
    } == {"duplicate_gateway_publish_topic"}


def test_reconcile_coalesces_unapplied_changes_per_gateway():
    _, db = _database()
    _, location, baseline = _seed(db)
    _gateway(db, 101, topic="gw/101/down")
    _gateway(db, 102, topic="gw/102/down")
    baseline.payload.update({"operation": "replace", "location_id": location.location_id})
    db.add_all([
        AnchorConfigDelivery(
            revision=baseline.revision, gateway_id=101, publish_topic="gw/101/down",
            payload=baseline.payload, status="applied",
        ),
        AnchorConfigDelivery(
            revision=baseline.revision, gateway_id=102, publish_topic="gw/102/down",
            payload=baseline.payload, status="applied",
        ),
    ])
    first = _delta_event(db, location, [_upsert(1, "Anchor A", 10.0)])
    db.add_all([
        AnchorConfigDelivery(
            revision=first.revision, gateway_id=101, publish_topic="gw/101/down",
            payload={**first.payload, "gateway_id": 101}, status="published",
        ),
        AnchorConfigDelivery(
            revision=first.revision, gateway_id=102, publish_topic="gw/102/down",
            payload={**first.payload, "gateway_id": 102}, status="applied",
        ),
    ])
    db.commit()
    latest = _delta_event(db, location, [_upsert(2, "Anchor B", 20.0)])

    deliveries = reconcile_latest_snapshot(db, latest)
    db.commit()
    latest_rows = {row.gateway_id: row for row in deliveries}

    assert [item["id"] for item in latest_rows[101].payload["anchors"]] == [1, 2]
    assert [item["id"] for item in latest_rows[102].payload["anchors"]] == [2]
    assert latest_rows[101].payload["gateway_id"] == 101
    assert latest_rows[102].payload["gateway_id"] == 102
    assert db.query(AnchorConfigDelivery).filter_by(
        revision=first.revision, gateway_id=101
    ).one().status == "superseded"


def test_reconcile_keeps_only_last_action_for_each_anchor():
    _, db = _database()
    _, location, baseline = _seed(db)
    _gateway(db, 101, topic="gw/101/down")
    baseline.payload.update({"operation": "replace", "location_id": location.location_id})
    db.add(AnchorConfigDelivery(
        revision=baseline.revision, gateway_id=101, publish_topic="gw/101/down",
        payload=baseline.payload, status="applied",
    ))
    db.commit()
    _delta_event(db, location, [_upsert(1, "Anchor A", 10.0)])
    _delta_event(db, location, [_upsert(1, "Anchor A", 25.0)])
    _delta_event(db, location, [{
        "action": "delete", "id": 1, "mac_address": "12:21:AA:43:1A:01",
    }], reason="delete")
    latest = _delta_event(db, location, [_upsert(2, "Anchor B", 30.0)])

    delivery = reconcile_latest_snapshot(db, latest)[0]

    assert delivery.payload["operation"] == "delta"
    assert delivery.payload["anchors"] == [
        {"action": "delete", "id": 1, "mac_address": "12:21:AA:43:1A:01"},
        _upsert(2, "Anchor B", 30.0),
    ]


def test_dispatcher_does_not_publish_duplicate_gateway_topics():
    engine, db = _database()
    _, _, outbox = _seed(db)
    _gateway(db, 101, topic="same/down")
    _gateway(db, 102, topic="same/down")
    reconcile_latest_snapshot(db, outbox)
    db.commit()
    calls = []

    dispatcher = AnchorDispatcher(
        session_factory=lambda: Session(engine),
        publish=lambda topic, payload: calls.append((topic, payload)) or True,
        retry_schedule=(5, 15),
        retry_steady=30,
    )
    assert dispatcher.run_once() == 0
    assert calls == []
    assert {row.status for row in db.query(AnchorConfigDelivery).all()} == {"misconfigured"}


def test_dispatcher_retries_publish_failure_on_schedule():
    engine, db = _database()
    _, _, outbox = _seed(db)
    _gateway(db, 101, topic="gw/101/down")
    reconcile_latest_snapshot(db, outbox)
    db.commit()
    failing = AnchorDispatcher(
        session_factory=lambda: Session(engine),
        publish=lambda _topic, _payload: False,
        retry_schedule=(5, 15),
        retry_steady=30,
    )
    assert failing.run_once() == 0
    row = db.query(AnchorConfigDelivery).first()
    assert row.attempt_count == 1
    assert row.next_attempt_at is not None
    assert row.last_error == "MQTT publish failed"


def test_dispatcher_uses_gateway_payload_and_retries_published_until_ack():
    engine, db = _database()
    _, _, outbox = _seed(db)
    _gateway(db, 101, topic="gw/101/down")
    reconcile_latest_snapshot(db, outbox)
    db.commit()
    calls = []
    started = datetime(2026, 8, 9, 10, 0, tzinfo=timezone.utc)
    dispatcher = AnchorDispatcher(
        session_factory=lambda: Session(engine),
        publish=lambda topic, payload: calls.append((topic, json.loads(payload))) or True,
        retry_schedule=(5, 15),
        retry_steady=30,
    )

    assert dispatcher.run_once(now=started) == 1
    assert calls[0][1]["gateway_id"] == 101
    assert dispatcher.run_once(now=started + timedelta(seconds=1)) == 0
    assert dispatcher.run_once(now=started + timedelta(seconds=5)) == 1
    delivery = db.query(AnchorConfigDelivery).one()
    db.refresh(delivery)
    assert delivery.status == "published"
    assert delivery.attempt_count == 2
    assert delivery.next_attempt_at == (started + timedelta(seconds=20)).replace(tzinfo=None)


def test_ack_is_idempotent_and_status_uses_presence_without_stale_downgrade():
    _, db = _database()
    _, location, outbox = _seed(db)
    gateway = _gateway(db, 101)
    reconcile_latest_snapshot(db, outbox)
    delivery = db.query(AnchorConfigDelivery).one()
    delivery.status = "published"
    db.commit()
    now = datetime.now(timezone.utc)

    assert apply_gateway_ack(
        db,
        gateway_id=101,
        location_id=location.location_id,
        revision=outbox.revision,
        status="applied",
        error=None,
        now=now,
    ) is True
    db.commit()
    assert apply_gateway_ack(
        db,
        gateway_id=101,
        location_id=location.location_id,
        revision=outbox.revision,
        status="applied",
        error=None,
        now=now + timedelta(seconds=1),
    ) is True
    db.commit()
    assert db.get(AnchorConfigOutbox, outbox.revision).status == "completed"
    assert apply_gateway_ack(
        db,
        gateway_id=101,
        location_id=location.location_id,
        revision=outbox.revision,
        status="rejected",
        error="late conflict",
        now=now + timedelta(seconds=2),
    ) is True
    db.commit()
    assert db.query(AnchorConfigDelivery).filter_by(revision=outbox.revision).one().status == "applied"

    old = AnchorConfigOutbox(
        revision=outbox.revision - 1,
        location_id=location.location_id,
        location=location.location,
        payload={"revision": outbox.revision - 1, "anchors": []},
        reason="update",
        status="superseded",
    )
    db.add(old)
    db.flush()
    db.add(AnchorConfigDelivery(
        revision=old.revision, gateway_id=101, payload=old.payload,
        status="superseded",
    ))
    db.commit()
    assert apply_gateway_ack(
        db,
        gateway_id=101,
        location_id=location.location_id,
        revision=old.revision,
        status="rejected",
        error="stale",
        now=now,
    ) is True
    db.commit()
    assert db.get(AnchorConfigOutbox, outbox.revision).status == "completed"
    stale = db.query(AnchorConfigDelivery).filter_by(revision=old.revision).one()
    assert stale.status == "superseded"
    assert stale.acked_at is not None

    gateway.last_seen_at = now.replace(tzinfo=None)
    db.commit()
    result = get_location_sync_status(db, location, now=now, offline_after_seconds=30)
    assert result["aggregate"] == "synced"
    assert result["gateways"][0]["online"] is True


def test_ack_completes_outbox_when_production_session_disables_autoflush():
    engine, setup = _database()
    _, location, outbox = _seed(setup)
    _gateway(setup, 101)
    reconcile_latest_snapshot(setup, outbox)
    setup.query(AnchorConfigDelivery).one().status = "published"
    setup.commit()
    location_id = location.location_id
    revision = outbox.revision
    setup.close()

    db = Session(engine, autoflush=False)
    assert apply_gateway_ack(
        db,
        gateway_id=101,
        location_id=location_id,
        revision=revision,
        status="applied",
        error=None,
    ) is True
    db.commit()

    assert db.query(AnchorConfigDelivery).one().status == "applied"
    assert db.get(AnchorConfigOutbox, revision).status == "completed"

    db.get(AnchorConfigOutbox, revision).status = "pending"
    db.commit()
    assert apply_gateway_ack(
        db,
        gateway_id=101,
        location_id=location_id,
        revision=revision,
        status="applied",
        error=None,
    ) is True
    db.commit()
    assert db.get(AnchorConfigOutbox, revision).status == "completed"


def test_status_uses_latest_target_for_each_gateway_after_targeted_resync():
    _, db = _database()
    _, location, baseline = _seed(db)
    _gateway(db, 101, topic="gw/101/down")
    _gateway(db, 102, topic="gw/102/down")
    baseline.payload.update({"operation": "replace", "location_id": location.location_id})
    db.add_all([
        AnchorConfigDelivery(
            revision=baseline.revision, gateway_id=101, publish_topic="gw/101/down",
            payload={**baseline.payload, "gateway_id": 101}, status="applied",
        ),
        AnchorConfigDelivery(
            revision=baseline.revision, gateway_id=102, publish_topic="gw/102/down",
            payload={**baseline.payload, "gateway_id": 102}, status="applied",
        ),
    ])
    targeted = AnchorConfigOutbox(
        location_id=location.location_id,
        location=location.location,
        target_gateway_id=101,
        payload={},
        reason="resync",
        status="pending",
    )
    db.add(targeted)
    db.flush()
    targeted.payload = {
        "schema": "anchor_config.v1",
        "operation": "replace",
        "location_id": location.location_id,
        "location": location.location,
        "revision": targeted.revision,
        "anchors": [],
    }
    reconcile_latest_snapshot(db, targeted)
    db.commit()

    status = get_location_sync_status(db, location)
    gateways = {row["gateway_id"]: row for row in status["gateways"]}

    assert gateways[101]["target_revision"] == targeted.revision
    assert gateways[101]["delivery_status"] == "pending"
    assert gateways[102]["target_revision"] == baseline.revision
    assert gateways[102]["delivery_status"] == "applied"
    assert status["aggregate"] == "partial"


def test_gateway_presence_throttles_database_flush_and_uses_server_time():
    engine, db = _database()
    _seed(db)
    _gateway(db, 101)
    start = datetime(2026, 8, 8, 10, 0, tzinfo=timezone.utc)
    presence = GatewayPresence(lambda: Session(engine), flush_seconds=5)

    assert presence.touch(101, now=start) is True
    assert presence.touch(101, now=start + timedelta(seconds=2)) is False
    assert presence.touch(101, now=start + timedelta(seconds=5)) is True
    db.expire_all()
    assert db.get(Device, 101).last_seen_at == (start + timedelta(seconds=5)).replace(tzinfo=None)


def test_mqtt_qos1_publish_waits_for_broker_ack_and_forwards_json_uplink():
    received = []
    sensor_payloads = []
    subscriber = MqttSubscriber(
        enabled=False, host="localhost", port=1883, username=None, password=None,
        client_id="test", keepalive=60, topics_csv="gw/up", qos=1, max_messages=10,
        on_gateway_payload=lambda topic, payload: received.append((topic, payload)),
        on_sensor_payload=sensor_payloads.append,
    )

    class Info:
        rc = 0
        mid = 7

        def wait_for_publish(self, timeout):
            assert timeout == 2
            return None

        def is_published(self):
            return True

    class Client:
        def publish(self, topic, payload, qos, retain):
            assert (topic, qos, retain) == ("gw/down", 1, True)
            assert payload == b"{}"
            return Info()

    subscriber._enabled = True
    subscriber._connected = True
    subscriber._client = Client()
    assert subscriber.publish_qos1_retained("gw/down", b"{}", timeout_seconds=2) is True

    class Message:
        topic = "gw/up"
        payload = b'{"type":"anchor_config_ack","gateway_id":101}'
        qos = 1
        retain = False

    subscriber._on_message(None, None, Message())
    assert received == [("gw/up", {"type": "anchor_config_ack", "gateway_id": 101})]
    assert sensor_payloads == []
    assert subscriber.message_count() == 1
