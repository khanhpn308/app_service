from sqlalchemy import CheckConstraint, UniqueConstraint
from sqlalchemy.dialects import mysql
from sqlalchemy.schema import CreateTable

from app.models import Base


EXPECTED_COLUMNS = {
    "map_group": {
        "group_id",
        "name",
        "owner_user_id",
        "created_by_user_id",
        "created_at",
        "updated_at",
    },
    "map_group_membership": {
        "group_id",
        "user_id",
        "status",
        "invited_by_user_id",
        "invited_at",
        "responded_at",
    },
    "locations_using": {
        "location_id",
        "location",
        "image_data",
        "mime_type",
        "original_filename",
        "checksum_sha256",
        "file_size_bytes",
        "width",
        "height",
        "group_id",
        "owner_user_id",
        "created_by_user_id",
        "created_at",
    },
    "locations_deleted": {
        "location_id",
        "location",
        "image_data",
        "mime_type",
        "original_filename",
        "checksum_sha256",
        "file_size_bytes",
        "width",
        "height",
        "group_id_snapshot",
        "group_name_snapshot",
        "owner_user_id_snapshot",
        "owner_username_snapshot",
        "created_by_user_id_snapshot",
        "created_by_username_snapshot",
        "created_at",
        "deleted_by_user_id_snapshot",
        "deleted_by_username_snapshot",
        "deleted_at",
        "delete_reason",
    },
}


def test_map_tables_register_the_required_columns() -> None:
    assert EXPECTED_COLUMNS.keys() <= Base.metadata.tables.keys()

    for table_name, expected_columns in EXPECTED_COLUMNS.items():
        assert set(Base.metadata.tables[table_name].columns.keys()) == expected_columns


def test_group_name_is_unique_per_owner_and_membership_status_is_constrained() -> None:
    group_table = Base.metadata.tables["map_group"]
    membership_table = Base.metadata.tables["map_group_membership"]

    unique_columns = {
        tuple(constraint.columns.keys())
        for constraint in group_table.constraints
        if isinstance(constraint, UniqueConstraint)
    }
    membership_checks = {
        str(constraint.sqltext)
        for constraint in membership_table.constraints
        if isinstance(constraint, CheckConstraint)
    }

    assert ("owner_user_id", "name") in unique_columns
    assert "status IN ('pending', 'accepted', 'rejected')" in membership_checks


def test_active_locations_use_mediumblob_and_enforce_image_invariants() -> None:
    table = Base.metadata.tables["locations_using"]
    mysql_ddl = str(CreateTable(table).compile(dialect=mysql.dialect()))
    unique_columns = {
        tuple(constraint.columns.keys())
        for constraint in table.constraints
        if isinstance(constraint, UniqueConstraint)
    }
    check_sql = {
        str(constraint.sqltext)
        for constraint in table.constraints
        if isinstance(constraint, CheckConstraint)
    }

    assert "MEDIUMBLOB" in mysql_ddl
    assert ("location",) in unique_columns
    assert "width >= 1" in check_sql
    assert "height >= 1" in check_sql
    assert "file_size_bytes >= 1 AND file_size_bytes < 10485760" in check_sql


def test_deleted_locations_are_an_fk_free_archive_without_status_column() -> None:
    table = Base.metadata.tables["locations_deleted"]
    mysql_ddl = str(CreateTable(table).compile(dialect=mysql.dialect()))
    check_sql = {
        str(constraint.sqltext)
        for constraint in table.constraints
        if isinstance(constraint, CheckConstraint)
    }

    assert "MEDIUMBLOB" in mysql_ddl
    assert "status" not in table.columns
    assert not table.foreign_keys
    assert "width >= 1" in check_sql
    assert "height >= 1" in check_sql
    assert "file_size_bytes >= 1 AND file_size_bytes < 10485760" in check_sql
