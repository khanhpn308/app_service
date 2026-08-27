from sqlalchemy import create_engine
from sqlalchemy.schema import CreateTable
import pytest

from app.core.config import Settings
from app.models.base import Base


def _anchor_models():
    try:
        from app.models import Anchor, AnchorConfigDelivery, AnchorConfigOutbox
    except ImportError:
        pytest.fail("Phase 0 Anchor ORM models are not registered")
    return Anchor, AnchorConfigDelivery, AnchorConfigOutbox


def test_anchor_models_register_complete_metadata() -> None:
    _anchor_models()
    expected_columns = {
        "anchor": {
            "anchor_id",
            "hardware_id",
            "mac_address",
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
        },
        "anchor_config_outbox": {
            "revision",
            "location_id",
            "location",
            "target_gateway_id",
            "payload",
            "reason",
            "status",
            "created_by_user_id",
            "created_at",
            "completed_at",
            "superseded_at",
        },
        "anchor_config_delivery": {
            "delivery_id",
            "revision",
            "gateway_id",
            "publish_topic",
            "payload",
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
        },
    }

    for table_name, columns in expected_columns.items():
        assert table_name in Base.metadata.tables
        assert set(Base.metadata.tables[table_name].columns.keys()) == columns


def test_anchor_snapshot_ids_preserve_lifecycle_and_delivery_audit() -> None:
    Anchor, AnchorConfigDelivery, AnchorConfigOutbox = _anchor_models()
    anchor_fks = {fk.target_fullname for fk in Anchor.__table__.foreign_keys}
    outbox_fks = {fk.target_fullname for fk in AnchorConfigOutbox.__table__.foreign_keys}
    delivery_fks = {
        fk.target_fullname for fk in AnchorConfigDelivery.__table__.foreign_keys
    }

    assert "locations_using.location_id" not in anchor_fks
    assert "user.user_id" in anchor_fks
    assert "locations_using.location_id" not in outbox_fks
    assert "device.device_id" not in delivery_fks
    assert delivery_fks == {"anchor_config_outbox.revision"}


def test_anchor_mysql_ddl_has_native_types_constraints_and_indexes() -> None:
    Anchor, AnchorConfigDelivery, AnchorConfigOutbox = _anchor_models()
    from sqlalchemy.dialects import mysql

    anchor_ddl = str(CreateTable(Anchor.__table__).compile(dialect=mysql.dialect()))
    outbox_ddl = str(
        CreateTable(AnchorConfigOutbox.__table__).compile(dialect=mysql.dialect())
    )
    delivery_ddl = str(
        CreateTable(AnchorConfigDelivery.__table__).compile(dialect=mysql.dialect())
    )

    assert "DECIMAL(7,4)" in anchor_ddl.replace(" ", "")
    assert "DATETIME(6)" in anchor_ddl
    assert "CHECK (x >= 0 AND x <= 100)" in anchor_ddl
    assert "ENUM('active','inactive')" in anchor_ddl.replace(" ", "")
    assert "JSON NOT NULL" in outbox_ddl
    assert "JSON NOT NULL" in delivery_ddl


def test_anchor_metadata_creates_on_sqlite() -> None:
    _anchor_models()
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)

    assert set(Base.metadata.tables).issubset(
        set(engine.dialect.get_table_names(engine.connect()))
    )


def test_phase0_settings_have_safe_defaults() -> None:
    settings = Settings(_env_file=None)

    assert settings.gateway_offline_after_seconds == 30
    assert settings.gateway_presence_flush_seconds == 5
    assert settings.anchor_dispatcher_enabled is True
    assert settings.anchor_dispatcher_poll_seconds == 1.0
    assert settings.anchor_dispatcher_lease_seconds == 30
    assert settings.anchor_publish_timeout_seconds == 10
    assert settings.anchor_retry_schedule_seconds == "5,15,30,60,300"
    assert settings.anchor_retry_steady_seconds == 300
