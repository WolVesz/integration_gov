"""Strict, bounded catalog metadata. No credentials or runtime calls belong here."""

import re
from typing import Annotated, Literal
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import AfterValidator, BaseModel, ConfigDict, Field, model_validator


def safe_text(value: str) -> str:
    # Prevent obvious credential material from entering catalog/audit history.
    if re.search(
        r"-----BEGIN .*PRIVATE KEY|\bBearer\s+\S+|\b(?:password|client_secret|access_token|api_key)\s*[:=]\s*\S+",
        value,
        re.I,
    ):
        raise ValueError("Store secret references only, never credential values")
    return value


Text = Annotated[str, Field(max_length=2000), AfterValidator(safe_text)]
Name = Annotated[str, Field(max_length=200), AfterValidator(safe_text)]
NonBlankName = Annotated[Name, Field(min_length=1)]
Items = Annotated[list[NonBlankName], Field(max_length=100)]


def safe_url(value: str) -> str:
    if not value:
        return value
    try:
        url = urlsplit(value)
        _ = url.port
        if (
            url.scheme not in ("https", "http")
            or not url.hostname
            or url.username
            or url.password
            or url.query
            or url.fragment
            or any(c.isspace() for c in value)
            or "\\" in value
        ):
            raise ValueError()
    except ValueError:
        raise ValueError(
            "Use an HTTP(S) URL without credentials, query parameters or fragments"
        ) from None
    return value


URL = Annotated[Text, AfterValidator(safe_url)]
EnvName = Literal["dev", "test", "qa", "prod"]
Stage = Literal["discovery", "design", "development", "validation", "ready", "live", "retired"]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, str_strip_whitespace=True)


class Ownership(StrictModel):
    business_owner: Name = ""
    technical_owner: Name = ""
    support_team: Name = ""
    criticality: Literal["low", "medium", "high", "critical"] = "medium"
    data_classification: Literal["public", "internal", "confidential", "restricted"] = "internal"


class Contract(StrictModel):
    repository_url: URL = ""
    openapi_url: URL = ""
    openapi_version: Annotated[str, Field(pattern=r"^(?:3\.\d+\.\d+)?$", max_length=30)] = ""
    api_version: Name = ""
    compatibility_policy: Text = ""
    auth_scheme: Name = ""
    scopes: Items = Field(default_factory=list)
    data_entities: Items = Field(default_factory=list)
    data_retention_days: Annotated[int | None, Field(ge=0, le=36500)] = None


def validate_cron(value: str) -> None:
    """Deliberately support the portable numeric five-field cron subset."""
    fields = value.split()
    if len(fields) != 5:
        raise ValueError("cron must have five numeric cron fields")
    for field, (low, high) in zip(
        fields, ((0, 59), (0, 23), (1, 31), (1, 12), (0, 7)), strict=True
    ):
        for term in field.split(","):
            parts = term.split("/")
            if len(parts) > 2:
                raise ValueError("Invalid cron step")
            base = parts[0]
            if len(parts) == 2 and (
                not parts[1].isdigit() or not 1 <= int(parts[1]) <= high - low + 1
            ):
                raise ValueError("Cron step is out of range")
            if base == "*":
                continue
            bounds = base.split("-")
            if not 1 <= len(bounds) <= 2 or any(
                not b.isdigit() or not low <= int(b) <= high for b in bounds
            ):
                raise ValueError("Cron field is out of range")
            if len(bounds) == 2 and int(bounds[0]) > int(bounds[1]):
                raise ValueError("Cron range must be ascending")


