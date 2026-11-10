"""Framework catalog lifecycle and immutable release plans; never deploys anything."""

import json
from copy import deepcopy

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..audit import audit_updated, diff_snapshots, snapshot, write_entry
from ..auth import CurrentUser, get_current_user
from ..database import get_db
from ..framework_schemas import (
    FrameworkOut,
    FrameworkPut,
    FrameworkSpec,
    ReleasePlanCreate,
    Transition,
)
from ..models import AuditAction, Integration, as_utc, new_id, utcnow
from ..models import IntegrationFrameworkProfile as Profile
from ..models import IntegrationReleasePlan as Plan
from ..search import refresh_search_document, update_embedding_post_commit

router = APIRouter(prefix="/integrations/{integration_id}/framework", tags=["framework"])


def integration_for(db, integration_id):
    integration = db.get(Integration, integration_id)
    if integration is None or integration.is_deleted:
        raise HTTPException(404, "Integration not found")
    return integration


def writer(user):
    if not user.is_admin:
        raise HTTPException(403, "Framework writes require the integration team role")


def plans_for(db, integration_id):
    return list(
        db.scalars(
            select(Plan)
            .where(Plan.integration_id == integration_id)
            .order_by(Plan.created_at.desc(), Plan.id.desc())
        )
    )


def environment_complete(e):
    return bool(
        e
        and all(
            (
                e.apim_service,
                e.apim_api_id,
                e.gateway_url,
                e.backend_url,
                e.temporal_namespace,
                e.task_queue,
                e.worker_deployment,
                e.release_version,
                e.git_sha,
                e.config_revision,
            )
        )
    )


def readiness(spec, integration):
    o, c, w, ops = spec.ownership, spec.contract, spec.orchestration, spec.operations
    prod = next((e for e in spec.environments if e.name == "prod"), None)
    checks = []

    def check(key, label, passed, detail):
        checks.append(dict(key=key, label=label, passed=bool(passed), detail=detail))

    check(
        "ownership",
        "Accountable owners",
        o.business_owner and o.technical_owner and o.support_team,
        "Business owner, technical owner and support team are required.",
    )
    check(
        "contract",
        "Versioned API contract",
        c.repository_url
        and c.openapi_url
        and c.openapi_version
        and c.api_version
        and c.compatibility_policy,
        "Repository, OpenAPI document/version, API version and compatibility policy are required.",
    )
    check(
        "security",
        "Security and retention",
        c.auth_scheme
        and c.data_entities
        and c.data_retention_days is not None
        and ops.pii_handling,
        "Document authentication, data entities, retention and PII handling; never store credentials.",
    )
    check(
        "workflow",
        "Reliable workflow",
        w.workflow_type
        and w.workflow_id_template
        and w.idempotency_key
        and w.compensation_strategy
        and w.dead_letter_destination,
        "Workflow identity, idempotency, compensation and dead-letter handling are required.",
    )
    check(
        "schedule",
        "Schedule policy",
        w.trigger != "schedule" or w.cron,
        "Scheduled workflows require a five-field cron expression and valid timezone.",
    )
    check(
        "operations",
        "Operational ownership",
        ops.runbook_url and ops.dashboard_url and ops.alert_route and ops.rollback_plan,
        "Runbook, dashboard, alert route and rollback plan are required.",
    )
    check(
        "objectives",
        "Service and recovery objectives",
        ops.slo_availability is not None
        and ops.latency_target_ms is not None
        and ops.rto_minutes is not None
        and ops.rpo_minutes is not None,
        "Availability percent, latency target, RTO and RPO must be explicit.",
    )
    check(
        "testing",
        "Test evidence",
        ops.test_evidence_url,
        "Link to reviewed test evidence. Links are recorded, not fetched or verified.",
    )
    check(
        "production",
        "Production environment mapping",
        environment_complete(prod),
        "Production needs APIM, FastAPI backend, Temporal namespace/queue/worker and release/config identity.",
    )
    check(
        "transport",
        "Production HTTPS",
        prod
        and prod.gateway_url.startswith("https://")
        and prod.backend_url.startswith("https://"),
        "Production gateway and backend must use HTTPS.",
    )
    check(
        "approvals",
        "Design and code approval records",
        integration.design_approved
        and integration.design_approver_id
        and integration.design_approval_date
        and integration.code_approved
        and integration.code_approver_id
        and integration.code_approval_date,
        "Legacy design and code approvals must include named approvers and dates; these are administrative attestations.",
    )
    return dict(ready=all(c["passed"] for c in checks), checks=checks)


