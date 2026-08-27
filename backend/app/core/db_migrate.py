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
        ("publish_topic", "ALTER TABLE `device` ADD COLUMN `publish_topic` VARCHAR(255) NULL"),
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


def ensure_device_publish_topic_column(engine: Engine) -> None:
    """Ensure persisted MQTT publish topic column exists on `device` for server->device send flow."""
    with engine.begin() as conn:
        r = conn.execute(
            text(
                """
                SELECT COUNT(*) FROM information_schema.COLUMNS
                WHERE TABLE_SCHEMA = DATABASE()
                  AND TABLE_NAME = 'device'
                  AND COLUMN_NAME = 'publish_topic'
                """
            )
        )
        if (r.scalar() or 0) == 0:
            conn.execute(text("ALTER TABLE `device` ADD COLUMN `publish_topic` VARCHAR(255) NULL"))
            logger.info("db_migrate: added device.publish_topic")
    logger.info("db_migrate: ensure_device_publish_topic_column OK")


def _column_exists(conn, table: str, column: str) -> bool:
    r = conn.execute(
        text(
            "SELECT COUNT(*) FROM information_schema.COLUMNS "
            "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = :t AND COLUMN_NAME = :c"
        ),
        {"t": table, "c": column},
    )
    return (r.scalar() or 0) > 0


def _index_exists(conn, table: str, index: str) -> bool:
    result = conn.execute(
        text(
            "SELECT COUNT(*) FROM information_schema.STATISTICS "
            "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = :t AND INDEX_NAME = :i"
        ),
        {"t": table, "i": index},
    )
    return (result.scalar() or 0) > 0


def ensure_anchor_mac_address_column(engine: Engine) -> None:
    """Add the canonical MAC column and safely backfill already-valid legacy IDs."""
    if engine.dialect.name != "mysql":
        return

    with engine.begin() as conn:
        if not _column_exists(conn, "anchor", "mac_address"):
            conn.execute(
                text(
                    "ALTER TABLE `anchor` ADD COLUMN `mac_address` VARCHAR(17) NULL "
                    "AFTER `hardware_id`, ALGORITHM=INSTANT"
                )
            )
        conn.execute(
            text(
                "UPDATE `anchor` SET `mac_address` = UPPER(TRIM(`hardware_id`)) "
                "WHERE `mac_address` IS NULL "
                "AND UPPER(TRIM(`hardware_id`)) "
                "REGEXP '^([0-9A-F]{2}:){5}[0-9A-F]{2}$'"
            )
        )
        if not _index_exists(conn, "anchor", "uq_anchor_mac_address"):
            conn.execute(
                text(
                    "ALTER TABLE `anchor` ADD UNIQUE INDEX "
                    "`uq_anchor_mac_address` (`mac_address`)"
                )
            )

    logger.info("db_migrate: ensure_anchor_mac_address_column OK")


def ensure_anchor_delta_delivery_columns(engine: Engine) -> None:
    """Add per-Gateway targeting/payload columns and backfill existing deliveries."""
    if engine.dialect.name != "mysql":
        return

    with engine.begin() as conn:
        if not _column_exists(conn, "anchor_config_outbox", "target_gateway_id"):
            conn.execute(
                text(
                    "ALTER TABLE `anchor_config_outbox` ADD COLUMN "
                    "`target_gateway_id` BIGINT NULL AFTER `location`"
                )
            )
        payload_added = not _column_exists(
            conn, "anchor_config_delivery", "payload"
        )
        if payload_added:
            conn.execute(
                text(
                    "ALTER TABLE `anchor_config_delivery` ADD COLUMN "
                    "`payload` JSON NULL AFTER `publish_topic`"
                )
            )
        conn.execute(
            text(
                "UPDATE `anchor_config_delivery` AS delivery "
                "JOIN `anchor_config_outbox` AS outbox "
                "ON outbox.`revision` = delivery.`revision` "
                "SET delivery.`payload` = outbox.`payload` "
                "WHERE delivery.`payload` IS NULL"
            )
        )
        nullable = conn.execute(
            text(
                "SELECT IS_NULLABLE FROM information_schema.COLUMNS "
                "WHERE TABLE_SCHEMA = DATABASE() "
                "AND TABLE_NAME = :t AND COLUMN_NAME = :c"
            ),
            {"t": "anchor_config_delivery", "c": "payload"},
        ).scalar()
        if payload_added or str(nullable or "").upper() == "YES":
            conn.execute(
                text(
                    "ALTER TABLE `anchor_config_delivery` "
                    "MODIFY COLUMN `payload` JSON NOT NULL"
                )
            )

    logger.info("db_migrate: ensure_anchor_delta_delivery_columns OK")


