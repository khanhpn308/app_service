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

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.router import api_router
from app.core.config import settings
from app.core.db import SessionLocal, engine
from app.core.db_migrate import (
    ensure_device_authorization_granted_by_varchar,
    ensure_device_drop_last_reading_columns,
    ensure_device_ui_columns,
    ensure_device_user_device_asignment_id_column,
    ensure_user_expired_at_column,
)
from app.core.db_wait import wait_for_db
from app.core.mqtt_subscriber import MqttSubscriber
from app.core.seed import ensure_default_admin, ensure_default_devices
from app.core.user_expiry import deactivate_expired_users
from app.models import device  # noqa: F401 — đăng ký model với metadata
from app.models import device_authorization  # noqa: F401
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
    ensure_device_authorization_granted_by_varchar(engine)
    with SessionLocal() as db:
        ensure_default_admin(db)
        ensure_default_devices(db)
        deactivate_expired_users(db)

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
    )
    mqtt_sub.start()
    app.state.mqtt = mqtt_sub
    yield
    try:
        mqtt_sub.stop()
    except Exception:  # noqa: BLE001 — shutdown: không crash process
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
    return app


app = create_app()
