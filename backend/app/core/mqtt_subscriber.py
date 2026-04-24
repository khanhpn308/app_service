"""
MQTT subscriber nền (thư viện **paho-mqtt**): kết nối broker, subscribe topic, buffer tin trong RAM.

Mục đích:
    - Nhận message telemetry / sự kiện từ thiết bị qua broker (ví dụ Mosquitto).
    - Lưu vòng tròn (deque) để API ``/api/mqtt/messages`` xem lại gần đây — **không** thay cho DB lịch sử dài hạn.

Viết tắt:
    - **QoS**: Quality of Service (0, 1, 2) — mức đảm bảo giao tin MQTT.
    - **topics_csv**: danh sách topic phân tách dấu phẩy trong cấu hình.

Luồng: ``loop_start()`` chạy thread nền; callback ``on_message`` chuẩn hóa JSON nếu được.
"""

from __future__ import annotations

import json
import threading
import time
from collections import deque
from dataclasses import dataclass
from typing import Any, Callable

from app.core.payload_decoder import decode_sensor_payload

import paho.mqtt.client as mqtt


@dataclass(frozen=True)
class MqttMessage:
    """Một tin đã nhận (bất biến) — lưu trong buffer vòng tròn."""

    topic: str
    payload: str
    qos: int
    retain: bool
    received_at: float


def _parse_topics(topics_csv: str) -> list[str]:
    """Tách chuỗi cấu hình thành danh sách topic không rỗng."""
    return [t.strip() for t in (topics_csv or "").split(",") if t.strip()]


