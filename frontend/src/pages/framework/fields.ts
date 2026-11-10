import type { Contract, Environment, Operations, Orchestration, Ownership } from '../../api/framework'

export interface Field<T> { key: keyof T; label: string; type?: 'number' | 'list' | 'textarea' | 'url'; options?: string[]; hint?: string; min?: number; max?: number; step?: number }
export const ownershipFields: Field<Ownership>[] = [
  { key: 'business_owner', label: 'Business owner' }, { key: 'technical_owner', label: 'Technical owner' },
  { key: 'support_team', label: 'Support team / on-call' },
  { key: 'criticality', label: 'Business criticality', options: ['low', 'medium', 'high', 'critical'] },
  { key: 'data_classification', label: 'Data classification', options: ['public', 'internal', 'confidential', 'restricted'] },
]
export const contractFields: Field<Contract>[] = [
  { key: 'repository_url', label: 'Source repository', type: 'url' },
  { key: 'openapi_url', label: 'OpenAPI definition URL', type: 'url', hint: 'Link to the version-controlled specification.' },
  { key: 'openapi_version', label: 'OpenAPI specification version', hint: 'For example, 3.1.0.' },
  { key: 'api_version', label: 'API product version', hint: 'Version exposed to consumers.' },
  { key: 'compatibility_policy', label: 'Compatibility & deprecation policy', type: 'textarea' },
  { key: 'auth_scheme', label: 'Authentication scheme', hint: 'Describe the scheme only. Never paste credentials.' },
  { key: 'scopes', label: 'Authorization scopes', type: 'list' },
  { key: 'data_entities', label: 'Data entities', type: 'list' },
  { key: 'data_retention_days', label: 'Data retention (days)', type: 'number', max: 36500, min: 0 },
]
export const orchestrationFields: Field<Orchestration>[] = [
  { key: 'workflow_type', label: 'Temporal workflow type' },
  { key: 'workflow_id_template', label: 'Workflow ID template', hint: 'A stable, business-key-based identifier.' },
  { key: 'trigger', label: 'Trigger', options: ['manual', 'api', 'schedule', 'event'] },
  { key: 'cron', label: 'Schedule / cron', hint: 'Required for scheduled workflows.' },
  { key: 'timezone', label: 'Schedule time zone', hint: 'IANA name, for example America/Denver.' },
  { key: 'schedule_overlap_policy', label: 'Schedule overlap', options: ['skip', 'buffer_one', 'buffer_all', 'allow_all'] },
  { key: 'catchup_window_seconds', label: 'Catch-up window (seconds)', type: 'number', max: 31536000, min: 0 },
  { key: 'idempotency_key', label: 'Idempotency key strategy', hint: 'Describe how duplicate business operations are prevented.' },
  { key: 'idempotency_retention_hours', label: 'Idempotency retention (hours)', type: 'number', max: 87600, min: 1 },
  { key: 'retry_max_attempts', label: 'Maximum retry attempts', type: 'number', max: 100, min: 1 },
  { key: 'retry_initial_seconds', label: 'Initial retry interval (seconds)', type: 'number', min: 0.001, step: 0.001, max: 86400 },
  { key: 'retry_max_seconds', label: 'Maximum retry interval (seconds)', type: 'number', min: 0.001, step: 0.001, max: 604800 },
  { key: 'backoff_coefficient', label: 'Retry backoff coefficient', type: 'number', max: 100, min: 1, step: 0.1 },
  { key: 'execution_timeout_seconds', label: 'Execution timeout (seconds)', type: 'number', max: 31536000, min: 1 },
  { key: 'activity_timeout_seconds', label: 'Activity timeout (seconds)', type: 'number', max: 604800, min: 1 },
  { key: 'heartbeat_timeout_seconds', label: 'Heartbeat timeout (seconds)', type: 'number', max: 604800, min: 1 },
  { key: 'non_retryable_errors', label: 'Non-retryable errors', type: 'list' },
  { key: 'compensation_strategy', label: 'Compensation strategy', type: 'textarea', hint: 'Recovery or reversal for partially completed operations.' },
  { key: 'concurrency_limit', label: 'Concurrency limit', type: 'number', max: 100000, min: 1 },
  { key: 'rate_limit_per_second', label: 'Rate limit (per second)', type: 'number', max: 1000000, min: 0.01, step: 0.01 },
  { key: 'fan_out_limit', label: 'Fan-out limit', type: 'number', max: 100000, min: 1 },
  { key: 'dead_letter_destination', label: 'Dead-letter destination' },
]
export const operationsFields: Field<Operations>[] = [
  { key: 'runbook_url', label: 'Runbook URL', type: 'url' }, { key: 'dashboard_url', label: 'Dashboard URL', type: 'url' },
  { key: 'alert_route', label: 'Alert route / escalation' },
  { key: 'slo_availability', label: 'Availability SLO (%)', type: 'number', min: 0.001, max: 100, step: 0.001 },
  { key: 'latency_target_ms', label: 'Latency target (ms)', type: 'number', max: 86400000, min: 1 },
  { key: 'rto_minutes', label: 'Recovery time objective (minutes)', type: 'number', max: 525600, min: 0 },
  { key: 'rpo_minutes', label: 'Recovery point objective (minutes)', type: 'number', max: 525600, min: 0 },
  { key: 'pii_handling', label: 'PII handling & protection', type: 'textarea' },
  { key: 'test_evidence_url', label: 'Test evidence URL', type: 'url' },
  { key: 'rollback_plan', label: 'Rollback plan', type: 'textarea' },
]
export const environmentFields: Field<Environment>[] = [
  { key: 'apim_service', label: 'APIM service' }, { key: 'apim_api_id', label: 'APIM API ID' },
  { key: 'gateway_url', label: 'Gateway URL', type: 'url' }, { key: 'backend_url', label: 'Backend URL', type: 'url' },
  { key: 'temporal_namespace', label: 'Temporal namespace' }, { key: 'task_queue', label: 'Task queue' },
  { key: 'worker_deployment', label: 'Worker deployment reference' }, { key: 'release_version', label: 'Release version' },
  { key: 'git_sha', label: 'Git commit SHA' }, { key: 'config_revision', label: 'Configuration revision' },
  { key: 'secret_references', label: 'Secret references', type: 'list', hint: 'Use secret://, keyvault://, vault:// or ssm:// references. Never enter secret values, tokens or connection strings.' },
]
