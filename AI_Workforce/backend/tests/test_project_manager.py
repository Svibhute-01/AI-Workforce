import json
import time
from types import SimpleNamespace

import pytest
from pydantic import ValidationError
from sqlalchemy import func, select

from app.agents.pm_context import build_requirements_context
from app.agents.pm_validation import compute_execution_order, normalize_plan, validate_plan
from app.llm import gemini_provider
from app.llm.gemini_provider import GeminiProvider, ProviderConfigurationError
from app.models import (
    AgentRun,
    PMEpic,
    PMMilestone,
    PMPlan,
    PMRisk,
    PMSprint,
    PMTask,
    PMTaskDependency,
    Project,
)
from app.schemas_pm import ProjectPlan

from .conftest import ScriptedProvider
from .plan_fixtures import mutated, registration_plan, registration_plan_dict

RUN = "/api/projects/{}/project-manager/run"
PLAN = "/api/projects/{}/project-manager"


@pytest.fixture
def project(client, make_user, make_project, seed_requirements):
    user = make_user()
    project_id = make_project(user)
    ids = seed_requirements(project_id)
    return SimpleNamespace(user=user, id=project_id, ids=ids, headers=user["headers"])


def run(client, project, provider=None, use_provider=None):
    if provider is not None:
        use_provider(provider)
    return client.post(RUN.format(project.id), headers=project.headers)


def context_for(db, project_id):
    return build_requirements_context(db, db.get(Project, project_id))


# ---------------------------------------------------------------------------
# Requirements Analyst -> Project Manager flow
# ---------------------------------------------------------------------------


def test_valid_flow_generates_and_returns_a_grounded_plan(client, project, use_provider):
    provider = ScriptedProvider(registration_plan)
    response = run(client, project, provider, use_provider)
    assert response.status_code == 200, response.text
    body = response.json()

    assert body["status"] == "COMPLETED"
    assert len(body["tasks"]) == 15 and len(body["epics"]) == 4
    assert [s["sprint_id"] for s in body["sprints"]] == ["S1", "S2", "S3"]
    assert len(provider.calls) == 1 and provider.calls[0]["feedback"] is None

    # The PM received the analyst's structured output (with ids), not raw SRS text.
    payload = provider.calls[0]["requirements"]
    titles = {r["title"] for r in payload["functional_requirements"]}
    assert {"Customer Registration", "Duplicate Email Handling", "Confirmation Email"} <= titles
    assert payload["functional_requirements"][0]["id"].startswith("REQ-")

    tasks = {t["task_id"]: t for t in body["tasks"]}
    # Traceability: EXPLICIT tasks cite ids, and source references are derived from them.
    dup = tasks["T8"]
    assert dup["grounding"] == "EXPLICIT" and dup["related_requirement_title"] == "Duplicate Email Handling"
    assert dup["source_references"] and dup["source_references"][0]["document"] == "SRS.pdf"
    # Inferred and ambiguous work is labelled, with a reason.
    assert tasks["T1"]["grounding"] == "INFERRED" and tasks["T1"]["rationale"]
    assert tasks["T3"]["grounding"] == "AMBIGUOUS" and tasks["T14"]["grounding"] == "AMBIGUOUS"
    # Nothing outside the SRS was invented.
    text = json.dumps(body).lower()
    for invented in ("biometric", "oauth", "payment", "social login"):
        assert invented not in text
    assert {t["story_points"] for t in body["tasks"]} <= {1, 2, 3, 5, 8, 13}
    assert body["plan"]["definition_of_done"] and body["plan"]["requirements_changed"] is False


def test_get_endpoints_return_the_persisted_plan(client, project, use_provider):
    run(client, project, ScriptedProvider(registration_plan), use_provider)
    base = f"/api/projects/{project.id}"
    full = client.get(PLAN.format(project.id), headers=project.headers).json()
    assert len(client.get(f"{base}/tasks", headers=project.headers).json()) == 15
    assert len(client.get(f"{base}/sprints", headers=project.headers).json()) == 3
    assert len(client.get(f"{base}/milestones", headers=project.headers).json()) == 3
    assert len(client.get(f"{base}/risks", headers=project.headers).json()) == 3
    deps = client.get(f"{base}/dependencies", headers=project.headers).json()
    assert len(deps) == len(full["dependencies"]) == 18
    assert any(d["dependency_type"] == "EXTERNAL" and d["depends_on_task_id"] is None for d in deps)
    assert all(d["is_blocking"] for d in full["blocking_dependencies"]) and full["blocking_dependencies"]


