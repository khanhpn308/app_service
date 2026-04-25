"""
Migration nhẹ cho volume MySQL đã tồn tại (script init chỉ chạy một lần khi tạo volume).

Mỗi hàm ``ensure_*`` kiểm tra ``information_schema`` rồi ``ALTER``/``UPDATE`` nếu thiếu hoặc sai kiểu.
Gọi từ ``main.lifespan`` sau ``create_all`` — không dùng Alembic full để giữ deploy đơn giản.

Lightweight schema patches for existing DB volumes (initdb scripts only run once).
"""

import logging

from sqlalchemy import text
from sqlalchemy.engine import Engine

logger = logging.getLogger(__name__)


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


def ensure_device_drop_last_reading_columns(engine: Engine) -> None:
    """Remove dynamic telemetry columns if present (live data comes from MQTT/payload, not DB)."""
    to_drop = ("last_reading_unit", "last_reading_value", "last_reading_at")
    with engine.begin() as conn:
        for col_name in to_drop:
            r = conn.execute(
                text(
                    f"""
                    SELECT COUNT(*) FROM information_schema.COLUMNS
                    WHERE TABLE_SCHEMA = DATABASE()
                      AND TABLE_NAME = 'device'
                      AND COLUMN_NAME = '{col_name}'
                    """
                )
            )
            if (r.scalar() or 0) > 0:
                conn.execute(text(f"ALTER TABLE `device` DROP COLUMN `{col_name}`"))
                logger.info("db_migrate: dropped device.%s", col_name)
    logger.info("db_migrate: ensure_device_drop_last_reading_columns OK")


def ensure_device_ui_columns(engine: Engine) -> None:
    """Add static UI columns on device (location, device_type)."""
    alters = [
        ("location", "ALTER TABLE `device` ADD COLUMN `location` VARCHAR(255) NULL"),
        ("device_type", "ALTER TABLE `device` ADD COLUMN `device_type` VARCHAR(45) NULL"),
        ("topic", "ALTER TABLE `device` ADD COLUMN `topic` VARCHAR(255) NULL"),
    ]
    with engine.begin() as conn:
        for col_name, ddl in alters:
            # Literal column name from fixed list only (avoids driver quirks with :named binds in some setups).
            r = conn.execute(
                text(
                    f"""
                    SELECT COUNT(*) FROM information_schema.COLUMNS
                    WHERE TABLE_SCHEMA = DATABASE()
                      AND TABLE_NAME = 'device'
                      AND COLUMN_NAME = '{col_name}'
                    """
                )
            )
            if (r.scalar() or 0) == 0:
                conn.execute(text(ddl))
                logger.info("db_migrate: added device.%s", col_name)
            else:
                logger.debug("db_migrate: device.%s already present", col_name)
    logger.info("db_migrate: ensure_device_ui_columns OK")


def ensure_device_topic_column(engine: Engine) -> None:
    """Ensure persisted MQTT topic column exists on `device` for auto-subscribe flow."""
    with engine.begin() as conn:
        r = conn.execute(
            text(
                """
                SELECT COUNT(*) FROM information_schema.COLUMNS
                WHERE TABLE_SCHEMA = DATABASE()
                  AND TABLE_NAME = 'device'
                  AND COLUMN_NAME = 'topic'
                """
            )
        )
        if (r.scalar() or 0) == 0:
            conn.execute(text("ALTER TABLE `device` ADD COLUMN `topic` VARCHAR(255) NULL"))
            logger.info("db_migrate: added device.topic")
    logger.info("db_migrate: ensure_device_topic_column OK")


def ensure_test_logs_table(engine: Engine) -> None:
    """Create `test_logs` table if missing for latency test feature."""
    with engine.begin() as conn:
        conn.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS `test_logs` (
                  `id` BIGINT NOT NULL AUTO_INCREMENT,
                  `protocol` VARCHAR(32) NOT NULL,
                  `version` INT NULL,
                                    `message_len` INT NULL,
                  `message` TEXT NULL,
                                    `node_id_len` INT NULL,
                  `node_id` VARCHAR(128) NOT NULL,
                  `device_name` VARCHAR(128) NULL,
                                    `gateway_id_len` INT NULL,
                  `gateway_id` VARCHAR(128) NOT NULL,
                  `event_timestamp_ms` BIGINT NULL,
                  `gateway_timestamp_ms` BIGINT NULL,
                  `mark_time_ms` BIGINT NOT NULL,
                  `delay_gateway_to_server_ms` BIGINT NULL,
                  `rssi` INT NULL,
                  `src_mac` VARCHAR(17) NULL,
                  `topic` VARCHAR(255) NULL,
                  `raw_hex` TEXT NULL,
                  `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                  PRIMARY KEY (`id`),
                  INDEX `idx_test_logs_lookup` (`gateway_id`, `node_id`, `protocol`, `created_at`)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
                """
            )
        )
        for col_name, ddl in (
            ("message_len", "ALTER TABLE `test_logs` ADD COLUMN `message_len` INT NULL AFTER `version`"),
            ("node_id_len", "ALTER TABLE `test_logs` ADD COLUMN `node_id_len` INT NULL AFTER `message`"),
            ("device_name", "ALTER TABLE `test_logs` ADD COLUMN `device_name` VARCHAR(128) NULL AFTER `node_id`"),
            ("gateway_id_len", "ALTER TABLE `test_logs` ADD COLUMN `gateway_id_len` INT NULL AFTER `device_name`"),
        ):
            r = conn.execute(
                text(
                    f"""
                    SELECT COUNT(*) FROM information_schema.COLUMNS
                    WHERE TABLE_SCHEMA = DATABASE()
                      AND TABLE_NAME = 'test_logs'
                      AND COLUMN_NAME = '{col_name}'
                    """
                )
            )
            if (r.scalar() or 0) == 0:
                conn.execute(text(ddl))

        for col_name in ("delay_node_to_gateway_ms", "delay_node_to_server_ms"):
            r = conn.execute(
                text(
                    f"""
                    SELECT COUNT(*) FROM information_schema.COLUMNS
                    WHERE TABLE_SCHEMA = DATABASE()
                      AND TABLE_NAME = 'test_logs'
                      AND COLUMN_NAME = '{col_name}'
                    """
                )
            )
            if (r.scalar() or 0) > 0:
                conn.execute(text(f"ALTER TABLE `test_logs` DROP COLUMN `{col_name}`"))
    logger.info("db_migrate: ensure_test_logs_table OK")
