"""
WebSocket routes cho dashboard frontend và kết nối thiết bị (ESP32).

Mô tả:
    Quản lý WebSocket cho realtime data streaming và device connectivity. Tất cả routes đều
    sử dụng ``RealtimeHub`` shared để broadcast dữ liệu MQTT đã chuẩn hóa từ payload_decoder
    tới frontend dashboard hoặc device clients.

Prefix thực tế khi chạy API:
    - Base: ``/api/ws`` (router prefix ``/ws`` + mount ``/api`` trong ``main``)
    - Endpoints:
        - ``/api/ws/global`` — broadcast realtime data tới tất cả frontend clients (GlobalDashboard)
        - ``/api/ws/devices/{device_id}`` — broadcast realtime data tới các client theo device-id
        - ``/api/ws/esp32/{device_id}`` — kết nối từ thiết bị ESP32 uplink (bi-directional)

Data flow:
    1. MQTT Subscriber (app.core.mqtt_subscriber) nhận message từ broker Mosquitto.
    2. Payload decode thành dict chuẩn via app.core.payload_decoder.
    3. Handler trong main.py gọi:
       - influx.write_sensor_point() → InfluxDB time-series storage
       - realtime_hub.publish_from_thread() → queue async broadcast
    4. RealtimeHub worker async broadcast tới:
       - Global clients (/ws/global)
       - Device-specific clients (/ws/devices/{device_id})
       - ESP32 device clients (/ws/esp32/{device_id})
"""

import json
import logging
import time

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.core.deps import authenticate_ws_device, authenticate_ws_user
from app.core.ingest import ingest_sensor_payload
from app.core.realtime_hub import RealtimeHub
from app.core.test_payload_codec import decode_coordinates_data_proto

router = APIRouter(prefix="/ws", tags=["websocket"])
logger = logging.getLogger("uvicorn.error")


def _get_realtime_hub(websocket: WebSocket) -> RealtimeHub | None:
    """Lấy shared RealtimeHub instance từ app state."""
    app = websocket.app
    return getattr(app.state, "realtime_hub", None)


