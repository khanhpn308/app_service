from datetime import date
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field, computed_field, field_validator, model_validator


class LoginRequest(BaseModel):
    username: str = Field(..., min_length=1, max_length=45)
    password: str = Field(..., min_length=1, max_length=128)


class RegisterRequest(BaseModel):
    username: str = Field(..., min_length=1, max_length=45)
    password: str = Field(..., min_length=6, max_length=45)
    fullname: str = Field(..., min_length=1, max_length=45)
    cccd: Decimal = Field(..., description="12-digit citizen ID")
    email: str | None = Field(default=None, max_length=45)
    phone: int | None = None
    expired_at: date = Field(..., description="Last valid day (inclusive); 0 remaining days => deactive")
    role: Literal["admin", "user"]

    @field_validator("cccd")
    @classmethod
    def cccd_digits(cls, v: Decimal) -> Decimal:
        s = str(int(v)) if v == int(v) else format(v, "f").rstrip("0").rstrip(".")
        if len(s) != 12 or not s.isdigit():
            raise ValueError("CCCD must be exactly 12 digits")
        return v

    @model_validator(mode="after")
    def expired_not_in_past(self) -> "RegisterRequest":
        if self.expired_at < date.today():
            raise ValueError("Ngày hết hạn không được trước hôm nay")
        return self


class UserPublic(BaseModel):
    user_id: int
    username: str
    fullname: str
    cccd: Decimal
    email: str | None
    phone: int | None
    creat_at: date
    expired_at: date | None
    status: str
    role: str

    model_config = {"from_attributes": True}

    @computed_field
    @property
    def validity_days(self) -> int:
        """expired_at - creat_at (days)."""
        if self.expired_at is None:
            return 0
        return (self.expired_at - self.creat_at).days

    @computed_field
    @property
    def remaining_days(self) -> int:
        """Days until expired_at (0 when expired or past)."""
        if self.expired_at is None:
            return 0
        return max(0, (self.expired_at - date.today()).days)


class UserStatusPatch(BaseModel):
    status: Literal["active", "deactive"]


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserPublic


class RecoverPasswordRequest(BaseModel):
    username: str = Field(..., min_length=1, max_length=45)
    cccd: Decimal

    @field_validator("cccd")
    @classmethod
    def cccd_digits(cls, v: Decimal) -> Decimal:
        s = str(int(v)) if v == int(v) else format(v, "f").rstrip("0").rstrip(".")
        if len(s) != 12 or not s.isdigit():
            raise ValueError("CCCD must be exactly 12 digits")
        return v


class RecoverPasswordResponse(BaseModel):
    """Plain passwords are not stored; a new temporary password is issued after verification."""

    message: str
    temporary_password: str


class ChangePasswordRequest(BaseModel):
    current_password: str = Field(..., min_length=1, max_length=128)
    new_password: str = Field(..., min_length=6, max_length=45)
    confirm_password: str = Field(..., min_length=6, max_length=45)


class BootstrapRequest(BaseModel):
    """Only works when the database has zero users."""

    username: str = Field(..., min_length=1, max_length=45)
    password: str = Field(..., min_length=6, max_length=45)
    fullname: str = Field(..., min_length=1, max_length=45)
    cccd: Decimal
    email: str | None = Field(default=None, max_length=45)
    phone: int | None = None
    expired_at: date | None = Field(default=None, description="Defaults to 2099-12-31 if omitted")

    @field_validator("cccd")
    @classmethod
    def cccd_digits(cls, v: Decimal) -> Decimal:
        s = str(int(v)) if v == int(v) else format(v, "f").rstrip("0").rstrip(".")
        if len(s) != 12 or not s.isdigit():
            raise ValueError("CCCD must be exactly 12 digits")
        return v
