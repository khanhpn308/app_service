from datetime import date, timedelta

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.core.deps import get_current_user, get_db
from app.models.anchor import Anchor, AnchorConfigDelivery, AnchorConfigOutbox
from app.models.base import Base
from app.models.map_group import MapGroup, MapGroupMembership
from app.models.map_location import LocationUsing
from app.models.user import User


def add_user(
    db: Session,
    username: str,
    sequence: int,
    *,
    role: str = "user",
    can_config_anchor: str = "no",
) -> User:
    user = User(
        username=username,
        password="not-used",
        fullname=f"User {username}",
        cccd=f"{sequence:012d}",
        creat_at=date.today(),
        expired_at=date.today() + timedelta(days=30),
        status="active",
        role=role,
        can_config_anchor=can_config_anchor,
    )
    db.add(user)
    db.flush()
    return user


def add_group_and_map(db: Session, owner: User, name: str, location: str):
    group = MapGroup(
        name=name,
        owner_user_id=owner.user_id,
        created_by_user_id=owner.user_id,
    )
    db.add(group)
    db.flush()
    floor = LocationUsing(
        location=location,
        image_data=b"image",
        mime_type="image/webp",
        original_filename=f"{location}.webp",
        checksum_sha256=("a" * 64),
        file_size_bytes=5,
        width=100,
        height=100,
        group_id=group.group_id,
        owner_user_id=owner.user_id,
        created_by_user_id=owner.user_id,
    )
    db.add(floor)
    db.flush()
    return group, floor


@pytest.fixture
def api():
    try:
        from app.api.anchors_routes import router
    except ImportError:
        pytest.fail("Phase 2 Anchor router is not implemented")

    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    db = Session(engine)
    actor = {"user": None}
    app = FastAPI()
    app.include_router(router, prefix="/api")

    def override_db():
        yield db

    def override_user():
        return actor["user"]

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_user] = override_user
    with TestClient(app) as client:
        yield client, db, actor
    db.close()


def test_create_normalizes_defaults_and_writes_deterministic_delta(api) -> None:
    client, db, actor = api
    owner = add_user(db, "owner", 1, can_config_anchor="yes")
    _, floor = add_group_and_map(db, owner, "Factory", "FLOOR_1")
    db.commit()
    actor["user"] = owner

    response = client.post(
        f"/api/locations/{floor.location_id}/anchors",
        json={"hardware_id": " aa:bb_01 ", "name": "  Cửa chính  "},
    )

    assert response.status_code == 201
    body = response.json()
    assert body["data"]["hardware_id"] == "AA:BB_01"
    assert body["data"]["name"] == "Cửa chính"
    assert (body["data"]["x"], body["data"]["y"], body["data"]["z"]) == (
        50.0,
        50.0,
        0.0,
    )
    outbox = db.query(AnchorConfigOutbox).one()
    assert outbox.revision == body["config_revision"]
    assert outbox.payload["schema"] == "anchor_config.v1"
    assert outbox.payload["operation"] == "delta"
    assert outbox.payload["revision"] == outbox.revision
    assert outbox.payload["location"] == "FLOOR_1"
    assert [item["id"] for item in outbox.payload["anchors"]] == [body["data"]["anchor_id"]]
    assert outbox.payload["anchors"][0]["action"] == "upsert"
    assert isinstance(outbox.payload["anchors"][0]["x"], float)


def test_create_uses_normalized_mac_address_in_db_api_and_gateway_snapshot(api) -> None:
    client, db, actor = api
    owner = add_user(db, "mac-owner", 11, can_config_anchor="yes")
    _, floor = add_group_and_map(db, owner, "MAC Factory", "MAC_FLOOR")
    db.commit()
    actor["user"] = owner

    response = client.post(
        f"/api/locations/{floor.location_id}/anchors",
        json={"mac_address": "12:21:aa:43:1f:9b", "name": "MAC Anchor"},
    )

    assert response.status_code == 201
    assert response.json()["data"]["mac_address"] == "12:21:AA:43:1F:9B"
    anchor = db.query(Anchor).one()
    assert anchor.mac_address == "12:21:AA:43:1F:9B"
    gateway_anchor = db.query(AnchorConfigOutbox).one().payload["anchors"][0]
    assert gateway_anchor["mac_address"] == "12:21:AA:43:1F:9B"
    assert "hardware_id" not in gateway_anchor


