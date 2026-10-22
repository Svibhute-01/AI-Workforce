"""API-level tests for POST /api/projects/{id}/workflow/run.

The real LangGraph pipeline (Requirements Analyst -> Project Manager -> System Architect, each
followed by its validation gate) and the real Project Manager and Architect agents run against
the SQLite test database. Only the Requirements Analyst's LLM/vector-store call is replaced, by
a function that stores the analyst's output exactly as the real agent would, and the LLM
itself is scripted.
"""

from types import SimpleNamespace

import pytest

from app.agents.pm_context import MissingRequirementsError
from app.agents.project_manager_agent import PlanValidationError
from app.api.workflow import get_vector_store
from app.main import app
from app.models import AgentRun, Document

from .architecture_fixtures import ScriptedArchitectProvider, mutated, registration_hld, registration_lld
from .conftest import ScriptedProvider
from .plan_fixtures import registration_plan

RUN = "/api/projects/{}/workflow/run"


class PipelineProvider(ScriptedArchitectProvider):
    """Plan responses for the Project Manager plus design responses for the System Architect."""

    def __init__(self, hld=(registration_hld,), lld=(registration_lld,)):
        super().__init__(hld=list(hld), lld=list(lld))
        self._plan = ScriptedProvider(registration_plan)

    def generate_project_plan(self, *args, **kwargs):
        return self._plan.generate_project_plan(*args, **kwargs)


@pytest.fixture
def project(client, make_user, make_project):
    user = make_user()
    return SimpleNamespace(user=user, id=make_project(user), headers=user["headers"])


@pytest.fixture
def processed_document(db):
    def _add(project_id: int, status: str = "COMPLETED"):
        db.add(
            Document(
                project_id=project_id, filename="SRS.pdf", file_type="application/pdf",
                file_size=1, storage_path="SRS.pdf", processing_status=status,
            )
        )
        db.commit()

    return _add


@pytest.fixture
def fake_analyst(monkeypatch, db, seed_requirements):
    """Replace only the analyst's LLM call; its saved output matches the real agent's."""
    calls = []

    def _install(project_id: int):
        def fake_run(db_session, project, provider, vector_store):
            calls.append(project.id)
            ids = seed_requirements(project_id)
            run = db_session.get(AgentRun, ids["run_id"])
            analysis = SimpleNamespace(
                functional_requirements=[object()] * 7,
                non_functional_requirements=[object()] * 3,
                user_stories=[object()] * 3,
                acceptance_criteria=[object()] * 7,
                ambiguities=[object()] * 4,
                risks=[],
            )
            return run, analysis

        monkeypatch.setattr("app.workflow.stages.run_requirements_analysis", fake_run)
        app.dependency_overrides[get_vector_store] = lambda: object()
        return ids_holder

    ids_holder = SimpleNamespace(calls=calls)
    ids_holder.install = _install
    return ids_holder


def test_workflow_runs_analyst_project_manager_and_architect_through_the_graph(
    client, project, processed_document, fake_analyst, use_provider
):
    processed_document(project.id)
    fake_analyst.install(project.id)
    use_provider(PipelineProvider())

    response = client.post(RUN.format(project.id), headers=project.headers)

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["workflow_status"] == "COMPLETED"
    assert body["project_id"] == project.id
    assert body["current_agent"] == "System Architect AI"
    assert body["requirements"]["functional_requirements"] == 7
    assert body["project_plan"]["tasks_generated"] == 15
    assert body["architecture"]["counts"]["components"] == 4
    # Each agent worked from the run before it.
    assert body["project_plan"]["requirements_run_id"] == body["requirements"]["agent_run_id"]
    assert body["architecture"]["requirements_run_id"] == body["requirements"]["agent_run_id"]
    assert body["architecture"]["plan_run_id"] == body["project_plan"]["agent_run_id"]
    assert list(body["validation_results"]) == ["requirements", "project_plan", "architecture"]
    assert all(item["passed"] for item in body["validation_results"].values())
    # The workflow response carries a summary; the design itself is served by GET /architecture.
    assert "design" not in body["architecture"] and "reference_ids" not in body["architecture"]
    # Developer and QA do not exist yet.
    assert not {"code", "test_results"} & set(body)

    stored = client.get(f"/api/projects/{project.id}/architecture", headers=project.headers).json()
    assert stored["status"] == "COMPLETED" and len(stored["hld"]["components"]) == 4


def test_missing_srs_stops_before_the_analyst_runs(client, project, fake_analyst, use_provider):
    fake_analyst.install(project.id)
    use_provider(ScriptedProvider(registration_plan))

    response = client.post(RUN.format(project.id), headers=project.headers)

    assert response.status_code == 409
    assert "SRS" in response.json()["detail"]
    assert fake_analyst.calls == []


