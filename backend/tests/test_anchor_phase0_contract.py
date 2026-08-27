from pathlib import Path


BACKEND_DIR = Path(__file__).resolve().parents[1]
WORKSPACE_DIR = BACKEND_DIR.parents[1]
SQL_DIR = WORKSPACE_DIR / "database_service" / "sql"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_clean_install_schema_declares_anchor_phase0_contract() -> None:
    schema_sql = _read(SQL_DIR / "schema.sql")

    assert "`can_config_anchor` ENUM('yes', 'no') NOT NULL DEFAULT 'no'" in schema_sql
    assert "`last_seen_at` DATETIME(6) NULL" in schema_sql
    for table_name in (
        "anchor",
        "anchor_config_outbox",
        "anchor_config_delivery",
    ):
        assert f"CREATE TABLE IF NOT EXISTS `demo_iot`.`{table_name}`" in schema_sql

    assert "anchor_group_member" not in schema_sql
    assert "`mac_address` VARCHAR(17) NULL" in schema_sql
    assert "UNIQUE INDEX `uq_anchor_mac_address` (`mac_address` ASC)" in schema_sql
    assert "UNIQUE INDEX `uq_anchor_hardware_id` (`hardware_id` ASC)" in schema_sql
    assert "UNIQUE INDEX `uq_anchor_location_name_key` (`location_id` ASC, `name_key` ASC)" in schema_sql
    assert "UNIQUE INDEX `uq_anchor_delivery_revision_gateway` (`revision` ASC, `gateway_id` ASC)" in schema_sql
    assert "CHECK (`x` >= 0 AND `x` <= 100)" in schema_sql
    assert "CHECK (`y` >= 0 AND `y` <= 100)" in schema_sql


def test_existing_volume_migration_is_guarded_and_non_destructive() -> None:
    migration_path = SQL_DIR / "011_anchor_configuration.sql"
    assert migration_path.is_file()
    migration_sql = _read(migration_path)

    assert "information_schema.COLUMNS" in migration_sql
    assert "CREATE TABLE IF NOT EXISTS `anchor`" in migration_sql
    assert "CREATE TABLE IF NOT EXISTS `anchor_config_outbox`" in migration_sql
    assert "CREATE TABLE IF NOT EXISTS `anchor_config_delivery`" in migration_sql
    assert "DROP TABLE `anchor`" not in migration_sql
    assert "DROP TABLE `anchor_group_member`" not in migration_sql
    assert "DEFAULT 'no'" in migration_sql


def test_mac_address_migration_is_additive_idempotent_and_preserves_legacy_id() -> None:
    migration_path = SQL_DIR / "013_anchor_mac_address.sql"
    assert migration_path.is_file()
    migration_sql = _read(migration_path)

    assert "information_schema.COLUMNS" in migration_sql
    assert "ADD COLUMN `mac_address` VARCHAR(17) NULL" in migration_sql
    assert "uq_anchor_mac_address" in migration_sql
    assert "REGEXP" in migration_sql
    assert "DROP COLUMN `hardware_id`" not in migration_sql
    assert "DROP TABLE" not in migration_sql


def test_anchor_migration_and_schema_use_matching_table_columns() -> None:
    schema_sql = _read(SQL_DIR / "schema.sql")
    migration_sql = _read(SQL_DIR / "011_anchor_configuration.sql")
    expected_columns = {
        "anchor": (
            "anchor_id",
            "hardware_id",
            "name",
            "name_key",
            "x",
            "y",
            "z",
            "location_id",
            "status",
            "created_by_user_id",
            "updated_by_user_id",
            "deleted_by_user_id",
            "created_at",
            "updated_at",
            "deleted_at",
        ),
        "anchor_config_outbox": (
            "revision",
            "location_id",
            "location",
            "payload",
            "reason",
            "status",
            "created_by_user_id",
            "created_at",
            "completed_at",
            "superseded_at",
        ),
        "anchor_config_delivery": (
            "delivery_id",
            "revision",
            "gateway_id",
            "publish_topic",
            "status",
            "attempt_count",
            "next_attempt_at",
            "lease_until",
            "leased_by",
            "published_at",
            "acked_at",
            "last_error",
            "created_at",
            "updated_at",
        ),
    }

    for columns in expected_columns.values():
        for column in columns:
            token = f"`{column}`"
            assert token in schema_sql
            assert token in migration_sql
