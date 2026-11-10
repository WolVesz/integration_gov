"""Catalog invariants: no runtime operations, additive state and immutable plans."""

from copy import deepcopy

import pytest
from sqlalchemy import select

from backend.database import SessionLocal
from backend.models import (
    AuditEntry,
    Integration,
    IntegrationFrameworkProfile,
    IntegrationReleasePlan,
)

from .conftest import ADMIN, USER, create_integration


def url(client):
    i = create_integration(client, "Framework example").json()
    return f"/api/integrations/{i['id']}/framework"


def complete_spec():
    from backend.framework_schemas import FrameworkSpec

    spec = FrameworkSpec().model_dump()
    spec["ownership"].update(
        business_owner="Business", technical_owner="Engineering", support_team="Operations"
    )
    spec["contract"].update(
        repository_url="https://github.com/example/api",
        openapi_url="https://api.example.com/openapi.json",
        openapi_version="3.1.0",
        api_version="1.0",
        compatibility_policy="Additive changes only",
        auth_scheme="OAuth2",
        data_entities=["Orders"],
        data_retention_days=30,
    )
    spec["orchestration"].update(
        workflow_type="OrderWorkflow",
        workflow_id_template="order/{id}",
        idempotency_key="order-id",
        compensation_strategy="Reverse completed steps",
        dead_letter_destination="queue/orders-failed",
    )
    spec["operations"].update(
        runbook_url="https://docs.example.com/runbook",
        dashboard_url="https://metrics.example.com/orders",
        alert_route="Integration on-call",
        slo_availability=99.9,
        latency_target_ms=100,
        rto_minutes=30,
        rpo_minutes=5,
        pii_handling="Redact personal data",
        test_evidence_url="https://ci.example.com/build/1",
        rollback_plan="Revert worker and APIM revision",
    )
    for name in ["dev", "test", "qa", "prod"]:
        spec["environments"].append(
            dict(
                name=name,
                apim_service=f"apim-{name}",
                apim_api_id="orders",
                gateway_url=f"https://{name}.example.com/orders",
                backend_url=f"https://backend-{name}.example.com",
                temporal_namespace=f"orders-{name}",
                task_queue="orders",
                worker_deployment="orders-worker",
                release_version="1.0.0",
                git_sha="abcdef1234567",
                config_revision="1",
                secret_references=["keyvault://integration/oauth-client"],
            )
        )
    return spec


def save(client, path, spec, version=0):
    return client.put(path, headers=ADMIN, json=dict(version=version, spec=spec))


def transition(client, path, version, target):
    return client.post(
        path + "/transition",
        headers=ADMIN,
        json=dict(version=version, target=target, reason="Reviewed"),
    )


def approve(path):
    from datetime import date

    from backend.models import AppUser

    with SessionLocal() as db:
        i = db.get(Integration, path.split("/")[3])
        assert i is not None
        admin = db.scalar(select(AppUser).where(AppUser.email == ADMIN["x-forwarded-email"]))
        assert admin is not None
        i.design_approved = i.code_approved = True
        i.design_approver_id = i.code_approver_id = admin.id
        i.design_approval_date = i.code_approval_date = date.today()
        db.commit()


def plan(client, path, version, environment):
    return client.post(
        path + "/release-plans",
        headers=ADMIN,
        json=dict(version=version, environment=environment, reason="Promotion review"),
    )


def test_default_roundtrip_version_and_legacy_unchanged(client):
    path = url(client)
    initial = client.get(path, headers=USER).json()
    assert initial["version"] == 0 and initial["stage"] == "discovery"
    assert not initial["readiness"]["ready"]
    response = save(client, path, complete_spec())
    assert response.status_code == 200, response.text
    saved = response.json()
    assert saved["version"] == 1 and saved["spec"]["contract"]["api_version"] == "1.0"
    assert client.get(path, headers=USER).json() == saved
    assert save(client, path, {}, 0).status_code == 409
    legacy = client.get(path.removesuffix("/framework"), headers=USER).json()
    assert legacy["version"] == 2 and legacy["status"] == "planning"
    with SessionLocal() as db:
        entries = list(db.scalars(select(AuditEntry).where(AuditEntry.field == "framework.spec")))
        assert len(entries) == 1 and entries[0].changed_by_email == "admin@example.com"


