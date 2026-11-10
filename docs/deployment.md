# Databricks Apps release and rollback

## Release boundary

This repository deploys the **catalog application**, not APIM APIs or Temporal workers. No target has been selected in source. Do not run deployment commands until the owner has confirmed the existing workspace profile, App name, workspace source directory, Lakebase instance/database/schema, resource permissions, admin groups, and release window. Never deploy this company's data into an earlier employer's App or database.

## Before changes

1. Record the current production commit, App deployment identifier, configuration/resource bindings, exact database/schema and tested rollback bundle. Keep secrets out of records and bundles.
2. Arrange an approved database snapshot/backup and verify its restore procedure in an isolated target. Keep legacy rows, comments/attachments, audit history and new planning tables. Backup and restore authorization is separate from read-only validation.
3. Test the upgrade on an approved staging clone or representative isolated PostgreSQL database. SQLite CI does not prove Lakebase permissions, schema search path, TLS, OAuth, or PostgreSQL DDL behavior.
4. Review `app.yaml`: explicitly set the real `ADMIN_GROUPS` and `LAKEBASE_INSTANCE_NAME`, attach the intended existing database resource, and keep `DEV_MODE=false`. Confirm `PGDATABASE`, `PGUSER`, schema/search path, and grants. Databricks production startup validates the existing PostgreSQL schema without creating tables; provision required tables beforehand.
5. Review Databricks SDK and platform compatibility, the locked dependency exports, both Python CI jobs, and the frontend lockfile. CI tests Python 3.11 and 3.12; live Lakebase compatibility still requires target-specific acceptance.

The following commands are templates, not configured targets. Substitute only owner-verified values. Run from the repository root in a controlled environment using the approved database configuration. Do not copy `.env` or credentials into the release.

## Explicit additive upgrade

```bash
uv sync --locked --dev
uv run --locked python -m scripts.migrate_framework \
  --production --expected-database "$APP_DATABASE" --expected-schema "$APP_SCHEMA"
# After reviewing target/DDL scope and obtaining the required authorization:
uv run --locked python -m scripts.migrate_framework \
  --production --expected-database "$APP_DATABASE" --expected-schema "$APP_SCHEMA" --apply
```

The default is dry-run. Both modes connect to the configured database, check its reported name/schema, require existing legacy tables/columns, and reject a mismatched target. `--production` also rejects SQLite and development identity. Verify the configured **host/workspace/instance** independently: name/schema checks alone cannot distinguish two servers with identical database names.

Schema inspection explicitly targets the verified schema, and PostgreSQL DDL uses a transaction-local search path restricted to that quoted schema so fallback schemas cannot satisfy or redirect it. Apply creates only `integration_framework_profiles` and `integration_release_plans` using `create_all(tables=[...], checkfirst=True)` in a transaction. PostgreSQL uses a transaction-scoped advisory lock to serialize this migration. Re-running it does not duplicate tables or modify existing rows. There is no migration ledger and no implicit ALTER, backfill, downgrade, or data import. Existing framework tables are checked for expected columns, but column presence is not a comprehensive type/constraint/index equivalence check. This is a narrowly scoped initial additive migration; future schema changes need explicit reviewed versioned migrations. An incompatible existing table must be investigated, never dropped to force success.

## New installation only: empty-schema bootstrap

For a new company installation, explicitly approve the target and schema creation first. Do not point bootstrap at the old company's database. The dedicated bootstrap script requires an empty target schema, rejects existing tables/views (including partial installations), creates all catalog tables but no rows, and uses the same expected database/schema and production guards. It does not provision a workspace, App, database, role, schema, resource, or seed data. Have the database owner create the approved empty database/schema and grants beforehand.

```bash
uv run --locked python -m scripts.bootstrap_database \
  --production --expected-database "$APP_DATABASE" --expected-schema "$APP_SCHEMA"
# Only after reviewing and approving this exact new target:
uv run --locked python -m scripts.bootstrap_database \
  --production --expected-database "$APP_DATABASE" --expected-schema "$APP_SCHEMA" --apply
```

A second bootstrap is intentionally rejected because the schema is no longer empty. Use the migration/preflight workflow for an existing installation. If a bootstrap fails partway, investigate the transaction and object state; do not drop existing objects automatically or treat them as disposable. Local startup can create the development schema.

