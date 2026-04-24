"""
Điểm vào ứng dụng FastAPI (ASGI).

Vai trò:
    - Đăng ký middleware CORS (cho phép frontend React gọi API cross-origin).
    - Gắn toàn bộ REST API dưới tiền tố ``/api`` (xem ``api/router.py``).
    - ``lifespan``: trước khi nhận request — chờ MySQL, tạo/bổ sung schema, seed dữ liệu mặc định,
      khởi chạy MQTT subscriber; khi tắt process — dừng subscriber.

Tên ``main`` / ``create_app``: quy ước phổ biến trong FastAPI/Flask — module chứa factory ``create_app()`` và
instance ``app`` dùng cho uvicorn: ``uvicorn app.main:app``.
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from app.api.router import api_router
from app.core.config import settings
from app.core.db import SessionLocal, engine
from app.core.db_migrate import (
    ensure_device_authorization_granted_by_varchar,
    ensure_device_drop_last_reading_columns,
    ensure_device_topic_column,
    ensure_test_logs_table,
    ensure_device_ui_columns,
    ensure_device_user_device_asignment_id_column,
    ensure_user_expired_at_column,
)
from app.core.db_wait import wait_for_db
from app.core.influx_service import InfluxService
from app.core.mqtt_subscriber import MqttSubscriber
from app.core.realtime_hub import RealtimeHub
from app.core.seed import ensure_default_admin, ensure_default_devices
from app.core.test_service import TestService
from app.core.user_expiry import deactivate_expired_users
from app.models.device import Device
from app.models import device  # noqa: F401 — đăng ký model với metadata
from app.models import device_authorization  # noqa: F401
from app.models import test_log  # noqa: F401
from app.models import user  # noqa: F401
from app.models.base import Base


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Hook vòng đời ứng dụng (startup / shutdown).

    Startup:
        1. ``wait_for_db`` — tránh lỗi race khi container DB chưa sẵn sàng.
        2. ``Base.metadata.create_all`` — tạo bảng thiếu theo ORM.
        3. Các hàm ``ensure_*`` trong ``db_migrate`` — ALTER nhẹ cho DB cũ (volume đã tồn tại).
        4. Seed admin/thiết bị mặc định; vô hiệu hóa user hết hạn.
        5. MQTT: ``MqttSubscriber.start()``; lưu instance vào ``app.state.mqtt`` cho route debug.

    Shutdown:
        Dừng vòng lặp MQTT (bỏ qua lỗi nếu broker đã ngắt).
    """
    await wait_for_db()
    Base.metadata.create_all(bind=engine)
    ensure_user_expired_at_column(engine)
    ensure_device_user_device_asignment_id_column(engine)
    ensure_device_drop_last_reading_columns(engine)
    ensure_device_ui_columns(engine)
    ensure_device_topic_column(engine)
    ensure_test_logs_table(engine)
    ensure_device_authorization_granted_by_varchar(engine)
    with SessionLocal() as db:
        ensure_default_admin(db)
        ensure_default_devices(db)
        deactivate_expired_users(db)

    influx = InfluxService(
        enabled=settings.influx_enabled,
        url=settings.influx_url,
        token=settings.influx_token,
        org=settings.influx_org,
        bucket=settings.influx_bucket,
        measurement=settings.influx_measurement,
    )
    influx.start()
    app.state.influx = influx

    realtime_hub = RealtimeHub()
    await realtime_hub.start()
    app.state.realtime_hub = realtime_hub
    test_service = TestService(SessionLocal)
    app.state.test_service = test_service

    def _handle_sensor_payload(payload: dict) -> None:
        influx.write_sensor_point(payload)
        realtime_hub.publish_from_thread(payload)
        try:
            test_service.process_decoded_uplink(
                decoded=payload,
                protocol="websocket",
                topic=str(payload.get("topic") or ""),
                raw_hex=str(payload.get("raw_hex") or ""),
            )
        except Exception:
            pass

    mqtt_sub = MqttSubscriber(
        enabled=settings.mqtt_enabled,
        host=settings.mqtt_host,
        port=settings.mqtt_port,
        username=settings.mqtt_username,
        password=settings.mqtt_password,
        client_id=settings.mqtt_client_id,
        keepalive=settings.mqtt_keepalive,
        topics_csv=settings.mqtt_topics,
        qos=settings.mqtt_qos,
        max_messages=settings.mqtt_max_messages,
        on_sensor_payload=_handle_sensor_payload,
    )
    mqtt_sub.start()
    # Restore topic subscriptions from persisted device.topic values.
    with SessionLocal() as db:
        topic_rows = db.query(Device.topic).filter(Device.topic.is_not(None)).all()
    for (topic,) in topic_rows:
        t = str(topic or "").strip()
        if t:
            mqtt_sub.subscribe_topic(t)
    app.state.mqtt = mqtt_sub
    yield
    try:
        mqtt_sub.stop()
    except Exception:  # noqa: BLE001 — shutdown: không crash process
        pass
    try:
        await realtime_hub.stop()
    except Exception:  # noqa: BLE001
        pass
    try:
        influx.stop()
    except Exception:  # noqa: BLE001
        pass


def create_app() -> FastAPI:
    """
    Factory tạo instance FastAPI (dễ test hoặc tạo nhiều app).

    Returns:
        Ứng dụng đã gắn CORS và ``api_router`` prefix ``/api``.
    """
    app = FastAPI(title=settings.app_name, lifespan=lifespan)

    origins = [o.strip() for o in settings.cors_origins.split(",") if o.strip()]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins or ["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(api_router, prefix="/api")

    @app.websocket("/ws/global")
    async def ws_global(websocket: WebSocket) -> None:
        """WebSocket luồng realtime cho GlobalDashboard."""
        hub = getattr(app.state, "realtime_hub", None)
        if hub is None:
            await websocket.close(code=1011)
            return
        await hub.connect_global(websocket)
        try:
            while True:
                await websocket.receive_text()
        except WebSocketDisconnect:
            await hub.disconnect_global(websocket)
        except Exception:
            await hub.disconnect_global(websocket)

    @app.websocket("/ws/devices/{device_id}")
    async def ws_device(websocket: WebSocket, device_id: str) -> None:
        """WebSocket luồng realtime cho dashboard theo từng thiết bị."""
        hub = getattr(app.state, "realtime_hub", None)
        if hub is None:
            await websocket.close(code=1011)
            return
        await hub.connect_device(websocket, device_id)
        try:
            while True:
                await websocket.receive_text()
        except WebSocketDisconnect:
            await hub.disconnect_device(websocket, device_id)
        except Exception:
            await hub.disconnect_device(websocket, device_id)

    return app


app = create_app()