@pytest.mark.parametrize(
    "body",
    [
        {"spec": {}},
        {"version": None, "spec": {}},
        {"version": "0", "spec": {}},
        {"version": 0, "spec": {}, "stage": "live"},
        {"version": 0, "spec": {"contract": {"secret": "oops"}}},
        {"version": 0, "spec": {"contract": {"repository_url": "javascript:alert(1)"}}},
        {
            "version": 0,
            "spec": {"contract": {"repository_url": "https://user:password@example.com"}},
        },
        {"version": 0, "spec": {"contract": {"openapi_url": "https://example.com?token=abc"}}},
        {"version": 0, "spec": {"orchestration": {"timezone": "Not/AZone"}}},
        {"version": 0, "spec": {"orchestration": {"retry_max_attempts": 0}}},
        {
            "version": 0,
            "spec": {"orchestration": {"retry_initial_seconds": 100, "retry_max_seconds": 1}},
        },
        {"version": 0, "spec": {"orchestration": {"heartbeat_timeout_seconds": 1000}}},
        {"version": 0, "spec": {"orchestration": {"cron": "* *"}}},
        {"version": 0, "spec": {"operations": {"slo_availability": 101}}},
        {"version": 0, "spec": {"environments": [{"name": "prod"}, {"name": "prod"}]}},
        {"version": 0, "spec": {"environments": [{"name": "dev", "git_sha": "not-a-sha"}]}},
        {
            "version": 0,
            "spec": {"environments": [{"name": "dev", "secret_references": ["raw-secret"]}]},
        },
        {"version": 0, "spec": {"ownership": {"business_owner": "password=hunter2"}}},
    ],
)
def test_strict_validation(client, body):
    response = client.put(url(client), headers=ADMIN, json=body)
    assert response.status_code == 422, response.text


def test_rbac_and_missing_deleted(client):
    path = url(client)
    assert client.put(path, headers=USER, json=dict(version=0, spec={})).status_code == 403
    assert (
        client.post(
            path + "/transition",
            headers=USER,
            json=dict(version=0, target="design", reason="Review"),
        ).status_code
        == 403
    )
    assert (
        client.post(
            path + "/release-plans",
            headers=USER,
            json=dict(version=0, environment="dev", reason="Review"),
        ).status_code
        == 403
    )
    assert client.get("/api/integrations/missing/framework", headers=ADMIN).status_code == 404
    with SessionLocal() as db:
        from backend.models import utcnow

        i = db.get(Integration, path.split("/")[3])
        assert i is not None
        i.deleted_at = utcnow()
        db.commit()
    assert client.get(path, headers=ADMIN).status_code == 404
    assert save(client, path, {}).status_code == 404
    assert transition(client, path, 0, "design").status_code == 404
    assert plan(client, path, 0, "dev").status_code == 404


def test_stage_sequence_gates_and_retirement(client):
    path = url(client)
    assert transition(client, path, 0, "live").status_code == 409
    assert transition(client, path, 0, "design").status_code == 200
    assert transition(client, path, 1, "development").status_code == 422
    assert save(client, path, complete_spec(), 1).status_code == 200
    assert transition(client, path, 2, "development").status_code == 200
    assert transition(client, path, 3, "validation").status_code == 200
    assert transition(client, path, 4, "ready").status_code == 422
    approve(path)
    assert transition(client, path, 4, "ready").status_code == 200
    assert transition(client, path, 5, "live").status_code == 422
    assert plan(client, path, 5, "prod").status_code == 422
    for version, env in enumerate(["dev", "test", "qa", "prod"], 5):
        response = plan(client, path, version, env)
        assert response.status_code == 201, response.text
    assert transition(client, path, 9, "live").status_code == 200
    assert transition(client, path, 10, "retired").status_code == 200
    assert transition(client, path, 11, "development").status_code == 409
    assert save(client, path, complete_spec(), 11).status_code == 409
    assert plan(client, path, 11, "prod").status_code == 422


def test_plan_snapshot_stays_immutable_and_edit_resets_stage(client):
    path = url(client)
    original = complete_spec()
    save(client, path, original)
    transition(client, path, 1, "design")
    transition(client, path, 2, "development")
    assert plan(client, path, 3, "test").status_code == 422
    response = plan(client, path, 3, "dev")
    assert response.status_code == 201, response.text
    assert response.json()["release_plans"][0]["status"] == "planned"
    assert plan(client, path, 3, "dev").status_code == 409
    transition(client, path, 4, "validation")
    changed = deepcopy(original)
    changed["contract"]["api_version"] = "2.0"
    response = save(client, path, changed, 5)
    assert response.json()["stage"] == "development"
    assert plan(client, path, 6, "test").status_code == 422
    with SessionLocal() as db:
        recorded = db.scalar(select(IntegrationReleasePlan))
        assert recorded is not None
        assert recorded.spec_snapshot["contract"]["api_version"] == "1.0"
        assert recorded.profile_version == 3
        assert recorded.created_by == "admin@example.com"
        fields = set(db.scalars(select(AuditEntry.field)))
        assert {"framework.spec", "framework.stage", "framework.release_plan"} <= fields


def test_database_compare_and_swap_rejects_stale_session(client):
    from fastapi import HTTPException

    from backend.auth import CurrentUser
    from backend.models import Role
    from backend.routers.framework import save as atomic_save

    path = url(client)
    save(client, path, {})
    iid = path.split("/")[3]
    with SessionLocal() as stale:
        p = stale.get(IntegrationFrameworkProfile, iid)
        assert p is not None
        integration = stale.get(Integration, iid)
        assert save(client, path, complete_spec(), 1).status_code == 200
        with pytest.raises(HTTPException) as error:
            atomic_save(
                stale,
                integration,
                p,
                1,
                p.spec,
                "design",
                CurrentUser(
                    id="unused",
                    email="admin@example.com",
                    display_name="Admin",
                    role=Role.integration,
                    groups=[],
                ),
                "framework.stage",
                "discovery",
                "design",
            )
        assert error.value.status_code == 409
    assert client.get(path, headers=ADMIN).json()["version"] == 2


