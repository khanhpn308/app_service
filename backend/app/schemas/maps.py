"""API contracts for active and archived floorplan maps."""

from datetime import datetime

from pydantic import BaseModel


class MapPublic(BaseModel):
    location_id: int
    location: str
    mime_type: str
    original_filename: str
    checksum_sha256: str
    file_size_bytes: int
    width: int
    height: int
    group_id: int
    owner_user_id: int
    created_by_user_id: int | None
    created_at: datetime
    image_url: str


class DeletedMapPublic(BaseModel):
    location_id: int
    location: str
    mime_type: str
    original_filename: str
    checksum_sha256: str
    file_size_bytes: int
    width: int
    height: int
    group_id_snapshot: int
    group_name_snapshot: str
    owner_user_id_snapshot: int
    owner_username_snapshot: str
    created_by_user_id_snapshot: int | None
    created_by_username_snapshot: str | None
    created_at: datetime
    deleted_by_user_id_snapshot: int
    deleted_by_username_snapshot: str
    deleted_at: datetime
    delete_reason: str


class DeletedMapPage(BaseModel):
    data: list[DeletedMapPublic]
    total: int
    limit: int
    offset: int
