"""Lightweight schema patches for existing DB volumes (initdb scripts only run once)."""

from sqlalchemy import text
from sqlalchemy.engine import Engine


def ensure_user_expired_at_column(engine: Engine) -> None:
    """Add `user.expired_at` when missing; backfill from creat_at."""
    with engine.begin() as conn:
        r = conn.execute(
            text(
                """
                SELECT COUNT(*) FROM information_schema.COLUMNS
                WHERE TABLE_SCHEMA = DATABASE()
                  AND TABLE_NAME = 'user'
                  AND COLUMN_NAME = 'expired_at'
                """
            )
        )
        if (r.scalar() or 0) == 0:
            conn.execute(
                text(
                    "ALTER TABLE `user` ADD COLUMN `expired_at` DATE NULL AFTER `creat_at`"
                )
            )
        conn.execute(
            text(
                """
                UPDATE `user`
                SET `expired_at` = DATE_ADD(`creat_at`, INTERVAL 365 DAY)
                WHERE `expired_at` IS NULL
                """
            )
        )


def ensure_device_user_device_asignment_id_column(engine: Engine) -> None:
    """
    Add `device.user_device_asignment_id` when missing.

    Some existing DB volumes were created from older schema versions without this column,
    but the current app expects it (NOT NULL).
    """
    with engine.begin() as conn:
        r = conn.execute(
            text(
                """
                SELECT COUNT(*) FROM information_schema.COLUMNS
                WHERE TABLE_SCHEMA = DATABASE()
                  AND TABLE_NAME = 'device'
                  AND COLUMN_NAME = 'user_device_asignment_id'
                """
            )
        )
        if (r.scalar() or 0) == 0:
            conn.execute(
                text(
                    "ALTER TABLE `device` ADD COLUMN `user_device_asignment_id` INT NOT NULL DEFAULT 0"
                )
            )


def ensure_device_authorization_granted_by_varchar(engine: Engine) -> None:
    """
    Ensure `device_authorization.granted_by` is VARCHAR(45).

    Older DB volumes used DATE for granted_by. The UI now sends admin identifier (e.g. username),
    which requires a string column.
    """
    with engine.begin() as conn:
        r = conn.execute(
            text(
                """
                SELECT DATA_TYPE, CHARACTER_MAXIMUM_LENGTH
                FROM information_schema.COLUMNS
                WHERE TABLE_SCHEMA = DATABASE()
                  AND TABLE_NAME = 'device_authorization'
                  AND COLUMN_NAME = 'granted_by'
                """
            )
        )
        row = r.first()
        # If column missing, do nothing: init schema should create it.
        if row is None:
            return
        data_type = (row[0] or "").lower()
        max_len = row[1]
        if data_type != "varchar" or (max_len is not None and int(max_len) < 45):
            conn.execute(
                text("ALTER TABLE `device_authorization` MODIFY `granted_by` VARCHAR(45) NULL")
            )
