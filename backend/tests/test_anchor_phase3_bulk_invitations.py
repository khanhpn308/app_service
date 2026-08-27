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
) -> User:
    user = User(
        username=username,
        password="not-used",
        fullname=f"User {username}",
        cccd=f"{sequence:012d}",
        creat_at=date(2026, 1, 1),
        expired_at=date(2099, 1, 1),
        status=status,
        role="user",
    )
    db.add(user)
    db.flush()
    return user


def test_bulk_invitation_returns_partial_results_and_processes_each_username_once(api) -> None:
    client, db, actor = api
    owner = add_user(db, "owner-bulk", 1)
    invited = add_user(db, "InviteExact", 2)
    inactive = add_user(db, "inactive", 3, status="deactive")
    accepted = add_user(db, "accepted", 4)
    rejected = add_user(db, "rejected", 5)
    group = MapGroup(
        name="Factory",
        owner_user_id=owner.user_id,
        created_by_user_id=owner.user_id,
    )
    db.add(group)
    db.flush()
    db.add_all(
        [
            MapGroupMembership(
                group_id=group.group_id,
                user_id=accepted.user_id,
                status="accepted",
                invited_by_user_id=owner.user_id,
            ),
            MapGroupMembership(
                group_id=group.group_id,
                user_id=rejected.user_id,
                status="rejected",
                invited_by_user_id=owner.user_id,
            ),
        ]
    )
    db.commit()
    actor["user"] = owner

    response = client.post(
        f"/api/map-groups/{group.group_id}/invitations/bulk",
        json={
            "usernames": [
                " InviteExact ",
                "InviteExact",
                "inviteexact",
                "inactive",
                "accepted",
                "rejected",
                "missing",
            ]
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["invited_count"] == 2
    assert body["error_count"] == 5
    assert [(item["username"], item["code"]) for item in body["results"]] == [
        ("InviteExact", None),
        ("InviteExact", "duplicate_input"),
        ("inviteexact", "user_not_found"),
        ("inactive", "inactive_user"),
        ("accepted", "already_member"),
        ("rejected", None),
        ("missing", "user_not_found"),
    ]
    memberships = db.query(MapGroupMembership).filter(
        MapGroupMembership.group_id == group.group_id
    ).all()
    states = {row.user_id: row.status for row in memberships}
    assert states[invited.user_id] == "pending"
    assert states[rejected.user_id] == "pending"
    assert states[accepted.user_id] == "accepted"


def test_bulk_invitation_validates_nonempty_max_50_and_manager_scope(api) -> None:
    client, db, actor = api
    owner = add_user(db, "owner-limits", 10)
    outsider = add_user(db, "outsider-limits", 11)
    group = MapGroup(
        name="Factory",
        owner_user_id=owner.user_id,
        created_by_user_id=owner.user_id,
    )
    db.add(group)
    db.commit()

    actor["user"] = owner
    assert client.post(
        f"/api/map-groups/{group.group_id}/invitations/bulk",
        json={"usernames": []},
    ).status_code == 422
    assert client.post(
        f"/api/map-groups/{group.group_id}/invitations/bulk",
        json={"usernames": [f"user-{index}" for index in range(51)]},
    ).status_code == 422
    assert client.post(
        f"/api/map-groups/{group.group_id}/invitations/bulk",
        json={"usernames": ["   "]},
    ).status_code == 422

    actor["user"] = outsider
    assert client.post(
        f"/api/map-groups/{group.group_id}/invitations/bulk",
        json={"usernames": ["owner-limits"]},
    ).status_code == 404


def test_bulk_invitation_uses_the_authenticated_invitation_rate_limit(api) -> None:
    client, db, actor = api
    owner = add_user(db, "owner-bulk-rate", 20)
    group = MapGroup(
        name="Factory",
        owner_user_id=owner.user_id,
        created_by_user_id=owner.user_id,
    )
    db.add(group)
    db.commit()
    actor["user"] = owner
    token = create_access_token(
        subject=owner.username,
        user_id=owner.user_id,
        role=owner.role,
    )
    headers = {"Authorization": f"Bearer {token}"}

    for index in range(100):
        response = client.post(
            f"/api/map-groups/{group.group_id}/invitations/bulk",
            json={"usernames": [f"missing-{index}"]},
            headers=headers,
        )
        assert response.status_code == 200

    limited = client.post(
        f"/api/map-groups/{group.group_id}/invitations/bulk",
        json={"usernames": ["missing-last"]},
        headers=headers,
    )
    assert limited.status_code == 429
