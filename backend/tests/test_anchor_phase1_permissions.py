from datetime import date, timedelta

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.api.auth_routes import router as auth_router
from app.api.users_routes import router as users_router
from app.core.deps import get_current_user, get_db
from app.core.security import decode_token, hash_password
from app.models.base import Base
from app.models.map_group import MapGroup
from app.models.user import User


def add_user(
    db: Session,
    username: str,
    sequence: int,
    *,
    role: str = "user",
    status: str = "active",
    can_config_anchor: str = "no",
    expired_at: date | None = None,
) -> User:
    user = User(
        username=username,
        password=hash_password("secret123"),
        fullname=f"User {username}",
        cccd=f"{sequence:012d}",
        creat_at=date.today(),
        expired_at=expired_at or date.today() + timedelta(days=30),
        status=status,
        role=role,
        can_config_anchor=can_config_anchor,
    )
    db.add(user)
    db.flush()
    return user


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
    app.include_router(auth_router, prefix="/api")
    app.include_router(users_router, prefix="/api")

    def override_db():
        yield db

    def override_user():
        return actor["user"]

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_user] = override_user
    with TestClient(app) as client:
        yield client, db, actor
    db.close()


def test_register_login_and_me_return_anchor_permission_without_putting_it_in_jwt(api) -> None:
    client, db, actor = api
    admin = add_user(db, "admin", 1, role="admin")
    db.commit()
    actor["user"] = admin

    registered = client.post(
        "/api/auth/register",
        json={
            "username": "owner",
            "password": "secret123",
            "fullname": "Anchor Owner",
            "cccd": "000000000002",
            "email": None,
            "phone": None,
            "expired_at": str(date.today() + timedelta(days=30)),
            "role": "user",
            "can_config_anchor": "yes",
        },
    )
    assert registered.status_code == 200
    assert registered.json()["can_config_anchor"] == "yes"

    login = client.post(
        "/api/auth/login",
        json={"username": "owner", "password": "secret123"},
    )
    assert login.status_code == 200
    assert login.json()["user"]["can_config_anchor"] == "yes"
    assert "can_config_anchor" not in decode_token(login.json()["access_token"])

    actor["user"] = db.query(User).filter(User.username == "owner").one()
    me = client.get("/api/auth/me")
    assert me.status_code == 200
    assert me.json()["can_config_anchor"] == "yes"


def test_admin_can_grant_and_revoke_anchor_permission(api) -> None:
    client, db, actor = api
    admin = add_user(db, "admin", 1, role="admin")
    target = add_user(db, "target", 2)
    db.commit()
    actor["user"] = admin

    granted = client.patch(
        f"/api/users/{target.user_id}/anchor-permission",
        json={"can_config_anchor": "yes"},
    )
    assert granted.status_code == 200
    assert granted.json()["can_config_anchor"] == "yes"

    revoked = client.patch(
        f"/api/users/{target.user_id}/anchor-permission",
        json={"can_config_anchor": "no"},
    )
    assert revoked.status_code == 200
    assert revoked.json()["can_config_anchor"] == "no"
    db.refresh(target)
    assert target.can_config_anchor == "no"


def test_non_admin_cannot_update_anchor_permission(api) -> None:
    client, db, actor = api
    actor["user"] = add_user(db, "actor", 1, can_config_anchor="yes")
    target = add_user(db, "target", 2)
    db.commit()

    response = client.patch(
        f"/api/users/{target.user_id}/anchor-permission",
        json={"can_config_anchor": "yes"},
    )
    assert response.status_code == 403
    db.refresh(target)
    assert target.can_config_anchor == "no"


def test_anchor_config_permission_matrix() -> None:
    try:
        from app.core.map_access import can_config_anchor
    except ImportError:
        pytest.fail("can_config_anchor helper is not implemented")

    today = date(2026, 8, 7)
    admin = User(
        user_id=1,
        role="admin",
        status="deactive",
        expired_at=today,
        can_config_anchor="no",
    )
    owner_yes = User(
        user_id=2,
        role="user",
        status="active",
        expired_at=today + timedelta(days=1),
        can_config_anchor="yes",
    )
    owner_no = User(
        user_id=3,
        role="user",
        status="active",
        expired_at=today + timedelta(days=1),
        can_config_anchor="no",
    )
    member_yes = User(
        user_id=4,
        role="user",
        status="active",
        expired_at=today + timedelta(days=1),
        can_config_anchor="yes",
    )
    inactive_owner = User(
        user_id=5,
        role="user",
        status="deactive",
        expired_at=today + timedelta(days=1),
        can_config_anchor="yes",
    )
    expired_owner = User(
        user_id=6,
        role="user",
        status="active",
        expired_at=today,
        can_config_anchor="yes",
    )

    assert can_config_anchor(admin, MapGroup(owner_user_id=99), today=today)
    assert can_config_anchor(owner_yes, MapGroup(owner_user_id=2), today=today)
    assert not can_config_anchor(owner_no, MapGroup(owner_user_id=3), today=today)
    assert not can_config_anchor(member_yes, MapGroup(owner_user_id=99), today=today)
    assert not can_config_anchor(inactive_owner, MapGroup(owner_user_id=5), today=today)
    assert not can_config_anchor(expired_owner, MapGroup(owner_user_id=6), today=today)
