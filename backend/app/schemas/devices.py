from pydantic import BaseModel, Field


class DeviceCreate(BaseModel):
    device_id: int
    devicename: str | None = None
    password: str | None = None
    status: str | None = None
    user_device_asignment_id: int
    location: str | None = Field(default=None, max_length=255)
    device_type: str | None = Field(default=None, max_length=45)


class DevicePublic(BaseModel):
    device_id: int
    devicename: str | None = None
    status: str | None = None
    location: str | None = None
    device_type: str | None = None

    model_config = {"from_attributes": True}


class DeviceDetailPublic(BaseModel):
    """Single device for detail page (includes password for admin / authorized user)."""

    device_id: int
    devicename: str | None = None
    status: str | None = None
    password: str | None = None
    location: str | None = None
    device_type: str | None = None

    model_config = {"from_attributes": True}


class DeviceUpdate(BaseModel):
    """Admin partial update (static fields only)."""

    devicename: str | None = Field(default=None, max_length=45)
    password: str | None = Field(default=None, max_length=45)
    status: str | None = Field(default=None, max_length=10)
    location: str | None = Field(default=None, max_length=255)
    device_type: str | None = Field(default=None, max_length=45)
