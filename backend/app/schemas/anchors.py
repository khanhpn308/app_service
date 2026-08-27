"""Typed REST contracts for Anchor CRUD and management search."""

import math
import re
from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

LEGACY_HARDWARE_ID_PATTERN = re.compile(r"^[A-Z0-9:_-]{1,64}$")
MAC_ADDRESS_PATTERN = re.compile(r"^(?:[0-9A-F]{2}:){5}[0-9A-F]{2}$")
COORDINATE_QUANTUM = Decimal("0.01")


def _clean_name(value: str) -> str:
    cleaned = value.strip()
    if not cleaned:
        raise ValueError("Anchor name must not be blank")
    return cleaned


def _finite_coordinate(value: float) -> float:
    number = float(value)
    if not math.isfinite(number):
        raise ValueError("Coordinate must be finite")
    return float(
        Decimal(str(number)).quantize(COORDINATE_QUANTUM, rounding=ROUND_HALF_UP)
    )


class AnchorCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    mac_address: str | None = Field(default=None, min_length=17, max_length=17)
    hardware_id: str | None = Field(default=None, min_length=1, max_length=64)
    name: str = Field(min_length=1, max_length=100)
    x: float = Field(default=50.0, ge=0, le=100)
    y: float = Field(default=50.0, ge=0, le=100)
    z: float = 0.0

    @field_validator("mac_address")
    @classmethod
    def normalize_mac_address(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip().upper()
        if not MAC_ADDRESS_PATTERN.fullmatch(normalized):
            raise ValueError("Invalid Anchor MAC Address")
        return normalized

    @field_validator("hardware_id")
    @classmethod
    def normalize_legacy_hardware_id(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip().upper()
        if not LEGACY_HARDWARE_ID_PATTERN.fullmatch(normalized):
            raise ValueError("Invalid Anchor hardware ID")
        return normalized

    @model_validator(mode="after")
    def require_identity(self) -> "AnchorCreate":
        if self.mac_address is None and self.hardware_id is None:
            raise ValueError("MAC Address is required")
        if (
            self.mac_address is not None
            and self.hardware_id is not None
            and self.mac_address != self.hardware_id
        ):
            raise ValueError("MAC Address and legacy hardware ID must match")
        return self

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        return _clean_name(value)

    @field_validator("x", "y", "z")
    @classmethod
    def finite_coordinates(cls, value: float) -> float:
        return _finite_coordinate(value)


class AnchorPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    mac_address: str | None = Field(default=None, min_length=17, max_length=17)
    name: str | None = Field(default=None, min_length=1, max_length=100)
    x: float | None = Field(default=None, ge=0, le=100)
    y: float | None = Field(default=None, ge=0, le=100)
    z: float | None = None

    @field_validator("mac_address")
    @classmethod
    def normalize_mac_address(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip().upper()
        if not MAC_ADDRESS_PATTERN.fullmatch(normalized):
            raise ValueError("Invalid Anchor MAC Address")
        return normalized

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str | None) -> str | None:
        return None if value is None else _clean_name(value)

    @field_validator("x", "y", "z")
    @classmethod
    def finite_coordinates(cls, value: float | None) -> float | None:
        return None if value is None else _finite_coordinate(value)

    @model_validator(mode="after")
    def require_change(self) -> "AnchorPatch":
        if not self.model_fields_set:
            raise ValueError("At least one field is required")
        if any(getattr(self, field) is None for field in self.model_fields_set):
            raise ValueError("Anchor patch fields must not be null")
        return self


class AnchorPublic(BaseModel):
    anchor_id: int
    mac_address: str | None
    hardware_id: str
    name: str
    x: float
    y: float
    z: float
    location_id: int
    location: str
    group_id: int
    status: Literal["active", "inactive"]
    created_by_user_id: int | None
    created_at: datetime
    updated_at: datetime


class AnchorMutationResponse(BaseModel):
    data: AnchorPublic
    config_revision: int | None
    sync_status: Literal["pending", "unchanged"] = "pending"


class AnchorDeleteResponse(BaseModel):
    deleted_anchor_id: int
    config_revision: int
    sync_status: Literal["pending"] = "pending"


class AnchorManageResponse(BaseModel):
    data: list[AnchorPublic]
    total: int
    limit: int
    offset: int


class AnchorConfigResyncResponse(BaseModel):
    gateway_id: int
    config_revision: int
    sync_status: Literal["pending"] = "pending"


class GatewaySyncPublic(BaseModel):
    gateway_id: int
    devicename: str | None
    online: bool
    last_seen_at: datetime | None
    target_revision: int | None
    applied_revision: int | None
    delivery_status: Literal[
        "pending", "published", "applied", "rejected", "misconfigured", "superseded"
    ]
    error: str | None


class AnchorConfigStatusResponse(BaseModel):
    location_id: int
    location: str
    revision: int | None
    aggregate: Literal["synced", "partial", "pending", "error", "no_gateway"]
    anchor_count: int
    gateways: list[GatewaySyncPublic]