def ensure_anchor_phase0_columns(engine: Engine) -> None:
    """Add and normalize Phase 0 user/device columns on existing MySQL volumes.

    New Anchor tables are created by ``Base.metadata.create_all``. Existing tables do
    not receive new columns from ``create_all``, so this additive patch handles the two
    columns needed before later permission and gateway-liveness phases.
    """

    if engine.dialect.name != "mysql":
        return

    with engine.begin() as conn:
        permission_added = not _column_exists(conn, "user", "can_config_anchor")
        if permission_added:
            conn.execute(
                text(
                    "ALTER TABLE `user` ADD COLUMN `can_config_anchor` "
                    "ENUM('yes','no') NOT NULL DEFAULT 'no', ALGORITHM=INSTANT"
                )
            )

        conn.execute(
            text(
                "UPDATE `user` SET `can_config_anchor` = 'no' "
                "WHERE `can_config_anchor` IS NULL"
            )
        )
        if not permission_added:
            permission_contract = conn.execute(
                text(
                    "SELECT COLUMN_TYPE, IS_NULLABLE, COLUMN_DEFAULT "
                    "FROM information_schema.COLUMNS "
                    "WHERE TABLE_SCHEMA = DATABASE() "
                    "AND TABLE_NAME = 'user' AND COLUMN_NAME = 'can_config_anchor'"
                )
            ).first()
            expected_contract = ("enum('yes','no')", "NO", "no")
            actual_contract = (
                tuple(str(value) if value is not None else None for value in permission_contract)
                if permission_contract is not None
                else None
            )
            # Repair an earlier nullable or differently typed ERD draft only once.
            if actual_contract != expected_contract:
                conn.execute(
                    text(
                        "ALTER TABLE `user` MODIFY COLUMN `can_config_anchor` "
                        "ENUM('yes','no') NOT NULL DEFAULT 'no'"
                    )
                )

        if not _column_exists(conn, "device", "last_seen_at"):
            conn.execute(
                text(
                    "ALTER TABLE `device` ADD COLUMN `last_seen_at` "
                    "DATETIME(6) NULL, ALGORITHM=INSTANT"
                )
            )

    logger.info("db_migrate: ensure_anchor_phase0_columns OK")


def ensure_anchor_location_snapshot(engine: Engine) -> None:
    """Drop the legacy location FK so inactive Anchors survive map archival."""
    if engine.dialect.name != "mysql":
        return
    with engine.begin() as conn:
        constraint = conn.execute(
            text(
                "SELECT CONSTRAINT_NAME FROM information_schema.KEY_COLUMN_USAGE "
                "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'anchor' "
                "AND COLUMN_NAME = 'location_id' AND REFERENCED_TABLE_NAME = 'locations_using'"
            )
        ).scalar()
        if constraint:
            safe_name = str(constraint).replace("`", "")
            conn.execute(text(f"ALTER TABLE `anchor` DROP FOREIGN KEY `{safe_name}`"))
    logger.info("db_migrate: ensure_anchor_location_snapshot OK")


def ensure_user_cccd_varchar(engine: Engine) -> None:
    """
    Đổi `user.cccd` từ DECIMAL/Numeric sang VARCHAR(12).

    Lý do: CCCD lưu dạng số làm MẤT số 0 đứng đầu (CCCD VN thường bắt đầu bằng 0),
    khiến validate "phải đúng 12 chữ số" thất bại. Sau khi đổi sang chuỗi, backfill
    bằng cách pad '0' bên trái cho các bản ghi cũ bị thiếu số (do từng lưu dạng số).

    Idempotent: chỉ ALTER khi kiểu hiện tại chưa phải varchar.
    """
    with engine.begin() as conn:
        r = conn.execute(
            text(
                """
                SELECT DATA_TYPE, CHARACTER_MAXIMUM_LENGTH
                FROM information_schema.COLUMNS
                WHERE TABLE_SCHEMA = DATABASE()
                  AND TABLE_NAME = 'user'
                  AND COLUMN_NAME = 'cccd'
                """
            )
        )
        row = r.first()
        if row is None:
            # Cột chưa tồn tại: init schema sẽ tạo. Không làm gì.
            return
        data_type = (row[0] or "").lower()
        if data_type != "varchar":
            # Đổi kiểu sang VARCHAR(12). MySQL tự cast giá trị số hiện có sang chuỗi.
            conn.execute(text("ALTER TABLE `user` MODIFY COLUMN `cccd` VARCHAR(12) NOT NULL"))
        # Backfill: pad '0' bên trái cho bản ghi < 12 ký tự (đã mất số 0 khi còn là số).
        conn.execute(
            text(
                "UPDATE `user` SET `cccd` = LPAD(`cccd`, 12, '0') "
                "WHERE CHAR_LENGTH(`cccd`) < 12"
            )
        )


