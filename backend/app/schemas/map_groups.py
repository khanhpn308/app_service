"""API contracts for map groups and invitation membership."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator


def _trim_required(value: str) -> str:
    trimmed = value.strip()
    if not trimmed:
        raise ValueError("Giá trị không được để trống")
    return trimmed


class GroupCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    owner_username: str | None = Field(default=None, max_length=45)

    _normalize_name = field_validator("name")(_trim_required)
    _normalize_owner = field_validator("owner_username")(
        lambda value: _trim_required(value) if value is not None else None
    )


class GroupPatch(BaseModel):
    name: str = Field(min_length=1, max_length=100)

    _normalize_name = field_validator("name")(_trim_required)


class GroupPublic(BaseModel):
    group_id: int
    name: str
    owner_user_id: int
    owner_username: str
    created_by_user_id: int | None
    created_at: datetime
    updated_at: datetime
    access_role: Literal["admin", "owner", "member"]
    can_manage: bool


class InvitationCreate(BaseModel):
    username: str = Field(min_length=1, max_length=45)

    _normalize_username = field_validator("username")(_trim_required)


class InvitationPatch(BaseModel):
    status: Literal["accepted", "rejected"]


class MembershipPublic(BaseModel):
    group_id: int
    user_id: int
    username: str
    fullname: str
    status: Literal["pending", "accepted", "rejected"]
    invited_by_user_id: int | None
    invited_at: datetime
    responded_at: datetime | None


class InvitationPublic(BaseModel):
    group_id: int
    group_name: str
    owner_username: str
    status: Literal["pending", "accepted", "rejected"]
    invited_at: datetime
    responded_at: datetime | None
