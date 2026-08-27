"""Thread-safe gateway liveness tracking with throttled MySQL persistence."""

from __future__ import annotations

import threading
from datetime import datetime, timedelta, timezone
from typing import Callable

from sqlalchemy.orm import Session

from app.models.device import Device


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class GatewayPresence:
    """Record trusted gateway activity using server time, flushing at most once/window."""

    def __init__(self, session_factory: Callable[[], Session], *, flush_seconds: int = 5):
        self._session_factory = session_factory
        self._flush_after = timedelta(seconds=max(1, int(flush_seconds)))
        self._last_seen: dict[int, datetime] = {}
        self._last_flushed: dict[int, datetime] = {}
        self._lock = threading.Lock()

    def touch(self, gateway_id: int, *, now: datetime | None = None) -> bool:
        observed = (now or utcnow()).astimezone(timezone.utc)
        gateway_id = int(gateway_id)
        with self._lock:
            self._last_seen[gateway_id] = observed
            previous = self._last_flushed.get(gateway_id)
            if previous is not None and observed - previous < self._flush_after:
                return False
            self._last_flushed[gateway_id] = observed

        db = self._session_factory()
        try:
            row = db.get(Device, gateway_id)
            if row is None or (row.device_type or "").strip().casefold() != "gateway":
                with self._lock:
                    self._last_flushed.pop(gateway_id, None)
                return False
            row.last_seen_at = observed.replace(tzinfo=None)
            db.commit()
            return True
        except Exception:
            db.rollback()
            with self._lock:
                self._last_flushed.pop(gateway_id, None)
            raise
        finally:
            db.close()

    def last_seen(self, gateway_id: int) -> datetime | None:
        with self._lock:
            value = self._last_seen.get(int(gateway_id))
        return value