@pytest.mark.parametrize(
    "cron",
    [
        "99 99 99 99 99",
        "*/0 * * * *",
        "60 * * * *",
        "* 24 * * *",
        "* * 0 * *",
        "* * * 13 *",
        "* * * * 8",
        "10-2 * * * *",
        "*, * * * *",
        "*/999 * * * *",
    ],
)
def test_invalid_cron_ranges(client, cron):
    assert save(client, url(client), {"orchestration": {"cron": cron}}).status_code == 422


@pytest.mark.parametrize("cron", ["*/15 8-17 * * 1-5", "0 0 1,15 * *", "1-59/2 0 1 1 0,7"])
def test_valid_cron_ranges(client, cron):
    assert save(client, url(client), {"orchestration": {"cron": cron}}).status_code == 200


def test_spec_edits_invalidate_approvals_with_audit_and_lock(client):
    path = url(client)
    save(client, path, complete_spec())
    approve(path)
    legacy_path = path.removesuffix("/framework")
    before = client.get(legacy_path, headers=ADMIN).json()
    changed = complete_spec()
    changed["contract"]["api_version"] = "2.0"
    assert save(client, path, changed, 1).status_code == 200
    after = client.get(legacy_path, headers=ADMIN).json()
    assert after["version"] == before["version"] + 1
    for key in ("design_approved", "code_approved"):
        assert after[key] is False
    for key in ("design_approval_date", "code_approval_date"):
        assert after[key] is None
    assert (
        client.patch(
            legacy_path, headers=ADMIN, json={"version": before["version"], "design_approved": True}
        ).status_code
        == 409
    )
    with SessionLocal() as db:
        fields = set(db.scalars(select(AuditEntry.field)))
        assert {
            "design_approved",
            "code_approved",
            "design_approver",
            "code_approver",
            "design_approval_date",
            "code_approval_date",
        } <= fields
    # A no-op replacement preserves current approvals.
    approve(path)
    assert save(client, path, changed, 2).status_code == 200
    assert client.get(legacy_path, headers=ADMIN).json()["design_approved"] is True


def test_framework_keyword_search_and_secret_reference_exclusion(client):
    path = url(client)
    spec = complete_spec()
    spec["ownership"]["technical_owner"] = "DistinctOwner"
    spec["orchestration"]["workflow_type"] = "DistinctWorkflow"
    spec["environments"][0]["apim_service"] = "DistinctGateway"
    spec["environments"][0]["secret_references"] = ["vault://DistinctSecretReference"]
    save(client, path, spec)
    for term in ["DistinctOwner", "DistinctWorkflow", "DistinctGateway"]:
        assert (
            client.get("/api/integrations", headers=USER, params={"q": term}).json()["total"] == 1
        )
    assert (
        client.get(
            "/api/integrations", headers=USER, params={"q": "DistinctSecretReference"}
        ).json()["total"]
        == 0
    )
    spec["orchestration"]["workflow_type"] = "ChangedWorkflow"
    save(client, path, spec, 1)
    assert (
        client.get("/api/integrations", headers=USER, params={"q": "DistinctWorkflow"}).json()[
            "total"
        ]
        == 0
    )
    assert (
        client.get("/api/integrations", headers=USER, params={"q": "ChangedWorkflow"}).json()[
            "total"
        ]
        == 1
    )


@pytest.mark.parametrize(
    "section,field",
    [
        ("contract", "data_entities"),
        ("contract", "scopes"),
        ("orchestration", "non_retryable_errors"),
    ],
)
def test_list_items_cannot_be_blank(client, section, field):
    assert save(client, url(client), {section: {field: ["   "]}}).status_code == 422


@pytest.mark.parametrize("version", ["2.0", "latest", "3", "3.x", "4.0.0"])
def test_openapi_version_must_be_3_x_semver(client, version):
    assert save(client, url(client), {"contract": {"openapi_version": version}}).status_code == 422


def test_framework_refreshes_embedding_only_after_commit(client, monkeypatch):
    from backend.routers import framework

    path = url(client)
    called = []

    def refresh(db, iid):
        with SessionLocal() as reader:
            profile = reader.get(IntegrationFrameworkProfile, iid)
            assert profile is not None
            assert profile.version == 1
        called.append(iid)

    monkeypatch.setattr(framework, "update_embedding_post_commit", refresh)
    assert save(client, path, complete_spec()).status_code == 200
    assert called == [path.split("/")[3]]


def test_release_plan_rejects_missing_environment(client):
    path = url(client)
    spec = complete_spec()
    spec["environments"] = [env for env in spec["environments"] if env["name"] == "dev"]
    assert save(client, path, spec).status_code == 200
    assert transition(client, path, 1, "design").status_code == 200
    assert transition(client, path, 2, "development").status_code == 200
    response = plan(client, path, 3, "test")
    assert response.status_code == 422
    assert "Selected environment needs complete" in response.json()["detail"]
