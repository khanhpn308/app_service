"""Strict boundary validation for application-level ESP32 ping messages."""

import re
from typing import Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    ValidationError,
    ValidationInfo,
    field_validator,
)

DEVICE_ID_PATTERN = re.compile(r"^[0-9]+$")


class PingMessage(BaseModel):
    """Validated JSON ping while preserving every original field value."""

    model_config = ConfigDict(extra="forbid", strict=True)

    device_id: str
    sensor_type: Literal["ping"]
    order: int = Field(ge=1, le=4294967295)
    payload: str
    size: int = Field(ge=1, le=16384)
    location: str
    timestamp: int = Field(ge=0, le=9223372036854775807)

    @field_validator("device_id")
    @classmethod
    def validate_device_id(cls, value: str) -> str:
        if not DEVICE_ID_PATTERN.fullmatch(value) or int(value) <= 0:
            raise ValueError("device ID must be a positive decimal string")
        return value

    @field_validator("size")
    @classmethod
    def validate_payload_size(cls, value: int, info: ValidationInfo) -> int:
        payload = info.data.get("payload")
        if isinstance(payload, str) and len(payload.encode("utf-8")) != value:
            raise ValueError("payload UTF-8 byte length does not match size")
        return value

    @property
    def canonical_device_id(self) -> int:
        """Catalog ID used for database lookup; leading zeroes remain in raw data."""

        return int(self.device_id)


class PingCurrentPayload(BaseModel):
    """Latest committed ping row for one device, selected by record ID."""

    id: int
    order: int
    timestamp: int


class PingSummaryResponse(BaseModel):
    """Admin summary counters for one catalog device."""

    device_id: str
    total_payload: int
    current_payload: PingCurrentPayload | None
    total_missing_payload: int


class PingDeleteResponse(BaseModel):
    """Result of atomically clearing ping sequence history for one device."""

    ok: Literal[True] = True
    device_id: str
    deleted_payloads: int
    deleted_missing_payloads: int
    predicted_order: Literal[1] = 1


def format_ping_validation_error(error: ValidationError) -> str:
    """Return one stable field/reason without echoing untrusted input values."""

    item = error.errors(include_url=False, include_context=False, include_input=False)[0]
    location = ".".join(str(part) for part in item["loc"]) or "ping"
    message = str(item["msg"])
    if message.startswith("Value error, "):
        message = message.removeprefix("Value error, ")
    return f"{location}: {message}"
