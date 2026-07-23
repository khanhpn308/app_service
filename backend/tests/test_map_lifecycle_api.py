from datetime import date

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.api.router import api_router
from app.core.deps import get_current_user, get_db, require_admin
from app.models.base import Base
from app.models.map_group import MapGroup, MapGroupMembership
from app.models.map_location import LocationDeleted, LocationUsing
from app.models.user import User


@pytest.fixture
def api():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    db = Session(engine)
    actor = {"user": None}
    app = FastAPI()
    app.include_router(api_router, prefix="/api")

    def override_db():
        yield db

    def override_actor():
        return actor["user"]

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_user] = override_actor
    app.dependency_overrides[require_admin] = override_actor
    with TestClient(app, raise_server_exceptions=False) as client:
        yield client, db, actor
    db.close()


def add_user(
    db: Session,
    username: str,
    sequence: int,
    *,
    role: str = "user",
    status: str = "active",
    expired_at: date | None = date(2099, 1, 1),
) -> User:
    user = User(
        username=username,
        password="not-used",
        fullname=username,
        cccd=f"{sequence:012d}",
        creat_at=date(2026, 1, 1),
        expired_at=expired_at,
        status=status,
        role=role,
    )
    db.add(user)
    db.flush()
    return user


def add_group(db: Session, owner: User, name: str) -> MapGroup:
    group = MapGroup(
        name=name,
        owner_user_id=owner.user_id,
        created_by_user_id=owner.user_id,
    )
    db.add(group)
    db.flush()
    return group


def add_map(
    db: Session,
    group: MapGroup,
    creator: User,
    location: str,
) -> LocationUsing:
    active = LocationUsing(
        location=location,
        image_data=f"webp-{location}".encode(),
        mime_type="image/webp",
        original_filename=f"{location}.webp",
        checksum_sha256=str(group.group_id).zfill(64),
        file_size_bytes=len(f"webp-{location}".encode()),
        width=800,
        height=480,
        group_id=group.group_id,
        owner_user_id=group.owner_user_id,
        created_by_user_id=creator.user_id,
    )
    db.add(active)
    db.flush()
    return active


def test_group_delete_archives_every_map_and_removes_memberships(api) -> None:
    client, db, actor = api
    owner = add_user(db, "group-owner", 201)
    member = add_user(db, "group-member", 202)
    group = add_group(db, owner, "Cascade Group")
    first = add_map(db, group, owner, "CASCADE_A")
    second = add_map(db, group, owner, "CASCADE_B")
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
    group_id = group.group_id
    map_ids = {first.location_id, second.location_id}

    response = client.delete(f"/api/map-groups/{group_id}")

    assert response.status_code == 204
    assert db.get(MapGroup, group_id) is None
    assert db.query(LocationUsing).filter_by(group_id=group_id).count() == 0
    assert db.query(MapGroupMembership).filter_by(group_id=group_id).count() == 0
    archived = db.query(LocationDeleted).filter(
        LocationDeleted.location_id.in_(map_ids)
    ).all()
    assert {row.location_id for row in archived} == map_ids
    assert {row.delete_reason for row in archived} == {"group_deleted"}


def test_repeated_group_delete_is_safe_and_does_not_duplicate_archive(api) -> None:
    client, db, actor = api
    owner = add_user(db, "race-owner", 211)
    group = add_group(db, owner, "Race Group")
    active = add_map(db, group, owner, "RACE_MAP")
    map_id = active.location_id
    group_id = group.group_id
    db.commit()
    actor["user"] = owner

    first = client.delete(f"/api/map-groups/{group_id}")
    second = client.delete(f"/api/map-groups/{group_id}")

    assert first.status_code == 204
    assert second.status_code == 404
    assert db.query(LocationDeleted).filter_by(location_id=map_id).count() == 1


