from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.router import api_router
from app.core.config import settings
from app.core.db import SessionLocal, engine
from app.core.db_migrate import (
    ensure_device_authorization_granted_by_varchar,
    ensure_device_user_device_asignment_id_column,
    ensure_user_expired_at_column,
)
from app.core.db_wait import wait_for_db
from app.core.mqtt_subscriber import MqttSubscriber
from app.core.seed import ensure_default_admin, ensure_default_devices
from app.core.user_expiry import deactivate_expired_users
from app.models import device  # noqa: F401
from app.models import device_authorization  # noqa: F401
from app.models import user  # noqa: F401
from app.models.base import Base


@asynccontextmanager
async def lifespan(app: FastAPI):
    await wait_for_db()
    Base.metadata.create_all(bind=engine)
    ensure_user_expired_at_column(engine)
    ensure_device_user_device_asignment_id_column(engine)
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
    except Exception:  # noqa: BLE001
        pass


def create_app() -> FastAPI:
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

