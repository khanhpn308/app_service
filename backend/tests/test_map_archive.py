from datetime import date

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.core.map_archive import (
    DeleteReason,
    LocationArchiveError,
    archive_location,
)
from app.models.base import Base
from app.models.map_group import MapGroup
from app.models.map_location import LocationDeleted, LocationUsing
from app.models.user import User


@pytest.fixture
def db() -> Session:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


def add_user(db: Session, username: str, sequence: int) -> User:
    user = User(
        username=username,
        password="not-used",
        fullname=username,
        cccd=f"{sequence:012d}",
        creat_at=date(2026, 1, 1),
        expired_at=date(2099, 1, 1),
        status="active",
        role="admin" if username == "admin" else "user",
    )
    db.add(user)
    db.flush()
    return user


def seed_location(db: Session) -> tuple[LocationUsing, User]:
    owner = add_user(db, "owner", 1)
    uploader = add_user(db, "uploader", 2)
    admin = add_user(db, "admin", 3)
    group = MapGroup(
        name="Factory A",
        owner_user_id=owner.user_id,
        created_by_user_id=owner.user_id,
    )
    db.add(group)
    db.flush()
    location = LocationUsing(
        location="Floor_1",
        image_data=b"trusted-webp-bytes",
        mime_type="image/webp",
        original_filename="floor_1.webp",
        checksum_sha256="a" * 64,
        file_size_bytes=len(b"trusted-webp-bytes"),
        width=800,
        height=488,
        group_id=group.group_id,
        owner_user_id=owner.user_id,
        created_by_user_id=uploader.user_id,
    )
    db.add(location)
    db.commit()
    db.refresh(location)
    db.refresh(admin)
    return location, admin


def test_archive_copies_full_row_and_snapshots_before_deleting_active(
    db: Session,
) -> None:
    location, admin = seed_location(db)
    location_id = location.location_id

    archived = archive_location(
        db,
        location_id,
        deleted_by=admin,
        reason=DeleteReason.MAP_DELETED,
    )
    db.commit()

    assert db.get(LocationUsing, location_id) is None
    assert db.get(LocationDeleted, location_id) is archived
    assert archived.location == "Floor_1"
    assert archived.image_data == b"trusted-webp-bytes"
    assert archived.original_filename == "floor_1.webp"
    assert archived.group_name_snapshot == "Factory A"
    assert archived.owner_username_snapshot == "owner"
    assert archived.created_by_username_snapshot == "uploader"
    assert archived.deleted_by_username_snapshot == "admin"
    assert archived.delete_reason == DeleteReason.MAP_DELETED.value


def test_archive_does_not_commit_callers_transaction(db: Session) -> None:
    location, admin = seed_location(db)
    location_id = location.location_id

    archive_location(
        db,
        location_id,
        deleted_by=admin,
        reason=DeleteReason.MAP_DELETED,
    )
    db.rollback()

    assert db.get(LocationUsing, location_id) is not None
    assert db.get(LocationDeleted, location_id) is None


def test_missing_location_fails_without_creating_archive(db: Session) -> None:
    admin = add_user(db, "admin", 1)
    db.commit()

    with pytest.raises(LocationArchiveError) as error:
        archive_location(
            db,
            999,
            deleted_by=admin,
            reason=DeleteReason.MAP_DELETED,
        )

    assert error.value.code == "location_not_found"
    assert db.query(LocationDeleted).count() == 0


def test_invalid_delete_reason_fails_before_mutation(db: Session) -> None:
    location, admin = seed_location(db)
    location_id = location.location_id

    with pytest.raises(LocationArchiveError) as error:
        archive_location(
            db,
            location_id,
            deleted_by=admin,
            reason="unexpected",
        )
    db.rollback()

    assert error.value.code == "invalid_delete_reason"
    assert db.get(LocationUsing, location_id) is not None
    assert db.get(LocationDeleted, location_id) is None
