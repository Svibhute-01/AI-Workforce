"""API tests for POST /api/projects/{id}/architect/run and GET /api/projects/{id}/architecture.

The endpoints run the real Architect agent and its LangGraph stage + validation gate against
the SQLite test database; only the LLM is scripted.
"""

from types import SimpleNamespace

import pytest

from app.llm.gemini_provider import ProviderConfigurationError
from app.models import ArchDesign
from sqlalchemy import select

from .architecture_fixtures import ScriptedArchitectProvider, mutated, registration_hld, registration_lld
from .conftest import ScriptedProvider
from .plan_fixtures import registration_plan

RUN = "/api/projects/{}/architect/run"
GET = "/api/projects/{}/architecture"
PM_RUN = "/api/projects/{}/project-manager/run"


@pytest.fixture
def requirements_only(client, make_user, make_project, seed_requirements):
    user = make_user()
    project_id = make_project(user)
    seed_requirements(project_id)
    return SimpleNamespace(id=project_id, headers=user["headers"], user=user)


@pytest.fixture
def project(client, requirements_only, use_provider):
    """Requirements Analyst output plus a project plan made by the real Project Manager endpoint."""
    use_provider(ScriptedProvider(registration_plan))
    response = client.post(PM_RUN.format(requirements_only.id), headers=requirements_only.headers)
    assert response.status_code == 200, response.text
    return requirements_only


def run(client, project, use_provider, hld=(registration_hld,), lld=(registration_lld,)):
    provider = use_provider(ScriptedArchitectProvider(hld=list(hld), lld=list(lld)))
    return client.post(RUN.format(project.id), headers=project.headers), provider


def test_run_generates_validates_and_returns_the_architecture(client, project, use_provider):
    response, provider = run(client, project, use_provider)

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] == "COMPLETED"
    assert len(body["hld"]["components"]) == 4 and len(body["lld"]["modules"]) == 3
    assert body["hld"]["style"]["grounding"] == "ASSUMED"
    assert [a["name"] for a in body["hld"]["actors"]] == ["Customer"]
    assert [n["node_id"] for n in body["hld"]["deployment"]] == ["DN1", "DN2", "DN3"]
    assert body["architecture"]["counts"]["actors"] == 1 and body["architecture"]["counts"]["deployment_nodes"] == 3
    assert body["architecture"]["counts"]["apis"] == 1
    assert body["architecture"]["requirements_changed"] is False and body["architecture"]["plan_changed"] is False
    # Derived views: the diagram follows the components / relationships, the matrix follows the cited ids.
    assert [n["id"] for n in body["diagram"]["nodes"]] == ["C1", "C2", "C3", "C4"]
    assert [e["id"] for e in body["diagram"]["edges"]] == ["R1", "R2", "R3"]
    assert any(row["requirement_id"] == "REQ-1" and row["status"] == "COVERED" for row in body["traceability"])
    # Detailed view: components with the modules, endpoints and tables the LLD places in them.
    containers = {c["id"]: c for c in body["diagram"]["detailed"]["containers"]}
    assert [m["id"] for m in containers["C2"]["modules"]] == ["M1", "M2", "M3"]
    assert containers["C2"]["modules"][0]["endpoints"][0]["path"] == "/api/register"
    assert [t["name"] for t in containers["C3"]["tables"]] == ["customer_accounts"]
    assert {item["kind"] for item in body["open_items"]} == {"ASSUMED", "UNKNOWN"}
    assert body["latest_agent_run"]["status"] == "COMPLETED"
    assert len(provider.hld_calls) == 1 and len(provider.lld_calls) == 1


def test_get_returns_the_saved_architecture(client, project, use_provider):
    created, _ = run(client, project, use_provider)

    fetched = client.get(GET.format(project.id), headers=project.headers)

    assert fetched.status_code == 200
    body = fetched.json()
    assert body["status"] == "COMPLETED"
    for key in ("hld", "lld", "diagram", "traceability", "open_items"):
        assert body[key] == created.json()[key]


