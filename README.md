# Integration Governance

An integration metadata catalog and development-planning workspace, delivered as a **Databricks App**: FastAPI serves a React/TypeScript frontend backed by Lakebase/PostgreSQL. SQLite is for local development only.

## What this version does

- Keeps the existing searchable integration inventory, relationships, field-level permissions, audit history, comments, approvals, and soft deletion.
- Adds a typed framework profile covering ownership, API/OpenAPI contracts, Temporal orchestration policies, operational readiness, and dev/test/qa/prod configuration references.
- Tracks a separate framework stage and profile version. Optimistic concurrency prevents silently overwriting another editor's framework changes.
- Records immutable planned-release snapshots with environment, release version, Git revision, actor, reason, and the full profile at planning time.
- Uses neutral branding by default, with optional name, logo, favicon and colors configured at build time.

**This is a catalog and planning application.** Recording APIM configuration does not create or update an Azure API Management API. Recording a Temporal namespace, schedule, or worker does not start workflows or deploy workers. A planned release is not proof of an actual deployment, runtime health, approval by an external authority, or successful promotion. Runtime automation remains in the integration framework and its delivery pipelines.

## Local development

Requires uv 0.13.5, Python 3.11 or 3.12, and Node 22.12+ (or Node 24). `uv.lock` and the frontend lockfile capture dependencies. See [development checks](docs/development.md).

```bash
cp .env.example .env
uv sync --locked --dev
uv run --locked pre-commit install
uv run --locked uvicorn backend.main:app --reload
# In a second terminal:
cd frontend && npm ci && npm run dev
```

The API runs on port 8000 and Vite on 5173. Local `DEV_MODE=true` fakes identity using `DEV_USER_*`; never use it in production. Local application startup creates missing development tables. Databricks production startup requires a pre-provisioned PostgreSQL schema and validates it without creating tables. Existing tables are not automatically altered. Demo seeding is optional, local-only (`uv run --locked python -m backend.seed`); never run it against company data.

```bash
(cd frontend && npm ci && npx playwright install chromium)
uv run --locked poe checks
```

Pre-commit and CI run the complete Poe checks gate. CI covers Python 3.11 and 3.12, frontend builds and browser tests, PostgreSQL migrations, pip runtime installation, and deterministic packaging. CI configuration is not evidence that remote CI has passed; review the checks for the exact release commit.

## Structure and API

- `backend/`: FastAPI, SQLAlchemy, identity, audit, inventory and framework routes.
- `frontend/`: React application; generated `frontend/dist` is served by FastAPI.
- `scripts/`: explicit migration, read-only preflight, deterministic release packaging.
- `docs/deployment.md`: target verification, upgrade, smoke test, rollback.
- `docs/framework.md`: framework metadata and workflow boundaries.
- `docs/branding.md`: optional identity configuration.

Core framework routes are under `/api/integrations/{id}/framework`: GET/PUT for the profile, POST `/transition`, and GET/POST `/release-plans`. See the generated OpenAPI schema (`/openapi.json`) for the exact request/response contract. The app's own API schema is distinct from the integration OpenAPI documents referenced by a profile.

`/healthz` is process liveness. `/readyz` checks database connectivity and model table/column presence; production also requires the built frontend. Neither validates external APIM/Temporal deployments. `/api/me` returns the authenticated user's role and legacy admin-only field list.

## Roles and security

Members of configured `ADMIN_GROUPS` receive the `integration` role; other authenticated users receive `general`. Existing inventory field permissions still apply. Framework writes, stage transitions and release-plan creation are integration-team operations; authenticated users may view them. Review the actual server permission checks, not only UI visibility.

Production identity trusts Databricks Apps forwarded identity headers. Run **only behind the Databricks Apps proxy** or an explicitly trusted authenticating proxy that replaces those headers. Exposing the uvicorn port directly permits identity spoofing. SCIM group membership is cached for `GROUP_CACHE_TTL_SECONDS` (default 300); role changes can take that long to apply. Verify service-principal SCIM access and both an admin and general user's role in the target workspace. Approver lists contain known admin users after their first visit.

Do not put passwords, API keys, tokens, client secrets, certificates, or personal-sensitive data in profiles, URLs, audit reasons, comments, or screenshots. Store only approved secret-manager references. Input validation blocks some obvious credential patterns; it is **not** a secret scanner or a substitute for review. Audit and planning history are retained and can be read by catalog users.

Lakebase connections obtain a fresh OAuth credential for each physical database connection. A `PGHOST` resource without `LAKEBASE_INSTANCE_NAME` is rejected rather than falling back to SQLite. `DEV_MODE` with Databricks runtime markers is rejected. Production configuration and database permissions must still be explicitly reviewed.

## Deploy and operate

Follow [the Databricks Apps release runbook](docs/deployment.md). No workspace, existing App, database, or group has been assumed, provisioned, or deployed by this change. The new database tables are additive: `integration_framework_profiles` and `integration_release_plans`. The upgrade script never drops or alters legacy tables and never seeds data.

Build the frontend **before** packaging. Databricks Apps does not run this repository's npm build. The packaging script explicitly includes ignored `frontend/dist` and excludes `.git`, `.env`, local databases, caches, and node_modules. Sync the extracted clean bundle, not the source checkout.

AI semantic search is optional and uses an approved Databricks model-serving endpoint. Without one, keyword search remains available. After enabling/changing embeddings, an authorized admin may run `POST /api/search/reindex`; this sends catalog text to the configured endpoint. Audit/comment history is retained without an automatic pruning policy. Define retention, backups, access reviews and incident handling before production use.
