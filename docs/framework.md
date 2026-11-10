# Framework catalog and development workflow

The framework profile is separate from the original inventory record and its lifecycle/status fields. Existing records need no backfill: GET returns a default discovery profile at version 0 until the first write. Framework edits advance a profile version and the parent integration version, and write audit entries in the same transaction.

## Metadata sections

- **Ownership:** business and technical owners, support team, criticality, and data classification.
- **Contract:** source repository, OpenAPI document/version, API version, compatibility policy, auth scheme/scopes, data entities and retention days.
- **Orchestration:** workflow type and identity template, trigger/cron/IANA timezone, schedule overlap/catch-up, idempotency key and retention, retry/backoff, execution/activity/heartbeat timeouts, non-retryable failures, compensation, concurrency/rate/fan-out limits and dead-letter handling.
- **Operations:** runbook, dashboard, alert destination, availability/latency targets, RTO/RPO, PII handling, test-evidence link and rollback plan.
- **Environments:** distinct dev/test/qa/prod entries with APIM service/API, gateway and backend URLs, Temporal namespace/task queue/worker deployment, release version/Git SHA, secret-manager references and config revision.

Inputs are bounded and typed, unknown fields are rejected, and URLs cannot contain credentials, query strings or fragments. Secret references use `secret://`, `keyvault://`, `vault://` or `ssm://` notation. These strings are references only: the catalog does not retrieve secrets, dereference URLs or verify remote contracts. Cron input is format-checked but not a runtime scheduler or complete semantic cron validator.

## Stages and gates

The forward path is discovery → design → development → validation → ready → live → retired. Validation, ready and live can return to development. Retired profiles are read-only. Transitions require the current profile version and a nonempty reason; stale writes return 409 rather than silently merging edits.

Moving into development requires owner and versioned-contract metadata. Validation requires workflow policies and a complete dev environment. Ready/live require the production checklist, including operational and recovery objectives, evidence links, production HTTPS mappings and existing design/code approval records. Live additionally requires a production release plan matching the current profile. These checks confirm **catalog completeness and recorded attestations**, not external deployment, live traffic, reviewed evidence, or independent security approval.

A material framework-spec edit clears existing design/code approval records, recording that invalidation in the audit trail. Editing a validation/ready/live profile returns it to development. Re-review and record approvals for the changed design before advancing it again; do not assume old approval applies to changed contracts or runtime settings.

## Planned releases

Only integration-team users can write profiles, transition stages or create release plans. General users can read them. Plans are append-only through this API and capture a profile snapshot, version, target environment, release version, Git SHA, actor and reason. There is no update/delete API for a plan; database administrators still control the underlying storage, so this is not tamper-proof/WORM evidence.

Planning requires complete environment routing/worker/release metadata. Plans follow dev → test → qa → prod for the identical profile snapshot, release version and Git SHA. Production planning requires ready/live and all checklist gates. Plan all environment mappings consistently before beginning this chain; changing the spec requires a new matching chain. A plan always remains `planned`; it is not a completed deployment or pipeline execution result.

Actual APIM publication, Temporal deployment/scheduling, change approval, environment promotion, runtime checks and rollback execution belong in approved delivery tooling. Link that tooling's results as evidence rather than representing these planning records as execution.

## API editing pattern

1. GET `/api/integrations/{id}/framework` to obtain the current version, full spec, stage, readiness checklist and plan summaries.
2. PUT the current `version` and the complete edited `spec`. On 409, reload and reconcile intentionally; do not retry the stale payload automatically.
3. POST `/transition` with `version`, `target`, and `reason`, or `/release-plans` with `version`, `environment`, and `reason`.
4. Use the returned version for the next write. Keep the existing inventory screen's version current too.

The generated API schema is authoritative for exact field bounds. There is no promise that a profile covers every integration style: this first readiness checklist assumes APIM/FastAPI/Temporal together and requires a production mapping. Non-API or non-Temporal designs may need a future explicitly modeled variant rather than fictitious values to satisfy gates.
