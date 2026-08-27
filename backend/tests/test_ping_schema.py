import pytest
from pydantic import ValidationError


def _schema_api():
    try:
        from app.schemas.pings import PingMessage, format_ping_validation_error
    except ImportError:
        pytest.fail("PING-03 strict ping schema is not implemented")
    return PingMessage, format_ping_validation_error


def _valid_ping(**overrides):
    data = {
        "device_id": "101",
        "sensor_type": "ping",
        "order": 1,
        "size": 8,
        "payload": "BCDEFGHI",
        "location": "",
        "timestamp": 12345,
    }
    data.update(overrides)
    return data


def test_valid_ping_preserves_fields_and_exposes_canonical_device_id() -> None:
    PingMessage, _ = _schema_api()

    ping = PingMessage.model_validate(_valid_ping(device_id="00101"))

    assert ping.device_id == "00101"
    assert ping.canonical_device_id == 101
    assert ping.model_dump() == _valid_ping(device_id="00101")


def test_payload_size_uses_utf8_bytes_not_character_count() -> None:
    PingMessage, _ = _schema_api()
    payload = "A🙂"

    ping = PingMessage.model_validate(
        _valid_ping(payload=payload, size=len(payload.encode("utf-8")))
    )

    assert ping.payload == payload


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("order", "1"),
        ("order", True),
        ("size", "8"),
        ("size", False),
        ("timestamp", "12345"),
        ("timestamp", True),
        ("device_id", 101),
        ("payload", 123),
        ("location", None),
    ],
)
def test_ping_fields_use_strict_types(field: str, value: object) -> None:
    PingMessage, _ = _schema_api()

    with pytest.raises(ValidationError):
        PingMessage.model_validate(_valid_ping(**{field: value}))


@pytest.mark.parametrize(
    ("overrides", "expected_field"),
    [
        ({"device_id": ""}, "device_id"),
        ({"device_id": "abc"}, "device_id"),
        ({"device_id": "0"}, "device_id"),
        ({"sensor_type": "PING"}, "sensor_type"),
        ({"order": 0}, "order"),
        ({"order": 4294967296}, "order"),
        ({"size": 0}, "size"),
        ({"size": 16385}, "size"),
        ({"timestamp": -1}, "timestamp"),
        ({"timestamp": 9223372036854775808}, "timestamp"),
        ({"payload": "short"}, "size"),
    ],
)
def test_ping_rejects_invalid_contract_ranges(
    overrides: dict, expected_field: str
) -> None:
    PingMessage, _ = _schema_api()

    with pytest.raises(ValidationError) as error:
        PingMessage.model_validate(_valid_ping(**overrides))

    assert expected_field in {
        str(item["loc"][0]) for item in error.value.errors(include_input=False)
    }


def test_all_fields_are_required_and_extra_fields_are_forbidden() -> None:
    PingMessage, _ = _schema_api()
    missing_location = _valid_ping()
    missing_location.pop("location")

    with pytest.raises(ValidationError):
        PingMessage.model_validate(missing_location)
    with pytest.raises(ValidationError):
        PingMessage.model_validate(_valid_ping(unexpected="value"))


def test_validation_error_message_is_stable_and_never_contains_payload() -> None:
    PingMessage, format_ping_validation_error = _schema_api()
    secret_payload = "DO-NOT-LOG-THIS-PAYLOAD"

    with pytest.raises(ValidationError) as error:
        PingMessage.model_validate(
            _valid_ping(payload=secret_payload, size=1)
        )

    message = format_ping_validation_error(error.value)
    assert message == "size: payload UTF-8 byte length does not match size"
    assert secret_payload not in message
