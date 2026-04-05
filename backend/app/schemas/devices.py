from pydantic import AliasChoices, BaseModel, ConfigDict, Field


class DeviceCreate(BaseModel):
    """Chấp nhận `device_type` hoặc `type` / `deviceType` trong JSON (trình duyệt, client cũ hay dùng `type`)."""

    model_config = ConfigDict(populate_by_name=True)

    device_id: int
    devicename: str | None = None
    password: str | None = None
    status: str | None = None
    user_device_asignment_id: int
    location: str | None = Field(
        default=None,
        max_length=255,
        validation_alias=AliasChoices("location", "deviceLocation"),
    )
    device_type: str | None = Field(
        default=None,
        max_length=45,
        validation_alias=AliasChoices("device_type", "type", "deviceType"),
    )


class DevicePublic(BaseModel):
    device_id: int
    devicename: str | None = None
    status: str | None = None
    location: str | None = None
    device_type: str | None = None

    model_config = {"from_attributes": True}


class DeviceAuthorizedUser(BaseModel):
    """User được phân quyền truy cập thiết bị (device_authorization + user)."""

    user_id: int
    username: str
    fullname: str
    expired_at: date | None = None


class DeviceDetailPublic(BaseModel):
    """Chi tiết thiết bị: mật khẩu cho mọi người có quyền; user_device_asignment_id chỉ admin."""

    device_id: int
    devicename: str | None = None
    status: str | None = None
    password: str | None = None
    location: str | None = None
    device_type: str | None = None
    user_device_asignment_id: int | None = None
    authorized_users: list[DeviceAuthorizedUser] = []

    model_config = {"from_attributes": True}


class DeviceUpdate(BaseModel):
    """Admin partial update (static fields only)."""

    model_config = ConfigDict(populate_by_name=True)

    devicename: str | None = Field(default=None, max_length=45)
    password: str | None = Field(default=None, max_length=45)
    status: str | None = Field(default=None, max_length=10)
    user_device_asignment_id: int | None = None
    location: str | None = Field(
        default=None,
        max_length=255,
        validation_alias=AliasChoices("location", "deviceLocation"),
    )
    device_type: str | None = Field(
        default=None,
        max_length=45,
        validation_alias=AliasChoices("device_type", "type", "deviceType"),
    )