def test_get_before_any_run_is_an_empty_state(client, project):
    body = client.get(PLAN.format(project.id), headers=project.headers).json()
    assert body["status"] == "NOT_GENERATED" and body["plan"] is None and body["tasks"] == []


# ---------------------------------------------------------------------------
# Missing Requirements Analyst output
# ---------------------------------------------------------------------------


def test_missing_requirements_output_is_refused(client, make_user, make_project, use_provider, db):
    user = make_user()
    project_id = make_project(user)
    provider = ScriptedProvider(registration_plan)
    use_provider(provider)
    response = client.post(RUN.format(project_id), headers=user["headers"])
    assert response.status_code == 409
    assert "Requirements Analyst" in response.json()["detail"]
    assert provider.calls == []  # the LLM was never called
    assert db.scalar(select(func.count()).select_from(PMPlan)) == 0
    assert db.scalar(select(func.count()).select_from(AgentRun)) == 0


def test_completed_analyst_run_without_requirements_is_refused(client, make_user, make_project, use_provider, db):
    user = make_user()
    project_id = make_project(user)
    db.add(AgentRun(project_id=project_id, agent_name="Requirements Analyst AI", status="COMPLETED", output_summary={}))
    db.commit()
    provider = ScriptedProvider(registration_plan)
    use_provider(provider)
    response = client.post(RUN.format(project_id), headers=user["headers"])
    assert response.status_code == 409 and provider.calls == []


def test_failed_analyst_run_does_not_count(client, make_user, make_project, use_provider, db):
    user = make_user()
    project_id = make_project(user)
    db.add(AgentRun(project_id=project_id, agent_name="Requirements Analyst AI", status="FAILED"))
    db.commit()
    use_provider(ScriptedProvider(registration_plan))
    assert client.post(RUN.format(project_id), headers=user["headers"]).status_code == 409


# ---------------------------------------------------------------------------
# Malformed / invalid LLM output
# ---------------------------------------------------------------------------


def _bad_schema_error():
    try:
        ProjectPlan.model_validate({"execution_summary": "x", "definition_of_done": {"items": []}})
    except ValidationError as exc:
        return exc


def test_malformed_output_is_not_stored_and_run_is_failed(client, project, use_provider, db):
    provider = ScriptedProvider(_bad_schema_error())
    response = run(client, project, provider, use_provider)
    assert response.status_code == 422
    assert "malformed" in response.json()["detail"].lower()
    assert len(provider.calls) == 2 and "not valid" in provider.calls[1]["feedback"][0]
    assert db.scalar(select(func.count()).select_from(PMTask)) == 0
    failed = db.scalars(select(AgentRun).where(AgentRun.agent_name == "Project Manager AI")).one()
    assert failed.status == "FAILED" and failed.error
    body = client.get(PLAN.format(project.id), headers=project.headers).json()
    assert body["status"] == "FAILED" and body["plan"] is None


def test_provider_outage_returns_503_and_stores_nothing(client, project, use_provider, db):
    response = run(client, project, ScriptedProvider(ProviderConfigurationError("quota exceeded")), use_provider)
    assert response.status_code == 503
    assert db.scalar(select(func.count()).select_from(PMPlan)) == 0


def test_repairs_a_plan_with_unknown_references_after_feedback(client, project, use_provider):
    def broken(payload):
        return mutated(payload, lambda d: d["tasks"][3].update(related_requirement_id="REQ-99999"))

    provider = ScriptedProvider(broken, registration_plan)
    response = run(client, project, provider, use_provider)
    assert response.status_code == 200
    assert len(provider.calls) == 2
    assert any("REQ-99999" in problem for problem in provider.calls[1]["feedback"])
    steps = response.json()["latest_agent_run"]["output_summary"]["steps"]
    assert [s["status"] for s in steps if s["node"] == "validate_plan"] == ["issues", "ok"]
    assert response.json()["latest_agent_run"]["output_summary"]["attempts"] == 2


