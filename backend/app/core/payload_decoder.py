"""
Bộ giải mã payload MQTT (khung mẫu) cho dữ liệu cảm biến IoT.

Mục tiêu:
    - Nhận payload bytes (có thể là NanoPB nhị phân) và chuyển thành dict thống nhất.
    - Trích xuất các trường chuẩn cho hệ thống: ``device_id``, ``sensor_type``,
      ``temperature``/``vibration``/``voltage``/``current`` và ``ts``.

Lưu ý:
    - Phần giải mã NanoPB bên dưới là **khung mẫu** để thay thế theo schema .proto thực tế.
    - Nếu payload không khớp định dạng mẫu, hàm sẽ trả ``raw_hex`` để debug.
"""

from __future__ import annotations

import json
import re
import struct
import time
from datetime import UTC, datetime
from typing import Any


MIN_REASONABLE_EPOCH_S = 946684800  # 2000-01-01T00:00:00Z


def _is_reasonable_epoch_seconds(v: float) -> bool:
    """Kiểm tra ts có hợp lý để coi là Unix epoch seconds hay không."""
    now = time.time()
    # Chấp nhận dữ liệu lệch tương lai tối đa 30 ngày.
    return MIN_REASONABLE_EPOCH_S <= v <= now + (30 * 24 * 3600)


def _parse_iso_ts_to_epoch_utc(raw_iso: str) -> float:
    """
    PIU = Parse ISO timestamp as UTC.

    Công dụng:
        - Parse chuỗi ISO thời gian sang epoch seconds.
        - Nếu chuỗi không có timezone (naive datetime), ép về UTC để tránh lệch múi giờ
          theo timezone của máy chủ (ví dụ GMT+7).
    """
    dt = datetime.fromisoformat(raw_iso.replace("Z", "+00:00"))
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt.timestamp()


def _extract_device_id_from_topic(topic: str) -> str | None:
    """
    DID = Device ID extractor.

    Công dụng:
        - Tìm ``device_id`` từ topic theo các pattern phổ biến như:
          ``devices/101/telemetry``, ``iot/device-101/data``, ...
    """
    match = re.search(r"(?:devices?/)?(\d{1,12})(?:\D|$)", topic or "")
    if not match:
        return None
    return match.group(1)


def _normalize_ts(raw_ts: Any) -> float:
    """
    TSN = TimeStamp normalizer.

    Công dụng:
        - Chuẩn hóa thời gian về Unix seconds (float).
        - Hỗ trợ input kiểu giây, mili-giây hoặc chuỗi ISO datetime.
    """
    if raw_ts is None:
        return time.time()

    if isinstance(raw_ts, (int, float)):
        v = float(raw_ts)
        # Nếu lớn hơn 1e12 thì nhiều khả năng là milliseconds.
        if v > 1_000_000_000_000:
            v = v / 1000.0
        # ESP32 thường gửi timestamp uptime (giây từ lúc boot), không phải epoch.
        # Trường hợp đó sẽ có giá trị nhỏ và phải thay bằng thời điểm hiện tại.
        return v if _is_reasonable_epoch_seconds(v) else time.time()

    s = str(raw_ts).strip()
    if not s:
        return time.time()

    try:
        n = float(s)
        if n > 1_000_000_000_000:
            n = n / 1000.0
        return n if _is_reasonable_epoch_seconds(n) else time.time()
    except ValueError:
        pass

    try:
        ts = _parse_iso_ts_to_epoch_utc(s)
        return ts if _is_reasonable_epoch_seconds(ts) else time.time()
    except ValueError:
        return time.time()


def _first_non_none(*values: Any) -> Any:
    """Trả về giá trị đầu tiên khác ``None`` và khác chuỗi rỗng."""
    for v in values:
        if v is None:
            continue
        if isinstance(v, str) and not v.strip():
            continue
        return v
    return None


def _normalize_sensor_type(raw_sensor_type: Any) -> str:
    """Chuẩn hóa tên loại cảm biến về bộ chuẩn: temperature, vibration, power."""
    if raw_sensor_type is None:
        return ""
    s = str(raw_sensor_type).strip().lower()
    if not s:
        return ""

    aliases = {
        "temperature": "temperature",
        "temp": "temperature",
        "temp_c": "temperature",
        "nhietdo": "temperature",
        "nhiet_do": "temperature",
        "vibration": "vibration",
        "vibration_mms": "vibration",
        "vib": "vibration",
        "rung": "vibration",
        "power": "power",
        "electric": "power",
        "dien": "power",
    }
    return aliases.get(s, s)


def _sensor_name_from_code(sensor_code: int) -> str:
    """
    STC = SensorType code mapper.

    Công dụng:
        - Đổi mã số loại cảm biến trong payload nhị phân mẫu thành tên chuẩn.
    """
    if sensor_code == 1:
        return "temperature"
    if sensor_code == 2:
        return "vibration"
    if sensor_code == 3:
        return "power"
    return "unknown"


