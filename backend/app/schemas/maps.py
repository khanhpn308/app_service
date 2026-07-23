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
