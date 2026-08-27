"""
Package ``app.models``: đăng ký các class ORM cho SQLAlchemy.

``__all__`` giúp ``from app.models import User`` rõ ràng. Import model trong ``main.py`` (kèm ``# noqa``)
để bảo đảm metadata đăng ký trước ``create_all``.
"""

from app.models.base import Base
from app.models.device import Device
from app.models.device_authorization import DeviceAuthorization
from app.models.map_group import MapGroup, MapGroupMembership
from app.models.map_location import LocationDeleted, LocationUsing
from app.models.anchor import Anchor, AnchorConfigDelivery, AnchorConfigOutbox
from app.models.ping import MissingPingPayload, PingPayload
from app.models.user import User

__all__ = [
    "Base",
    "User",
    "Device",
    "DeviceAuthorization",
    "MapGroup",
    "MapGroupMembership",
    "LocationUsing",
    "Anchor",
    "AnchorConfigOutbox",
    "AnchorConfigDelivery",
    "PingPayload",
    "MissingPingPayload",
    "LocationDeleted",
]