def test_group_delete_rolls_back_every_change_when_one_archive_fails(api) -> None:
    client, db, actor = api
    owner = add_user(db, "rollback-owner", 215)
    group = add_group(db, owner, "Rollback Group")
    first = add_map(db, group, owner, "ROLLBACK_A")
    second = add_map(db, group, owner, "ROLLBACK_B")
    db.add(
        LocationDeleted(
            location_id=second.location_id,
            location=second.location,
            image_data=second.image_data,
            mime_type=second.mime_type,
            original_filename=second.original_filename,
            checksum_sha256=second.checksum_sha256,
            file_size_bytes=second.file_size_bytes,
            width=second.width,
            height=second.height,
            group_id_snapshot=group.group_id,
            group_name_snapshot=group.name,
            owner_user_id_snapshot=owner.user_id,
            owner_username_snapshot=owner.username,
            created_by_user_id_snapshot=owner.user_id,
            created_by_username_snapshot=owner.username,
            created_at=second.created_at,
            deleted_by_user_id_snapshot=owner.user_id,
            deleted_by_username_snapshot=owner.username,
            delete_reason="map_deleted",
        )
    )
    db.commit()
    actor["user"] = owner
    group_id = group.group_id
    first_id = first.location_id
    second_id = second.location_id

    response = client.delete(f"/api/map-groups/{group_id}")

    assert response.status_code == 409
    assert db.get(MapGroup, group_id) is not None
    assert db.get(LocationUsing, first_id) is not None
    assert db.get(LocationUsing, second_id) is not None
    assert db.get(LocationDeleted, first_id) is None
    assert db.get(LocationDeleted, second_id) is not None


def test_user_delete_archives_owned_groups_and_only_removes_foreign_membership(
    api,
) -> None:
    client, db, actor = api
    admin = add_user(db, "lifecycle-admin", 221, role="admin")
    target = add_user(db, "owner-to-delete", 222)
    other_owner = add_user(db, "other-owner", 223)
    owned_group = add_group(db, target, "Owned By Target")
    shared_group = add_group(db, other_owner, "Keep This Group")
    owned_map = add_map(db, owned_group, target, "OWNER_DELETE_MAP")
    shared_map = add_map(db, shared_group, other_owner, "KEEP_MAP")
    db.add(
        MapGroupMembership(
            group_id=shared_group.group_id,
            user_id=target.user_id,
            status="accepted",
            invited_by_user_id=other_owner.user_id,
        )
    )
    db.commit()
    actor["user"] = admin
    target_id = target.user_id
    owned_group_id = owned_group.group_id
    shared_group_id = shared_group.group_id
    owned_map_id = owned_map.location_id
    shared_map_id = shared_map.location_id

    response = client.delete(f"/api/users/{target_id}")

    assert response.status_code == 204
    assert db.get(User, target_id) is None
    assert db.get(MapGroup, owned_group_id) is None
    assert db.get(LocationUsing, owned_map_id) is None
    assert db.get(LocationDeleted, owned_map_id).delete_reason == "owner_deleted"
    assert db.get(MapGroup, shared_group_id) is not None
    assert db.get(LocationUsing, shared_map_id) is not None
    assert db.get(MapGroupMembership, (shared_group_id, target_id)) is None


def test_inactive_owner_hides_maps_from_member_but_not_admin_then_reappears(
    api,
) -> None:
    client, db, actor = api
    admin = add_user(db, "visibility-admin", 231, role="admin")
    owner = add_user(db, "visibility-owner", 232, status="deactive")
    member = add_user(db, "visibility-member", 233)
    group = add_group(db, owner, "Hidden Temporarily")
    active = add_map(db, group, owner, "VISIBILITY_MAP")
    db.add(
        MapGroupMembership(
            group_id=group.group_id,
            user_id=member.user_id,
            status="accepted",
            invited_by_user_id=admin.user_id,
        )
    )
    db.commit()

    actor["user"] = member
    assert client.get("/api/map-groups").json() == []
    assert client.get(f"/api/maps/{active.location_id}/image").status_code == 404

    actor["user"] = admin
    assert client.get(f"/api/maps/{active.location_id}/image").status_code == 200
    assert client.get(f"/api/map-groups/{group.group_id}/maps").status_code == 200

    owner.status = "active"
    db.commit()
    actor["user"] = member
    assert [row["group_id"] for row in client.get("/api/map-groups").json()] == [
        group.group_id
    ]
    assert client.get(f"/api/maps/{active.location_id}/image").status_code == 200