def test_plan_that_stays_invalid_is_rejected_and_never_saved(client, project, use_provider, db):
    def broken(payload):
        return mutated(payload, lambda d: d["tasks"][3].update(related_requirement_id="REQ-99999"))

    response = run(client, project, ScriptedProvider(broken), use_provider)
    assert response.status_code == 422 and "REQ-99999" in response.json()["detail"]
    assert db.scalar(select(func.count()).select_from(PMTask)) == 0
    assert db.scalar(select(func.count()).select_from(PMPlan)) == 0


def test_schema_rules_reject_non_fibonacci_points_and_unknown_roles():
    good = registration_plan_dict(_payload_stub())
    for change in ({"story_points": 4}, {"suggested_role": "Wizard"}, {"priority": "URGENT"}, {"grounding": "GUESS"}):
        bad = json.loads(json.dumps(good))
        bad["tasks"][0].update(change)
        with pytest.raises(ValidationError):
            ProjectPlan.model_validate(bad)


def _payload_stub():
    """Minimal payload with the titles the fixture looks up (ids need not be real here)."""
    titles = ["Customer Registration", "Email Validation", "Password Requirement", "Duplicate Email Handling",
              "Successful Registration", "Confirmation Email", "Registration Response"]
    stories = ["Register with email and password", "Receive confirmation email", "Reject duplicate registration"]
    return {
        "functional_requirements": [{"id": f"REQ-{i}", "title": t} for i, t in enumerate(titles, 1)],
        "non_functional_requirements": [{"id": f"NFR-{i}", "category": c} for i, c in enumerate(["Performance", "Security", "Reliability"], 1)],
        "user_stories": [{"id": f"US-{i}", "title": t} for i, t in enumerate(stories, 1)],
        "acceptance_criteria": [{"id": f"AC-{i}"} for i in range(1, 8)],
        "ambiguities": [{"id": f"AMB-{i}"} for i in range(1, 5)],
        "dependencies": [{"id": f"DEP-{i}"} for i in range(1, 4)],
        "constraints": [{"id": f"CON-{i}"} for i in range(1, 3)],
    }


class FakeGeminiClient:
    def __init__(self, *texts):
        self.texts = list(texts)
        self.prompts = []
        self.models = SimpleNamespace(generate_content=self._generate)

    def _generate(self, model, contents, config):
        self.prompts.append(contents)
        text = self.texts[min(len(self.prompts), len(self.texts)) - 1]
        return SimpleNamespace(parsed=None, text=text)


def gemini_with(client) -> GeminiProvider:
    provider = object.__new__(GeminiProvider)
    provider._client, provider._model = client, "test-model"
    return provider


def test_gemini_provider_rejects_malformed_json_after_one_retry(monkeypatch):
    monkeypatch.setattr(time, "sleep", lambda _: None)
    fake = FakeGeminiClient("{not json", "still {not json")
    with pytest.raises(ProviderConfigurationError):
        gemini_with(fake).generate_project_plan("P", "", {"a": 1}, {})
    assert len(fake.prompts) == 2
    assert "REJECTED" in fake.prompts[1]  # retry carries the parse failure back to the model


def test_gemini_provider_rejects_schema_violations(monkeypatch):
    monkeypatch.setattr(time, "sleep", lambda _: None)
    data = registration_plan_dict(_payload_stub())
    data["tasks"][0]["story_points"] = 4
    fake = FakeGeminiClient(json.dumps(data))
    with pytest.raises(ProviderConfigurationError):
        gemini_with(fake).generate_project_plan("P", "", {}, {})
    assert "story_points must be one of" in fake.prompts[1]


def test_gemini_provider_parses_valid_json_and_sends_the_analyst_output(monkeypatch):
    monkeypatch.setattr(time, "sleep", lambda _: None)
    payload = _payload_stub()
    fake = FakeGeminiClient(json.dumps(registration_plan_dict(payload)))
    plan = gemini_with(fake).generate_project_plan("Reg", "desc", payload, {"start_date": None}, ["fix X"])
    assert len(plan.tasks) == 15
    prompt = fake.prompts[0]
    assert "Customer Registration" in prompt and "REQ-1" in prompt and "fix X" in prompt
    assert "Do not re-derive requirements" in prompt


# ---------------------------------------------------------------------------
# Project isolation
# ---------------------------------------------------------------------------


