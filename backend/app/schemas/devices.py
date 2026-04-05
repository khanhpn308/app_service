from pydantic import BaseModel


class DeviceCreate(BaseModel):
    device_id: int
    devicename: str | None = None
    password: str | None = None
    status: str | None = None
    user_device_asignment_id: int


class DevicePublic(BaseModel):
    device_id: int
    devicename: str | None = None
    status: str | None = None

    model_config = {"from_attributes": True}


class DeviceDetailPublic(BaseModel):
    """Single device for detail page (includes password for admin / authorized user)."""

    device_id: int
    devicename: str | None = None
    status: str | None = None
    password: str | None = None

    model_config = {"from_attributes": True}

