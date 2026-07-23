from datetime import date

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.api.map_groups_routes import router
from app.core.deps import get_current_user, get_db
from app.models.base import Base
from app.models.map_group import MapGroup, MapGroupMembership
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


def add_group(db: Session, owner: User, name: str) -> MapGroup:
    group = MapGroup(
        name=name,
        owner_user_id=owner.user_id,
        created_by_user_id=owner.user_id,
    )
    db.add(group)
    db.flush()
    return group


def test_group_list_respects_owner_membership_and_owner_status(api) -> None:
    client, db, actor = api
    owner = add_user(db, "owner", 1)
    member = add_user(db, "member", 2)
    other = add_user(db, "other", 3)
    inactive_owner = add_user(db, "inactive", 4, status="deactive")
    owned = add_group(db, owner, "Owned")
    shared = add_group(db, other, "Shared")
    hidden = add_group(db, inactive_owner, "Hidden")
    db.add_all(
        [
            MapGroupMembership(
                group_id=shared.group_id,
                user_id=member.user_id,
                status="accepted",
                invited_by_user_id=other.user_id,
            ),
            MapGroupMembership(
                group_id=hidden.group_id,
                user_id=member.user_id,
                status="accepted",
                invited_by_user_id=inactive_owner.user_id,
            ),
        ]
    )
    db.commit()

    actor["user"] = owner
    owner_response = client.get("/api/map-groups")
    assert owner_response.status_code == 200
    assert [(row["name"], row["access_role"]) for row in owner_response.json()] == [
        ("Owned", "owner")
    ]

    actor["user"] = member
    member_response = client.get("/api/map-groups")
    assert member_response.status_code == 200
    assert [row["name"] for row in member_response.json()] == ["Shared"]


def test_admin_lists_all_groups_and_can_create_for_exact_owner(api) -> None:
    client, db, actor = api
    admin = add_user(db, "admin", 1, role="admin")
    owner = add_user(db, "OwnerExact", 2)
    add_group(db, owner, "Existing")
    db.commit()
    actor["user"] = admin

    response = client.post(
        "/api/map-groups",
        json={"name": "  Factory B  ", "owner_username": "OwnerExact"},
    )

    assert response.status_code == 201
    assert response.json()["name"] == "Factory B"
    assert response.json()["owner_username"] == "OwnerExact"
    assert response.json()["access_role"] == "admin"
    assert len(client.get("/api/map-groups").json()) == 2

    wrong_case = client.post(
        "/api/map-groups",
        json={"name": "Other", "owner_username": "ownerexact"},
    )
    assert wrong_case.status_code == 404


def test_user_creates_trimmed_group_and_duplicate_is_case_insensitive(api) -> None:
    client, db, actor = api
    owner = add_user(db, "owner", 1)
    db.commit()
    actor["user"] = owner

    created = client.post("/api/map-groups", json={"name": "  Factory A  "})
    duplicate = client.post("/api/map-groups", json={"name": "factory a"})
    blank = client.post("/api/map-groups", json={"name": "   "})

    assert created.status_code == 201
    assert created.json()["name"] == "Factory A"
    assert created.json()["can_manage"] is True
    assert duplicate.status_code == 409
    assert blank.status_code == 422


def test_only_owner_or_admin_can_rename_group_without_idor_leak(api) -> None:
    client, db, actor = api
    owner = add_user(db, "owner", 1)
    member = add_user(db, "member", 2)
    group = add_group(db, owner, "Before")
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
    denied = client.patch(
        f"/api/map-groups/{group.group_id}",
        json={"name": "Hijacked"},
    )
    assert denied.status_code == 404

    actor["user"] = owner
    renamed = client.patch(
        f"/api/map-groups/{group.group_id}",
        json={"name": "  After  "},
    )
    assert renamed.status_code == 200
    assert renamed.json()["name"] == "After"