def result(db, integration):
    p = db.get(Profile, integration.id)
    spec = FrameworkSpec.model_validate(p.spec) if p else FrameworkSpec()
    return dict(
        integration_id=integration.id,
        version=p.version if p else 0,
        stage=p.stage if p else "discovery",
        spec=spec,
        readiness=readiness(spec, integration),
        release_plans=[
            dict(
                id=r.id,
                environment=r.environment,
                release_version=r.release_version,
                git_sha=r.git_sha,
                created_at=as_utc(r.created_at).isoformat(),
                created_by=r.created_by,
                reason=r.reason,
                status=r.status,
            )
            for r in plans_for(db, integration.id)
        ],
    )


def current(db, integration_id, version):
    p = db.get(Profile, integration_id)
    if (p.version if p else 0) != version:
        raise HTTPException(409, "Framework changed. Reload before saving.")
    return p


def save(db, integration, p, version, spec, stage, user, field, old, new):
    """Compare-and-swap plus audit in one transaction; first-create races become 409."""
    now = utcnow()
    change_group = new_id()
    # Serialize framework writes with existing optimistic integration edits,
    # especially approval changes and soft deletion. No legacy status is changed.
    integration_version = integration.version
    material_spec_change = field == "framework.spec" and (p is None or p.spec != spec)
    try:
        locked = db.execute(
            update(Integration)
            .where(
                Integration.id == integration.id,
                Integration.version == integration_version,
                Integration.deleted_at.is_(None),
            )
            .values(version=integration_version + 1, updated_at=now, updated_by_id=user.id)
        )
        if locked.rowcount != 1:
            db.rollback()
            raise HTTPException(409, "Integration changed. Reload before saving.")
        if material_spec_change:
            before_approvals = snapshot(db, integration)
            for name in (
                "design_approved",
                "code_approved",
                "design_approver_id",
                "code_approver_id",
                "design_approval_date",
                "code_approval_date",
            ):
                setattr(integration, name, False if name.endswith("_approved") else None)
            # Drop relationship caches so audit/search cannot retain old approver names.
            db.flush()
            db.expire(integration, ["design_approver", "code_approver", "updated_by"])
            audit_updated(
                db,
                integration,
                diff_snapshots(before_approvals, snapshot(db, integration)),
                user,
                change_group,
            )
        if p is None:
            db.add(
                Profile(
                    integration_id=integration.id,
                    version=1,
                    spec=spec,
                    stage=stage,
                    updated_at=now,
                    updated_by=user.email,
                )
            )
        else:
            changed = db.execute(
                update(Profile)
                .where(Profile.integration_id == integration.id, Profile.version == version)
                .values(
                    version=version + 1,
                    spec=spec,
                    stage=stage,
                    updated_at=now,
                    updated_by=user.email,
                )
            )
            if changed.rowcount != 1:
                db.rollback()
                raise HTTPException(409, "Framework changed. Reload before saving.")
        db.flush()
        db.expire(integration, ["updated_by"])
        refresh_search_document(db, integration)
        write_entry(
            db,
            integration_id=integration.id,
            integration_name=integration.name,
            action=AuditAction.updated,
            user=user,
            change_group_id=change_group,
            field=field,
            old_value=json.dumps(old, sort_keys=True),
            new_value=json.dumps(new, sort_keys=True),
        )
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "Framework changed. Reload before saving.") from None
    update_embedding_post_commit(db, integration.id)
    db.expire_all()
    return result(db, integration)


@router.get("", response_model=FrameworkOut)
def get_framework(
    integration_id: str,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
):
    return result(db, integration_for(db, integration_id))