def test_unprocessed_srs_is_treated_as_missing(client, project, processed_document, fake_analyst, use_provider):
    processed_document(project.id, status="PROCESSING")
    fake_analyst.install(project.id)
    use_provider(ScriptedProvider(registration_plan))

    assert client.post(RUN.format(project.id), headers=project.headers).status_code == 409
    assert fake_analyst.calls == []


def test_project_manager_plan_validation_failure_maps_to_422_and_reports_progress(
    client, project, processed_document, fake_analyst, use_provider, monkeypatch
):
    processed_document(project.id)
    fake_analyst.install(project.id)
    use_provider(ScriptedProvider(registration_plan))

    def reject(*args, **kwargs):
        raise PlanValidationError("The generated project plan failed validation", ["bad dependency"])

    monkeypatch.setattr("app.workflow.stages.run_project_manager", reject)

    response = client.post(RUN.format(project.id), headers=project.headers)

    assert response.status_code == 422
    detail = response.json()["detail"]
    assert "project_plan" in detail and "failed validation" in detail
    assert "Completed stages: requirements" in detail


def test_project_manager_missing_requirements_maps_to_409(
    client, project, processed_document, fake_analyst, use_provider, monkeypatch
):
    processed_document(project.id)
    fake_analyst.install(project.id)
    use_provider(ScriptedProvider(registration_plan))

    def missing(*args, **kwargs):
        raise MissingRequirementsError("No completed Requirements Analyst output exists for this project.")

    monkeypatch.setattr("app.workflow.stages.run_project_manager", missing)

    assert client.post(RUN.format(project.id), headers=project.headers).status_code == 409


def test_unexpected_agent_failure_maps_to_503(
    client, project, processed_document, fake_analyst, use_provider, monkeypatch
):
    processed_document(project.id)
    fake_analyst.install(project.id)
    use_provider(ScriptedProvider(registration_plan))

    def broken(*args, **kwargs):
        raise RuntimeError("LLM provider unavailable")

    monkeypatch.setattr("app.workflow.stages.run_project_manager", broken)

    response = client.post(RUN.format(project.id), headers=project.headers)
    assert response.status_code == 503
    assert "LLM provider unavailable" in response.json()["detail"]


def test_analyst_failure_stops_the_workflow_before_the_project_manager(
    client, project, processed_document, use_provider, monkeypatch
):
    processed_document(project.id)
    provider = use_provider(ScriptedProvider(registration_plan))
    app.dependency_overrides[get_vector_store] = lambda: object()

    def broken(*args, **kwargs):
        raise RuntimeError("embedding service down")

    monkeypatch.setattr("app.workflow.stages.run_requirements_analysis", broken)

    response = client.post(RUN.format(project.id), headers=project.headers)

    assert response.status_code == 503
    assert "embedding service down" in response.json()["detail"]
    assert provider.calls == []  # the Project Manager never asked the LLM for a plan


def test_workflow_requires_authentication_and_project_ownership(client, project, make_user):
    assert client.post(RUN.format(project.id)).status_code in (401, 403)
    other = make_user()
    assert client.post(RUN.format(project.id), headers=other["headers"]).status_code == 404


def test_invalid_architecture_stops_the_workflow_after_the_earlier_stages(
    client, project, processed_document, fake_analyst, use_provider
):
    processed_document(project.id)
    fake_analyst.install(project.id)

    def unknown_requirement(d):
        d["components"][0]["requirement_ids"].append("REQ-999")

    provider = use_provider(PipelineProvider(hld=[mutated(registration_hld, unknown_requirement)]))

    response = client.post(RUN.format(project.id), headers=project.headers)

    assert response.status_code == 422
    detail = response.json()["detail"]
    assert "architecture" in detail and "REQ-999" in detail
    assert "Completed stages: requirements, project_plan" in detail
    assert len(provider.hld_calls) == 2  # one repair attempt, then the workflow stopped
    assert client.get(f"/api/projects/{project.id}/architecture", headers=project.headers).json()["hld"] is None


def test_gemini_failure_in_the_architect_stage_maps_to_503(
    client, project, processed_document, fake_analyst, use_provider
):
    processed_document(project.id)
    fake_analyst.install(project.id)
    use_provider(PipelineProvider(hld=[RuntimeError("Gemini is unavailable")]))

    response = client.post(RUN.format(project.id), headers=project.headers)

    assert response.status_code == 503
    assert "Gemini is unavailable" in response.json()["detail"]
