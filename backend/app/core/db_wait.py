"""Wait until MySQL accepts connections (Docker startup race)."""

import asyncio
import logging

from sqlalchemy import text

from app.core.config import settings
from app.core.db import engine

logger = logging.getLogger(__name__)

MAX_ATTEMPTS = 60
SLEEP_SEC = 2.0


async def wait_for_db() -> None:
    """Retry TCP/SQL connect until DB is up or attempts exhausted."""

    logger.info(
        "Waiting for database at %s:%s",
        settings.db_host,
        settings.db_port,
    )

    last_err: Exception | None = None
    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:

            def _ping() -> None:
                with engine.connect() as conn:
                    conn.execute(text("SELECT 1"))

            await asyncio.to_thread(_ping)
            if attempt > 1:
                logger.info("Database became available after %s attempts", attempt)
            return
        except Exception as exc:  # noqa: BLE001
            last_err = exc
            logger.warning(
                "Database not ready (%s/%s): %s",
                attempt,
                MAX_ATTEMPTS,
                exc,
            )
            await asyncio.sleep(SLEEP_SEC)

    msg = (
        "Database unavailable after "
        f"{MAX_ATTEMPTS} attempts at {settings.db_host}:{settings.db_port}: {last_err!r}"
    )
    raise RuntimeError(msg) from last_err
