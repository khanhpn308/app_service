from datetime import date, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.core.map_access import can_manage_group, can_view_group, is_user_active
from app.models.base import Base
from app.models.map_group import MapGroup, MapGroupMembership
from app.models.user import User


@pytest.fixture
def db() -> Session:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


def add_user(
    db: Session,
    username: str,
    *,
    role: str = "user",
    status: str = "active",
    expired_at: date | None = None,
) -> User:
    user = User(
        username=username,
        password="not-used",
        fullname=username,
        cccd=f"{len(db.query(User).all()) + 1:012d}",
        creat_at=date(2026, 1, 1),
        expired_at=expired_at,
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


def test_active_account_requires_active_status_and_future_expiry() -> None:
    today = date(2026, 7, 23)

    assert is_user_active(
        User(status="active", expired_at=today + timedelta(days=1)),
        today=today,
    )
    assert not is_user_active(
        User(status="deactive", expired_at=today + timedelta(days=1)),
        today=today,
    )
    assert not is_user_active(
        User(status="active", expired_at=today),
        today=today,
    )
    assert not is_user_active(
        User(status="active", expired_at=today - timedelta(days=1)),
        today=today,
    )


def test_admin_can_manage_and_view_any_group(db: Session) -> None:
    owner = add_user(db, "owner", status="deactive")
    admin = add_user(db, "admin", role="admin", status="deactive")
    group = add_group(db, owner)

    assert can_manage_group(admin, group)
    assert can_view_group(db, admin, group)


def test_active_owner_can_manage_and_view_own_group(db: Session) -> None:
    owner = add_user(db, "owner")
    group = add_group(db, owner)

    assert can_manage_group(owner, group)
    assert can_view_group(db, owner, group)


def test_only_accepted_member_can_view_active_owner_group(db: Session) -> None:
    owner = add_user(db, "owner")
    accepted = add_user(db, "accepted")
    pending = add_user(db, "pending")
    rejected = add_user(db, "rejected")
    outsider = add_user(db, "outsider")
    group = add_group(db, owner)
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
                user_id=pending.user_id,
                status="pending",
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
    db.flush()

    assert can_view_group(db, accepted, group)
    assert not can_view_group(db, pending, group)
    assert not can_view_group(db, rejected, group)
    assert not can_view_group(db, outsider, group)
    assert not can_manage_group(accepted, group)


def test_non_admin_cannot_view_group_when_owner_is_inactive(
    db: Session,
) -> None:
    owner = add_user(db, "owner", status="deactive")
    member = add_user(db, "member")
    group = add_group(db, owner)
    db.add(
        MapGroupMembership(
            group_id=group.group_id,
            user_id=member.user_id,
            status="accepted",
            invited_by_user_id=owner.user_id,
        )
    )
    db.flush()

    assert not can_view_group(db, owner, group)
    assert not can_view_group(db, member, group)


def test_inactive_member_cannot_view_active_owner_group(db: Session) -> None:
    owner = add_user(db, "owner")
    member = add_user(db, "member", status="deactive")
    group = add_group(db, owner)
    db.add(
        MapGroupMembership(
            group_id=group.group_id,
            user_id=member.user_id,
            status="accepted",
            invited_by_user_id=owner.user_id,
        )
    )
    db.flush()

    assert not can_view_group(db, member, group)
