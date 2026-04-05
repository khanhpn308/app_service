from fastapi import APIRouter, Query, Request
from fastapi import HTTPException


router = APIRouter(prefix="/mqtt")


def _get_mqtt(request: Request):
    mqtt = getattr(request.app.state, "mqtt", None)
    if mqtt is None:
        raise HTTPException(status_code=503, detail="mqtt subscriber not initialized")
    return mqtt


@router.get("/status")
def mqtt_status(request: Request):
    mqtt = _get_mqtt(request)
    return mqtt.status()


@router.get("/messages")
def mqtt_messages(
    request: Request,
    limit: int = Query(default=50, ge=1, le=1000),
):
    mqtt = _get_mqtt(request)
    return {"items": mqtt.latest_messages(limit=limit)}