def test_projects_never_see_each_others_plans_or_requirements(client, make_user, make_project, seed_requirements, use_provider, db):
    user_a, user_b = make_user(), make_user()
    a, b = make_project(user_a, "Project A"), make_project(user_b, "Project B")
    seed_requirements(a)
    seed_requirements(b)
    provider = ScriptedProvider(registration_plan)
    use_provider(provider)

    assert client.post(RUN.format(a), headers=user_a["headers"]).status_code == 200
    # Project B has requirements but has not run the PM: it must see nothing of A's plan.
    b_view = client.get(PLAN.format(b), headers=user_b["headers"]).json()
    assert b_view["status"] == "NOT_GENERATED" and b_view["tasks"] == []
    assert client.get(f"/api/projects/{b}/tasks", headers=user_b["headers"]).json() == []

    assert client.post(RUN.format(b), headers=user_b["headers"]).status_code == 200
    a_ids = {r["id"] for r in provider.calls[0]["requirements"]["functional_requirements"]}
    b_ids = {r["id"] for r in provider.calls[1]["requirements"]["functional_requirements"]}
    assert a_ids.isdisjoint(b_ids)  # each prompt contained only its own project's requirements

    for project_id in (a, b):
        for model in (PMTask, PMEpic, PMSprint, PMMilestone, PMRisk, PMTaskDependency):
            assert db.scalar(select(func.count()).select_from(model).where(model.project_id == project_id)) > 0
    assert db.scalar(select(func.count()).select_from(PMPlan)) == 2
    a_plan = client.get(PLAN.format(a), headers=user_a["headers"]).json()
    assert all(t["related_requirement_id"] in a_ids or t["related_requirement_id"] is None for t in a_plan["tasks"])


def test_llm_citing_another_projects_requirement_is_rejected(client, make_user, make_project, seed_requirements, use_provider, db):
    user_a, user_b = make_user(), make_user()
    a, b = make_project(user_a, "A"), make_project(user_b, "B")
    seed_requirements(a)
    b_ids = seed_requirements(b)
    foreign = b_ids["REQ"]["Customer Registration"]

    def leaks(payload):
        return mutated(payload, lambda d: d["tasks"][3].update(related_requirement_id=foreign))

    response = client.post(RUN.format(a), headers=user_a["headers"]) if use_provider(ScriptedProvider(leaks)) else None
    assert response.status_code == 422 and foreign in response.json()["detail"]
    assert db.scalar(select(func.count()).select_from(PMTask).where(PMTask.project_id == a)) == 0


# ---------------------------------------------------------------------------
# Task dependencies
# ---------------------------------------------------------------------------


def _issues(db, project, mutate):
    context = context_for(db, project.id)
    plan = mutated(context.payload, mutate) if mutate else registration_plan(context.payload)
    return validate_plan(plan, context), plan


def test_good_plan_has_no_errors_and_full_coverage(db, project):
    issues, _ = _issues(db, project, None)
    assert issues.errors == [] and issues.coverage_gaps == []


def test_execution_order_respects_every_dependency(client, project, use_provider):
    body = run(client, project, ScriptedProvider(registration_plan), use_provider).json()
    order = body["plan"]["execution_order"]
    position = {task_id: i for i, task_id in enumerate(order)}
    assert sorted(order) == sorted(t["task_id"] for t in body["tasks"])
    for dep in body["dependencies"]:
        if dep["depends_on_task_id"]:
            assert position[dep["depends_on_task_id"]] < position[dep["task_id"]]
    assert [t["execution_index"] for t in body["tasks"]] == sorted(t["execution_index"] for t in body["tasks"])
    tasks = {t["task_id"]: t for t in body["tasks"]}
    assert tasks["T11"]["dependencies"] == ["T9", "T10"]  # confirmation email needs the account and email delivery


def test_dependency_cycle_is_rejected(db, project):
    issues, _ = _issues(db, project, lambda d: d["dependencies"].append(
        {"task_id": "T1", "depends_on_task_id": "T15", "dependency_type": "TECHNICAL", "description": "x", "is_blocking": False}))
    assert any("cycle" in e.lower() for e in issues.errors)


def test_dependency_on_unknown_or_self_task_is_rejected(db, project):
    bad = lambda d: d["dependencies"].extend([
        {"task_id": "T2", "depends_on_task_id": "T99", "dependency_type": "DATA", "description": "x", "is_blocking": False},
        {"task_id": "T3", "depends_on_task_id": "T3", "dependency_type": "DATA", "description": "x", "is_blocking": False}])
    issues, _ = _issues(db, project, bad)
    assert any("T99" in e for e in issues.errors) and any("itself" in e for e in issues.errors)


