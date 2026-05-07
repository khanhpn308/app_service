from __future__ import annotations

import threading
import time
from typing import Any

from sqlalchemy.orm import Session, sessionmaker

from app.models.device import Device
from app.models.test_log import TestLog


def _epoch_ms_now() -> int:
    return time.time_ns() // 1_000_000


def _coerce_int(value: Any) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return int(value)
    try:
        return int(value)
    except Exception:
        return None


class TestService:
    def __init__(self, session_factory: sessionmaker):
        self._session_factory = session_factory
        self._lock = threading.Lock()
        self._enabled = False
        self._protocol = "mqtt"
        self._gateway_id = ""
        self._node_id = ""
        self._device_id = ""
        self._default_message = ""

    def get_config(self) -> dict[str, Any]:
        with self._lock:
            return {
                "enabled": self._enabled,
                "protocol": self._protocol,
                "gateway_id": self._gateway_id,
                "node_id": self._node_id,
                "device_id": self._device_id,
                "message": self._default_message,
            }

    def update_config(
        self,
        *,
        enabled: bool,
        protocol: str,
        gateway_id: str,
        node_id: str,
        device_id: str,
        message: str,
    ) -> dict[str, Any]:
        with self._lock:
            self._enabled = bool(enabled)
            self._protocol = str(protocol or "mqtt").strip() or "mqtt"
            self._gateway_id = str(gateway_id or "").strip()
            self._node_id = str(node_id or "").strip()
            self._device_id = str(device_id or "").strip()
            self._default_message = str(message or "").strip()
            return {
                "enabled": self._enabled,
                "protocol": self._protocol,
                "gateway_id": self._gateway_id,
                "node_id": self._node_id,
                "device_id": self._device_id,
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

    def _matches_websocket(self, *, device_id: str) -> bool:
        with self._lock:
            if not self._enabled:
                return False
            if self._protocol != "websocket":
                return False
            return self._device_id == str(device_id or "").strip()

    def _resolve_device_name(self, db: Session, *, device_id: str, fallback: str) -> str:
        device_id_int = _coerce_int(device_id)
        if device_id_int is not None:
            device = db.query(Device).filter(Device.device_id == device_id_int).first()
            if device is not None:
                name = str(device.devicename or "").strip()
                if name:
                    return name
        return fallback

    def _write_test_log(
        self,
        *,
        protocol: str,
        gateway_id: str,
        node_id: str,
        device_name: str | None,
        event_timestamp_ms: int | None,
        gateway_timestamp_ms: int | None,
        delay_gateway_to_server_ms: int | None,
        topic: str,
        raw_hex: str,
        version: int | None = None,
        message_len: int | None = None,
        message: str | None = None,
        node_id_len: int | None = None,
        gateway_id_len: int | None = None,
        rssi: int | None = None,
        src_mac: str | None = None,
    ) -> None:
        with self._session_factory() as db:
            db: Session
            row = TestLog(
                protocol=protocol,
                version=version,
                message_len=message_len,
                message=message,
                node_id_len=node_id_len,
                node_id=node_id,
                device_name=device_name,
                gateway_id_len=gateway_id_len,
                gateway_id=gateway_id,
                event_timestamp_ms=event_timestamp_ms,
                gateway_timestamp_ms=gateway_timestamp_ms,
                mark_time_ms=gateway_timestamp_ms or _epoch_ms_now(),
                delay_gateway_to_server_ms=delay_gateway_to_server_ms,
                rssi=rssi,
                src_mac=src_mac,
                topic=topic,
                raw_hex=raw_hex,
            )
            db.add(row)
            db.commit()

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

        with self._session_factory() as db:
            db: Session
            device = None
            if device_name is None and topic:
                device = db.query(Device).filter(Device.topic == topic).first()
            if device is not None:
                device_name = str(device.devicename or "").strip() or None
            if device_name is None:
                # Final fallback for display when registry name is unavailable.
                device_name = node_id

        self._write_test_log(
            protocol=protocol,
            gateway_id=gateway_id,
            node_id=node_id,
            device_name=device_name,
            event_timestamp_ms=event_ts_int,
            gateway_timestamp_ms=gateway_ts_int,
            delay_gateway_to_server_ms=delay_gateway_to_server,
            topic=topic,
            raw_hex=raw_hex,
            version=_coerce_int(decoded.get("version")),
            message_len=_coerce_int(decoded.get("message_len")),
            message=str(decoded.get("message") or ""),
            node_id_len=_coerce_int(decoded.get("node_id_len")),
            gateway_id_len=_coerce_int(decoded.get("gateway_id_len")),
            rssi=_coerce_int(decoded.get("rssi")),
            src_mac=str(decoded.get("src_mac") or "") or None,
        )
        return True

    def process_websocket_uplink(self, *, decoded: dict[str, Any], device_id: str, raw_hex: str = "") -> bool:
        t_server_receive_ms = int(decoded.get("server_receive_ms") or _epoch_ms_now())
        if not self._matches_websocket(device_id=device_id):
            return False

        payload_ts_ms = decoded.get("timestamp_ms")
        if payload_ts_ms is None and decoded.get("ts") is not None:
            try:
                payload_ts_ms = int(float(decoded.get("ts")) * 1000.0)
            except Exception:
                payload_ts_ms = None

        try:
            payload_ts_int = int(payload_ts_ms) if payload_ts_ms is not None else None
        except Exception:
            payload_ts_int = None

        delay_ms = None
        if payload_ts_int is not None:
            delay_ms = t_server_receive_ms - payload_ts_int

        with self._session_factory() as db:
            db: Session
            device_name = self._resolve_device_name(db, device_id=device_id, fallback=str(device_id).strip())

        self._write_test_log(
            protocol="websocket",
            gateway_id="websocket",
            node_id=str(device_id).strip() or "unknown",
            device_name=device_name,
            event_timestamp_ms=payload_ts_int,
            gateway_timestamp_ms=t_server_receive_ms,
            delay_gateway_to_server_ms=delay_ms,
            topic=str(decoded.get("topic") or f"ws/{device_id}"),
            raw_hex=raw_hex,
        )
        return True
