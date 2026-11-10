# Development

- Keep changes scoped, readable and simple. Preserve Databricks Apps runtime and guarded migrations.
- Use Python 3.11/3.12 with uv, pytest, Ruff, Pyright, Poe, Bandit and yamllint.
- `uv run --locked poe format` formats; `poe lint` runs lint checks; `poe checks` runs all non-mutating validation, including browser tests.
- Install the pre-commit hook and pass `uv run --locked poe checks` before committing and before deployment. Report blocked validation honestly. Do not bypass a mandatory gate.
- Use built-in Ruff password rules and Bandit. These are not broad repository or history secret scanners. Never add credentials or invent a scanner.
- Keep neutral branding defaults. Optional branding uses documented Vite variables and same-origin static assets.
- Do not merge, deploy or mutate live databases without separate authorization.
