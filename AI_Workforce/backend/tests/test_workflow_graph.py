"""LangGraph workflow tests that need no database or LLM.

The graph is built from fake stages, so these tests prove the orchestration itself:
execution order, shared state, validation gates, conditional transitions, error routing
and extensibility.
"""

import pytest

from app.workflow.graph import Stage, build_workflow
from app.workflow.state import (
    AGENT_ERROR,
    COMPLETED,
    FAILED,
    MISSING_INPUT,
    VALIDATION_FAILED,
    StageError,
    initial_state,
)
from app.workflow.validators import validate_project_plan, validate_requirements


def make_stage(key, calls, *, output=None, passes=True, raises=None, node_name=None, validation_name=None):
    def run(state):
        calls.append(f"run:{key}")
        if raises:
            raise raises
        return output(state) if callable(output) else (output or {})

    def validate(state):
        calls.append(f"validate:{key}")
        return {"passed": passes, "errors": [] if passes else [f"{key} is bad"], "warnings": []}

    return Stage(
        key=key,
        agent=f"{key} agent",
        node_name=node_name or f"{key}_node",
        validation_name=validation_name or f"validate_{key}",
        run=run,
        validate=validate,
    )


def run_graph(*stages):
    return build_workflow(list(stages)).invoke(initial_state(project_id=7))


# --- execution order, shared state, handoff ---------------------------------


def test_agents_and_gates_run_in_order_and_workflow_completes():
    calls = []
    final = run_graph(
        make_stage("requirements", calls, output={"requirements": {"functional_requirements": 3}}),
        make_stage("project_plan", calls, output={"project_plan": {"tasks_generated": 5}}),
    )
    assert calls == ["run:requirements", "validate:requirements", "run:project_plan", "validate:project_plan"]
    assert final["workflow_status"] == COMPLETED
    assert final["error"] is None
    assert final["project_id"] == 7
    assert final["current_agent"] == "project_plan agent"
    assert set(final["validation_results"]) == {"requirements", "project_plan"}
    assert all(result["passed"] for result in final["validation_results"].values())


def test_state_is_shared_between_agents():
    calls = []
    seen = {}

    def plan_from_requirements(state):
        seen["requirements"] = state["requirements"]
        return {"project_plan": {"tasks_generated": state["requirements"]["functional_requirements"] * 2}}

    final = run_graph(
        make_stage("requirements", calls, output={"requirements": {"functional_requirements": 4}}),
        make_stage("project_plan", calls, output=plan_from_requirements),
    )
    assert seen["requirements"] == {"functional_requirements": 4}
    assert final["requirements"] == {"functional_requirements": 4}
    assert final["project_plan"] == {"tasks_generated": 8}


def test_future_agent_fields_stay_empty():
    final = run_graph(
        make_stage("requirements", [], output={"requirements": {"functional_requirements": 1}}),
        make_stage("project_plan", [], output={"project_plan": {"tasks_generated": 1}}),
    )
    for field in ("architecture", "code", "test_results"):
        assert final.get(field) is None


# --- validation gates and conditional transitions ----------------------------


def test_failed_validation_gate_stops_the_workflow():
    calls = []
    final = run_graph(
        make_stage("requirements", calls, output={"requirements": {"functional_requirements": 0}}, passes=False),
        make_stage("project_plan", calls, output={"project_plan": {"tasks_generated": 1}}),
    )
    assert calls == ["run:requirements", "validate:requirements"]  # Project Manager never ran
    assert final["workflow_status"] == FAILED
    assert final["error"]["stage"] == "requirements"
    assert final["error"]["kind"] == VALIDATION_FAILED
    assert "requirements is bad" in final["error"]["message"]
    assert final["validation_results"]["requirements"]["passed"] is False
    assert final.get("project_plan") is None


def test_second_gate_failing_keeps_first_stage_result():
    calls = []
    final = run_graph(
        make_stage("requirements", calls, output={"requirements": {"functional_requirements": 2}}),
        make_stage("project_plan", calls, output={"project_plan": {"tasks_generated": 0}}, passes=False),
    )
    assert final["workflow_status"] == FAILED
    assert final["error"]["stage"] == "project_plan"
    assert final["validation_results"]["requirements"]["passed"] is True
    assert final["validation_results"]["project_plan"]["passed"] is False
    assert final["requirements"] == {"functional_requirements": 2}


def test_validator_that_raises_fails_the_gate():
    calls = []
    stage = make_stage("requirements", calls)

    def broken(state):
        raise RuntimeError("validator exploded")

    final = run_graph(Stage(**{**stage.__dict__, "validate": broken}), make_stage("project_plan", calls))
    assert final["workflow_status"] == FAILED
    assert final["error"]["kind"] == VALIDATION_FAILED
    assert "validator exploded" in final["error"]["message"]
    assert "run:project_plan" not in calls


# --- workflow errors ----------------------------------------------------------


