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
            return v / 1000.0
        return v

    s = str(raw_ts).strip()
    if not s:
        return time.time()

    try:
        n = float(s)
        if n > 1_000_000_000_000:
            return n / 1000.0
        return n
    except ValueError:
        pass

    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00")).timestamp()
    except ValueError:
        return time.time()


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
        # 2) Fallback: giải mã nhị phân theo khung NanoPB template
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
    device_id = parsed.get("device_id") or topic_device_id
    sensor_type = str(parsed.get("sensor_type") or "").strip().lower()

    if not sensor_type:
        has_power = parsed.get("voltage") is not None or parsed.get("current") is not None
        has_temp = parsed.get("temperature") is not None
        has_vib = parsed.get("vibration") is not None or parsed.get("vibration_mms") is not None
        if has_power:
            sensor_type = "power"
        elif has_temp:
            sensor_type = "temperature"
        elif has_vib:
            sensor_type = "vibration"

    ts = _normalize_ts(parsed.get("ts") or parsed.get("timestamp") or parsed.get("time"))

    out: dict[str, Any] = {
        "topic": topic,
        "device_id": str(device_id) if device_id is not None else "",
        "sensor_type": sensor_type,
        "ts": ts,
        "ts_iso": datetime.fromtimestamp(ts, tz=UTC).isoformat(),
        "temperature": parsed.get("temperature"),
        "vibration": parsed.get("vibration", parsed.get("vibration_mms")),
        "voltage": parsed.get("voltage"),
        "current": parsed.get("current"),
        "raw": parsed,
    }
    return out
