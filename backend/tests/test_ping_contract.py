from pathlib import Path

import pytest
from sqlalchemy import BigInteger, Integer, UniqueConstraint, create_engine
from sqlalchemy.dialects import mysql
from sqlalchemy.schema import CreateTable

from app.models.base import Base


BACKEND_DIR = Path(__file__).resolve().parents[1]
WORKSPACE_DIR = BACKEND_DIR.parents[1]
SQL_DIR = WORKSPACE_DIR / "database_service" / "sql"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _ping_models():
    try:
        from app.models import MissingPingPayload, PingPayload
    except ImportError:
        pytest.fail("PING-01 ORM models are not registered")
    return PingPayload, MissingPingPayload


def test_ping_models_register_exact_metadata() -> None:
    PingPayload, MissingPingPayload = _ping_models()

    assert set(PingPayload.__table__.columns.keys()) == {
        "id",
        "device_id",
        "cycle_id",
        "order",
        "node_timestamp_ms",
    }
    assert set(MissingPingPayload.__table__.columns.keys()) == {
        "id",
        "payload_id",
        "device_id",
        "cycle_id",
    }
    assert isinstance(PingPayload.__table__.c.id.type, BigInteger)
    assert isinstance(PingPayload.__table__.c.device_id.type, Integer)
    assert all(
        isinstance(PingPayload.__table__.c[column_name].type, BigInteger)
        for column_name in ("cycle_id", "order", "node_timestamp_ms")
    )
    assert isinstance(MissingPingPayload.__table__.c.id.type, BigInteger)
    assert isinstance(MissingPingPayload.__table__.c.device_id.type, Integer)
    assert all(
        isinstance(MissingPingPayload.__table__.c[column_name].type, BigInteger)
        for column_name in ("payload_id", "cycle_id")
    )
    assert {fk.target_fullname for fk in PingPayload.__table__.foreign_keys} == {
        "device.device_id"
    }
    assert {
        fk.target_fullname for fk in MissingPingPayload.__table__.foreign_keys
    } == {"device.device_id"}
    assert all(
        fk.ondelete == "CASCADE" and fk.onupdate == "CASCADE"
        for table in (PingPayload.__table__, MissingPingPayload.__table__)
        for fk in table.foreign_keys
    )
    assert {fk.name for fk in PingPayload.__table__.foreign_keys} == {
        "fk_ping_payload_device"
    }
    assert {fk.name for fk in MissingPingPayload.__table__.foreign_keys} == {
        "fk_missing_ping_payload_device"
    }
    assert {
        constraint.name
        for constraint in MissingPingPayload.__table__.constraints
        if isinstance(constraint, UniqueConstraint)
    } == {"uq_missing_ping_payload_device_cycle_payload"}


def test_ping_models_compile_mysql_constraints_and_indexes() -> None:
    PingPayload, MissingPingPayload = _ping_models()

    ping_ddl = str(CreateTable(PingPayload.__table__).compile(dialect=mysql.dialect()))
    missing_ddl = str(
        CreateTable(MissingPingPayload.__table__).compile(dialect=mysql.dialect())
    )

    assert "BIGINT NOT NULL AUTO_INCREMENT" in ping_ddl
    assert "CHECK (cycle_id >= 1)" in ping_ddl
    assert "CHECK (`order` >= 1 AND `order` <= 4294967295)" in ping_ddl
    assert "CHECK (node_timestamp_ms >= 0)" in ping_ddl
    assert "ON DELETE CASCADE ON UPDATE CASCADE" in ping_ddl
    assert "CHECK (payload_id >= 1 AND payload_id <= 4294967295)" in missing_ddl
    assert "UNIQUE (device_id, cycle_id, payload_id)" in missing_ddl

    assert {index.name for index in PingPayload.__table__.indexes} == {
        "idx_ping_payload_device_id_id",
        "idx_ping_payload_device_cycle_order",
    }
    assert {index.name for index in MissingPingPayload.__table__.indexes} == {
        "idx_missing_ping_payload_device_id_id",
    }


def test_ping_metadata_creates_on_sqlite() -> None:
    _ping_models()
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)

    with engine.connect() as connection:
        table_names = set(engine.dialect.get_table_names(connection))

    assert {"ping_payload", "missing_ping_payload"}.issubset(table_names)


def test_clean_install_schema_declares_ping_tables() -> None:
    schema_sql = _read(SQL_DIR / "schema.sql")

    for table_name in ("ping_payload", "missing_ping_payload"):
        assert f"CREATE TABLE IF NOT EXISTS `demo_iot`.`{table_name}`" in schema_sql

    required_tokens = (
        "`node_timestamp_ms` BIGINT NOT NULL",
        "CONSTRAINT `fk_ping_payload_device`",
        "CONSTRAINT `fk_missing_ping_payload_device`",
        "UNIQUE INDEX `uq_missing_ping_payload_device_cycle_payload`",
        "INDEX `idx_ping_payload_device_id_id`",
        "INDEX `idx_ping_payload_device_cycle_order`",
        "INDEX `idx_missing_ping_payload_device_id_id`",
    )
    for token in required_tokens:
        assert token in schema_sql


def test_ping_migration_is_additive_idempotent_and_matches_clean_schema() -> None:
    migration_path = SQL_DIR / "015_ping_payload_tracking.sql"
    rollback_path = SQL_DIR / "015_ping_payload_tracking.rollback.sql"

    assert migration_path.is_file()
    assert rollback_path.is_file()

    migration_sql = _read(migration_path)
    clean_schema_sql = _read(SQL_DIR / "schema.sql")
    for table_name in ("ping_payload", "missing_ping_payload"):
        assert f"CREATE TABLE IF NOT EXISTS `{table_name}`" in migration_sql
        assert f"CREATE TABLE IF NOT EXISTS `demo_iot`.`{table_name}`" in clean_schema_sql
    assert "DROP TABLE" not in migration_sql

    for column in (
        "id",
        "device_id",
        "cycle_id",
        "order",
        "node_timestamp_ms",
        "payload_id",
    ):
        assert f"`{column}`" in migration_sql
        assert f"`{column}`" in clean_schema_sql


def test_ping_rollback_drops_only_new_tables_child_first() -> None:
    rollback_sql = _read(SQL_DIR / "015_ping_payload_tracking.rollback.sql")
    statements = [
        line.strip()
        for line in rollback_sql.splitlines()
        if line.strip().upper().startswith("DROP TABLE")
    ]

    assert statements == [
        "DROP TABLE IF EXISTS `missing_ping_payload`;",
        "DROP TABLE IF EXISTS `ping_payload`;",
    ]