class Orchestration(StrictModel):
    workflow_type: Name = ""
    workflow_id_template: Name = ""
    trigger: Literal["manual", "api", "schedule", "event"] = "api"
    cron: Name = ""
    timezone: Name = "UTC"
    schedule_overlap_policy: Literal["skip", "buffer_one", "buffer_all", "allow_all"] = "skip"
    catchup_window_seconds: Annotated[int, Field(ge=0, le=31536000)] = 60
    idempotency_key: Name = ""
    idempotency_retention_hours: Annotated[int, Field(ge=1, le=87600)] = 24
    retry_max_attempts: Annotated[int, Field(ge=1, le=100)] = 3
    retry_initial_seconds: Annotated[float, Field(gt=0, le=86400, allow_inf_nan=False)] = 1
    retry_max_seconds: Annotated[float, Field(gt=0, le=604800, allow_inf_nan=False)] = 60
    backoff_coefficient: Annotated[float, Field(ge=1, le=100, allow_inf_nan=False)] = 2
    execution_timeout_seconds: Annotated[int, Field(ge=1, le=31536000)] = 3600
    activity_timeout_seconds: Annotated[int, Field(ge=1, le=604800)] = 300
    heartbeat_timeout_seconds: Annotated[int | None, Field(ge=1, le=604800)] = None
    non_retryable_errors: Items = Field(default_factory=list)
    compensation_strategy: Text = ""
    concurrency_limit: Annotated[int, Field(ge=1, le=100000)] = 10
    rate_limit_per_second: Annotated[float | None, Field(gt=0, le=1000000, allow_inf_nan=False)] = (
        None
    )
    fan_out_limit: Annotated[int, Field(ge=1, le=100000)] = 100
    dead_letter_destination: Text = ""

    @model_validator(mode="after")
    def consistent(self):
        try:
            ZoneInfo(self.timezone)
        except (ValueError, ZoneInfoNotFoundError):
            raise ValueError("timezone must be an IANA timezone") from None
        if self.retry_max_seconds < self.retry_initial_seconds:
            raise ValueError("retry_max_seconds must be >= retry_initial_seconds")
        if self.activity_timeout_seconds > self.execution_timeout_seconds:
            raise ValueError("activity timeout must not exceed execution timeout")
        if (
            self.heartbeat_timeout_seconds
            and self.heartbeat_timeout_seconds > self.activity_timeout_seconds
        ):
            raise ValueError("heartbeat timeout must not exceed activity timeout")
        if self.cron:
            validate_cron(self.cron)
        return self


class Operations(StrictModel):
    runbook_url: URL = ""
    dashboard_url: URL = ""
    alert_route: Name = ""
    slo_availability: Annotated[float | None, Field(gt=0, le=100, allow_inf_nan=False)] = None
    latency_target_ms: Annotated[int | None, Field(ge=1, le=86400000)] = None
    rto_minutes: Annotated[int | None, Field(ge=0, le=525600)] = None
    rpo_minutes: Annotated[int | None, Field(ge=0, le=525600)] = None
    pii_handling: Text = ""
    test_evidence_url: URL = ""
    rollback_plan: Text = ""


def secret_reference(value: str) -> str:
    if not re.fullmatch(
        r"(?:secret|keyvault|vault|ssm)://[A-Za-z0-9][A-Za-z0-9_./:@-]{0,480}", value
    ):
        raise ValueError(
            "Use secret://, keyvault://, vault:// or ssm:// references, not secret values"
        )
    return value


class Environment(StrictModel):
    name: EnvName
    apim_service: Name = ""
    apim_api_id: Name = ""
    gateway_url: URL = ""
    backend_url: URL = ""
    temporal_namespace: Name = ""
    task_queue: Name = ""
    worker_deployment: Name = ""
    release_version: Name = ""
    git_sha: Annotated[str, Field(pattern=r"^(?:[a-fA-F0-9]{7,40})?$")] = ""
    secret_references: Annotated[
        list[Annotated[Name, AfterValidator(secret_reference)]], Field(max_length=100)
    ] = Field(default_factory=list)
    config_revision: Name = ""


class FrameworkSpec(StrictModel):
    ownership: Ownership = Field(default_factory=Ownership)
    contract: Contract = Field(default_factory=Contract)
    orchestration: Orchestration = Field(default_factory=Orchestration)
    operations: Operations = Field(default_factory=Operations)
    environments: Annotated[list[Environment], Field(max_length=4)] = Field(default_factory=list)

    @model_validator(mode="after")
    def unique_environments(self):
        names = [e.name for e in self.environments]
        if len(names) != len(set(names)):
            raise ValueError("Environment names must be unique")
        return self


class Versioned(StrictModel):
    version: Annotated[int, Field(ge=0)]


class FrameworkPut(Versioned):
    spec: FrameworkSpec


class Transition(Versioned):
    target: Stage
    reason: Annotated[Text, Field(min_length=1)]


class ReleasePlanCreate(Versioned):
    environment: EnvName
    reason: Annotated[Text, Field(min_length=1)]


class ReadinessCheck(StrictModel):
    key: str
    label: str
    passed: bool
    detail: str


class Readiness(StrictModel):
    ready: bool
    checks: list[ReadinessCheck]


class ReleasePlanOut(StrictModel):
    id: str
    environment: EnvName
    release_version: str
    git_sha: str
    created_at: str
    created_by: str
    reason: str
    status: Literal["planned"] = "planned"


class FrameworkOut(StrictModel):
    integration_id: str
    version: int
    stage: Stage
    spec: FrameworkSpec
    readiness: Readiness
    release_plans: list[ReleasePlanOut]
