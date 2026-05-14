from __future__ import annotations

import time
import uuid
from decimal import Decimal
from datetime import UTC, datetime
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.deps import get_db, require_admin
from app.models.test_log import TestLog
from app.models.user import User


router = APIRouter(prefix="/test", tags=["test"])


def _to_int(v):
    if v is None:
        return None
    if isinstance(v, bool):
        return int(v)
    if isinstance(v, (int, Decimal)):
        return int(v)
    try:
        return int(v)
    except Exception:
        return None


class TestConfigPayload(BaseModel):
    enabled: bool
    protocol: Literal["mqtt", "websocket"] = "mqtt"
    gateway_id: str = Field(default="", max_length=128)
    node_id: str = Field(default="", max_length=128)
    device_id: str = Field(default="", max_length=128)
    message: str = Field(default="", max_length=500)


class TestSendPayload(BaseModel):
    protocol: Literal["mqtt"] = "mqtt"
    gateway_id: str = Field(..., min_length=1, max_length=128)
    node_id: str = Field(..., min_length=1, max_length=128)
    message: str = Field(..., min_length=1, max_length=500)


def _get_test_service(request: Request):
    service = getattr(request.app.state, "test_service", None)
    if service is None:
        raise HTTPException(status_code=503, detail="test service not initialized")
    return service


def _get_mqtt(request: Request):
    mqtt = getattr(request.app.state, "mqtt", None)
    if mqtt is None:
        raise HTTPException(status_code=503, detail="mqtt subscriber not initialized")
    return mqtt


@router.get("/config")
def get_test_config(
    request: Request,
    _: User = Depends(require_admin),
):
    service = _get_test_service(request)
    return service.get_config()


@router.put("/config")
def update_test_config(
    body: TestConfigPayload,
    request: Request,
    _: User = Depends(require_admin),
):
    service = _get_test_service(request)
    return service.update_config(
        enabled=body.enabled,
        protocol=body.protocol,
        gateway_id=body.gateway_id,
        node_id=body.node_id,
        device_id=body.device_id,
        message=body.message,
    )


@router.post("/send")
def send_test_message(
    body: TestSendPayload,
    request: Request,
    _: User = Depends(require_admin),
):
    mqtt = _get_mqtt(request)
    if body.protocol != "mqtt":
        raise HTTPException(status_code=422, detail="send is only supported for mqtt test mode")
    gateway_id = body.gateway_id.strip()
    node_id = body.node_id.strip()
    if not gateway_id or not node_id:
        raise HTTPException(status_code=422, detail="gateway_id and node_id must not be blank")

    msg_id = uuid.uuid4().hex
    server_mark_time_ms = time.time_ns() // 1_000_000
    payload_text = str(body.message)
    payload = payload_text.encode("utf-8")
    topic = f"gateway/{gateway_id}/node/{node_id}/downlink"
    info = mqtt.publish_binary(topic=topic, payload=payload, qos=0, retain=False)
    if not info.get("ok"):
        raise HTTPException(status_code=503, detail=info.get("error") or "publish failed")

    return {
        "ok": True,
        "msg_id": msg_id,
        "topic": topic,
        "sent_at_ms": server_mark_time_ms,
        "payload": payload_text,
        "payload_hex": payload.hex(),
        "note": "payload sent as UTF-8 text (websocket-like)",
    }


@router.get("/logs")
def list_test_logs(
    limit: int = Query(default=100, ge=1, le=1000),
    device_name: str | None = Query(default=None, max_length=128),
    protocol: str | None = Query(default=None, max_length=32),
    device_id: str | None = Query(default=None, max_length=128),
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    q = db.query(TestLog)
    # Filter by protocol if provided (e.g. "websocket" or "mqtt").
    if protocol:
        q = q.filter(TestLog.protocol == protocol)

    # Filter by device_id (matches TestLog.node_id for websocket/mqtt test entries).
    if device_id:
        q = q.filter(func.coalesce(TestLog.node_id, "") == str(device_id).strip())

    # Backwards-compatible device_name search for display name matching.
    search = (device_name or "").strip()
    if search:
        q = q.filter(func.lower(func.coalesce(TestLog.device_name, "")).like(f"%{search.lower()}%"))
    rows = q.order_by(TestLog.id.desc()).limit(limit).all()
    items = []
    for r in rows:
        ts_ms = _to_int(r.mark_time_ms)
        if ts_ms is None:
            continue
        delay_gs = _to_int(r.delay_gateway_to_server_ms)
        items.append(
            {
                "id": _to_int(r.id),
                "protocol": r.protocol,
                "version": _to_int(r.version),
                "message": r.message,
                "node_id": r.node_id,
                "device_name": r.device_name,
                "gateway_id": r.gateway_id,
                "event_timestamp_ms": _to_int(r.event_timestamp_ms),
                "gateway_timestamp_ms": _to_int(r.gateway_timestamp_ms),
                "mark_time_ms": ts_ms,
                "time_test": datetime.fromtimestamp(ts_ms / 1000, tz=UTC).isoformat(),
                "delay_gateway_to_server_ms": delay_gs,
                "rssi": _to_int(r.rssi),
                "src_mac": r.src_mac,
                "topic": r.topic,
            }
        )
    return {"items": items}