def test_create_rejects_non_mac_identifier(api) -> None:
    client, db, actor = api
    owner = add_user(db, "bad-mac-owner", 12, can_config_anchor="yes")
    _, floor = add_group_and_map(db, owner, "Bad MAC Factory", "BAD_MAC_FLOOR")
    db.commit()
    actor["user"] = owner

    response = client.post(
        f"/api/locations/{floor.location_id}/anchors",
        json={"mac_address": "12:21:aa:43:jh", "name": "Invalid MAC"},
    )

    assert response.status_code == 422

def test_legacy_anchor_can_receive_immutable_mac_address_once(api) -> None:
    client, db, actor = api
    owner = add_user(db, "legacy-mac-owner", 13, can_config_anchor="yes")
    _, floor = add_group_and_map(db, owner, "Legacy Factory", "LEGACY_FLOOR")
    db.commit()
    actor["user"] = owner
    created = client.post(
        f"/api/locations/{floor.location_id}/anchors",
        json={"hardware_id": "978294", "name": "Legacy Anchor"},
    ).json()

    assigned = client.patch(
        f"/api/anchors/{created['data']['anchor_id']}",
        json={"mac_address": "12:21:aa:43:1a:29"},
    )

    assert assigned.status_code == 200
    assert assigned.json()["data"]["mac_address"] == "12:21:AA:43:1A:29"
    assert assigned.json()["data"]["hardware_id"] == "978294"
    assert db.query(AnchorConfigOutbox).order_by(AnchorConfigOutbox.revision.desc()).first().payload[
        "anchors"
    ][0]["mac_address"] == "12:21:AA:43:1A:29"

    changed_again = client.patch(
        f"/api/anchors/{created['data']['anchor_id']}",
        json={"mac_address": "12:21:AA:43:1A:30"},
    )
    assert changed_again.status_code == 409


def test_create_rounds_all_coordinates_to_two_decimal_places(api) -> None:
    client, db, actor = api
    owner = add_user(db, "owner", 1, can_config_anchor="yes")
    _, floor = add_group_and_map(db, owner, "Factory", "FLOOR_1")
    db.commit()
    actor["user"] = owner

    response = client.post(
        f"/api/locations/{floor.location_id}/anchors",
        json={
            "hardware_id": "A-ROUND",
            "name": "Rounded",
            "x": 8.325,
            "y": 7.644,
            "z": -1.005,
        },
    )

    assert response.status_code == 201
    assert (
        response.json()["data"]["x"],
        response.json()["data"]["y"],
        response.json()["data"]["z"],
    ) == (8.33, 7.64, -1.01)
    anchor = db.query(Anchor).one()
    assert (float(anchor.x), float(anchor.y), float(anchor.z)) == (8.33, 7.64, -1.01)
    assert db.query(AnchorConfigOutbox).one().payload["anchors"][0] == {
        "action": "upsert",
        "id": anchor.anchor_id,
        "mac_address": None,
        "name": "Rounded",
        "x": 8.33,
        "y": 7.64,
        "z": -1.01,
    }


def test_update_delete_and_resync_create_one_revision_and_supersede_old_delivery(api) -> None:
    client, db, actor = api
    owner = add_user(db, "owner", 1, can_config_anchor="yes")
    _, floor = add_group_and_map(db, owner, "Factory", "FLOOR_1")
    db.commit()
    actor["user"] = owner
    created = client.post(
        f"/api/locations/{floor.location_id}/anchors",
        json={"hardware_id": "A-1", "name": "Alpha", "x": 10, "y": 20},
    ).json()
    created_outbox = db.get(AnchorConfigOutbox, created["config_revision"])
    db.add(
        AnchorConfigDelivery(
            revision=created["config_revision"],
            gateway_id=100,
            payload=created_outbox.payload,
            status="pending",
        )
    )
    db.commit()

    updated = client.patch(
        f"/api/anchors/{created['data']['anchor_id']}",
        json={"name": "Beta", "x": 25.5, "z": 1.25},
    )
    assert updated.status_code == 200
    assert updated.json()["config_revision"] > created["config_revision"]
    assert updated.json()["data"]["hardware_id"] == "A-1"
    assert db.query(AnchorConfigDelivery).one().status == "superseded"

    try:
        from app.services.anchor_service import resync_location
    except ImportError:
        pytest.fail("resync_location service is not implemented")
    resync = resync_location(db, floor, owner, gateway_id=100)
    db.commit()
    assert resync.revision > updated.json()["config_revision"]

    deleted = client.delete(f"/api/anchors/{created['data']['anchor_id']}")
    assert deleted.status_code == 200
    assert deleted.json()["deleted_anchor_id"] == created["data"]["anchor_id"]
    assert db.query(Anchor).one().status == "inactive"
    deleted_event = db.query(AnchorConfigOutbox).filter(
        AnchorConfigOutbox.reason == "delete"
    ).one()
    assert deleted_event.payload["operation"] == "delta"
    assert deleted_event.payload["anchors"] == [{
        "action": "delete",
        "id": created["data"]["anchor_id"],
        "mac_address": None,
    }]
    recreated = client.post(
        f"/api/locations/{floor.location_id}/anchors",
        json={"hardware_id": "A-2", "name": "Beta"},
    )
    assert recreated.status_code == 201
    assert db.query(AnchorConfigOutbox).count() == 5


