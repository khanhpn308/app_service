from __future__ import annotations


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
    mark_time_ms: int,
    protocol: str,
) -> bytes:
    """
    Encode command payload as protobuf binary compatible with nanopb.

    Schema (proto3):
      message TestCommand {
        string gateway_id = 1;
        string node_id = 2;
        string message = 3;
        uint64 mark_time_ms = 4;
        string protocol = 5;
      }
    """
    return b"".join(
        [
            _encode_len_field(1, gateway_id),
            _encode_len_field(2, node_id),
            _encode_len_field(3, message),
            _encode_u64_field(4, mark_time_ms),
            _encode_len_field(5, protocol),
        ]
    )
