from contextlib import contextmanager
from types import SimpleNamespace

import pytest


class _ScalarResult:
    def __init__(self, value):
        self.value = value

    def scalar(self) -> int:
        return self.value

    def first(self):
        return self.value


class _FakeConnection:
    def __init__(
        self,
        existing_columns: set[tuple[str, str]],
        existing_indexes: set[tuple[str, str]] | None = None,
        permission_contract=("enum('yes','no')", "NO", "no"),
    ):
        self.existing_columns = existing_columns
        self.existing_indexes = existing_indexes or set()
        self.permission_contract = permission_contract
        self.statements: list[str] = []

    def execute(self, statement, params=None):
        sql = str(statement)
        self.statements.append(" ".join(sql.split()))
        if "COLUMN_TYPE, IS_NULLABLE, COLUMN_DEFAULT" in sql:
            return _ScalarResult(self.permission_contract)
        if "information_schema.STATISTICS" in sql:
            key = (str(params["t"]), str(params["i"]))
            return _ScalarResult(1 if key in self.existing_indexes else 0)
        if "information_schema.COLUMNS" in sql:
            key = (str(params["t"]), str(params["c"]))
            return _ScalarResult(1 if key in self.existing_columns else 0)
        return _ScalarResult(0)


class _FakeEngine:
    def __init__(
        self,
        existing_columns: set[tuple[str, str]],
        dialect_name: str = "mysql",
        existing_indexes: set[tuple[str, str]] | None = None,
        permission_contract=("enum('yes','no')", "NO", "no"),
    ):
        self.dialect = SimpleNamespace(name=dialect_name)
        self.connection = _FakeConnection(
            existing_columns, existing_indexes, permission_contract
        )

    @contextmanager
    def begin(self):
        yield self.connection


def _migration_function():
    try:
        from app.core.db_migrate import ensure_anchor_phase0_columns
    except ImportError:
        pytest.fail("ensure_anchor_phase0_columns is not implemented")
    return ensure_anchor_phase0_columns


def test_existing_volume_patch_adds_missing_columns_and_backfills_users() -> None:
    engine = _FakeEngine(set())

    _migration_function()(engine)

    executed = "\n".join(engine.connection.statements)
    assert "ADD COLUMN `can_config_anchor`" in executed
    assert "ADD COLUMN `last_seen_at`" in executed
    assert "SET `can_config_anchor` = 'no'" in executed
    assert "MODIFY COLUMN `can_config_anchor`" not in executed


def test_existing_volume_patch_is_idempotent_when_columns_exist() -> None:
    engine = _FakeEngine(
        {("user", "can_config_anchor"), ("device", "last_seen_at")}
    )

    _migration_function()(engine)

    executed = "\n".join(engine.connection.statements)
    assert "ADD COLUMN `can_config_anchor`" not in executed
    assert "ADD COLUMN `last_seen_at`" not in executed
    assert "SET `can_config_anchor` = 'no'" in executed
    assert "MODIFY COLUMN `can_config_anchor`" not in executed


def test_existing_volume_patch_repairs_nullable_permission_draft() -> None:
    engine = _FakeEngine(
        {("user", "can_config_anchor"), ("device", "last_seen_at")},
        permission_contract=("enum('yes','no')", "YES", None),
    )

    _migration_function()(engine)

    executed = "\n".join(engine.connection.statements)
    assert "SET `can_config_anchor` = 'no'" in executed
    assert "MODIFY COLUMN `can_config_anchor`" in executed


def test_existing_volume_patch_is_noop_outside_mysql() -> None:
    engine = _FakeEngine(set(), dialect_name="sqlite")

    _migration_function()(engine)

    assert engine.connection.statements == []


def _mac_migration_function():
    try:
        from app.core.db_migrate import ensure_anchor_mac_address_column
    except ImportError:
        pytest.fail("ensure_anchor_mac_address_column is not implemented")
    return ensure_anchor_mac_address_column


def test_existing_anchor_volume_adds_and_backfills_mac_address() -> None:
    engine = _FakeEngine({("anchor", "hardware_id")})

    _mac_migration_function()(engine)

    executed = "\n".join(engine.connection.statements)
    assert "ADD COLUMN `mac_address` VARCHAR(17) NULL" in executed
    assert "REGEXP" in executed
    assert "ADD UNIQUE INDEX `uq_anchor_mac_address`" in executed
    assert "DROP COLUMN `hardware_id`" not in executed


def test_existing_anchor_mac_patch_is_idempotent() -> None:
    engine = _FakeEngine(
        {("anchor", "hardware_id"), ("anchor", "mac_address")},
        existing_indexes={("anchor", "uq_anchor_mac_address")},
    )

    _mac_migration_function()(engine)

    executed = "\n".join(engine.connection.statements)
    assert "ADD COLUMN `mac_address`" not in executed
    assert "ADD UNIQUE INDEX `uq_anchor_mac_address`" not in executed
    assert "REGEXP" in executed


def _delta_delivery_migration_function():
    try:
        from app.core.db_migrate import ensure_anchor_delta_delivery_columns
    except ImportError:
        pytest.fail("ensure_anchor_delta_delivery_columns is not implemented")
    return ensure_anchor_delta_delivery_columns


def test_existing_anchor_delivery_volume_adds_target_and_payload_columns() -> None:
    engine = _FakeEngine(set())

    _delta_delivery_migration_function()(engine)

    executed = "\n".join(engine.connection.statements)
    assert "anchor_config_outbox` ADD COLUMN `target_gateway_id` BIGINT NULL" in executed
    assert "anchor_config_delivery` ADD COLUMN `payload` JSON NULL" in executed
    assert "UPDATE `anchor_config_delivery` AS delivery" in executed
    assert "JOIN `anchor_config_outbox` AS outbox" in executed


def test_existing_anchor_delivery_patch_is_idempotent() -> None:
    engine = _FakeEngine(
        {
            ("anchor_config_outbox", "target_gateway_id"),
            ("anchor_config_delivery", "payload"),
        }
    )

    _delta_delivery_migration_function()(engine)

    executed = "\n".join(engine.connection.statements)
    assert "ADD COLUMN `target_gateway_id`" not in executed
    assert "ADD COLUMN `payload`" not in executed
    assert "UPDATE `anchor_config_delivery` AS delivery" in executed