def test_get_before_any_run_is_not_generated(client, project):
    body = client.get(GET.format(project.id), headers=project.headers).json()
    assert body["status"] == "NOT_GENERATED"
    assert body["hld"] is None and body["lld"] is None and body["diagram"] is None
    assert body["traceability"] == [] and body["latest_agent_run"] is None


def test_run_without_a_project_plan_is_409(client, requirements_only, use_provider):
    response, provider = run(client, requirements_only, use_provider)
    assert response.status_code == 409
    assert "Project Manager" in response.json()["detail"]
    assert provider.hld_calls == []


def test_run_without_requirements_is_409(client, make_user, make_project, use_provider):
    user = make_user()
    empty = SimpleNamespace(id=make_project(user), headers=user["headers"])
    response, provider = run(client, empty, use_provider)
    assert response.status_code == 409
    assert provider.hld_calls == []


def test_invented_requirement_ids_return_422_and_nothing_is_saved(client, project, use_provider, db):
    def unknown_requirement(d):
        d["components"][0]["requirement_ids"].append("REQ-999")

    response, provider = run(client, project, use_provider, hld=[mutated(registration_hld, unknown_requirement)])

    assert response.status_code == 422
    assert "REQ-999" in response.json()["detail"]
    assert len(provider.hld_calls) == 2
    assert db.scalars(select(ArchDesign)).all() == []
    state = client.get(GET.format(project.id), headers=project.headers).json()
    assert state["status"] == "FAILED" and state["hld"] is None
    assert "REQ-999" in state["latest_agent_run"]["error"]


def test_inconsistent_low_level_design_returns_422(client, project, use_provider):
    def api_with_unknown_model(d):
        d["apis"][0]["request_model_id"] = "DM404"

    response, _ = run(client, project, use_provider, lld=[mutated(registration_lld, api_with_unknown_model)])
    assert response.status_code == 422 and "DM404" in response.json()["detail"]


def test_gemini_failure_returns_503(client, project, use_provider):
    response, _ = run(
        client, project, use_provider, hld=[ProviderConfigurationError("Gemini is unavailable")]
    )
    assert response.status_code == 503
    assert "Gemini is unavailable" in response.json()["detail"]
    assert client.get(GET.format(project.id), headers=project.headers).json()["status"] == "FAILED"


def test_failed_regeneration_keeps_serving_the_previous_design(client, project, use_provider):
    first, _ = run(client, project, use_provider)
    assert first.status_code == 200

    def broken(d):
        d["relationships"][0]["target_component_id"] = "C99"

    second, _ = run(client, project, use_provider, hld=[mutated(registration_hld, broken)])
    assert second.status_code == 422

    body = client.get(GET.format(project.id), headers=project.headers).json()
    assert body["status"] == "FAILED"  # the most recent run failed ...
    assert body["hld"] == first.json()["hld"]  # ... but the earlier valid design is still returned
    assert body["latest_agent_run"]["error"]


def test_architecture_reports_when_its_inputs_changed_afterwards(client, project, use_provider, db):
    run(client, project, use_provider)
    design = db.scalars(select(ArchDesign)).one()
    design.requirements_run_id = design.requirements_run_id + 1000
    design.plan_run_id = (design.plan_run_id or 0) + 1000
    db.commit()

    info = client.get(GET.format(project.id), headers=project.headers).json()["architecture"]
    assert info["requirements_changed"] is True and info["plan_changed"] is True


def test_endpoints_require_authentication_and_project_ownership(client, project, make_user, use_provider):
    run(client, project, use_provider)
    other = make_user()

    assert client.post(RUN.format(project.id)).status_code in (401, 403)
    assert client.get(GET.format(project.id)).status_code in (401, 403)
    assert client.post(RUN.format(project.id), headers=other["headers"]).status_code == 404
    assert client.get(GET.format(project.id), headers=other["headers"]).status_code == 404
