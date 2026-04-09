"""
API quan sát MQTT subscriber (debug / vận hành).

Subscriber thật được tạo trong ``main.lifespan`` và gắn vào ``request.app.state.mqtt``.
Các route này đọc trạng thái và buffer tin nhận gần đây — **không** thay cho broker hay rule nghiệp vụ IoT đầy đủ.
"""

from pydantic import BaseModel
from fastapi import APIRouter, Depends, Query, Request
from fastapi import HTTPException

from app.core.deps import require_admin
from app.models.user import User


router = APIRouter(prefix="/mqtt")


class TopicPayload(BaseModel):
    """Body chuẩn cho thao tác subscribe/unsubscribe topic runtime."""

    topic: str
    qos: int | None = None


def _get_mqtt(request: Request):
    """Lấy instance ``MqttSubscriber`` từ app state; 503 nếu chưa khởi tạo."""
    mqtt = getattr(request.app.state, "mqtt", None)
    if mqtt is None:
        raise HTTPException(status_code=503, detail="mqtt subscriber not initialized")
    return mqtt


def _get_influx(request: Request):
    """Lấy Influx service từ app state; 503 nếu chưa khởi tạo."""
    influx = getattr(request.app.state, "influx", None)
    if influx is None:
        raise HTTPException(status_code=503, detail="influx service not initialized")
    return influx


@router.get("/status")
def mqtt_status(request: Request):
    """Trả dict trạng thái: kết nối, host, topic, lỗi kết nối gần nhất, …"""
    mqtt = _get_mqtt(request)
    return mqtt.status()


@router.get("/messages")
def mqtt_messages(
    request: Request,
    limit: int = Query(default=50, ge=1, le=1000),
):
    """Danh sách tin đã buffer trong bộ nhớ (giới hạn ``limit``)."""
    mqtt = _get_mqtt(request)
    return {"items": mqtt.latest_messages(limit=limit)}


@router.get("/topics")
def mqtt_topics(
    request: Request,
    _: User = Depends(require_admin),
):
    """Admin: danh sách topic đang theo dõi."""
    mqtt = _get_mqtt(request)
    return {"items": mqtt.list_topics()}


@router.post("/topics/subscribe")
def mqtt_subscribe_topic(
    body: TopicPayload,
    request: Request,
    _: User = Depends(require_admin),
):
    """Admin: subscribe topic động khi runtime (không cần restart app)."""
    mqtt = _get_mqtt(request)
    changed = mqtt.subscribe_topic(body.topic, qos=body.qos)
    return {"ok": True, "changed": changed, "topics": mqtt.list_topics()}


@router.post("/topics/unsubscribe")
def mqtt_unsubscribe_topic(
    body: TopicPayload,
    request: Request,
    _: User = Depends(require_admin),
):
    """Admin: unsubscribe topic động khi runtime."""
    mqtt = _get_mqtt(request)
    changed = mqtt.unsubscribe_topic(body.topic)
    return {"ok": True, "changed": changed, "topics": mqtt.list_topics()}


@router.get("/history")
def mqtt_history(
    request: Request,
    minutes: int = Query(default=30, ge=1, le=180),
    device_id: str | None = Query(default=None),
):
    """Lịch sử dữ liệu cảm biến từ InfluxDB trong N phút gần nhất (mặc định 30 phút)."""
    influx = _get_influx(request)
    items = influx.query_history(minutes=minutes, device_id=device_id)
    return {"items": items, "minutes": minutes, "device_id": device_id}


@router.get("/influx/status")
def mqtt_influx_status(request: Request):
    """Trạng thái Influx service: enabled/start/bucket/last_error để debug ghi dữ liệu."""
    influx = _get_influx(request)
    return influx.status()
