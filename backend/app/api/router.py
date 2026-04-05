from fastapi import APIRouter

from .auth_routes import router as auth_router
from .authorizations_routes import router as authorizations_router
from .devices_routes import router as devices_router
from .health import router as health_router
from .mqtt_routes import router as mqtt_router
from .users_routes import router as users_router

api_router = APIRouter()
api_router.include_router(health_router, tags=["health"])
api_router.include_router(mqtt_router, tags=["mqtt"])
api_router.include_router(auth_router)
api_router.include_router(devices_router)
api_router.include_router(authorizations_router)
api_router.include_router(users_router)