def test_update_event_contains_only_changed_anchor_and_noop_creates_no_revision(api) -> None:
    client, db, actor = api
    owner = add_user(db, "delta-owner", 21, can_config_anchor="yes")
    _, floor = add_group_and_map(db, owner, "Delta Factory", "DELTA_FLOOR")
    db.commit()
    actor["user"] = owner
    first = client.post(
        f"/api/locations/{floor.location_id}/anchors",
        json={"mac_address": "12:21:AA:43:1A:01", "name": "Anchor A"},
    ).json()
    second = client.post(
        f"/api/locations/{floor.location_id}/anchors",
        json={"mac_address": "12:21:AA:43:1A:02", "name": "Anchor B"},
    ).json()

    updated = client.patch(
        f"/api/anchors/{first['data']['anchor_id']}",
        json={"name": "Anchor A moved", "x": 25.25},
    )

    assert updated.status_code == 200
    event = db.get(AnchorConfigOutbox, updated.json()["config_revision"])
    assert event.payload["operation"] == "delta"
    assert [item["id"] for item in event.payload["anchors"]] == [
        first["data"]["anchor_id"]
    ]
    assert event.payload["anchors"][0]["action"] == "upsert"
    assert second["data"]["anchor_id"] not in {
        item["id"] for item in event.payload["anchors"]
    }

    revision_count = db.query(AnchorConfigOutbox).count()
    anchor_before = db.get(Anchor, first["data"]["anchor_id"])
    updated_at_before = anchor_before.updated_at
    noop = client.patch(
        f"/api/anchors/{first['data']['anchor_id']}",
        json={"name": "Anchor A moved", "x": 25.25},
    )

    assert noop.status_code == 200
    assert noop.json()["config_revision"] is None
    assert noop.json()["sync_status"] == "unchanged"
    assert db.query(AnchorConfigOutbox).count() == revision_count
    assert db.get(Anchor, first["data"]["anchor_id"]).updated_at == updated_at_before


def test_view_and_mutation_authorization_prevents_idor(api) -> None:
    client, db, actor = api
    owner = add_user(db, "owner", 1, can_config_anchor="yes")
    member = add_user(db, "member", 2, can_config_anchor="yes")
    outsider = add_user(db, "outsider", 3, can_config_anchor="yes")
    group, floor = add_group_and_map(db, owner, "Factory", "FLOOR_1")
    db.add(
        MapGroupMembership(
            group_id=group.group_id,
            user_id=member.user_id,
            status="accepted",
            invited_by_user_id=owner.user_id,
        )
    )
    db.commit()
    actor["user"] = owner
    anchor_id = client.post(
        f"/api/locations/{floor.location_id}/anchors",
        json={"hardware_id": "A-1", "name": "Alpha"},
    ).json()["data"]["anchor_id"]

    actor["user"] = member
    assert client.get(f"/api/locations/{floor.location_id}/anchors").status_code == 200
    assert client.get("/api/anchors/manage").json()["total"] == 0
    assert client.patch(f"/api/anchors/{anchor_id}", json={"name": "No"}).status_code == 403

    membership = db.get(MapGroupMembership, (group.group_id, member.user_id))
    membership.status = "pending"
    db.commit()
    assert client.get(f"/api/locations/{floor.location_id}/anchors").status_code == 404
    membership.status = "rejected"
    db.commit()
    assert client.get(f"/api/locations/{floor.location_id}/anchors").status_code == 404

    actor["user"] = outsider
    assert client.get(f"/api/anchors/{anchor_id}").status_code == 404
    assert client.get(f"/api/locations/{floor.location_id}/anchors").status_code == 404

    owner.can_config_anchor = "no"
    db.commit()
    actor["user"] = owner
    assert client.patch(f"/api/anchors/{anchor_id}", json={"name": "No"}).status_code == 403


