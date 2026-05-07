from __future__ import annotations

import struct
from typing import Any


class TestPayloadDecodeError(ValueError):
    pass


def _read_u8(data: bytes, offset: int) -> tuple[int, int]:
    if offset + 1 > len(data):
        raise TestPayloadDecodeError("truncated payload")
    return data[offset], offset + 1


def _read_bytes(data: bytes, offset: int, size: int) -> tuple[bytes, int]:
    if size < 0 or offset + size > len(data):
        raise TestPayloadDecodeError("truncated payload")
    return data[offset : offset + size], offset + size


def _read_len_ascii(data: bytes, offset: int) -> tuple[str, int, int]:
    length, offset = _read_u8(data, offset)
    raw, offset = _read_bytes(data, offset, length)
    return raw.decode("ascii", errors="replace"), length, offset


def _read_varint(data: bytes, offset: int) -> tuple[int, int]:
    value = 0
    shift = 0
    while offset < len(data):
        b = data[offset]
        offset += 1
        value |= (b & 0x7F) << shift
        if (b & 0x80) == 0:
            return value, offset
        shift += 7
        if shift >= 64:
            raise TestPayloadDecodeError("invalid varint")
    raise TestPayloadDecodeError("truncated payload")


def _skip_protobuf_value(data: bytes, offset: int, wire_type: int) -> int:
    if wire_type == 0:
        _, offset = _read_varint(data, offset)
        return offset
    if wire_type == 1:
        offset += 8
        if offset > len(data):
            raise TestPayloadDecodeError("truncated payload")
        return offset
    if wire_type == 2:
        length, offset = _read_varint(data, offset)
        offset += length
        if offset > len(data):
            raise TestPayloadDecodeError("truncated payload")
        return offset
    if wire_type == 5:
        offset += 4
        if offset > len(data):
            raise TestPayloadDecodeError("truncated payload")
        return offset
    raise TestPayloadDecodeError(f"unsupported wire type: {wire_type}")


def decode_coordinates_data_proto(payload: bytes) -> dict[str, Any]:
    """
    Decode payload for:

    .. code-block:: proto

        syntax = "proto3";

        message coordinates_data {
            uint32 device_id = 1;
            uint32 type = 2;
            float x = 3;
            float y = 4;
            uint64 timestamp_ms = 5;
        }

    Current backend support:
        - type = 1: GPS payload with x/y coordinates.
        - Other types are preserved as parsed fields so new frames can be added later.
    """
    data = bytes(payload or b"")
    offset = 0
    out: dict[str, Any] = {}
    hit_any_known_field = False

    while offset < len(data):
        key, offset = _read_varint(data, offset)
        field_number = key >> 3
        wire_type = key & 0x07

        if field_number == 1 and wire_type == 0:
            device_id, offset = _read_varint(data, offset)
            out["device_id"] = int(device_id)
            hit_any_known_field = True
            continue

        if field_number == 2 and wire_type == 0:
            type_code, offset = _read_varint(data, offset)
            out["type"] = int(type_code)
            hit_any_known_field = True
            continue

        if field_number == 3 and wire_type == 5:
            if offset + 4 > len(data):
                raise TestPayloadDecodeError("truncated payload")
            (x,) = struct.unpack_from("<f", data, offset)
            out["x"] = float(x)
            offset += 4
            hit_any_known_field = True
            continue

        if field_number == 4 and wire_type == 5:
            if offset + 4 > len(data):
                raise TestPayloadDecodeError("truncated payload")
            (y,) = struct.unpack_from("<f", data, offset)
            out["y"] = float(y)
            offset += 4
            hit_any_known_field = True
            continue

        if field_number == 5 and wire_type == 0:
            timestamp_ms, offset = _read_varint(data, offset)
            out["timestamp_ms"] = int(timestamp_ms)
            hit_any_known_field = True
            continue

        offset = _skip_protobuf_value(data, offset, wire_type)

    if not hit_any_known_field:
        raise TestPayloadDecodeError("payload is not coordinates_data protobuf")

    type_code = int(out.get("type") or 0)
    out["sensor_type"] = "gps" if type_code == 1 else f"type_{type_code}" if type_code else "unknown"
    if "timestamp_ms" in out:
        out["ts"] = float(int(out["timestamp_ms"])) / 1000.0
    return out


