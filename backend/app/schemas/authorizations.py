from datetime import date

from pydantic import BaseModel, Field


class AuthorizedDeviceBrief(BaseModel):
    """Thiết bị đã phân quyền cho user (dùng trong GET /users)."""

    device_id: int
    devicename: str | None = None


class AuthorizationCreate(BaseModel):
    device_id: int
    user_id: int
    granted_at: date | None = None
    granted_by: str | None = Field(default=None, max_length=45)
    expired_at: date | None = None


class AuthorizationPublic(BaseModel):
    device_id: int
    user_id: int
    granted_at: date | None = None
    granted_by: str | None = None
    expired_at: date | None = None

    model_config = {"from_attributes": True}

