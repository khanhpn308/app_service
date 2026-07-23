from datetime import date
from hashlib import sha256
from io import BytesIO

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from PIL import Image
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.api.router import api_router
from app.core.deps import get_current_user, get_db
from app.core.map_archive import DeleteReason, archive_location
from app.core.rate_limit import limiter
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
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
    app.include_router(api_router, prefix="/api")

    def override_db():
        yield db

    def override_user():
        return actor["user"]

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_user] = override_user
    with TestClient(app) as client:
        yield client, db, actor
    db.close()


def add_user(
    db: Session,
    username: str,
    sequence: int,
    *,
    role: str = "user",
    status: str = "active",
) -> User:
    user = User(
        username=username,
        password="not-used",
        fullname=f"User {username}",
        cccd=f"{sequence:012d}",
        creat_at=date(2026, 1, 1),
        expired_at=date(2099, 1, 1),
        status=status,
        role=role,
    )
    db.add(user)
    db.flush()
    return user


def add_group(db: Session, owner: User, name: str = "Factory") -> MapGroup:
    group = MapGroup(
        name=name,
        owner_user_id=owner.user_id,
        created_by_user_id=owner.user_id,
    )
    db.add(group)
    db.flush()
    return group


def webp_bytes(width: int = 800, height: int = 320) -> bytes:
    output = BytesIO()
    Image.new("RGB", (width, height), color=(220, 225, 230)).save(
        output,
        format="WEBP",
    )
    return output.getvalue()


def add_map(
    db: Session,
    group: MapGroup,
    creator: User,
    location: str,
) -> LocationUsing:
    content = webp_bytes()
    active = LocationUsing(
        location=location,
        image_data=content,
        mime_type="image/webp",
        original_filename=f"{location}.webp",
        checksum_sha256=sha256(content).hexdigest(),
        file_size_bytes=len(content),
        width=800,
        height=320,
        group_id=group.group_id,
        owner_user_id=group.owner_user_id,
        created_by_user_id=creator.user_id,
    )
    db.add(active)
    db.flush()
    return active


def test_member_reads_only_accepted_group_maps_and_private_image(api) -> None:
    client, db, actor = api
    owner = add_user(db, "delivery-owner", 100)
    member = add_user(db, "delivery-member", 101)
    outsider = add_user(db, "delivery-outsider", 102)
    group = add_group(db, owner)
    active = add_map(db, group, owner, "Shared_Map")
    image_bytes = active.image_data
    db.add(
        MapGroupMembership(
            group_id=group.group_id,
            user_id=member.user_id,
            status="accepted",
            invited_by_user_id=owner.user_id,
        )
    )
    db.commit()

    actor["user"] = member
    listed = client.get(f"/api/map-groups/{group.group_id}/maps")
    image = client.get(f"/api/maps/{active.location_id}/image")
    legacy_locations = client.get("/api/locations")
    legacy_image = client.get("/api/floorplans/shared_map.webp")

    assert listed.status_code == 200
    assert listed.json()[0]["image_url"] == f"/api/maps/{active.location_id}/image"
    assert image.status_code == 200
    assert image.content == image_bytes
    assert image.headers["content-type"] == "image/webp"
    assert image.headers["cache-control"] == "private, no-store"
    assert image.headers["x-content-type-options"] == "nosniff"
    assert legacy_locations.json() == {"data": ["Shared_Map"]}
    assert legacy_image.status_code == 200
    assert legacy_image.content == image_bytes

    actor["user"] = outsider
    assert client.get(f"/api/maps/{active.location_id}/image").status_code == 404
    assert client.get("/api/floorplans/Shared_Map.webp").status_code == 404
    assert client.get("/api/locations").json() == {"data": []}


def test_owner_archives_map_and_can_reuse_location_with_new_id(api) -> None:
    client, db, actor = api
    owner = add_user(db, "archive-owner", 110)
    member = add_user(db, "archive-member", 111)
    group = add_group(db, owner)
    active = add_map(db, group, owner, "Reusable_Map")
    original_id = active.location_id
    db.add(
        MapGroupMembership(
            group_id=group.group_id,
            user_id=member.user_id,
            status="accepted",
            invited_by_user_id=owner.user_id,
        )
    )
    db.commit()

    actor["user"] = member
    assert client.delete(f"/api/maps/{original_id}").status_code == 404

    actor["user"] = owner
    deleted = client.delete(f"/api/maps/{original_id}")
    assert deleted.status_code == 204
    assert db.get(LocationUsing, original_id) is None
    archived = db.get(LocationDeleted, original_id)
    assert archived is not None
    assert archived.delete_reason == "map_deleted"
    assert archived.image_data.startswith(b"RIFF")
    assert client.get(f"/api/maps/{original_id}/image").status_code == 404

    replacement = client.post(
        f"/api/map-groups/{group.group_id}/maps",
        data={"location": " reusable_map "},
        files={"file": ("replacement.webp", webp_bytes(), "image/webp")},
    )
    assert replacement.status_code == 201
    assert replacement.json()["location_id"] != original_id


def test_admin_deleted_map_history_is_paginated_metadata_only(api) -> None:
    client, db, actor = api
    admin = add_user(db, "history-admin", 120, role="admin")
    owner = add_user(db, "history-owner", 121)
    group = add_group(db, owner)
    first = add_map(db, group, owner, "History_A")
    second = add_map(db, group, owner, "History_B")
    db.commit()
    archive_location(
        db,
        first.location_id,
        deleted_by=admin,
        reason=DeleteReason.MAP_DELETED,
    )
    archive_location(
        db,
        second.location_id,
        deleted_by=admin,
        reason=DeleteReason.MAP_DELETED,
    )
    db.commit()

    actor["user"] = owner
    assert client.get("/api/admin/deleted-maps").status_code == 403

    actor["user"] = admin
    first_page = client.get("/api/admin/deleted-maps?limit=1&offset=0")
    second_page = client.get("/api/admin/deleted-maps?limit=1&offset=1")

    assert first_page.status_code == 200
    assert first_page.json()["total"] == 2
    assert first_page.json()["limit"] == 1
    assert first_page.json()["offset"] == 0
    assert len(first_page.json()["data"]) == 1
    assert len(second_page.json()["data"]) == 1
    assert "image_data" not in first_page.json()["data"][0]
    assert {
        first_page.json()["data"][0]["location"],
        second_page.json()["data"][0]["location"],
    } == {"History_A", "History_B"}
    assert client.get("/api/admin/deleted-maps?limit=101").status_code == 422
