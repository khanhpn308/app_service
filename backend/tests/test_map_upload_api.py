from datetime import date
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
from app.core.rate_limit import limiter
from app.core.security import create_access_token
from app.models.base import Base
from app.models.map_group import MapGroup, MapGroupMembership
from app.models.map_location import LocationUsing
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
) -> User:
    user = User(
        username=username,
        password="not-used",
        fullname=f"User {username}",
        cccd=f"{sequence:012d}",
        creat_at=date(2026, 1, 1),
        expired_at=date(2099, 1, 1),
        status="active",
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
    Image.new("RGB", (width, height), color=(240, 240, 240)).save(
        output,
        format="WEBP",
    )
    return output.getvalue()

def animated_webp_bytes() -> bytes:
    output = BytesIO()
    first = Image.new("RGB", (800, 20), color="white")
    second = Image.new("RGB", (800, 20), color="black")
    first.save(
        output,
        format="WEBP",
        save_all=True,
        append_images=[second],
        duration=100,
        loop=0,
    )
    return output.getvalue()


def image_bytes(
    image_format: str,
    *,
    width: int,
    height: int,
) -> bytes:
    output = BytesIO()
    Image.new("RGB", (width, height), color=(240, 240, 240)).save(
        output,
        format=image_format,
    )
    return output.getvalue()


def upload(
    client: TestClient,
    group_id: int,
    *,
    location: str,
    content: bytes,
    filename: str = "floor.webp",
    content_type: str = "image/webp",
    headers: dict[str, str] | None = None,
):
    return client.post(
        f"/api/map-groups/{group_id}/maps",
        data={"location": location},
        files={"file": (filename, content, content_type)},
        headers=headers,
    )


@pytest.mark.parametrize(
    ("image_format", "filename", "content_type"),
    [
        ("WEBP", "floor.webp", "image/webp"),
        ("PNG", "floor.png", "image/png"),
        ("JPEG", "floor.jpg", "image/jpeg"),
    ],
)
def test_owner_uploads_supported_image_and_lists_metadata_without_blob(
    api,
    image_format: str,
    filename: str,
    content_type: str,
) -> None:
    client, db, actor = api
    owner = add_user(db, "owner-upload", 1)
    group = add_group(db, owner)
    db.commit()
    actor["user"] = owner
    content = image_bytes(image_format, width=1234, height=418)

    response = upload(
        client,
        group.group_id,
        location="  Floor_A  ",
        content=content,
        filename=filename,
        content_type=content_type,
    )

    assert response.status_code == 201
    assert response.json()["location"] == "Floor_A"
    assert response.json()["width"] == 1234
    assert response.json()["height"] == 418
    assert response.json()["mime_type"] == content_type
    assert response.json()["owner_user_id"] == owner.user_id
    assert response.json()["created_by_user_id"] == owner.user_id
    assert "image_data" not in response.json()

    stored = db.get(LocationUsing, response.json()["location_id"])
    assert stored is not None
    assert stored.mime_type == content_type

    image = client.get(f"/api/maps/{stored.location_id}/image")
    assert image.status_code == 200
    assert image.headers["content-type"] == content_type
    assert image.content == content

    listed = client.get(f"/api/map-groups/{group.group_id}/maps")
    assert listed.status_code == 200
    assert [item["location"] for item in listed.json()] == ["Floor_A"]
    assert "image_data" not in listed.json()[0]


def test_upload_rejects_member_duplicate_and_invalid_files(api) -> None:
    client, db, actor = api
    owner = add_user(db, "owner-validation", 10)
    member = add_user(db, "member-validation", 11)
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
    denied = upload(
        client,
        group.group_id,
        location="Member_Map",
        content=webp_bytes(),
    )
    assert denied.status_code == 404

    actor["user"] = owner
    created = upload(
        client,
        group.group_id,
        location="Floor_B",
        content=webp_bytes(),
    )
    duplicate = upload(
        client,
        group.group_id,
        location=" floor_b ",
        content=webp_bytes(),
    )
    arbitrary_size = upload(
        client,
        group.group_id,
        location="Arbitrary_Size",
        content=webp_bytes(width=799, height=8001),
    )
    wrong_type = upload(
        client,
        group.group_id,
        location="Wrong_Type",
        content=b"GIF89a",
        filename="floor.gif",
        content_type="image/gif",
    )
    too_large = upload(
        client,
        group.group_id,
        location="Too_Large",
        content=b"x" * (10 * 1024 * 1024),
    )

    assert created.status_code == 201
    assert duplicate.status_code == 409
    assert arbitrary_size.status_code == 201
    assert wrong_type.status_code == 415
    assert too_large.status_code == 413

def test_upload_rejects_disguised_and_animated_webp_at_api_boundary(api) -> None:
    client, db, actor = api
    owner = add_user(db, "owner-malicious-upload", 15)
    group = add_group(db, owner)
    db.commit()
    actor["user"] = owner

    png = BytesIO()
    Image.new("RGB", (800, 20), color="white").save(png, format="PNG")

    disguised = upload(
        client,
        group.group_id,
        location="DISGUISED_PNG",
        content=png.getvalue(),
        filename="disguised.webp",
        content_type="image/webp",
    )
    animated = upload(
        client,
        group.group_id,
        location="ANIMATED_WEBP",
        content=animated_webp_bytes(),
    )

    assert disguised.status_code == 422
    assert disguised.json()["detail"] == "Định dạng nội dung ảnh không khớp tên file hoặc MIME"
    assert animated.status_code == 422
    assert animated.json()["detail"] == "Không hỗ trợ ảnh động"
    assert db.query(LocationUsing).count() == 0


def test_admin_upload_uses_group_owner_but_records_admin_as_creator(api) -> None:
    client, db, actor = api
    admin = add_user(db, "admin-upload", 20, role="admin")
    owner = add_user(db, "owner-admin-upload", 21)
    group = add_group(db, owner)
    db.commit()
    actor["user"] = admin

    response = upload(
        client,
        group.group_id,
        location="Admin_Map",
        content=webp_bytes(),
    )

    assert response.status_code == 201
    assert response.json()["owner_user_id"] == owner.user_id
    assert response.json()["created_by_user_id"] == admin.user_id


def test_upload_rate_limit_is_scoped_to_authenticated_user(api) -> None:
    client, db, actor = api
    owner = add_user(db, "rate-owner", 30)
    other_owner = add_user(db, "rate-other", 31)
    group = add_group(db, owner, "Rate First")
    other_group = add_group(db, other_owner, "Rate Second")
    db.commit()
    payload = webp_bytes(height=64)

    actor["user"] = owner
    token = create_access_token(
        subject=owner.username,
        user_id=owner.user_id,
        role=owner.role,
    )
    headers = {"Authorization": f"Bearer {token}"}
    for index in range(30):
        response = upload(
            client,
            group.group_id,
            location=f"Rate_{index}",
            content=payload,
            headers=headers,
        )
        assert response.status_code == 201

    limited = upload(
        client,
        group.group_id,
        location="Rate_Limited",
        content=payload,
        headers=headers,
    )

    actor["user"] = other_owner
    other_token = create_access_token(
        subject=other_owner.username,
        user_id=other_owner.user_id,
        role=other_owner.role,
    )
    separate_user = upload(
        client,
        other_group.group_id,
        location="Other_Rate",
        content=payload,
        headers={"Authorization": f"Bearer {other_token}"},
    )

    assert limited.status_code == 429
    assert separate_user.status_code == 201