def test_validation_duplicates_and_immutable_patch_fields(api) -> None:
    client, db, actor = api
    owner = add_user(db, "owner", 1, can_config_anchor="yes")
    _, floor = add_group_and_map(db, owner, "Factory", "FLOOR_1")
    db.commit()
    actor["user"] = owner
    first = client.post(
        f"/api/locations/{floor.location_id}/anchors",
        json={"hardware_id": "A-1", "name": "Alpha"},
    )
    anchor_id = first.json()["data"]["anchor_id"]

    assert client.post(
        f"/api/locations/{floor.location_id}/anchors",
        json={"hardware_id": "A-1", "name": "Other"},
    ).status_code == 409
    assert client.post(
        f"/api/locations/{floor.location_id}/anchors",
        json={"hardware_id": "A-2", "name": " alpha "},
    ).status_code == 409
    assert client.post(
        f"/api/locations/{floor.location_id}/anchors",
        json={"hardware_id": "bad space", "name": "Bad"},
    ).status_code == 422
    assert client.post(
        f"/api/locations/{floor.location_id}/anchors",
        json={"hardware_id": "A-3", "name": "Bad", "x": 101},
    ).status_code == 422
    assert client.patch(f"/api/anchors/{anchor_id}", json={}).status_code == 422
    assert client.patch(
        f"/api/anchors/{anchor_id}", json={"x": None}
    ).status_code == 422
    assert client.patch(
        f"/api/anchors/{anchor_id}", json={"hardware_id": "A-9"}
    ).status_code == 422
    assert db.query(Anchor).count() == 1
    assert db.query(AnchorConfigOutbox).count() == 1

def test_database_failure_rolls_back_anchor_and_outbox(api, monkeypatch) -> None:
    from app.api import anchors_routes

    client, db, actor = api
    owner = add_user(db, "owner", 1, can_config_anchor="yes")
    _, floor = add_group_and_map(db, owner, "Factory", "FLOOR_1")
    db.commit()
    actor["user"] = owner

    def fail_after_anchor_flush(session, location, user, data):
        session.add(
            Anchor(
                hardware_id=data.hardware_id,
                name=data.name,
                name_key=data.name.casefold(),
                x=data.x,
                y=data.y,
                z=data.z,
                location_id=location.location_id,
                created_by_user_id=user.user_id,
                updated_by_user_id=user.user_id,
            )
        )
        session.flush()
        raise RuntimeError("simulated database failure")

    monkeypatch.setattr(anchors_routes, "create_anchor", fail_after_anchor_flush)
    with pytest.raises(RuntimeError, match="simulated database failure"):
        client.post(
            f"/api/locations/{floor.location_id}/anchors",
            json={"hardware_id": "A-1", "name": "Alpha"},
        )

    assert db.query(Anchor).count() == 0
    assert db.query(AnchorConfigOutbox).count() == 0


def test_manage_search_pagination_is_scoped_to_owned_groups(api) -> None:
    client, db, actor = api
    owner = add_user(db, "owner", 1, can_config_anchor="yes")
    other = add_user(db, "other", 2, can_config_anchor="yes")
    admin = add_user(db, "admin", 3, role="admin")
    _, own_map = add_group_and_map(db, owner, "Owned", "FLOOR_1")
    _, other_map = add_group_and_map(db, other, "Other", "FLOOR_2")
    db.commit()
    actor["user"] = owner
    own_ids = []
    for hardware_id, name in (("OWN-1", "Lobby"), ("OWN-2", "Door")):
        own_ids.append(
            client.post(
                f"/api/locations/{own_map.location_id}/anchors",
                json={"hardware_id": hardware_id, "name": name},
            ).json()["data"]["anchor_id"]
        )
    actor["user"] = other
    other_id = client.post(
        f"/api/locations/{other_map.location_id}/anchors",
        json={"hardware_id": "OTHER-1", "name": "Secret"},
    ).json()["data"]["anchor_id"]

    actor["user"] = owner
    page = client.get("/api/anchors/manage?limit=1&offset=1")
    assert page.status_code == 200
    assert page.json()["total"] == 2
    assert len(page.json()["data"]) == 1
    assert client.get("/api/anchors/manage?q=own-2").json()["data"][0]["hardware_id"] == "OWN-2"
    assert client.get(f"/api/anchors/manage?q={own_ids[0]}").json()["total"] == 1
    assert client.get("/api/anchors/manage?q=secret").json()["total"] == 0

    actor["user"] = admin
    all_rows = client.get("/api/anchors/manage")
    assert all_rows.status_code == 200
    assert all_rows.json()["total"] == 3
    assert other_id in [item["anchor_id"] for item in all_rows.json()["data"]]