def ensure_schema_hardening(engine: Engine) -> None:
    """Áp các thay đổi Phase 3 cho volume DB cũ (đồng bộ với 009_schema_hardening.sql).

    - device.password -> VARCHAR(255); user.phone -> VARCHAR(20)
      (user.cccd -> VARCHAR(12) xử lý riêng ở ensure_user_cccd_varchar để giữ số 0 đầu)
    - status ENUM thêm 'inactive'
    - updated_at cho user/device/device_authorization
    - index device(user_device_asignment_id)
    - FK device_authorization -> ON DELETE/UPDATE CASCADE

    Idempotent: kiểm tra trước khi ALTER. Lỗi từng bước không làm sập app (chỉ log).
    """
    try:
        with engine.begin() as conn:
            # Kiểu cột (MODIFY idempotent — chạy lại an toàn).
            conn.execute(text("ALTER TABLE `device` MODIFY COLUMN `password` VARCHAR(255) NULL"))
            conn.execute(text("ALTER TABLE `user` MODIFY COLUMN `phone` VARCHAR(20) NULL"))
            conn.execute(text("ALTER TABLE `user` MODIFY COLUMN `status` ENUM('active','deactive','inactive') NOT NULL"))
            conn.execute(text("ALTER TABLE `device` MODIFY COLUMN `status` ENUM('active','deactive','inactive') NULL"))

            # updated_at
            for table in ("user", "device", "device_authorization"):
                if not _column_exists(conn, table, "updated_at"):
                    conn.execute(text(
                        f"ALTER TABLE `{table}` ADD COLUMN `updated_at` DATETIME NOT NULL "
                        "DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP"
                    ))

            # index device(user_device_asignment_id)
            r = conn.execute(text(
                "SELECT COUNT(*) FROM information_schema.STATISTICS "
                "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'device' "
                "AND INDEX_NAME = 'idx_device_user_assignment'"
            ))
            if (r.scalar() or 0) == 0:
                conn.execute(text(
                    "ALTER TABLE `device` ADD INDEX `idx_device_user_assignment` (`user_device_asignment_id`)"
                ))

            # FK cascade — drop + recreate nếu constraint cũ tồn tại với rule khác.
            for fk, col, ref_table, ref_col in (
                ("fk_device_has_user_device", "device_id", "device", "device_id"),
                ("fk_device_has_user_user1", "user_id", "user", "user_id"),
            ):
                rule = conn.execute(text(
                    "SELECT DELETE_RULE FROM information_schema.REFERENTIAL_CONSTRAINTS "
                    "WHERE CONSTRAINT_SCHEMA = DATABASE() AND CONSTRAINT_NAME = :n"
                ), {"n": fk}).scalar()
                if rule is not None and rule != "CASCADE":
                    conn.execute(text(f"ALTER TABLE `device_authorization` DROP FOREIGN KEY `{fk}`"))
                    conn.execute(text(
                        f"ALTER TABLE `device_authorization` ADD CONSTRAINT `{fk}` "
                        f"FOREIGN KEY (`{col}`) REFERENCES `{ref_table}` (`{ref_col}`) "
                        "ON DELETE CASCADE ON UPDATE CASCADE"
                    ))
        logger.info("db_migrate: ensure_schema_hardening OK")
    except Exception:
        logger.warning("db_migrate: ensure_schema_hardening gặp lỗi (bỏ qua, không sập app)", exc_info=True)


def ensure_map_image_constraints(engine: Engine) -> None:
    """Replace legacy 800px/5 MiB checks on existing MySQL volumes."""
    if engine.dialect.name != "mysql":
        return

    desired_constraints = {
        ("locations_using", "ck_locations_using_width"): "width >= 1",
        ("locations_using", "ck_locations_using_height"): "height >= 1",
        (
            "locations_using",
            "ck_locations_using_file_size",
        ): "file_size_bytes >= 1 AND file_size_bytes < 10485760",
        ("locations_deleted", "ck_locations_deleted_width"): "width >= 1",
        ("locations_deleted", "ck_locations_deleted_height"): "height >= 1",
        (
            "locations_deleted",
            "ck_locations_deleted_file_size",
        ): "file_size_bytes >= 1 AND file_size_bytes < 10485760",
    }

    def normalize(clause: str) -> str:
        return (
            str(clause or "")
            .lower()
            .replace("`", "")
            .replace("(", "")
            .replace(")", "")
            .replace(" ", "")
            .replace("\n", "")
            .replace("\t", "")
        )

    with engine.begin() as conn:
        for (table, constraint), desired_clause in desired_constraints.items():
            current_clause = conn.execute(
                text(
                    """
                    SELECT CHECK_CLAUSE
                    FROM information_schema.CHECK_CONSTRAINTS
                    WHERE CONSTRAINT_SCHEMA = DATABASE()
                      AND CONSTRAINT_NAME = :constraint
                    """
                ),
                {"constraint": constraint},
            ).scalar()
            if normalize(current_clause) == normalize(desired_clause):
                continue
            if current_clause is not None:
                conn.execute(
                    text(
                        f"ALTER TABLE `{table}` DROP CHECK `{constraint}`"
                    )
                )
            conn.execute(
                text(
                    f"ALTER TABLE `{table}` ADD CONSTRAINT `{constraint}` "
                    f"CHECK ({desired_clause})"
                )
            )
    logger.info("db_migrate: ensure_map_image_constraints OK")
