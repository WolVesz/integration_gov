"""Read-only schema checks shared by release tools; does not run app lifespan."""

from pathlib import Path

from sqlalchemy import inspect, text

FRAMEWORK_TABLES = ("integration_framework_profiles", "integration_release_plans")


def target_identity(connection):
    if connection.dialect.name == "postgresql":
        row = connection.execute(text("SELECT current_database(), current_schema()")).one()
        return {"database": row[0], "schema": row[1]}
    if connection.dialect.name == "sqlite":
        path = connection.engine.url.database or ":memory:"
        return {
            "database": str(Path(path).resolve()) if path != ":memory:" else path,
            "schema": "main",
        }
    raise RuntimeError("Only PostgreSQL and local SQLite are supported by release tools")


def validate_target(connection, expected_database, expected_schema, production=False):
    from backend.config import get_settings

    if production and (get_settings().dev_mode or connection.dialect.name != "postgresql"):
        raise RuntimeError("Production requires DEV_MODE=false and PostgreSQL/Lakebase")
    actual = target_identity(connection)
    if actual != {"database": expected_database, "schema": expected_schema}:
        raise RuntimeError(f"Database target mismatch: connected to {actual!r}; no changes applied")
    if connection.dialect.name == "postgresql":
        # Resolve all unqualified DDL/FKs only in the verified schema. Quote as
        # an identifier, never interpolate raw operator input into SQL.
        quoted = connection.dialect.identifier_preparer.quote_identifier(expected_schema)
        connection.exec_driver_sql(f"SET LOCAL search_path TO {quoted}")
    return actual


def schema_problems(connection, metadata, names):
    inspector = inspect(connection)
    schema = target_identity(connection)["schema"]
    if not schema:
        raise RuntimeError("No current database schema; configure an explicit existing schema")
    problems = []
    for name in names:
        if not inspector.has_table(name, schema=schema):
            problems.append(f"Missing table: {name}")
            continue
        actual = {c["name"] for c in inspector.get_columns(name, schema=schema)}
        missing = set(metadata.tables[name].columns.keys()) - actual
        if missing:
            problems.append(f"Missing columns in {name}: {', '.join(sorted(missing))}")
    return problems