def decode_test_uplink_binary(payload: bytes) -> dict:
    data = bytes(payload or b"")
    offset = 0

    version, offset = _read_u8(data, offset)
    if version != 0x02:
        raise TestPayloadDecodeError("unsupported version")

    message, message_len, offset = _read_len_ascii(data, offset)
    node_id, node_id_len, offset = _read_len_ascii(data, offset)

    event_ts_raw, offset = _read_bytes(data, offset, 8)
    gateway_ts_raw, offset = _read_bytes(data, offset, 8)
    event_timestamp_ms = int.from_bytes(event_ts_raw, byteorder="little", signed=False)
    gateway_timestamp_ms = int.from_bytes(gateway_ts_raw, byteorder="little", signed=False)

    rssi_u8, offset = _read_u8(data, offset)
    rssi = rssi_u8 - 256 if rssi_u8 > 127 else rssi_u8

    src_mac_raw, offset = _read_bytes(data, offset, 6)
    src_mac = ":".join(f"{b:02X}" for b in src_mac_raw)

    gateway_id, gateway_id_len, offset = _read_len_ascii(data, offset)

    if offset != len(data):
        # Keep strict parsing so malformed packets are obvious during tests.
        raise TestPayloadDecodeError("unexpected trailing bytes")

    return {
        "version": version,
        "message_len": message_len,
        "message": message,
        "node_id_len": node_id_len,
        "node_id": node_id,
        "event_timestamp_ms": event_timestamp_ms,
        "gateway_timestamp_ms": gateway_timestamp_ms,
        "rssi": rssi,
        "src_mac": src_mac,
        "gateway_id_len": gateway_id_len,
        "gateway_id": gateway_id,
    }


def _encode_varint(value: int) -> bytes:
    if value < 0:
        raise ValueError("varint must be non-negative")
    out = bytearray()
    v = int(value)
    while v >= 0x80:
        out.append((v & 0x7F) | 0x80)
        v >>= 7
    out.append(v)
    return bytes(out)


def _encode_key(field_number: int, wire_type: int) -> bytes:
    return _encode_varint((field_number << 3) | wire_type)


def _encode_len_field(field_number: int, value: str) -> bytes:
    raw = value.encode("utf-8")
    return _encode_key(field_number, 2) + _encode_varint(len(raw)) + raw


def _encode_u64_field(field_number: int, value: int) -> bytes:
    return _encode_key(field_number, 0) + _encode_varint(int(value))


def encode_test_downlink_proto(
    *,
    gateway_id: str,
    node_id: str,
    message: str,
    server_mark_time_ms: int | None = None,
    mark_time_ms: int | None = None,
    protocol: str,
) -> bytes:
    """
    Encode command payload as protobuf binary compatible with nanopb.

    Schema (proto3):
      message TestCommand {
        string gateway_id = 1;
        string node_id = 2;
        string message = 3;
        uint64 mark_time_ms = 4;  # server_mark_time_ms semantic
        string protocol = 5;
      }
    """
    # Backward compatible with existing call-sites using `mark_time_ms`.
    if server_mark_time_ms is None:
        if mark_time_ms is None:
            raise ValueError("server_mark_time_ms (or mark_time_ms) is required")
        server_mark_time_ms = int(mark_time_ms)

    return b"".join(
        [
            _encode_len_field(1, gateway_id),
            _encode_len_field(2, node_id),
            _encode_len_field(3, message),
            _encode_u64_field(4, int(server_mark_time_ms)),
            _encode_len_field(5, protocol),
        ]
    )