def test_sprint_must_not_precede_a_dependency(db, project):
    issues, _ = _issues(db, project, lambda d: d["tasks"][3].update(sprint="S1") or d["tasks"][8].update(sprint="S1") or d["tasks"][1].update(sprint="S3"))
    assert any("scheduled later" in e for e in issues.errors)


def test_external_dependency_rules(db, project):
    issues, _ = _issues(db, project, lambda d: d["dependencies"][-1].update(depends_on_task_id="T1"))
    assert any("EXTERNAL" in e for e in issues.errors)
    issues, _ = _issues(db, project, lambda d: d["dependencies"][0].update(depends_on_task_id=None))
    assert any("depends_on_task_id" in e for e in issues.errors)


def test_duplicate_dependency_entries_are_collapsed(db, project):
    context = context_for(db, project.id)
    plan = mutated(context.payload, lambda d: d["dependencies"].append(dict(d["dependencies"][0])))
    cleaned, _ = normalize_plan(plan, None, None)
    assert len(cleaned.dependencies) == len(registration_plan(context.payload).dependencies)


def test_compute_execution_order_prefers_earlier_sprint_then_priority(db, project):
    plan = registration_plan(context_for(db, project.id).payload)
    order = compute_execution_order(plan)
    assert order[0] == "T1" and order.index("T2") < order.index("T4") < order.index("T8")


# ---------------------------------------------------------------------------
# Grounding
# ---------------------------------------------------------------------------


def test_explicit_task_without_any_citation_is_rejected(db, project):
    issues, _ = _issues(db, project, lambda d: d["tasks"][6].update(related_artifact_ids=[]))
    assert any("T7" in e and "EXPLICIT" in e for e in issues.errors)


def test_inferred_task_needs_rationale_and_traceability(db, project):
    def orphan(d):
        d["tasks"][0].update(rationale=None)
        d["dependencies"] = [x for x in d["dependencies"] if "T1" not in (x["task_id"], x["depends_on_task_id"])]

    issues, _ = _issues(db, project, orphan)
    assert any("T1" in e and "rationale" in e for e in issues.errors)
    assert any("T1" in e and "not traceable" in e for e in issues.errors)


def test_ambiguous_task_needs_a_reason(db, project):
    issues, _ = _issues(db, project, lambda d: d["tasks"][2].update(rationale=""))
    assert any("T3" in e and "AMBIGUOUS" in e for e in issues.errors)


def test_uncovered_requirements_are_reported_as_gaps(db, project):
    issues, _ = _issues(db, project, lambda d: d.update(tasks=[t for t in d["tasks"] if t["task_id"] != "T13"]) or d.update(
        dependencies=[x for x in d["dependencies"] if "T13" not in (x["task_id"], x["depends_on_task_id"])]))
    assert any("Registration Response" in g for g in issues.coverage_gaps)


def test_coverage_gap_triggers_repair_then_is_accepted_with_a_warning(client, project, use_provider):
    def missing_response_task(payload):
        def drop(d):
            d["tasks"] = [t for t in d["tasks"] if t["task_id"] != "T13"]
            d["dependencies"] = [x for x in d["dependencies"] if "T13" not in (x["task_id"], x["depends_on_task_id"])]
            d["milestones"][1]["task_ids"] = [t for t in d["milestones"][1]["task_ids"] if t != "T13"]
        return mutated(payload, drop)

    provider = ScriptedProvider(missing_response_task)
    response = run(client, project, provider, use_provider)
    assert response.status_code == 200
    assert len(provider.calls) == 2 and "Registration Response" in provider.calls[1]["feedback"][0]
    warnings = response.json()["plan"]["warnings"]
    assert any("Coverage gap" in w and "Registration Response" in w for w in warnings)


# ---------------------------------------------------------------------------
# Sprint generation
# ---------------------------------------------------------------------------


def test_sprint_count_follows_the_plan_not_a_fixed_number(client, project, use_provider):
    def two_sprints(payload):
        def merge(d):
            d["sprints"] = d["sprints"][:2]
            for task in d["tasks"]:
                if task["sprint"] == "S3":
                    task["sprint"] = "S2"
            d["milestones"][2]["target_sprint"] = "S2"
        return mutated(payload, merge)

    two = run(client, project, ScriptedProvider(two_sprints), use_provider).json()
    assert [s["sprint_id"] for s in two["sprints"]] == ["S1", "S2"]
    three = run(client, project, ScriptedProvider(registration_plan), use_provider).json()
    assert [s["sprint_id"] for s in three["sprints"]] == ["S1", "S2", "S3"]