## Build, package and preflight

```bash
(cd frontend && npm ci && npx playwright install chromium)
uv run --locked poe checks
uv run --locked python -m scripts.preflight \
  --production --expected-database "$APP_DATABASE" --expected-schema "$APP_SCHEMA"
uv run --locked python -m scripts.package_release --output /tmp/integration-gov-release.tar
```

Before deployment, require successful CI on the exact release commit. The runtime bundle deliberately excludes `pyproject.toml`, `uv.lock` and development requirements, preserving Databricks Apps installation from `requirements.txt` and its existing uvicorn command. Do not sync the full source checkout. `APP_NAME` is only the API display title; `DATABRICKS_APP_NAME` below identifies the verified deployment target.

Use a **new** output filename for each release; existing archives are never overwritten. Packaging includes backend Python, hash-pinned runtime requirements, the MIT license, runbooks, scripts, `app.yaml`, and built `frontend/dist`. It uses an allowlist rather than gitignored checkout sync. The tar contains `RELEASE_MANIFEST.json` with per-file SHA-256 hashes and prints an archive digest. Equal inputs produce equal archives; this does not promise byte-identical npm builds across toolchains. Review the built frontend and configuration for embedded secrets: filename exclusion is not content scanning. Never put credentials in `VITE_*` variables.

The preflight is read-only and independent of FastAPI lifespan. It verifies database connectivity/identity, table and column presence, frontend build, development-mode lockout and nonempty admin-group configuration. It does not verify group membership, runtime OAuth renewal, full schema equivalence, external service availability, or authorization correctness.

## Sync and deploy an approved release

Extract into a new clean directory outside the checkout. Inspect its manifest and target-specific `app.yaml`. The bundle has no `.gitignore`, so the built assets are not silently excluded by checkout ignore rules.

```bash
mkdir "$NEW_EMPTY_RELEASE_DIR"
tar -xf /tmp/integration-gov-release.tar -C "$NEW_EMPTY_RELEASE_DIR"
# Only after the target and release are approved:
databricks sync "$NEW_EMPTY_RELEASE_DIR" "$APP_WORKSPACE_SOURCE" --profile "$WORKSPACE_PROFILE"
databricks apps deploy "$DATABRICKS_APP_NAME" \
  --source-code-path "$APP_WORKSPACE_SOURCE" --profile "$WORKSPACE_PROFILE"
```

Confirm syntax against the installed Databricks CLI before execution. The variables above are intentionally not populated. Check the sync output and workspace files to confirm `frontend/dist/index.html` and its referenced assets exist. Save the resulting deployment identifier and the released source commit/archive digest. Do not change App database bindings while deploying unless separately approved.

## Acceptance checks

Through the authenticated Databricks Apps URL:

- `/healthz` returns 200 and `{"status":"ok"}`.
- `/readyz` returns 200; failures return generic 503 without disclosing infrastructure details. Inspect authorized server logs and run preflight for diagnosis.
- `/api/me` identifies the correct signed-in user and role. Verify **both** admin and general accounts; spoofed client headers must not override the proxy identity.
- Load inventory, detail, graph, comments, audit and framework pages, then reload a deep link. Check browser console and failed asset requests.
- Confirm existing record/relationship counts and representative audit/comments against the baseline without overwriting records.
- In a dedicated approved test record, verify framework save, stale-version conflict, transition validation, and immutable release planning. Confirm general users cannot mutate framework metadata. Do not alter a live production integration just to smoke-test.
- Confirm the UI labels plans as plans, not completed deployments. No APIM/Temporal side effect should occur.
- Review logs, database errors, restart behavior and role resolution during the agreed acceptance window. `/healthz` alone is insufficient.

## Rollback

If acceptance fails, stop new edits as appropriate and redeploy the previously verified application bundle to the **same confirmed** App/database bindings. Restore the earlier configuration only when its changes are understood and approved. Keep the two additive framework tables and all their data; the old app can ignore them. Do not drop tables, delete new audit rows, or run a destructive down migration. Retain the failed bundle and deployment evidence for investigation.

Application rollback does not undo user edits or planned-release history. If data recovery is necessary, compare backup/restore options with the database owner and obtain explicit approval for the specific restore target and data-loss window. Prefer isolated recovery/verification first; do not blindly restore over current company data.
