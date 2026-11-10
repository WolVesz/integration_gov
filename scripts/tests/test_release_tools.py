import pytest
from fastapi.responses import JSONResponse
from sqlalchemy import Column, Integer, MetaData, Table, create_engine

from scripts.db_checks import schema_problems, target_identity, validate_target
from scripts.package_release import release_files


def test_target_mismatch_is_rejected(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}")
    with engine.connect() as conn:
        identity = target_identity(conn)
        assert identity == {"database": str(tmp_path / "test.db"), "schema": "main"}
        with pytest.raises(RuntimeError, match="target mismatch"):
            validate_target(conn, "other-database", "main")
        with pytest.raises(RuntimeError, match="Production requires"):
            validate_target(conn, identity["database"], "main", production=True)


def test_schema_check_is_read_only():
    engine = create_engine("sqlite://")
    metadata = MetaData()
    Table("example", metadata, Column("id", Integer, primary_key=True))
    with engine.connect() as conn:
        assert schema_problems(conn, metadata, ["example"]) == ["Missing table: example"]
        assert schema_problems(conn, metadata, ["example"]) == ["Missing table: example"]


def test_bundle_requires_frontend_and_excludes_local_data(tmp_path):
    with pytest.raises(RuntimeError, match="Build frontend"):
        release_files(tmp_path)
    for name in [
        "frontend/dist/index.html",
        "backend/main.py",
        "app.yaml",
        "requirements.txt",
        "constraints.txt",
        "pyproject.toml",
        "uv.lock",
        "requirements-dev.txt",
        "README.md",
        "LICENSE",
        ".env",
        "backend/private.db",
    ]:
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("test")
    files = {str(p.relative_to(tmp_path)) for p in release_files(tmp_path)}
    assert "frontend/dist/index.html" in files
    assert "requirements.txt" in files
    assert "LICENSE" in files
    assert not {"constraints.txt", "requirements-dev.txt", "pyproject.toml", "uv.lock"} & files
    assert ".env" not in files
    assert "backend/private.db" not in files


def test_bundle_rejects_symlinks(tmp_path):
    (tmp_path / "frontend/dist").mkdir(parents=True)
    (tmp_path / "frontend/dist/index.html").symlink_to("/etc/hosts")
    with pytest.raises(RuntimeError, match="Refusing symlink"):
        release_files(tmp_path)


def test_readiness_fails_closed_and_checks_frontend(monkeypatch, tmp_path):
    from types import SimpleNamespace

    from backend.models import Base
    from backend.routers import readiness

    engine = create_engine("sqlite://")
    monkeypatch.setattr(readiness, "engine", engine)
    monkeypatch.setattr(readiness, "get_settings", lambda: SimpleNamespace(dev_mode=True))
    response = readiness.readyz()
    assert isinstance(response, JSONResponse)
    assert response.status_code == 503
    Base.metadata.create_all(engine)
    assert readiness.readyz() == {"status": "ok"}
    monkeypatch.setattr(readiness, "get_settings", lambda: SimpleNamespace(dev_mode=False))
    monkeypatch.setattr(readiness, "_DIST", tmp_path)
    response = readiness.readyz()
    assert isinstance(response, JSONResponse)
    assert response.status_code == 503
    (tmp_path / "index.html").write_text("built")
    assert readiness.readyz() == {"status": "ok"}


def test_migration_is_additive_and_idempotent(tmp_path, monkeypatch):
    import sys

    from sqlalchemy import inspect, text

    from backend import database
    from backend.models import Base
    from scripts import migrate_framework
    from scripts.db_checks import FRAMEWORK_TABLES

    path = tmp_path / "upgrade.db"
    engine = create_engine(f"sqlite:///{path}")
    monkeypatch.setattr(database, "engine", engine)
    Base.metadata.create_all(
        engine, tables=[t for n, t in Base.metadata.tables.items() if n not in FRAMEWORK_TABLES]
    )
    with engine.begin() as conn:
        conn.execute(text("CREATE TABLE preserved_marker (value TEXT)"))
        conn.execute(text("INSERT INTO preserved_marker VALUES ('retain')"))
    args = ["migrate", "--expected-database", str(path), "--expected-schema", "main"]
    monkeypatch.setattr(sys, "argv", args)
    migrate_framework.main()
    assert not set(FRAMEWORK_TABLES) & set(inspect(engine).get_table_names())
    monkeypatch.setattr(sys, "argv", args + ["--apply"])
    migrate_framework.main()
    migrate_framework.main()
    assert set(FRAMEWORK_TABLES) <= set(inspect(engine).get_table_names())
    with engine.connect() as conn:
        assert conn.execute(text("SELECT value FROM preserved_marker")).scalar() == "retain"


def test_bootstrap_requires_empty_database_and_never_seeds(tmp_path, monkeypatch):
    import sys

    from sqlalchemy import inspect, text

    from backend import database
    from backend.models import Base
    from scripts import bootstrap_database

    path = tmp_path / "new.db"
    engine = create_engine(f"sqlite:///{path}")
    monkeypatch.setattr(database, "engine", engine)
    args = ["bootstrap", "--expected-database", str(path), "--expected-schema", "main"]
    monkeypatch.setattr(sys, "argv", args)
    bootstrap_database.main()
    assert inspect(engine).get_table_names() == []
    monkeypatch.setattr(sys, "argv", args + ["--apply"])
    bootstrap_database.main()
    assert set(inspect(engine).get_table_names()) == set(Base.metadata.tables)
    with engine.connect() as conn:
        assert conn.execute(text("SELECT COUNT(*) FROM integrations")).scalar() == 0
    with pytest.raises(RuntimeError, match="empty schema"):
        bootstrap_database.main()


def test_postgres_target_restricts_search_path_with_quoted_identifier():
    from unittest.mock import MagicMock

    from sqlalchemy.dialects.postgresql import dialect

    connection = MagicMock()
    connection.dialect = dialect()
    connection.execute.return_value.one.return_value = ("catalog", 'approved"schema')
    assert validate_target(connection, "catalog", 'approved"schema') == {
        "database": "catalog",
        "schema": 'approved"schema',
    }
    connection.exec_driver_sql.assert_called_once_with(
        'SET LOCAL search_path TO "approved""schema"'
    )


def test_inspection_never_uses_search_path_fallback(monkeypatch):
    from unittest.mock import MagicMock

    from scripts import db_checks

    inspector = MagicMock()
    inspector.has_table.return_value = True
    inspector.get_columns.return_value = [{"name": "id"}]
    monkeypatch.setattr(db_checks, "inspect", lambda connection: inspector)
    monkeypatch.setattr(
        db_checks,
        "target_identity",
        lambda connection: {"database": "catalog", "schema": "approved"},
    )
    metadata = MetaData()
    Table("example", metadata, Column("id", Integer))
    assert schema_problems(MagicMock(), metadata, ["example"]) == []
    inspector.has_table.assert_called_once_with("example", schema="approved")
    inspector.get_columns.assert_called_once_with("example", schema="approved")
