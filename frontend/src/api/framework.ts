import { get, post, request } from './client'

export const STAGES = ['discovery', 'design', 'development', 'validation', 'ready', 'live', 'retired'] as const
export type Stage = typeof STAGES[number]
export type EnvironmentName = 'dev' | 'test' | 'qa' | 'prod'
export interface Ownership {
  business_owner: string; technical_owner: string; support_team: string
  criticality: 'low' | 'medium' | 'high' | 'critical'
  data_classification: 'public' | 'internal' | 'confidential' | 'restricted'
}
export interface Contract {
  repository_url: string; openapi_url: string; openapi_version: string; api_version: string
  compatibility_policy: string; auth_scheme: string; scopes: string[]; data_entities: string[]
  data_retention_days: number | null
}
export interface Orchestration {
  workflow_type: string; workflow_id_template: string; trigger: 'manual' | 'api' | 'schedule' | 'event'
  cron: string; timezone: string; schedule_overlap_policy: 'skip' | 'buffer_one' | 'buffer_all' | 'allow_all'
  catchup_window_seconds: number; idempotency_key: string; idempotency_retention_hours: number
  retry_max_attempts: number; retry_initial_seconds: number; retry_max_seconds: number
  backoff_coefficient: number; execution_timeout_seconds: number; activity_timeout_seconds: number
  heartbeat_timeout_seconds: number | null; non_retryable_errors: string[]; compensation_strategy: string
  concurrency_limit: number; rate_limit_per_second: number | null; fan_out_limit: number
  dead_letter_destination: string
}
export interface Operations {
  runbook_url: string; dashboard_url: string; alert_route: string; slo_availability: number | null
  latency_target_ms: number | null; rto_minutes: number | null; rpo_minutes: number | null
  pii_handling: string; test_evidence_url: string; rollback_plan: string
}
export interface Environment {
  name: EnvironmentName; apim_service: string; apim_api_id: string; gateway_url: string; backend_url: string
  temporal_namespace: string; task_queue: string; worker_deployment: string; release_version: string
  git_sha: string; secret_references: string[]; config_revision: string
}
export interface FrameworkSpec {
  ownership: Ownership; contract: Contract; orchestration: Orchestration; operations: Operations
  environments: Environment[]
}
export interface FrameworkProfile {
  integration_id: string; version: number; stage: Stage; spec: FrameworkSpec
  readiness: { ready: boolean; checks: { key: string; label: string; passed: boolean; detail: string }[] }
  release_plans: { id: string; environment: EnvironmentName; release_version: string; git_sha: string
    created_at: string; created_by: string; reason: string; status: 'planned' }[]
}
const path = (id: string) => `/integrations/${encodeURIComponent(id)}/framework`
export const getFramework = (id: string, signal?: AbortSignal) => get<FrameworkProfile>(path(id), signal)
export const saveFramework = (id: string, version: number, spec: FrameworkSpec) =>
  request<FrameworkProfile>(path(id), { method: 'PUT', body: JSON.stringify({ version, spec }) })
export const transitionFramework = (id: string, version: number, target: Stage, reason: string) =>
  post<FrameworkProfile>(`${path(id)}/transition`, { version, target, reason })
export const planRelease = (id: string, version: number, environment: EnvironmentName, reason: string) =>
  post<FrameworkProfile>(`${path(id)}/release-plans`, { version, environment, reason })

export function emptyEnvironment(name: EnvironmentName): Environment {
  return { name, apim_service: '', apim_api_id: '', gateway_url: '', backend_url: '', temporal_namespace: '',
    task_queue: '', worker_deployment: '', release_version: '', git_sha: '', secret_references: [], config_revision: '' }
}
