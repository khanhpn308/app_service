from pathlib import Path


BACKEND_DIR = Path(__file__).resolve().parents[1]
WORKSPACE_DIR = BACKEND_DIR.parents[1]


def test_runtime_and_test_dependencies_are_pinned() -> None:
    dev_requirements_path = BACKEND_DIR / "requirements-dev.txt"
    assert dev_requirements_path.is_file()

    runtime_requirements = (BACKEND_DIR / "requirements.txt").read_text(
        encoding="utf-8"
    )
    dev_requirements = dev_requirements_path.read_text(encoding="utf-8")

    assert "Pillow==12.3.0" in runtime_requirements
    assert "python-multipart==0.0.32" in runtime_requirements
    assert "-r requirements.txt" in dev_requirements
    assert "pytest==9.1.1" in dev_requirements


def test_mysql_schema_declares_all_map_tables_and_mediumblobs() -> None:
    schema_sql = (
        WORKSPACE_DIR / "database_service" / "sql" / "schema.sql"
    ).read_text(encoding="utf-8")

    for table_name in (
        "map_group",
        "map_group_membership",
        "locations_using",
        "locations_deleted",
    ):
        assert f"CREATE TABLE IF NOT EXISTS `demo_iot`.`{table_name}`" in schema_sql

    assert schema_sql.count("MEDIUMBLOB") >= 2
    assert "UNIQUE INDEX `uq_locations_using_location` (`location` ASC)" in schema_sql
