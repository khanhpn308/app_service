"""
Package ``app.models``: đăng ký các class ORM cho SQLAlchemy.

``__all__`` giúp ``from app.models import User`` rõ ràng. Import model trong ``main.py`` (kèm ``# noqa``)
để bảo đảm metadata đăng ký trước ``create_all``.
"""

from app.models.base import Base
from app.models.device import Device
from app.models.device_authorization import DeviceAuthorization
from app.models.user import User

__all__ = ["Base", "User", "Device", "DeviceAuthorization"]
