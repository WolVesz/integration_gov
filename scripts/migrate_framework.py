"""Add only the two framework tables. Dry-run unless --apply is explicit."""

import argparse
import json

from sqlalchemy import inspect, text

from scripts.db_checks import FRAMEWORK_TABLES, schema_problems, validate_target


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--expected-database", required=True, help="Database name, or absolute SQLite path"
    )
    parser.add_argument("--expected-schema", required=True)
    parser.add_argument("--production", action="store_true")
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    from backend.database import engine
    from backend.models import Base

    with engine.begin() as connection:
        target = validate_target(
            connection, args.expected_database, args.expected_schema, args.production
        )
        # Serialize this migration in PostgreSQL. create(checkfirst=True) alone is
        # not concurrency safe. Advisory lock is released at transaction end.
        if args.apply and connection.dialect.name == "postgresql":
            connection.execute(text("SELECT pg_advisory_xact_lock(1848305021)"))
        legacy_names = set(Base.metadata.tables) - set(FRAMEWORK_TABLES)
        problems = schema_problems(connection, Base.metadata, legacy_names)
        if problems:
            raise RuntimeError(
                "Existing installation required; do not bootstrap production: "
                + "; ".join(problems)
            )
        existing = set(inspect(connection).get_table_names(schema=target["schema"]))
        create = [name for name in FRAMEWORK_TABLES if name not in existing]
        problems = schema_problems(connection, Base.metadata, set(FRAMEWORK_TABLES) & existing)
        if problems:
            raise RuntimeError("Existing framework schema is incompatible: " + "; ".join(problems))
        if args.apply:
            Base.metadata.create_all(
                connection,
                tables=[Base.metadata.tables[n] for n in FRAMEWORK_TABLES],
                checkfirst=True,
            )
        print(
            json.dumps(
                {
                    "target": target,
                    "mode": "applied" if args.apply else "dry-run",
                    "create_tables": create,
                    "legacy_tables_unchanged": True,
                },
                indent=2,
            )
        )


if __name__ == "__main__":
    main()
