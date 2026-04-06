"""
API quan sát MQTT subscriber (debug / vận hành).

Subscriber thật được tạo trong ``main.lifespan`` và gắn vào ``request.app.state.mqtt``.
Các route này đọc trạng thái và buffer tin nhận gần đây — **không** thay cho broker hay rule nghiệp vụ IoT đầy đủ.
"""

from fastapi import APIRouter, Query, Request
from fastapi import HTTPException


router = APIRouter(prefix="/mqtt")


def _get_mqtt(request: Request):
    """Lấy instance ``MqttSubscriber`` từ app state; 503 nếu chưa khởi tạo."""
    mqtt = getattr(request.app.state, "mqtt", None)
    if mqtt is None:
        raise HTTPException(status_code=503, detail="mqtt subscriber not initialized")
    return mqtt


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
