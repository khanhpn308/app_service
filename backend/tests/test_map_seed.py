from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.core.map_archive import DeleteReason, archive_location
from app.core.seed import (
    DEFAULT_ADMIN_USERNAME,
    SYSTEM_MAP_GROUP_NAME,
    ensure_default_admin,
    ensure_default_maps,
)
from app.models.base import Base
from app.models.map_group import MapGroup
from app.models.map_location import LocationDeleted, LocationUsing
from app.models.user import User


FLOORPLAN_DIR = Path(__file__).resolve().parents[2] / "src" / "assets" / "floorplans"
APP_SERVICE_DIR = Path(__file__).resolve().parents[2]


@pytest.fixture
def db() -> Session:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


def test_seed_creates_system_group_and_four_valid_maps_idempotently(
    db: Session,
) -> None:
    ensure_default_admin(db)

    ensure_default_maps(db, floorplan_dir=FLOORPLAN_DIR)
    first_ids = {
        row.location: row.location_id
        for row in db.query(LocationUsing).order_by(LocationUsing.location).all()
    }
    ensure_default_maps(db, floorplan_dir=FLOORPLAN_DIR)
    second_ids = {
        row.location: row.location_id
        for row in db.query(LocationUsing).order_by(LocationUsing.location).all()
    }

    admin = db.query(User).filter_by(username=DEFAULT_ADMIN_USERNAME).one()
    group = db.query(MapGroup).filter_by(
        owner_user_id=admin.user_id,
        name=SYSTEM_MAP_GROUP_NAME,
    ).one()
    assert first_ids == second_ids
    assert set(first_ids) == {"Floor_1", "Floor_2", "Floor_3", "Floor_4"}
    assert db.query(LocationUsing).count() == 4
    assert {
        (row.width, row.height <= 8000, row.mime_type, row.group_id)
        for row in db.query(LocationUsing).all()
    } == {(800, True, "image/webp", group.group_id)}
    assert {
        (row.owner_user_id, row.created_by_user_id)
        for row in db.query(LocationUsing).all()
    } == {(admin.user_id, admin.user_id)}


def test_seed_never_restores_a_location_found_in_archive(db: Session) -> None:
    ensure_default_admin(db)
    ensure_default_maps(db, floorplan_dir=FLOORPLAN_DIR)
    admin = db.query(User).filter_by(username=DEFAULT_ADMIN_USERNAME).one()
    floor_one = db.query(LocationUsing).filter_by(location="Floor_1").one()
    archived_id = floor_one.location_id
    archive_location(
        db,
        archived_id,
        deleted_by=admin,
        reason=DeleteReason.MAP_DELETED,
    )
    db.commit()

    ensure_default_maps(db, floorplan_dir=FLOORPLAN_DIR)

    assert db.query(LocationUsing).filter_by(location="Floor_1").count() == 0
    assert db.get(LocationDeleted, archived_id).location == "Floor_1"
    assert {row.location for row in db.query(LocationUsing).all()} == {
        "Floor_2",
        "Floor_3",
        "Floor_4",
    }


def test_seed_skips_case_insensitive_location_already_active_elsewhere(
    db: Session,
) -> None:
    ensure_default_admin(db)
    admin = db.query(User).filter_by(username=DEFAULT_ADMIN_USERNAME).one()
    existing_group = MapGroup(
        name="Existing Maps",
        owner_user_id=admin.user_id,
        created_by_user_id=admin.user_id,
    )
    db.add(existing_group)
    db.flush()
    db.add(
        LocationUsing(
            location="floor_2",
            image_data=b"existing",
            mime_type="image/webp",
            original_filename="existing.webp",
            checksum_sha256="e" * 64,
            file_size_bytes=8,
            width=800,
            height=100,
            group_id=existing_group.group_id,
            owner_user_id=admin.user_id,
            created_by_user_id=admin.user_id,
        )
    )
    db.commit()

    ensure_default_maps(db, floorplan_dir=FLOORPLAN_DIR)

    assert db.query(LocationUsing).filter(
        LocationUsing.location.ilike("floor_2")
    ).count() == 1
    assert db.query(LocationUsing).filter_by(location="Floor_2").count() == 0
    assert db.query(LocationUsing).count() == 4


def test_startup_and_backend_image_package_the_system_floorplans() -> None:
    main_source = (APP_SERVICE_DIR / "backend" / "app" / "main.py").read_text(
        encoding="utf-8"
    )
    dockerfile = (APP_SERVICE_DIR / "Dockerfile.backend").read_text(encoding="utf-8")

    assert main_source.index("ensure_default_admin(db)") < main_source.index(
        "ensure_default_maps(db)"
    )
    assert "COPY src/assets/floorplans/ /app/seed_floorplans/" in dockerfile