def test_every_task_is_in_exactly_one_sprint_and_points_are_totalled(client, project, use_provider):
    body = run(client, project, ScriptedProvider(registration_plan), use_provider).json()
    listed = [task_id for sprint in body["sprints"] for task_id in sprint["tasks"]]
    assert sorted(listed) == sorted(t["task_id"] for t in body["tasks"]) and len(listed) == len(set(listed))
    for sprint in body["sprints"]:
        expected = sum(t["story_points"] for t in body["tasks"] if t["sprint"] == sprint["sprint_id"])
        assert sprint["total_story_points"] == expected and sprint["goal"]


def test_task_assigned_to_a_missing_sprint_is_rejected(db, project):
    issues, _ = _issues(db, project, lambda d: d["tasks"][0].update(sprint="S9"))
    assert any("S9" in e for e in issues.errors)


def test_dates_are_never_fabricated(client, project, use_provider):
    def with_dates(payload):
        return mutated(payload, lambda d: d["sprints"][0].update(start_date="2026-10-05", end_date="2026-10-16"))

    body = run(client, project, ScriptedProvider(with_dates), use_provider).json()
    assert body["sprints"][0]["start_date"] is None and body["sprints"][0]["end_date"] is None
    assert any("no dates are assumed" in w for w in body["plan"]["warnings"])


def test_valid_dates_inside_the_project_window_are_kept(client, make_user, make_project, seed_requirements, use_provider):
    user = make_user()
    project_id = make_project(user, start_date="2026-10-01", due_date="2026-12-31")
    seed_requirements(project_id)

    def with_dates(payload):
        return mutated(payload, lambda d: d["sprints"][0].update(start_date="2026-10-05", end_date="2026-10-16"))

    use_provider(ScriptedProvider(with_dates))
    body = client.post(RUN.format(project_id), headers=user["headers"]).json()
    assert body["sprints"][0]["start_date"] == "2026-10-05" and body["sprints"][1]["start_date"] is None


# ---------------------------------------------------------------------------
# Persistence
# ---------------------------------------------------------------------------


def test_plan_is_persisted_in_every_table_with_run_metadata(client, project, use_provider, db):
    run(client, project, ScriptedProvider(registration_plan), use_provider)
    db.expire_all()
    counts = {m.__tablename__: db.scalar(select(func.count()).select_from(m).where(m.project_id == project.id))
              for m in (PMPlan, PMEpic, PMTask, PMTaskDependency, PMSprint, PMMilestone, PMRisk)}
    assert counts == {"pm_plans": 1, "pm_epics": 4, "pm_tasks": 15, "pm_task_dependencies": 18,
                      "pm_sprints": 3, "pm_milestones": 3, "pm_risks": 3}
    plan = db.scalars(select(PMPlan)).one()
    assert plan.definition_of_done and plan.execution_order and plan.requirements_run_id == project.ids["run_id"]
    agent_run = db.get(AgentRun, plan.agent_run_id)
    summary = agent_run.output_summary
    assert agent_run.agent_name == "Project Manager AI" and agent_run.status == "COMPLETED"
    assert summary["tasks_generated"] == 15 and summary["total_story_points"] == sum(
        t.story_points for t in db.scalars(select(PMTask)))
    assert [s["node"] for s in summary["steps"]] == [
        "validate_requirements", "generate_plan", "validate_plan", "persist"]


def test_existing_requirements_analyst_view_is_unaffected_by_a_pm_run(client, project, use_provider):
    before = client.get(f"/api/projects/{project.id}/analysis", headers=project.headers).json()
    run(client, project, ScriptedProvider(registration_plan), use_provider)
    after = client.get(f"/api/projects/{project.id}/analysis", headers=project.headers).json()
    assert after["project_summary"] == before["project_summary"] != {"summary": "No completed requirements analysis is available yet."}
    assert after["latest_agent_run"]["agent_name"] == "Requirements Analyst AI"
    assert len(after["functional_requirements"]) == 7