def _read_varint(data: bytes, pos: int) -> tuple[int, int]:
    """
    Đọc protobuf varint từ vị trí ``pos``.
    """
    value = 0
    shift = 0
    while pos < len(data):
        b = data[pos]
        pos += 1
        value |= (b & 0x7F) << shift
        if (b & 0x80) == 0:
            return value, pos
        shift += 7
        if shift >= 64:
            raise ValueError("invalid varint (too many bytes)")
    raise ValueError("truncated varint")


def _skip_protobuf_value(data: bytes, pos: int, wire_type: int) -> int:
    """
    Bỏ qua một field protobuf không dùng tới để parser vẫn tiếp tục.
    """
    if wire_type == 0:  # varint
        _, pos = _read_varint(data, pos)
        return pos
    if wire_type == 1:  # 64-bit
        pos += 8
        if pos > len(data):
            raise ValueError("truncated 64-bit field")
        return pos
    if wire_type == 2:  # length-delimited
        length, pos = _read_varint(data, pos)
        pos += length
        if pos > len(data):
            raise ValueError("truncated length-delimited field")
        return pos
    if wire_type == 5:  # 32-bit
        pos += 4
        if pos > len(data):
            raise ValueError("truncated 32-bit field")
        return pos
    raise ValueError(f"unsupported wire type: {wire_type}")


def _decode_simple_sensor_proto(payload: bytes) -> dict[str, Any]:
    """
    Giải mã protobuf cho schema test:

    .. code-block:: proto

        syntax = "proto3";
        message SimpleSensor {
            string device_id = 1;
            float temperature = 2;
            bool is_active = 3;
            uint32 sequence = 4;
            uint64 timestamp_ms = 5;
        }
    """
    pos = 0
    out: dict[str, Any] = {"sensor_type": "temperature"}
    hit_any_known_field = False

    while pos < len(payload):
        key, pos = _read_varint(payload, pos)
        field_number = key >> 3
        wire_type = key & 0x07

        if field_number == 1 and wire_type == 2:
            length, pos = _read_varint(payload, pos)
            end = pos + length
            if end > len(payload):
                raise ValueError("truncated device_id string")
            out["device_id"] = payload[pos:end].decode("utf-8", errors="ignore")
            pos = end
            hit_any_known_field = True
            continue

        if field_number == 2 and wire_type == 5:
            if pos + 4 > len(payload):
                raise ValueError("truncated temperature float32")
            (temperature,) = struct.unpack_from("<f", payload, pos)
            out["temperature"] = float(temperature)
            pos += 4
            hit_any_known_field = True
            continue

        if field_number == 3 and wire_type == 0:
            active, pos = _read_varint(payload, pos)
            out["is_active"] = bool(active)
            hit_any_known_field = True
            continue

        if field_number == 4 and wire_type == 0:
            sequence, pos = _read_varint(payload, pos)
            out["sequence"] = int(sequence)
            hit_any_known_field = True
            continue

        if field_number == 5 and wire_type == 0:
            timestamp_ms, pos = _read_varint(payload, pos)
            out["timestamp_ms"] = int(timestamp_ms)
            hit_any_known_field = True
            continue

        pos = _skip_protobuf_value(payload, pos, wire_type)

    if not hit_any_known_field:
        raise ValueError("payload is not SimpleSensor protobuf")

    return out


def _decode_nanopb_template(payload: bytes) -> dict[str, Any]:
    """
    NPB = NanoPB template decoder.

    Công dụng:
        - Khung mẫu giải mã payload nhị phân theo layout giả định để bạn chỉnh lại nhanh.

    Layout mẫu (little-endian):
        - Byte 0: ``sensor_type_code`` (1=temp, 2=vibration, 3=power)
        - Byte 1..4: ``timestamp_s`` (uint32, epoch giây)
        - Byte 5..8: ``device_id`` (uint32)
        - Byte 9..n: dữ liệu float32 theo loại cảm biến
            - Temperature: ``temperature``
            - Vibration: ``vibration``
            - Power: ``voltage``, ``current``
    """
    if len(payload) < 9:
        raise ValueError("payload too short for template binary layout")

    sensor_code = payload[0]
    ts_s = int.from_bytes(payload[1:5], byteorder="little", signed=False)
    device_id = int.from_bytes(payload[5:9], byteorder="little", signed=False)
    sensor_type = _sensor_name_from_code(sensor_code)

    pos = 9
    out: dict[str, Any] = {
        "sensor_type": sensor_type,
        "device_id": str(device_id),
        "ts": float(ts_s),
    }

    if sensor_type == "temperature":
        if len(payload) < pos + 4:
            raise ValueError("temperature payload missing float32 value")
        (temperature,) = struct.unpack_from("<f", payload, pos)
        out["temperature"] = float(temperature)
    elif sensor_type == "vibration":
        if len(payload) < pos + 4:
            raise ValueError("vibration payload missing float32 value")
        (vibration,) = struct.unpack_from("<f", payload, pos)
        out["vibration"] = float(vibration)
    elif sensor_type == "power":
        if len(payload) < pos + 8:
            raise ValueError("power payload missing voltage/current float32 values")
        voltage, current = struct.unpack_from("<ff", payload, pos)
        out["voltage"] = float(voltage)
        out["current"] = float(current)

    return out


