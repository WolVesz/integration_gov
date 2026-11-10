"""Read-only release preflight; no table creation and no seed data."""

import argparse
import json
from pathlib import Path

from scripts.db_checks import schema_problems, validate_target


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--expected-database", required=True)
    parser.add_argument("--expected-schema", required=True)
    parser.add_argument("--production", action="store_true")
    args = parser.parse_args()
    from backend.config import get_settings
    from backend.database import engine
    from backend.models import Base

    with engine.connect() as connection:
        target = validate_target(
            connection, args.expected_database, args.expected_schema, args.production
        )
        problems = schema_problems(connection, Base.metadata, Base.metadata.tables)
    if not (Path(__file__).resolve().parents[1] / "frontend/dist/index.html").is_file():
        problems.append("Missing frontend/dist/index.html; build and package the frontend")
    if args.production and not get_settings().admin_group_set:
        problems.append("ADMIN_GROUPS must name the verified workspace admin groups")
    if problems:
        raise RuntimeError("Preflight failed: " + "; ".join(problems))
    print(
        json.dumps(
            {
                "status": "ok",
                "target": target,
                "checks": [
                    "database connectivity",
                    "table and column presence",
                    "frontend build",
                    "production configuration" if args.production else "local configuration",
                ],
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
