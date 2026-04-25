from __future__ import annotations

import threading
import time
from typing import Any

from sqlalchemy.orm import Session, sessionmaker

from app.models.device import Device
from app.models.test_log import TestLog


def _epoch_ms_now() -> int:
    return time.time_ns() // 1_000_000


class TestService:
    def __init__(self, session_factory: sessionmaker):
        self._session_factory = session_factory
        self._lock = threading.Lock()
        self._enabled = False
        self._protocol = "websocket"
        self._gateway_id = ""
        self._node_id = ""
        self._default_message = ""

    def get_config(self) -> dict[str, Any]:
        with self._lock:
            return {
                "enabled": self._enabled,
                "protocol": self._protocol,
                "gateway_id": self._gateway_id,
                "node_id": self._node_id,
                "message": self._default_message,
            }

    def update_config(
        self,
        *,
        enabled: bool,
        protocol: str,
        gateway_id: str,
        node_id: str,
        message: str,
    ) -> dict[str, Any]:
        with self._lock:
            self._enabled = bool(enabled)
            self._protocol = str(protocol or "websocket").strip() or "websocket"
            self._gateway_id = str(gateway_id or "").strip()
            self._node_id = str(node_id or "").strip()
            self._default_message = str(message or "").strip()
            return {
                "enabled": self._enabled,
                "protocol": self._protocol,
                "gateway_id": self._gateway_id,
                "node_id": self._node_id,
                "message": self._default_message,
            }

    def _matches(self, *, protocol: str, gateway_id: str, node_id: str) -> bool:
        with self._lock:
            if not self._enabled:
                return False
            if self._protocol != protocol:
                return False
            if self._gateway_id != str(gateway_id or "").strip():
                return False
            if self._node_id != str(node_id or "").strip():
                return False
            return True

    def process_decoded_uplink(self, *, decoded: dict[str, Any], protocol: str, topic: str, raw_hex: str) -> bool:
        t_server_receive_ms = int(decoded.get("server_receive_ms") or _epoch_ms_now())
        gateway_id = str(decoded.get("gateway_id") or "").strip()
        node_id = str(decoded.get("node_id") or "").strip()
        if not gateway_id or not node_id:
            return False
        if not self._matches(protocol=protocol, gateway_id=gateway_id, node_id=node_id):
            return False

        event_ts = decoded.get("event_timestamp_ms")
        gateway_ts = decoded.get("gateway_timestamp_ms")
        delay_gateway_to_server = None
        device_name = str(decoded.get("device_name") or "").strip() or None
        device_id_int = None

        try:
            gateway_ts_int = int(gateway_ts) if gateway_ts is not None else None
            if gateway_ts_int is not None:
                delay_gateway_to_server = t_server_receive_ms - gateway_ts_int
        except Exception:
            gateway_ts_int = None

        try:
            event_ts_int = int(event_ts) if event_ts is not None else None
        except Exception:
            event_ts_int = None

        try:
            device_id_int = int(decoded.get("device_id")) if decoded.get("device_id") is not None else None
        except Exception:
            device_id_int = None

        with self._session_factory() as db:
            db: Session
            device = None
            if device_name is None and topic:
                device = db.query(Device).filter(Device.topic == topic).first()
            if device is None and device_name is None and device_id_int is not None:
                device = db.query(Device).filter(Device.device_id == device_id_int).first()
            if device is not None:
                device_name = str(device.devicename or "").strip() or None
            if device_name is None:
                # Final fallback for display when registry name is unavailable.
                device_name = node_id

            row = TestLog(
                protocol=protocol,
                version=decoded.get("version"),
                message_len=decoded.get("message_len"),
                message=str(decoded.get("message") or ""),
                node_id_len=decoded.get("node_id_len"),
                node_id=node_id,
                device_name=device_name,
                gateway_id_len=decoded.get("gateway_id_len"),
                gateway_id=gateway_id,
                event_timestamp_ms=event_ts_int,
                gateway_timestamp_ms=gateway_ts_int,
                mark_time_ms=t_server_receive_ms,
                delay_gateway_to_server_ms=delay_gateway_to_server,
                rssi=decoded.get("rssi"),
                src_mac=decoded.get("src_mac"),
                topic=topic,
                raw_hex=raw_hex,
            )
            db.add(row)
            db.commit()
        return True
