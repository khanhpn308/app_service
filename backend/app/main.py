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

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from app.api.router import api_router
from app.core.config import settings
from app.core.rate_limit import limiter
from app.core.db import SessionLocal, engine
from app.core.db_migrate import (
    ensure_device_authorization_granted_by_varchar,
    ensure_device_drop_last_reading_columns,
    ensure_device_publish_topic_column,
    ensure_device_topic_column,
    ensure_device_ui_columns,
    ensure_device_user_device_asignment_id_column,
    ensure_map_image_constraints,
    ensure_schema_hardening,
    ensure_user_cccd_varchar,
    ensure_user_expired_at_column,
)
from app.core.db_wait import wait_for_db
from app.core.influx_service import InfluxService
from app.core.ingest import ingest_sensor_payload
from app.core.mqtt_subscriber import MqttSubscriber
from app.core.realtime_hub import RealtimeHub
from app.core.seed import (
    ensure_default_admin,
    ensure_default_devices,
    ensure_default_maps,
)
from app.core.user_expiry import deactivate_expired_users
from app.models.device import Device
from app.models import device  # noqa: F401 — đăng ký model với metadata
from app.models import device_authorization  # noqa: F401
from app.models import user  # noqa: F401
from app.models.base import Base
from app.api.websocket_routes import router as websocket_router

logger = logging.getLogger("uvicorn.error")


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

    """các hàm trong db_migrate: đảm bảo schema có các cột mới mà app hiện tại cần, 
    thao tác với database bằng sql trực tiếp -> sử dụng engine thay vì session ORM.
    ưu: kiểm soát tốt hơn, tốc độ tối ưu hơn
    nhược: phải viết SQL thủ công, dễ lỗi hơn ORM."""
    ensure_user_expired_at_column(engine)
    ensure_device_user_device_asignment_id_column(engine)
    ensure_device_drop_last_reading_columns(engine)
    ensure_device_ui_columns(engine)
    ensure_device_topic_column(engine)
    ensure_device_publish_topic_column(engine)
    ensure_device_authorization_granted_by_varchar(engine)
    ensure_user_cccd_varchar(engine)
    ensure_schema_hardening(engine)
    ensure_map_image_constraints(engine)

    """Sau khi schema đã sẵn sàng, dùng session ORM để seed dữ liệu mặc định và xử lý user hết hạn.
    thao tác với database bằng python class model -> sử dụng session ORM.
    ưu: Code sạch và dễ bảo trì, dễ viết.
    Nhược: tốc độ kém hơn sql thuần túy, kiểm soát kèm hơn"""
    with SessionLocal() as db:
        ensure_default_admin(db)
        ensure_default_devices(db)
        ensure_default_maps(db)
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

    def _handle_sensor_payload(payload: dict) -> None:
        # Dùng pipeline chung (ghi Influx + broadcast) — cùng đường với WebSocket uplink.
        ingest_sensor_payload(app, payload)

    def _resolve_ping_reply_topic(incoming_topic: str) -> str | None:
        t = str(incoming_topic or "").strip()
        if not t:
            return None
        with SessionLocal() as db:
            row = (
                db.query(Device.publish_topic)
                .filter(Device.topic == t)
                .filter(Device.publish_topic.is_not(None))
                .first()
            )
        if row is None:
            return None
        return str(row[0] or "").strip() or None

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
        on_ping_reply_topic=_resolve_ping_reply_topic,
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

    # Rate limiter (slowapi) — chống brute-force endpoint auth.
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

    origins = [o.strip() for o in settings.cors_origins.split(",") if o.strip()]
    is_prod = settings.environment.lower() in {"prod", "production"}
    if not origins:
        if is_prod:
            # Không bao giờ dùng "*" với allow_credentials=True (browser từ chối + rủi ro CSRF).
            raise RuntimeError(
                "CORS_ORIGINS rỗng khi chạy production. Liệt kê origin frontend tường minh."
            )
        # Chỉ dev mới fallback localhost cho tiện.
        origins = ["http://localhost:3000", "http://localhost:5173", "http://localhost"]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(api_router, prefix="/api")
    # Also expose websocket endpoints without /api prefix for existing clients.
    app.include_router(websocket_router)
    # WebSocket routes (/ws/global, /ws/devices/{device_id}, /ws/esp32/{device_id}) được define
    # trong app/api/websocket_routes.py và auto-include vào api_router prefix=/api.
    # Xem websocket_routes.py để tìm hiểu chi tiết flow + payload schema.

    return app


app = create_app()