@router.put("", response_model=FrameworkOut)
def put_framework(
    integration_id: str,
    body: FrameworkPut,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
):
    writer(user)
    integration = integration_for(db, integration_id)
    p = current(db, integration_id, body.version)
    if p and p.stage == "retired":
        raise HTTPException(409, "Retired profiles are read-only")
    stage = p.stage if p else "discovery"
    spec = body.spec.model_dump()
    if p and p.spec != spec and stage in ("validation", "ready", "live"):
        stage = "development"
    return save(
        db,
        integration,
        p,
        body.version,
        spec,
        stage,
        user,
        "framework.spec",
        dict(spec=p.spec, stage=p.stage) if p else None,
        dict(spec=spec, stage=stage),
    )


ALLOWED = {
    "discovery": {"design"},
    "design": {"development"},
    "development": {"validation"},
    "validation": {"development", "ready"},
    "ready": {"development", "live"},
    "live": {"development", "retired"},
    "retired": set(),
}


@router.post("/transition", response_model=FrameworkOut)
def transition(
    integration_id: str,
    body: Transition,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
):
    writer(user)
    integration = integration_for(db, integration_id)
    p = current(db, integration_id, body.version)
    stage = p.stage if p else "discovery"
    if body.target not in ALLOWED[stage]:
        raise HTTPException(409, f"Transition {stage} → {body.target} is not allowed")
    spec = FrameworkSpec.model_validate(p.spec) if p else FrameworkSpec()
    checks = {c["key"]: c["passed"] for c in readiness(spec, integration)["checks"]}
    if (
        body.target == "development"
        and stage == "design"
        and not all(checks[k] for k in ("ownership", "contract"))
    ):
        raise HTTPException(422, "Development requires ownership and versioned contract metadata")
    if body.target == "validation" and not (
        checks["workflow"]
        and checks["schedule"]
        and environment_complete(next((e for e in spec.environments if e.name == "dev"), None))
    ):
        raise HTTPException(
            422, "Validation requires workflow policy and a complete dev environment"
        )
    if body.target in ("ready", "live") and not all(checks.values()):
        raise HTTPException(422, "Production readiness checks must pass")
    if body.target == "live" and not any(
        r.environment == "prod" and r.spec_snapshot == spec.model_dump()
        for r in plans_for(db, integration_id)
    ):
        raise HTTPException(
            422,
            "Live catalog status requires a production release plan for this spec; it does not deploy or verify runtime state",
        )
    return save(
        db,
        integration,
        p,
        body.version,
        spec.model_dump(),
        body.target,
        user,
        "framework.stage",
        stage,
        dict(stage=body.target, reason=body.reason),
    )


@router.post("/release-plans", response_model=FrameworkOut, status_code=201)
def plan_release(
    integration_id: str,
    body: ReleasePlanCreate,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
):
    writer(user)
    integration = integration_for(db, integration_id)
    p = current(db, integration_id, body.version)
    if not p or p.stage not in ("development", "validation", "ready", "live"):
        raise HTTPException(422, "Release planning requires development or a later active stage")
    spec = FrameworkSpec.model_validate(p.spec)
    env = next((e for e in spec.environments if e.name == body.environment), None)
    if env is None or not environment_complete(env):
        raise HTTPException(
            422, "Selected environment needs complete routing, worker and release/config metadata"
        )
    if body.environment == "prod" and (
        p.stage not in ("ready", "live") or not readiness(spec, integration)["ready"]
    ):
        raise HTTPException(
            422, "Production planning requires ready/live stage and all production readiness checks"
        )
    predecessor = {"test": "dev", "qa": "test", "prod": "qa"}.get(body.environment)
    if predecessor and not any(
        r.environment == predecessor
        and r.release_version == env.release_version
        and r.git_sha == env.git_sha
        and r.spec_snapshot == p.spec
        for r in plans_for(db, integration_id)
    ):
        raise HTTPException(
            422, f"Plan {predecessor} first with identical spec, release version and git SHA"
        )
    plan = Plan(
        id=new_id(),
        integration_id=integration_id,
        profile_version=body.version,
        environment=env.name,
        release_version=env.release_version,
        git_sha=env.git_sha,
        spec_snapshot=deepcopy(p.spec),
        created_by=user.email,
        reason=body.reason,
        status="planned",
    )
    db.add(plan)
    return save(
        db,
        integration,
        p,
        body.version,
        p.spec,
        p.stage,
        user,
        "framework.release_plan",
        None,
        dict(id=plan.id, environment=env.name, status="planned", reason=body.reason),
    )
