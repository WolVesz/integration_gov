# Development checks

Use uv 0.13.5 and Python 3.11 or 3.12, with Node 22.12+ or Node 24.

```bash
uv sync --locked --dev
(cd frontend && npm ci && npx playwright install chromium)
uv run --locked pre-commit install
uv run --locked poe checks
```

`poe format` runs formatting commands. `poe lint` runs Python and YAML linting. `poe checks` runs every non-mutating source check: lock/export drift, lint, format verification, Pyright, Bandit, pytest with branch coverage, frontend unit tests, build and browser tests. Run it before committing and before deployment. The local pre-commit hook uses this same gate and CI repeats it on Python 3.11 and 3.12. A blocked check is not a pass. Do not bypass it.

`uv.lock` is authoritative. After an intentional dependency update, run `uv run --locked poe export-deps` to regenerate both requirements files, then run checks. These hash-pinned exports preserve pip-based Databricks deployment; they are not independently edited. CI tests installation of the runtime export separately. No arbitrary coverage percentage is imposed.

Ruff uses its built-in S105/S106/S107 hardcoded-password checks, alongside E/F/I/B/UP/ASYNC. Bandit checks Python security issues. Neither covers all credential formats, other file types, or repository history. Do not store secrets in Git, YAML or frontend build variables. Use the deployment environment and approved secret storage. No custom scanner is included. Tests are excluded from Bandit, not from Ruff or Pyright. YAML is linted; no standalone SQL files currently require SQLFluff.

For an existing Chromium installation, set `PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH` to its executable; otherwise install Playwright Chromium as shown above. Browser tests run a local isolated development app and temporary SQLite database. Production authentication, Lakebase OAuth, and live target permissions still require separate authorized acceptance checks.

See [branding](branding.md) for optional build-time settings. CI tests both neutral and custom identity, restores the neutral build, and only then packages release artifacts.