class MqttSubscriber:
    """
    Client subscribe đơn giản: bật/tắt bằng ``enabled``, buffer ``max_messages`` tin mới nhất.

    Gắn vào ``app.state.mqtt`` để route HTTP đọc ``status()`` / ``latest_messages()``.
    """

    def __init__(
        self,
        *,
        enabled: bool,
        host: str,
        port: int,
        username: str | None,
        password: str | None,
        client_id: str,
        keepalive: int,
        topics_csv: str,
        qos: int,
        max_messages: int,
        on_sensor_payload: Callable[[dict[str, Any]], None] | None = None,
    ) -> None:
        self._enabled = enabled
        self._host = host
        self._port = port
        self._username = username
        self._password = password
        self._client_id = client_id
        self._keepalive = keepalive
        self._topics = _parse_topics(topics_csv)
        self._qos = int(qos)
        self._on_sensor_payload = on_sensor_payload

        self._messages: deque[MqttMessage] = deque(maxlen=max(1, int(max_messages)))
        self._lock = threading.Lock()

        self._connected = False
        self._last_connect_error: str | None = None
        self._started_at: float | None = None

        self._client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=self._client_id)
        if self._username:
            self._client.username_pw_set(self._username, self._password)

        self._client.on_connect = self._on_connect
        self._client.on_disconnect = self._on_disconnect
        self._client.on_message = self._on_message

    def start(self) -> None:
        """Kết nối broker và ``loop_start()``; nếu ``enabled`` false hoặc đã start thì không làm gì."""
        if not self._enabled:
            return
        if self._started_at is not None:
            return
        self._started_at = time.time()

        try:
            self._client.connect(self._host, self._port, keepalive=self._keepalive)
            self._client.loop_start()
        except Exception as exc:  # noqa: BLE001 — ghi lỗi, không crash app
            self._last_connect_error = str(exc)
            self._connected = False

    def stop(self) -> None:
        """Dừng loop và disconnect (gọi khi shutdown app)."""
        if not self._enabled:
            return
        try:
            self._client.loop_stop()
        finally:
            try:
                self._client.disconnect()
            except Exception:  # noqa: BLE001
                pass
        self._connected = False

    def status(self) -> dict[str, Any]:
        """Snapshot trạng thái phục vụ ``GET /api/mqtt/status``."""
        return {
            "enabled": self._enabled,
            "connected": self._connected,
            "host": self._host,
            "port": self._port,
            "client_id": self._client_id,
            "topics": list(self._topics),
            "qos": self._qos,
            "started_at": self._started_at,
            "last_connect_error": self._last_connect_error,
            "buffered_messages": self.message_count(),
        }

    def list_topics(self) -> list[str]:
        """
        LTP = List Topics.

        Công dụng:
            - Trả danh sách topic hiện hành (được subscribe khi reconnect).
        """
        with self._lock:
            return list(self._topics)

    def subscribe_topic(self, topic: str, qos: int | None = None) -> bool:
        """
        SUB = SUBscribe topic runtime.

        Công dụng:
            - Thêm topic mới vào danh sách theo dõi.
            - Nếu đang kết nối broker thì subscribe ngay, không cần restart app.
        """
        t = (topic or "").strip()
        if not t:
            return False

        with self._lock:
            if t in self._topics:
                return False
            self._topics.append(t)

        if self._connected:
            try:
                self._client.subscribe(t, qos=self._qos if qos is None else int(qos))
            except Exception as exc:  # noqa: BLE001
                self._last_connect_error = f"subscribe failed ({t}): {exc}"
        return True

    def unsubscribe_topic(self, topic: str) -> bool:
        """
        UNS = UNSubscribe topic runtime.

        Công dụng:
            - Bỏ topic khỏi danh sách theo dõi động.
            - Nếu đang kết nối broker thì unsubscribe ngay.
        """
        t = (topic or "").strip()
        if not t:
            return False

        removed = False
        with self._lock:
            if t in self._topics:
                self._topics = [x for x in self._topics if x != t]
                removed = True

        if removed and self._connected:
            try:
                self._client.unsubscribe(t)
            except Exception as exc:  # noqa: BLE001
                self._last_connect_error = f"unsubscribe failed ({t}): {exc}"
        return removed

    def message_count(self) -> int:
        """Số tin đang giữ trong buffer."""
        with self._lock:
            return len(self._messages)

    def latest_messages(self, limit: int = 50) -> list[dict[str, Any]]:
        """Trả tối đa ``limit`` tin cuối (mặc định 50, tối đa 1000)."""
        limit = max(1, min(int(limit), 1000))
        with self._lock:
            msgs = list(self._messages)[-limit:]
        return [
            {
                "topic": m.topic,
                "payload": m.payload,
                "qos": m.qos,
                "retain": m.retain,
                "received_at": m.received_at,
            }
            for m in msgs
        ]

    def publish_binary(self, *, topic: str, payload: bytes, qos: int = 0, retain: bool = False) -> dict[str, Any]:
        """PUB = publish payload bytes lên topic, dùng cho downlink command/testing."""
        t = str(topic or "").strip()
        if not t:
            return {"ok": False, "error": "topic is required"}
        if not self._enabled:
            return {"ok": False, "error": "mqtt disabled"}
        if not self._connected:
            return {"ok": False, "error": "mqtt not connected"}

        try:
            info = self._client.publish(t, payload=bytes(payload), qos=int(qos), retain=bool(retain))
            return {
                "ok": bool(info.rc == mqtt.MQTT_ERR_SUCCESS),
                "rc": int(info.rc),
                "mid": int(getattr(info, "mid", 0)),
            }
        except Exception as exc:  # noqa: BLE001
            self._last_connect_error = f"publish failed ({t}): {exc}"
            return {"ok": False, "error": str(exc)}

    def _on_connect(self, client: mqtt.Client, userdata: Any, flags: Any, reason_code: Any, properties: Any) -> None:  # noqa: ARG002
        """Callback paho: subscribe từng topic sau khi kết nối thành công."""
        self._connected = bool(getattr(reason_code, "value", reason_code) == 0)
        self._last_connect_error = None if self._connected else f"connect failed: {reason_code}"
        if not self._connected:
            return
        with self._lock:
            topics = list(self._topics)
        for topic in topics:
            try:
                client.subscribe(topic, qos=self._qos)
            except Exception as exc:  # noqa: BLE001
                self._last_connect_error = f"subscribe failed ({topic}): {exc}"

    def _on_disconnect(self, client: mqtt.Client, userdata: Any, disconnect_flags: Any, reason_code: Any, properties: Any) -> None:  # noqa: ARG002
        """Callback paho: đánh dấu mất kết nối."""
        self._connected = False
        if reason_code not in (0, None):
            self._last_connect_error = f"disconnected: {reason_code}"

    def _on_message(self, client: mqtt.Client, userdata: Any, msg: mqtt.MQTTMessage) -> None:  # noqa: ARG002
        """Callback paho: decode UTF-8, thử pretty-print JSON, append vào deque."""
        try:
            payload_raw = msg.payload.decode("utf-8", errors="replace")
        except Exception:  # noqa: BLE001
            payload_raw = str(msg.payload)

        # Normalize JSON payloads (handy for debugging / later forwarding)
        payload = payload_raw
        try:
            payload = json.dumps(json.loads(payload_raw), ensure_ascii=False)
        except Exception:  # noqa: BLE001
            pass

        decoded = decode_sensor_payload(str(msg.topic), bytes(msg.payload))
        if isinstance(decoded, dict):
            try:
                payload = json.dumps(decoded, ensure_ascii=False)
            except Exception:  # noqa: BLE001
                pass

            if self._on_sensor_payload is not None:
                try:
                    self._on_sensor_payload(decoded)
                except Exception as exc:  # noqa: BLE001
                    self._last_connect_error = f"sensor payload callback error: {exc}"

        with self._lock:
            self._messages.append(
                MqttMessage(
                    topic=str(msg.topic),
                    payload=payload,
                    qos=int(getattr(msg, "qos", 0)),
                    retain=bool(getattr(msg, "retain", False)),
                    received_at=time.time(),
                )
            )
