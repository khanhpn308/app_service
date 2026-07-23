from datetime import date

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.api.map_groups_routes import router
from app.core.deps import get_current_user, get_db
from app.core.rate_limit import limiter
from app.core.security import create_access_token
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
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
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
    status: str = "active",
    role: str = "user",
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


def test_owner_invites_exact_active_username_and_lists_members(api) -> None:
    client, db, actor = api
    owner = add_user(db, "owner", 1)
    target = add_user(db, "MemberExact", 2)
    group = add_group(db, owner)
    db.commit()
    actor["user"] = owner

    wrong_case = client.post(
        f"/api/map-groups/{group.group_id}/invitations",
        json={"username": "memberexact"},
    )
    invited = client.post(
        f"/api/map-groups/{group.group_id}/invitations",
        json={"username": "MemberExact"},
    )
    members = client.get(f"/api/map-groups/{group.group_id}/members")

    assert wrong_case.status_code == 404
    assert invited.status_code == 201
    assert invited.json()["user_id"] == target.user_id
    assert invited.json()["status"] == "pending"
    assert members.status_code == 200
    assert [(row["username"], row["status"]) for row in members.json()] == [
        ("MemberExact", "pending")
    ]


def test_invitation_rejects_self_duplicate_inactive_and_non_manager(api) -> None:
    client, db, actor = api
    owner = add_user(db, "owner", 1)
    target = add_user(db, "target", 2)
    inactive = add_user(db, "inactive", 3, status="deactive")
    outsider = add_user(db, "outsider", 4)
    group = add_group(db, owner)
    db.commit()
    actor["user"] = owner

    self_invite = client.post(
        f"/api/map-groups/{group.group_id}/invitations",
        json={"username": "owner"},
    )
    first = client.post(
        f"/api/map-groups/{group.group_id}/invitations",
        json={"username": "target"},
    )
    duplicate = client.post(
        f"/api/map-groups/{group.group_id}/invitations",
        json={"username": "target"},
    )
    inactive_response = client.post(
        f"/api/map-groups/{group.group_id}/invitations",
        json={"username": "inactive"},
    )

    actor["user"] = outsider
    denied = client.post(
        f"/api/map-groups/{group.group_id}/invitations",
        json={"username": "target"},
    )

    assert self_invite.status_code == 409
    assert first.status_code == 201
    assert duplicate.status_code == 409
    assert inactive_response.status_code == 409
    assert denied.status_code == 404


def test_rejected_user_can_be_reinvited_and_manager_can_remove_member(api) -> None:
    client, db, actor = api
    owner = add_user(db, "owner", 1)
    target = add_user(db, "target", 2)
    group = add_group(db, owner)
    membership = MapGroupMembership(
        group_id=group.group_id,
        user_id=target.user_id,
        status="rejected",
        invited_by_user_id=owner.user_id,
    )
    db.add(membership)
    db.commit()
    actor["user"] = owner

    reinvited = client.post(
        f"/api/map-groups/{group.group_id}/invitations",
        json={"username": "target"},
    )
    removed = client.delete(
        f"/api/map-groups/{group.group_id}/members/{target.user_id}"
    )

    assert reinvited.status_code == 201
    assert reinvited.json()["status"] == "pending"
    assert removed.status_code == 204
    assert db.get(MapGroupMembership, (group.group_id, target.user_id)) is None


def test_member_cannot_remove_self_or_manage_members(api) -> None:
    client, db, actor = api
    owner = add_user(db, "owner", 1)
    member = add_user(db, "member", 2)
    group = add_group(db, owner)
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

    assert client.get(f"/api/map-groups/{group.group_id}/members").status_code == 404
    assert (
        client.delete(
            f"/api/map-groups/{group.group_id}/members/{member.user_id}"
        ).status_code
        == 404
    )


def test_user_accepts_or_rejects_only_their_pending_invitations(api) -> None:
    client, db, actor = api
    owner = add_user(db, "owner", 1)
    invited = add_user(db, "invited", 2)
    other = add_user(db, "other", 3)
    accepted_group = add_group(db, owner, "Accept")
    rejected_group = add_group(db, owner, "Reject")
    db.add_all(
        [
            MapGroupMembership(
                group_id=accepted_group.group_id,
                user_id=invited.user_id,
                status="pending",
                invited_by_user_id=owner.user_id,
            ),
            MapGroupMembership(
                group_id=rejected_group.group_id,
                user_id=invited.user_id,
                status="pending",
                invited_by_user_id=owner.user_id,
            ),
        ]
    )
    db.commit()
    actor["user"] = invited

    inbox = client.get("/api/map-group-invitations")
    accepted = client.patch(
        f"/api/map-group-invitations/{accepted_group.group_id}",
        json={"status": "accepted"},
    )
    rejected = client.patch(
        f"/api/map-group-invitations/{rejected_group.group_id}",
        json={"status": "rejected"},
    )
    repeated = client.patch(
        f"/api/map-group-invitations/{accepted_group.group_id}",
        json={"status": "rejected"},
    )
    actor["user"] = other
    idor = client.patch(
        f"/api/map-group-invitations/{accepted_group.group_id}",
        json={"status": "accepted"},
    )

    assert inbox.status_code == 200
    assert {row["group_name"] for row in inbox.json()} == {"Accept", "Reject"}
    assert accepted.status_code == 200
    assert accepted.json()["status"] == "accepted"
    assert rejected.status_code == 200
    assert rejected.json()["status"] == "rejected"
    assert repeated.status_code == 409
    assert idor.status_code == 404


def test_accept_is_blocked_when_group_owner_is_inactive(api) -> None:
    client, db, actor = api
    owner = add_user(db, "owner", 1, status="deactive")
    invited = add_user(db, "invited", 2)
    group = add_group(db, owner)
    db.add(
        MapGroupMembership(
            group_id=group.group_id,
            user_id=invited.user_id,
            status="pending",
            invited_by_user_id=owner.user_id,
        )
    )
    db.commit()
    actor["user"] = invited

    response = client.patch(
        f"/api/map-group-invitations/{group.group_id}",
        json={"status": "accepted"},
    )

    assert response.status_code == 409
    assert db.get(MapGroupMembership, (group.group_id, invited.user_id)).status == "pending"


def test_invitation_rate_limit_is_scoped_to_authenticated_user(api) -> None:
    client, db, actor = api
    owner = add_user(db, "owner", 1)
    second_owner = add_user(db, "second-owner", 2)
    first_group = add_group(db, owner, "First")
    second_group = add_group(db, second_owner, "Second")
    targets = [add_user(db, f"target-{index}", index + 10) for index in range(102)]
    db.commit()

    actor["user"] = owner
    owner_token = create_access_token(
        subject=owner.username,
        user_id=owner.user_id,
        role=owner.role,
    )
    owner_headers = {"Authorization": f"Bearer {owner_token}"}
    for target in targets[:100]:
        response = client.post(
            f"/api/map-groups/{first_group.group_id}/invitations",
            json={"username": target.username},
            headers=owner_headers,
        )
        assert response.status_code == 201

    limited = client.post(
        f"/api/map-groups/{first_group.group_id}/invitations",
        json={"username": targets[100].username},
        headers=owner_headers,
    )

    actor["user"] = second_owner
    second_token = create_access_token(
        subject=second_owner.username,
        user_id=second_owner.user_id,
        role=second_owner.role,
    )
    separate_user = client.post(
        f"/api/map-groups/{second_group.group_id}/invitations",
        json={"username": targets[101].username},
        headers={"Authorization": f"Bearer {second_token}"},
    )

    assert limited.status_code == 429
    assert separate_user.status_code == 201
