"""Explicit first-install bootstrap for a verified empty schema. Never seeds rows."""

import argparse
import json

from sqlalchemy import inspect, text

from scripts.db_checks import validate_target


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--expected-database", required=True)
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
        if args.apply and connection.dialect.name == "postgresql":
            connection.execute(text("SELECT pg_advisory_xact_lock(1848305021)"))
        inspector = inspect(connection)
        # Refuse all existing application/user tables or views, including a
        # partial failed installation. Do not guess which objects are disposable.
        objects = inspector.get_table_names(schema=target["schema"]) + inspector.get_view_names(
            schema=target["schema"]
        )
        if connection.dialect.name == "postgresql":
            objects += inspector.get_materialized_view_names(schema=target["schema"])
        if objects:
            raise RuntimeError(
                "Bootstrap requires an empty schema; existing objects found. Use reviewed upgrade/recovery instead."
            )
        if args.apply:
            Base.metadata.create_all(connection, checkfirst=True)
        print(
            json.dumps(
                {
                    "target": target,
                    "mode": "applied" if args.apply else "dry-run",
                    "create_tables": sorted(Base.metadata.tables),
                    "seed_rows": 0,
                },
                indent=2,
            )
        )


if __name__ == "__main__":
    main()