def test_agent_exception_ends_the_workflow_without_running_its_gate():
    calls = []
    final = run_graph(
        make_stage("requirements", calls, raises=RuntimeError("model unavailable")),
        make_stage("project_plan", calls),
    )
    assert calls == ["run:requirements"]
    assert final["workflow_status"] == FAILED
    assert final["error"] == {"stage": "requirements", "kind": AGENT_ERROR, "message": "model unavailable"}
    assert final["validation_results"] == {}


def test_classified_stage_error_keeps_its_kind():
    calls = []
    final = run_graph(
        make_stage("requirements", calls, raises=StageError(MISSING_INPUT, "Upload an SRS first")),
        make_stage("project_plan", calls),
    )
    assert final["error"] == {"stage": "requirements", "kind": MISSING_INPUT, "message": "Upload an SRS first"}
    assert calls == ["run:requirements"]


def test_stage_returning_unknown_state_field_is_reported():
    final = run_graph(make_stage("requirements", [], output={"not_a_field": 1}))
    assert final["workflow_status"] == FAILED
    assert final["error"]["kind"] == AGENT_ERROR
    assert "not_a_field" in final["error"]["message"]


# --- extensibility ------------------------------------------------------------


def test_new_stage_is_added_without_changing_the_graph_code():
    calls = []

    def architect(state):
        return {"architecture": {"derived_from_tasks": state["project_plan"]["tasks_generated"]}}

    final = run_graph(
        make_stage("requirements", calls, output={"requirements": {"functional_requirements": 1}}),
        make_stage("project_plan", calls, output={"project_plan": {"tasks_generated": 6}}),
        make_stage("architecture", calls, output=architect, node_name="architect_node", validation_name="validate_architecture"),
    )
    assert calls == [
        "run:requirements", "validate:requirements",
        "run:project_plan", "validate:project_plan",
        "run:architecture", "validate:architecture",
    ]
    assert final["architecture"] == {"derived_from_tasks": 6}
    assert final["workflow_status"] == COMPLETED
    assert final["current_agent"] == "architecture agent"


def test_added_stage_is_gated_by_the_previous_validation():
    calls = []
    final = run_graph(
        make_stage("requirements", calls),
        make_stage("project_plan", calls, passes=False),
        make_stage("architecture", calls, node_name="architect_node", validation_name="validate_architecture"),
    )
    assert "run:architecture" not in calls
    assert final["error"]["stage"] == "project_plan"


def test_builder_rejects_empty_and_duplicate_stages():
    with pytest.raises(ValueError):
        build_workflow([])
    with pytest.raises(ValueError):
        build_workflow([make_stage("a", [], node_name="same"), make_stage("b", [], node_name="same")])


# --- validation gates (real validators) ---------------------------------------

GOOD_REQUIREMENTS = {
    "agent_run_id": 11, "status": "COMPLETED", "functional_requirements": 7,
    "user_stories": 3, "acceptance_criteria": 7,
}
GOOD_PLAN = {
    "agent_run_id": 12, "status": "COMPLETED", "requirements_run_id": 11,
    "tasks_generated": 15, "sprints": 3, "warnings": [],
}


def test_requirements_gate_accepts_a_complete_analysis():
    result = validate_requirements({"requirements": GOOD_REQUIREMENTS})
    assert result == {"passed": True, "errors": [], "warnings": []}


@pytest.mark.parametrize(
    "requirements, fragment",
    [
        (None, "no output"),
        ({**GOOD_REQUIREMENTS, "status": "FAILED"}, "did not complete"),
        ({**GOOD_REQUIREMENTS, "functional_requirements": 0}, "No functional requirements"),
    ],
)
def test_requirements_gate_rejects_unusable_output(requirements, fragment):
    result = validate_requirements({"requirements": requirements})
    assert result["passed"] is False
    assert any(fragment in error for error in result["errors"])


def test_requirements_gate_warns_but_passes_without_stories_or_criteria():
    result = validate_requirements({"requirements": {**GOOD_REQUIREMENTS, "user_stories": 0, "acceptance_criteria": 0}})
    assert result["passed"] is True
    assert len(result["warnings"]) == 2


def test_plan_gate_accepts_a_complete_plan_and_passes_warnings_through():
    state = {"requirements": GOOD_REQUIREMENTS, "project_plan": {**GOOD_PLAN, "warnings": ["Coverage gap: REQ-3"]}}
    result = validate_project_plan(state)
    assert result["passed"] is True
    assert result["warnings"] == ["Coverage gap: REQ-3"]


@pytest.mark.parametrize(
    "plan, fragment",
    [
        (None, "no plan"),
        ({**GOOD_PLAN, "status": "FAILED"}, "did not complete"),
        ({**GOOD_PLAN, "tasks_generated": 0}, "no tasks"),
        ({**GOOD_PLAN, "sprints": 0}, "no sprints"),
        ({**GOOD_PLAN, "requirements_run_id": 99}, "run 99"),
    ],
)
def test_plan_gate_rejects_unusable_plans(plan, fragment):
    result = validate_project_plan({"requirements": GOOD_REQUIREMENTS, "project_plan": plan})
    assert result["passed"] is False
    assert any(fragment in error for error in result["errors"])