# ---------------------------------------------------------------------------
# Authorization
# ---------------------------------------------------------------------------

ENDPOINTS = [("post", "/project-manager/run"), ("get", "/project-manager"), ("get", "/tasks"), ("get", "/sprints"),
             ("get", "/milestones"), ("get", "/risks"), ("get", "/dependencies")]


@pytest.mark.parametrize("method,path", ENDPOINTS)
def test_endpoints_require_authentication(client, project, method, path):
    assert getattr(client, method)(f"/api/projects/{project.id}{path}").status_code == 401
    bad = {"Authorization": "Bearer nonsense"}
    assert getattr(client, method)(f"/api/projects/{project.id}{path}", headers=bad).status_code == 401


@pytest.mark.parametrize("method,path", ENDPOINTS)
def test_other_users_cannot_access_the_project(client, project, make_user, use_provider, method, path):
    use_provider(ScriptedProvider(registration_plan))
    stranger = make_user()
    assert getattr(client, method)(f"/api/projects/{project.id}{path}", headers=stranger["headers"]).status_code == 404


def test_unknown_project_is_404(client, make_user):
    user = make_user()
    assert client.get(PLAN.format(4242), headers=user["headers"]).status_code == 404


# ---------------------------------------------------------------------------
# Regeneration
# ---------------------------------------------------------------------------


def test_regeneration_replaces_the_plan_without_duplicates(client, project, use_provider, db):
    first = run(client, project, ScriptedProvider(registration_plan), use_provider).json()

    def leaner(payload):
        def trim(d):
            d["tasks"][0]["title"] = "Regenerated task"
        return mutated(payload, trim)

    second = run(client, project, ScriptedProvider(leaner), use_provider).json()
    assert second["latest_agent_run"]["id"] != first["latest_agent_run"]["id"]
    assert not any(t["title"] == "Regenerated task" for t in first["tasks"])
    assert sum(t["title"] == "Regenerated task" for t in second["tasks"]) == 1
    db.expire_all()
    assert db.scalar(select(func.count()).select_from(PMPlan)) == 1
    assert db.scalar(select(func.count()).select_from(PMTask)) == 15
    runs = db.scalars(select(AgentRun).where(AgentRun.agent_name == "Project Manager AI")).all()
    assert [r.status for r in runs] == ["COMPLETED", "COMPLETED"]


def test_failed_regeneration_keeps_the_previous_plan(client, project, use_provider, db):
    first = run(client, project, ScriptedProvider(registration_plan), use_provider).json()
    failed = run(client, project, ScriptedProvider(ProviderConfigurationError("boom")), use_provider)
    assert failed.status_code == 503
    body = client.get(PLAN.format(project.id), headers=project.headers).json()
    assert body["status"] == "FAILED" and body["latest_agent_run"]["error"]
    assert body["plan"]["id"] == first["plan"]["id"] and len(body["tasks"]) == 15


def test_invalid_regeneration_keeps_the_previous_plan(client, project, use_provider):
    first = run(client, project, ScriptedProvider(registration_plan), use_provider).json()

    def bad(payload):
        return mutated(payload, lambda d: d["tasks"][0].update(related_requirement_id="REQ-424242"))

    assert run(client, project, ScriptedProvider(bad), use_provider).status_code == 422
    body = client.get(PLAN.format(project.id), headers=project.headers).json()
    assert body["plan"]["id"] == first["plan"]["id"] and len(body["tasks"]) == 15


def test_plan_is_flagged_when_requirements_change_after_generation(client, project, use_provider, db):
    run(client, project, ScriptedProvider(registration_plan), use_provider)
    assert client.get(PLAN.format(project.id), headers=project.headers).json()["plan"]["requirements_changed"] is False
    db.add(AgentRun(project_id=project.id, agent_name="Requirements Analyst AI", status="COMPLETED", output_summary={}))
    db.commit()
    assert client.get(PLAN.format(project.id), headers=project.headers).json()["plan"]["requirements_changed"] is True


def test_concurrent_run_is_refused(client, project, use_provider, db):
    db.add(AgentRun(project_id=project.id, agent_name="Project Manager AI", status="PROCESSING"))
    db.commit()
    provider = ScriptedProvider(registration_plan)
    response = run(client, project, provider, use_provider)
    assert response.status_code == 409 and "already in progress" in response.json()["detail"] and provider.calls == []
