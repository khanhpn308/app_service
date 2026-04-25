from __future__ import annotations

import time
from decimal import Decimal
from datetime import UTC, datetime
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.deps import get_db, require_admin
from app.core.test_payload_codec import encode_test_downlink_proto
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
    protocol: Literal["websocket"] = "websocket"
    gateway_id: str = Field(default="", max_length=128)
    node_id: str = Field(default="", max_length=128)
    message: str = Field(default="", max_length=500)


class TestSendPayload(BaseModel):
    protocol: Literal["websocket"] = "websocket"
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
        message=body.message,
    )


@router.post("/send")
def send_test_message(
    body: TestSendPayload,
    request: Request,
    _: User = Depends(require_admin),
):
    mqtt = _get_mqtt(request)
    mark_time_ms = int(time.time() * 1000)
    payload = encode_test_downlink_proto(
        gateway_id=body.gateway_id.strip(),
        node_id=body.node_id.strip(),
        message=body.message,
        mark_time_ms=mark_time_ms,
        protocol=body.protocol,
    )
    topic = f"gateway/{body.gateway_id.strip()}/node/{body.node_id.strip()}/downlink"
    info = mqtt.publish_binary(topic=topic, payload=payload, qos=0, retain=False)
    if not info.get("ok"):
        raise HTTPException(status_code=503, detail=info.get("error") or "publish failed")

    return {
        "ok": True,
        "topic": topic,
        "mark_time_ms": mark_time_ms,
        "payload_hex": payload.hex(),
        "note": "payload uses protobuf binary format compatible with nanopb",
    }


@router.get("/logs")
def list_test_logs(
    limit: int = Query(default=100, ge=1, le=1000),
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    rows = db.query(TestLog).order_by(TestLog.id.desc()).limit(limit).all()
    items = []
    for r in rows:
        ts_ms = _to_int(r.mark_time_ms)
        if ts_ms is None:
            continue
        delay_ng = _to_int(r.delay_node_to_gateway_ms)
        delay_gs = _to_int(r.delay_gateway_to_server_ms)
        delay_ns = _to_int(r.delay_node_to_server_ms)
        items.append(
            {
                "id": _to_int(r.id),
                "protocol": r.protocol,
                "version": _to_int(r.version),
                "message": r.message,
                "node_id": r.node_id,
                "gateway_id": r.gateway_id,
                "event_timestamp_ms": _to_int(r.event_timestamp_ms),
                "gateway_timestamp_ms": _to_int(r.gateway_timestamp_ms),
                "mark_time_ms": ts_ms,
                "time_test": datetime.fromtimestamp(ts_ms / 1000, tz=UTC).isoformat(),
                "delay_node_to_gateway_ms": delay_ng,
                "delay_gateway_to_server_ms": delay_gs,
                "delay_node_to_server_ms": delay_ns,
                "rssi": _to_int(r.rssi),
                "src_mac": r.src_mac,
                "topic": r.topic,
            }
        )
    return {"items": items}
