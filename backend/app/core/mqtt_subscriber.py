from __future__ import annotations

import json
import threading
import time
from collections import deque
from dataclasses import dataclass
from typing import Any

import paho.mqtt.client as mqtt


@dataclass(frozen=True)
class MqttMessage:
    topic: str
    payload: str
    qos: int
    retain: bool
    received_at: float


def _parse_topics(topics_csv: str) -> list[str]:
    return [t.strip() for t in (topics_csv or "").split(",") if t.strip()]


class MqttSubscriber:
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
        if not self._enabled:
            return
        if self._started_at is not None:
            return
        self._started_at = time.time()

        try:
            self._client.connect(self._host, self._port, keepalive=self._keepalive)
            self._client.loop_start()
        except Exception as exc:  # noqa: BLE001
            self._last_connect_error = str(exc)
            self._connected = False

    def stop(self) -> None:
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

    def message_count(self) -> int:
        with self._lock:
            return len(self._messages)

    def latest_messages(self, limit: int = 50) -> list[dict[str, Any]]:
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

    def _on_connect(self, client: mqtt.Client, userdata: Any, flags: Any, reason_code: Any, properties: Any) -> None:  # noqa: ARG002
        self._connected = bool(getattr(reason_code, "value", reason_code) == 0)
        self._last_connect_error = None if self._connected else f"connect failed: {reason_code}"
        if not self._connected:
            return
        for topic in self._topics:
            try:
                client.subscribe(topic, qos=self._qos)
            except Exception as exc:  # noqa: BLE001
                self._last_connect_error = f"subscribe failed ({topic}): {exc}"

    def _on_disconnect(self, client: mqtt.Client, userdata: Any, disconnect_flags: Any, reason_code: Any, properties: Any) -> None:  # noqa: ARG002
        self._connected = False
        if reason_code not in (0, None):
            self._last_connect_error = f"disconnected: {reason_code}"

    def _on_message(self, client: mqtt.Client, userdata: Any, msg: mqtt.MQTTMessage) -> None:  # noqa: ARG002
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