@router.websocket("/global")
async def ws_global(websocket: WebSocket) -> None:
    """GlobalDashboard WebSocket: broadcast realtime sensor data tới tất cả connected frontend clients.

    Mô tả:
        Frontend (React Dashboard) mở kết nối WebSocket để nhận real-time telemetry data từ các thiết bị.
        Server broadcast dữ liệu đã decode từ MQTT tới tất cả global clients.
        Client không cần gửi dữ liệu (server chỉ broadcast); kết nối dùng để giữ kênh mở.

    Flow:
        1. Client `await fetch('/api/ws/global')` hoặc dùng library WebSocket client.
        2. Server accept kết nối và thêm vào group `_global_clients` của hub.
        3. MQTT data -> decoder -> hub.publish_from_thread() -> worker broadcast tới global group.
        4. Client nhận frame JSON với sensor data từ các device.
        5. Client disconnect -> server gỡ khỏi group.

    Payload nhận được (ví dụ):
        ```json
        {
            "device_id": "101",
            "sensor_type": "temperature",
            "temperature": 28.5,
            "ts": 1714000000,
            "server_receive_ms": 1714000001234,
            ...
        }
        ```

    Error handling:
        - Nếu RealtimeHub chưa khởi tạo: close code 1011 (server error).
        - Nếu client disconnect: server tự động cleanup.
        - Nếu exception: disconnect + cleanup.
    """
    hub = _get_realtime_hub(websocket)
    if hub is None:
        await websocket.close(code=1011)
        return
    if await authenticate_ws_user(websocket) is None:
        return  # authenticate_ws_user đã close(1008)
    await hub.connect_global(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        await hub.disconnect_global(websocket)
    except Exception:
        await hub.disconnect_global(websocket)


@router.websocket("/devices/{device_id}")
async def ws_device(websocket: WebSocket, device_id: str) -> None:
    """Device-specific WebSocket: broadcast realtime data tới frontend dashboard của một thiết bị.

    Mô tả:
        Frontend (Device Dashboard) mở kết nối để nhận real-time data của một thiết bị cụ thể.
        Server chỉ broadcast data có `device_id` khớp với kết nối tới group này.
        Giống `/ws/global` nhưng scope là per-device thay vì global.

    Flow:
        1. Client `await fetch(f'/api/ws/devices/{device_id}')` để theo dõi một thiết bị cụ thể.
        2. Server accept kết nối và thêm vào group `_device_clients[device_id]` của hub.
        3. MQTT data -> decoder -> nếu `msg["device_id"] == device_id` thì broadcast.
        4. Client nhận frame JSON chỉ chứa data của thiết bị đó.
        5. Client disconnect -> server gỡ khỏi group.

    Khi nào dùng:
        - GlobalDashboard: hiển thị snapshot tất cả device → dùng `/ws/global`.
        - DeviceDashboard (chart, timeline chi tiết): hiển thị 1 device → dùng `/ws/devices/{device_id}`.

    Payload (tương tự `/ws/global` nhưng chỉ có 1 device_id):
        ```json
        {
            "device_id": "101",
            "sensor_type": "vibration",
            "vibration": 0.45,
            "ts": 1714000010,
            ...
        }
        ```

    Error handling:
        - Tương tự `/ws/global`.
    """
    hub = _get_realtime_hub(websocket)
    if hub is None:
        await websocket.close(code=1011)
        return
    if await authenticate_ws_user(websocket) is None:
        return  # authenticate_ws_user đã close(1008)
    await hub.connect_device(websocket, device_id)
    try:
        while True:
            try:
                message = await websocket.receive()
                if message.get("type") == "websocket.disconnect":
                    break

                raw_text = message.get("text")
                raw_bytes = message.get("bytes")
                if raw_text is None and raw_bytes is None:
                    continue

                if raw_bytes is not None:
                    decoded_payload = None
                    try:
                        decoded_payload = decode_coordinates_data_proto(raw_bytes)
                    except Exception:
                        decoded_payload = None
                    if decoded_payload is None:
                        continue

                    decoded_payload["server_receive_ms"] = time.time_ns() // 1_000_000
                    decoded_payload.setdefault("device_id", str(device_id))
                    decoded_payload.setdefault("topic", f"ws/{device_id}")
                    # Pipeline chung: ghi Influx + broadcast (không chỉ broadcast như trước).
                    ingest_sensor_payload(websocket.app, decoded_payload)
                    continue

                if not str(raw_text).strip():
                    continue
                try:
                    payload = json.loads(str(raw_text))
                except json.JSONDecodeError:
                    continue

                payload["server_receive_ms"] = time.time_ns() // 1_000_000
                payload.setdefault("device_id", str(device_id))
                payload.setdefault("topic", f"ws/{device_id}")
                # Pipeline chung: ghi Influx + broadcast.
                ingest_sensor_payload(websocket.app, payload)
            except RuntimeError as exc:
                if "disconnect message" in str(exc):
                    break
                raise
    except WebSocketDisconnect:
        await hub.disconnect_device(websocket, device_id)
    except Exception:
        await hub.disconnect_device(websocket, device_id)


@router.websocket("/esp32/{device_id}")
async def ws_esp32(websocket: WebSocket, device_id: str) -> None:
    """ESP32 Device WebSocket: bi-directional uplink kết nối từ thiết bị IoT.

    Mô tả:
        Thiết bị ESP32 (hoặc các device khác) mở WebSocket đôi chiều để:
        - **Uplink**: gửi sensor data (telemetry) lên server.
        - **Downlink**: nhận command từ server (remote control, config update, ...).
        
        Endpoint này quản lý kết nối device theo device_id và forward data vào pipeline
        xử lý tương tự MQTT (decoder → InfluxDB → RealtimeHub broadcast).

    Flow:
        1. ESP32 firmware `ws_connect(f'ws://server:8000/api/ws/esp32/{device_id}')` với device_id duy nhất.
        2. Server accept kết nối và thêm vào group `_esp32_clients[device_id]` của hub.
        3. Server reply: `{"ok": true, "device_id": "...", "message": "connected"}`.
        4. **Uplink (device → server)**:
           - Device gửi JSON frame: `{"temperature": 28.5, "timestamp_ms": ...}`.
           - Server echo lại `{"ok": true, "received": {...}}` làm ack.
           - Server có thể integrate payload vào InfluxDB/RealtimeHub broadcast (TODO).
        5. **Downlink (server → device)**:
           - Server gọi `hub.send_to_esp32(device_id, {"cmd": "reboot", ...})` từ REST API hoặc khác.
           - Frame gửi tới tất cả ESP32 kết nối với `device_id` này.
        6. Device disconnect → server tự động cleanup.

    Frame types:
        - **Text**: JSON payload device gửi lên.
            ```json
            {
                "device_id": "101",
                "temperature": 28.5,
                "humidity": 65,
                "timestamp_ms": 1714000012345
            }
            ```
        - **Binary**: device firmware gửi binary frame (ví dụ protobuf); server echo bytes count.
        - **Empty string / whitespace**: server phản hồi pong.

    Error handling:
        - Nếu RealtimeHub chưa khởi tạo: close code 1011.
        - Nếu JSON parse fail: echo lại raw string.
        - Nếu disconnect: cleanup và gỡ khỏi group.

    Lưu ý:
        - Hiện tại endpoint chỉ nhận + echo; chưa integrate uplink data vào InfluxDB/DB.
        - Downlink command có thể thêm sau (gọi `hub.send_to_esp32()` từ API route).
        - TODO: xác thực device (API key, JWT token, hoặc device_secret).
    """
    hub = _get_realtime_hub(websocket)
    if hub is None:
        await websocket.close(code=1011)
        return
    if await authenticate_ws_device(websocket, device_id) is None:
        return  # authenticate_ws_device đã close(1008)

    await hub.connect_esp32(websocket, device_id)
    try:
        await websocket.send_json({"ok": True, "device_id": device_id, "message": "connected"})
        while True:
            try:
                message = await websocket.receive()
                if message.get("type") == "websocket.disconnect":
                    break

                raw_text = message.get("text")
                raw_bytes = message.get("bytes")

                if raw_text is None and raw_bytes is None:
                    continue

                # ESP32 keep-alive ping: echo back the exact same frame.
                # Firmware dấu hiệu ping: payload bắt đầu bằng "PING|".
                if raw_text is not None and str(raw_text).startswith("PING|"):
                    await websocket.send_text(str(raw_text))
                    continue
                if raw_bytes is not None and raw_bytes.startswith(b"PING|"):
                    await websocket.send_bytes(raw_bytes)
                    continue

                if raw_bytes is not None:
                    decoded_payload = None
                    try:
                        decoded_payload = decode_coordinates_data_proto(raw_bytes)
                    except Exception:
                        decoded_payload = None

                    if decoded_payload is not None:
                        decoded_payload["server_receive_ms"] = time.time_ns() // 1_000_000
                        decoded_payload.setdefault("device_id", str(device_id))
                        decoded_payload.setdefault("topic", f"ws/{device_id}")
                        # Pipeline chung: ghi Influx + broadcast (/ws/global và /ws/devices/{id}).
                        ingest_sensor_payload(websocket.app, decoded_payload)
                    await websocket.send_json(
                        {
                            "ok": True,
                            "device_id": device_id,
                            "echo_bytes": len(raw_bytes),
                        }
                    )
                    continue

                if not str(raw_text).strip():
                    await websocket.send_json({"ok": True, "type": "pong", "device_id": device_id})
                    continue
                try:
                    payload = json.loads(str(raw_text))
                except json.JSONDecodeError:
                    await websocket.send_json({"ok": True, "device_id": device_id, "echo": str(raw_text)})
                    continue

                payload["server_receive_ms"] = time.time_ns() // 1_000_000
                payload.setdefault("device_id", device_id)
                payload.setdefault("topic", f"ws/{device_id}")
                # Pipeline chung: ghi Influx + broadcast cho dashboards.
                ingest_sensor_payload(websocket.app, payload)

                await websocket.send_json({"ok": True, "device_id": device_id, "received": payload})
            except WebSocketDisconnect:
                break
            except RuntimeError as exc:
                # Starlette raises RuntimeError if receive() is called after disconnect frame.
                if "disconnect message" in str(exc):
                    break
                raise
    finally:
        await hub.disconnect_esp32(websocket, device_id)