def decode_sensor_payload(topic: str, payload: bytes) -> dict[str, Any]:
    """
    DSP = Decode Sensor Payload.

    Công dụng:
        - Chuẩn hóa payload MQTT về schema thống nhất để ghi InfluxDB + phát WebSocket.
        - Ưu tiên parse JSON UTF-8; fallback về khung nhị phân NanoPB mẫu.
    """
    topic = str(topic or "")
    payload_bytes = bytes(payload or b"")

    parsed: dict[str, Any]

    # 1) Thử decode JSON text trước (hỗ trợ thiết bị gửi JSON thô)
    try:
        text = payload_bytes.decode("utf-8")
        raw = json.loads(text)
        parsed = raw if isinstance(raw, dict) else {"value": raw}
    except Exception:  # noqa: BLE001
        # 2) Fallback: thử protobuf test schema (SimpleSensor)
        try:
            parsed = _decode_simple_sensor_proto(payload_bytes)
            parsed["decode_format"] = "protobuf-simple-sensor"
        except Exception:
            # 3) Fallback tiếp: giải mã nhị phân theo khung NanoPB template
            try:
                parsed = _decode_nanopb_template(payload_bytes)
                parsed["decode_format"] = "nanopb-template"
            except Exception as exc:  # noqa: BLE001
                parsed = {
                    "decode_format": "raw-bytes",
                    "decode_error": str(exc),
                    "raw_hex": payload_bytes.hex(),
                }

    # Chuẩn hóa các trường lõi
    topic_device_id = _extract_device_id_from_topic(topic)
    device_id = _first_non_none(
        parsed.get("device_id"),
        parsed.get("deviceId"),
        parsed.get("id"),
        parsed.get("node_id"),
        parsed.get("nodeId"),
        topic_device_id,
    )
    sensor_type = _normalize_sensor_type(
        _first_non_none(
            parsed.get("sensor_type"),
            parsed.get("sensorType"),
            parsed.get("type"),
        )
    )

    temperature = _first_non_none(
        parsed.get("temperature"),
        parsed.get("temp"),
        parsed.get("temp_c"),
        parsed.get("temperature_c"),
    )
    vibration = _first_non_none(
        parsed.get("vibration"),
        parsed.get("vibration_mms"),
        parsed.get("vibrationMmS"),
        parsed.get("vib"),
    )
    voltage = _first_non_none(
        parsed.get("voltage"),
        parsed.get("volt"),
        parsed.get("v"),
    )
    current = _first_non_none(
        parsed.get("current"),
        parsed.get("ampere"),
        parsed.get("amps"),
        parsed.get("a"),
    )

    if not sensor_type:
        has_power = voltage is not None or current is not None
        has_temp = temperature is not None
        has_vib = vibration is not None
        if has_power:
            sensor_type = "power"
        elif has_temp:
            sensor_type = "temperature"
        elif has_vib:
            sensor_type = "vibration"

    # Nhiều template mới gửi payload chung dạng {sensor_type, value}.
    value = _first_non_none(parsed.get("value"), parsed.get("reading"), parsed.get("measurement"))
    if value is not None:
        if sensor_type == "temperature" and temperature is None:
            temperature = value
        elif sensor_type == "vibration" and vibration is None:
            vibration = value
        elif sensor_type == "power" and voltage is None and current is None:
            voltage = value

    ts = _normalize_ts(
        parsed.get("ts")
        or parsed.get("timestamp_ms")
        or parsed.get("timestamp")
        or parsed.get("time")
    )

    out: dict[str, Any] = {
        "topic": topic,
        "device_id": str(device_id) if device_id is not None else "",
        "sensor_type": sensor_type,
        "ts": ts,
        "ts_iso": datetime.fromtimestamp(ts, tz=UTC).isoformat(),
        "temperature": temperature,
        "is_active": parsed.get("is_active"),
        "sequence": parsed.get("sequence"),
        "timestamp_ms": parsed.get("timestamp_ms"),
        "vibration": vibration,
        "voltage": voltage,
        "current": current,
        "raw": parsed,
    }
    return out
