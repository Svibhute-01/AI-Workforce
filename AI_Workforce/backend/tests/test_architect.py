"""System Architect AI: agent flow, validation rules, persistence and the workflow gate.

These tests run the real Requirements-seed -> Project Manager -> Architect code against the
SQLite test database. Only the LLM is replaced (``ScriptedArchitectProvider``), and the
Requirements Analyst's LLM call is replaced by the project's own ``seed_requirements``.
No HTTP is involved; the endpoints are covered in ``test_architect_api.py``.
"""

import dataclasses
from types import SimpleNamespace

import pytest
from pydantic import ValidationError
from sqlalchemy import func, select

from app.agents.architect_agent import (
    ArchitectRunInProgressError,
    ArchitectureValidationError,
    MissingPlanError,
    run_architect,
)
from app.agents.architect_context import build_architect_context
from app.agents.architect_validation import build_detailed_diagram, validate_design, validate_hld
from app.agents.pm_context import MissingRequirementsError
from app.agents.project_manager_agent import run_project_manager
from app.llm.architect_prompts import hld_prompt, lld_prompt
from app.llm.gemini_provider import _architect_response_schema, _gemini_response_schema
from app.models import AgentRun, ArchDesign, Document, Project
from app.schemas_architect import ARCHITECT_AGENT_NAME, HighLevelDesign, LowLevelDesign
from app.workflow.service import WorkflowFailure, WorkflowService
from app.workflow.stages import default_stages
from app.workflow.validators import validate_architecture

from .architecture_fixtures import (
    ScriptedArchitectProvider,
    mutated,
    registration_hld,
    registration_hld_dict,
    registration_lld,
    registration_lld_dict,
)
from .conftest import ScriptedProvider
from .plan_fixtures import registration_plan


@pytest.fixture
def bare_project(db, make_user, make_project):
    """A project with nothing generated yet."""
    return db.get(Project, make_project(make_user()))


@pytest.fixture
def requirements_only(db, bare_project, seed_requirements):
    """Requirements Analyst output exists, but no Project Manager plan."""
    seed_requirements(bare_project.id)
    return bare_project


@pytest.fixture
def planned(db, requirements_only):
    """Requirements Analyst output AND a real Project Manager plan."""
    run_project_manager(db, requirements_only, ScriptedProvider(registration_plan))
    return requirements_only


def good_provider():
    return ScriptedArchitectProvider(hld=[registration_hld], lld=[registration_lld])


def design_rows(db, project):
    return db.scalars(select(ArchDesign).where(ArchDesign.project_id == project.id)).all()


def architect_runs(db, project):
    return db.scalars(
        select(AgentRun).where(AgentRun.project_id == project.id, AgentRun.agent_name == ARCHITECT_AGENT_NAME)
    ).all()


def context_of(db, project):
    return build_architect_context(db, project)


def hld_dict(ctx):
    return registration_hld_dict(ctx.requirements.payload, ctx.plan_payload)


def lld_dict(ctx):
    return registration_lld_dict(ctx.requirements.payload, ctx.plan_payload)


# ---------------------------------------------------------------------------
# RA -> PM -> Architect: generation and persistence
# ---------------------------------------------------------------------------


def test_valid_flow_validates_and_persists_hld_and_lld(db, planned):
    provider = good_provider()
    run = run_architect(db, planned, provider)

    assert run.status == "COMPLETED"
    assert [step["node"] for step in run.output_summary["steps"]] == [
        "load_context", "generate_hld", "validate_hld", "generate_lld", "validate_design", "persist",
    ]
    assert run.output_summary["components"] == 4 and run.output_summary["apis"] == 1

    (design,) = design_rows(db, planned)
    assert design.agent_run_id == run.id
    assert len(design.hld["components"]) == 4 and len(design.lld["modules"]) == 3
    assert design.hld["style"]["grounding"] == "ASSUMED"
    assert design.hld["style"]["rationale"]
    # The design is stored as valid HLD / LLD documents.
    HighLevelDesign.model_validate(design.hld)
    LowLevelDesign.model_validate(design.lld)

    # The Architect was fed the saved Requirements Analyst and Project Manager output.
    sent = provider.hld_calls[0]
    assert sent["feedback"] is None
    assert {r["title"] for r in sent["requirements"]["functional_requirements"]} >= {"Customer Registration"}
    assert len(sent["plan"]["tasks"]) == 15
    assert provider.lld_calls[0]["hld"]["components"][0]["component_id"] == "C1"  # LLD builds on the validated HLD


def test_agent_run_is_tracked_with_the_existing_agent_run_table(db, planned):
    run_architect(db, planned, good_provider())
    (run,) = architect_runs(db, planned)
    assert run.status == "COMPLETED" and run.completed_at is not None
    assert run.input_summary["requirements"] == 7 and run.input_summary["tasks"] == 15
    assert run.input_summary["plan_run_id"] is not None


def test_diagram_is_derived_from_the_generated_components_and_relationships(db, planned):
    run_architect(db, planned, good_provider())
    (design,) = design_rows(db, planned)

    node_ids = [n["id"] for n in design.diagram["nodes"]]
    assert node_ids == [c["component_id"] for c in design.hld["components"]]
    assert [e["id"] for e in design.diagram["edges"]] == [r["relationship_id"] for r in design.hld["relationships"]]
    assert all(e["source"] in node_ids and e["target"] in node_ids for e in design.diagram["edges"])
    layers = {n["id"]: n["layer"] for n in design.diagram["nodes"]}
    assert layers["C1"] < layers["C2"] < layers["C3"] < layers["C4"]  # client -> api -> database -> external
    assert design.diagram["mermaid"].startswith("flowchart")


def test_diagram_follows_the_components_the_model_produced(db, planned):
    def fewer(d):
        d["components"] = [c for c in d["components"] if c["component_id"] != "C4"]
        d["relationships"] = [r for r in d["relationships"] if "C4" not in (r["source_component_id"], r["target_component_id"])]
        d["data_flows"][0]["steps"] = d["data_flows"][0]["steps"][:2]
        d["integrations"][0]["component_id"] = None
        d["risks"][0]["component_ids"] = []

    run_architect(db, planned, ScriptedArchitectProvider(hld=[mutated(registration_hld, fewer)], lld=[registration_lld]))
    (design,) = design_rows(db, planned)
    assert [n["id"] for n in design.diagram["nodes"]] == ["C1", "C2", "C3"]
    assert [e["id"] for e in design.diagram["edges"]] == ["R1", "R2"]


def test_traceability_is_built_from_the_ids_the_design_cites(db, planned):
    run_architect(db, planned, good_provider())
    (design,) = design_rows(db, planned)
    refs = context_of(db, planned).references

    by_id = {row["requirement_id"]: row for row in design.traceability}
    assert set(by_id) <= refs.requirement_ids
    registration = by_id["REQ-1"]  # Customer Registration
    assert registration["status"] == "COVERED" and "C1" in registration["component_ids"]
    assert "M1" in registration["module_ids"] and "API1" in registration["api_ids"]
    assert set(registration["task_ids"]) <= refs.task_ids
    assert by_id["REQ-7"]["status"] == "COVERED"
    # CON-1 / CON-2 are not cited by the scripted design: reported, never hidden.
    assert by_id["CON-1"]["status"] == "NOT_COVERED"


def test_open_items_keep_assumed_and_unknown_separate(db, planned):
    run_architect(db, planned, good_provider())
    (design,) = design_rows(db, planned)
    kinds = {item["item_id"]: item["kind"] for item in design.open_items}
    assert kinds == {"OH1": "ASSUMED", "OH2": "UNKNOWN", "OL1": "UNKNOWN"}


# ---------------------------------------------------------------------------
# Repair loop and failures
# ---------------------------------------------------------------------------


def test_validation_problems_are_fed_back_for_one_repair_attempt(db, planned):
    def cites_unknown_requirement(d):
        d["components"][0]["requirement_ids"].append("REQ-999")

    provider = ScriptedArchitectProvider(
        hld=[mutated(registration_hld, cites_unknown_requirement), registration_hld], lld=[registration_lld]
    )
    run = run_architect(db, planned, provider)

    assert run.status == "COMPLETED"
    assert run.output_summary["attempts"] == {"hld": 2, "lld": 1}
    assert provider.hld_calls[0]["feedback"] is None
    assert any("REQ-999" in problem for problem in provider.hld_calls[1]["feedback"])


def _unknown_requirement(d):
    d["components"][0]["requirement_ids"].append("REQ-999")


def _unknown_task(d):
    d["components"][1]["task_ids"].append("T999")


@pytest.mark.parametrize("mutate, fragment", [(_unknown_requirement, "REQ-999"), (_unknown_task, "T999")])
def test_invented_requirement_and_task_ids_are_never_saved(db, planned, mutate, fragment):
    provider = ScriptedArchitectProvider(hld=[mutated(registration_hld, mutate)], lld=[registration_lld])

    with pytest.raises(ArchitectureValidationError, match=fragment):
        run_architect(db, planned, provider)

    assert design_rows(db, planned) == []
    (run,) = architect_runs(db, planned)
    assert run.status == "FAILED" and fragment in run.error
    assert len(provider.hld_calls) == 2 and provider.lld_calls == []  # repaired once, never reached the LLD


def test_invented_ids_in_the_lld_are_rejected_too(db, planned):
    def bad_lld(d):
        d["modules"][0]["requirement_ids"].append("REQ-404")
        d["apis"][0]["task_ids"].append("T404")

    provider = ScriptedArchitectProvider(hld=[registration_hld], lld=[mutated(registration_lld, bad_lld)])
    with pytest.raises(ArchitectureValidationError) as caught:
        run_architect(db, planned, provider)
    assert "REQ-404" in str(caught.value) and "T404" in "; ".join(caught.value.problems)
    assert design_rows(db, planned) == []


def test_malformed_model_output_is_retried_once_then_rejected(db, planned):
    with pytest.raises(ValidationError) as schema_error:
        HighLevelDesign.model_validate({"overview": "only an overview"})

    provider = ScriptedArchitectProvider(hld=[schema_error.value], lld=[registration_lld])
    with pytest.raises(ArchitectureValidationError, match="malformed"):
        run_architect(db, planned, provider)

    assert len(provider.hld_calls) == 2
    assert "not valid against the schema" in provider.hld_calls[1]["feedback"][0]
    assert design_rows(db, planned) == []
    assert architect_runs(db, planned)[0].status == "FAILED"


def test_invalid_grounding_classification_is_rejected_by_the_schema(db, planned):
    data = hld_dict(context_of(db, planned))
    data["components"][0]["grounding"] = "AMBIGUOUS"  # not one of EXPLICIT / INFERRED / ASSUMED / UNKNOWN
    with pytest.raises(ValidationError):
        HighLevelDesign.model_validate(data)


def test_gemini_failure_marks_the_run_failed_and_saves_nothing(db, planned):
    provider = ScriptedArchitectProvider(hld=[RuntimeError("Gemini is unavailable")], lld=[registration_lld])

    with pytest.raises(RuntimeError, match="Gemini is unavailable"):
        run_architect(db, planned, provider)

    assert design_rows(db, planned) == []
    (run,) = architect_runs(db, planned)
    assert run.status == "FAILED" and "Gemini is unavailable" in run.error
    assert run.completed_at is not None


def test_failed_regeneration_keeps_the_previous_design(db, planned):
    first = run_architect(db, planned, good_provider())

    def breaks_a_relationship(d):
        d["relationships"][0]["target_component_id"] = "C99"

    bad = ScriptedArchitectProvider(hld=[mutated(registration_hld, breaks_a_relationship)], lld=[registration_lld])
    with pytest.raises(ArchitectureValidationError):
        run_architect(db, planned, bad)

    (design,) = design_rows(db, planned)
    assert design.agent_run_id == first.id  # the earlier, valid design is untouched
    assert sorted(run.status for run in architect_runs(db, planned)) == ["COMPLETED", "FAILED"]


def test_regenerating_replaces_the_design_instead_of_duplicating_it(db, planned):
    run_architect(db, planned, good_provider())
    second = run_architect(db, planned, good_provider())

    (design,) = design_rows(db, planned)
    assert design.agent_run_id == second.id
    assert db.scalar(select(func.count()).select_from(ArchDesign)) == 1


def test_missing_requirements_or_plan_stops_before_any_run_is_recorded(db, bare_project, requirements_only):
    other = db.get(Project, bare_project.id)
    provider = good_provider()

    with pytest.raises(MissingPlanError, match="Project Manager"):
        run_architect(db, other, provider)  # requirements exist, plan does not
    assert provider.hld_calls == [] and architect_runs(db, other) == []


def test_project_without_requirements_cannot_be_designed(db, bare_project):
    with pytest.raises(MissingRequirementsError):
        run_architect(db, bare_project, good_provider())
    assert architect_runs(db, bare_project) == []


def test_second_run_while_one_is_in_progress_is_refused(db, planned):
    db.add(AgentRun(project_id=planned.id, agent_name=ARCHITECT_AGENT_NAME, status="PROCESSING"))
    db.commit()
    with pytest.raises(ArchitectRunInProgressError):
        run_architect(db, planned, good_provider())


# ---------------------------------------------------------------------------
# Validation rules (pure checks on a design)
# ---------------------------------------------------------------------------


def _set(path_fn):
    return path_fn


HLD_CASES = [
    ("duplicate component id", lambda d: d["components"][1].update(component_id="C1"), "Duplicate component id 'C1'"),
    ("relationship to unknown component", lambda d: d["relationships"][0].update(target_component_id="C99"), "unknown target component 'C99'"),
    ("relationship to itself", lambda d: d["relationships"][0].update(target_component_id="C1"), "connects component 'C1' to itself"),
    ("data flow step with unknown component", lambda d: d["data_flows"][0]["steps"][0].update(target_component_id="C77"), "unknown component 'C77'"),
    ("data flow repeats a step number", lambda d: d["data_flows"][0]["steps"][1].update(order=1), "repeats a step order number"),
    ("unknown requirement id", lambda d: d["components"][0]["requirement_ids"].append("REQ-999"), "unknown requirement id 'REQ-999'"),
    ("unknown task id", lambda d: d["components"][0]["task_ids"].append("T999"), "unknown task id 'T999'"),
    ("EXPLICIT without a requirement", lambda d: d["components"][3].update(requirement_ids=[]), "classified EXPLICIT but cites no requirement"),
    ("ASSUMED without a rationale", lambda d: d["decisions"][0].update(rationale=None), "classified ASSUMED but gives no rationale"),
    ("quality topic skipped", lambda d: d.update(quality_considerations=[q for q in d["quality_considerations"] if q["category"] != "SECURITY"]), "does not address security"),
    ("integration with unknown component", lambda d: d["integrations"][0].update(component_id="C55"), "unknown component 'C55'"),
    ("risk with unknown component", lambda d: d["risks"][0].update(component_ids=["C66"]), "unknown component 'C66'"),
    ("no data flows", lambda d: d.update(data_flows=[]), "defines no data flows"),
    ("actor with an unknown component", lambda d: d["actors"][0].update(component_ids=["C9"]), "Actor A1 references unknown component 'C9'"),
    ("actor that interacts with nothing", lambda d: d["actors"][0].update(component_ids=[]), "Actor A1 interacts with no component"),
    ("duplicate actor id", lambda d: d["actors"].append({**d["actors"][0]}), "Duplicate actor id 'A1'"),
    ("actor id that is also a component id", lambda d: d["actors"][0].update(actor_id="C1"), "used for more than one kind of HLD element"),
    ("EXPLICIT actor without a requirement", lambda d: d["actors"][0].update(requirement_ids=[]), "Actor A1 is classified EXPLICIT but cites no requirement"),
    ("deployment node on an unknown component", lambda d: d["deployment"][0].update(component_ids=["C9"]), "Deployment node DN1 hosts unknown component 'C9'"),
    ("deployment node that hosts nothing", lambda d: d["deployment"][0].update(component_ids=[]), "Deployment node DN1 hosts no component"),
    ("component on two deployment nodes", lambda d: d["deployment"][1].update(component_ids=["C2", "C1"]), "Component C1 is placed on several deployment nodes"),
    ("duplicate deployment node id", lambda d: d["deployment"][1].update(node_id="DN1"), "Duplicate deployment node id 'DN1'"),
    ("unsupported ASSUMED deployment node", lambda d: d["deployment"][0].update(rationale=None), "Deployment node DN1 is classified ASSUMED but gives no rationale"),
    ("no components", lambda d: d.update(components=[], relationships=[]), "defines no components"),
]


@pytest.mark.parametrize("label, mutate, fragment", HLD_CASES)
def test_hld_validation_rejects(db, planned, label, mutate, fragment):
    ctx = context_of(db, planned)
    data = hld_dict(ctx)
    mutate(data)
    issues = validate_hld(HighLevelDesign.model_validate(data), ctx.references)
    assert any(fragment in error for error in issues.errors), (label, issues.errors)


LLD_CASES = [
    ("module of an unknown component", lambda d: d["modules"][0].update(component_id="C9"), "belongs to unknown component 'C9'"),
    ("module depends on an unknown module", lambda d: d["modules"][0].update(depends_on_module_ids=["M9"]), "depends on unknown module 'M9'"),
    ("duplicate module id", lambda d: d["modules"][1].update(module_id="M1"), "Duplicate module id 'M1'"),
    ("module id clashes with a component id", lambda d: d["modules"][0].update(module_id="C1"), "used for both a component and a module"),
    ("API of an unknown component", lambda d: d["apis"][0].update(component_id="C9"), "belongs to unknown component 'C9'"),
    ("API implemented by an unknown module", lambda d: d["apis"][0].update(module_id="M9"), "implemented by unknown module 'M9'"),
    ("API with an unknown request model", lambda d: d["apis"][0].update(request_model_id="DM9"), "unknown request model 'DM9'"),
    ("API path without a leading slash", lambda d: d["apis"][0].update(path="api/register"), "must start with '/'"),
    ("two APIs on one route", lambda d: d["apis"].append({**d["apis"][0], "api_id": "API2"}), "duplicates the route POST /api/register"),
    ("table relationship with an unknown column", lambda d: d.update(table_relationships=[
        {"relationship_id": "TR1", "source_table_id": "TBL1", "source_column": "nope", "target_table_id": "TBL1",
         "target_column": "id", "cardinality": "ONE_TO_MANY", "description": None}]), "unknown source column 'TBL1.nope'"),
    ("table relationship with an unknown table", lambda d: d.update(table_relationships=[
        {"relationship_id": "TR1", "source_table_id": "TBL1", "source_column": "id", "target_table_id": "TBL9",
         "target_column": "id", "cardinality": "ONE_TO_ONE", "description": None}]), "unknown target table 'TBL9'"),
    ("table without a primary key", lambda d: [c.update(primary_key=False) for c in d["tables"][0]["columns"]], "has no primary key column"),
    ("sequence step with an unknown API", lambda d: d["sequence_flows"][0]["steps"][1].update(api_id="API9"), "references unknown API 'API9'"),
    ("sequence step with an undeclared participant", lambda d: d["sequence_flows"][0]["steps"][0].update(source_participant_id="P9"), "undeclared participant 'P9'"),
    ("no sequence flows", lambda d: d.update(sequence_flows=[]), "defines no sequence flows"),
    ("pattern applied to an unknown module", lambda d: d["design_patterns"][0].update(applied_to_module_ids=["M9"]), "applied to unknown module 'M9'"),
    ("validation rule on an unknown field", lambda d: d["validation_rules"][0].update(field_name="nope"), "unknown field 'DM1.nope'"),
    ("validation rule citing an unknown requirement", lambda d: d["validation_rules"][0].update(requirement_ids=["REQ-999"]), "unknown requirement id 'REQ-999'"),
]


@pytest.mark.parametrize("label, mutate, fragment", LLD_CASES)
def test_lld_validation_rejects(db, planned, label, mutate, fragment):
    ctx = context_of(db, planned)
    hld = HighLevelDesign.model_validate(hld_dict(ctx))
    data = lld_dict(ctx)
    mutate(data)
    issues = validate_design(hld, LowLevelDesign.model_validate(data), ctx.references)
    assert any(fragment in error for error in issues.errors), (label, issues.errors)


def test_a_good_design_has_no_errors_and_reports_coverage_honestly(db, planned):
    ctx = context_of(db, planned)
    issues = validate_design(
        HighLevelDesign.model_validate(hld_dict(ctx)), LowLevelDesign.model_validate(lld_dict(ctx)), ctx.references
    )
    assert issues.errors == []
    assert issues.coverage_gaps == []  # every functional and non-functional requirement is addressed
    assert any("not referenced by the design" in warning for warning in issues.warnings)  # unused tasks / constraints


def test_uncovered_requirements_become_coverage_gaps_not_errors(db, planned):
    ctx = context_of(db, planned)

    def drop_registration_response(d):
        for element in (*d["components"], *d["data_flows"]):
            element["requirement_ids"] = [r for r in element["requirement_ids"] if r != "REQ-7"]
            if element["grounding"] == "EXPLICIT" and not element["requirement_ids"]:
                element["requirement_ids"] = ["REQ-1"]

    data = hld_dict(ctx)
    drop_registration_response(data)
    lld = lld_dict(ctx)
    for module in lld["modules"]:
        module["requirement_ids"] = [r for r in module["requirement_ids"] if r != "REQ-7"]
    for model in lld["data_models"]:
        model["requirement_ids"] = [r for r in model["requirement_ids"] if r != "REQ-7"] or ["REQ-1"]
    issues = validate_design(HighLevelDesign.model_validate(data), LowLevelDesign.model_validate(lld), ctx.references)

    assert issues.errors == []
    assert any("REQ-7" in gap for gap in issues.coverage_gaps)


# ---------------------------------------------------------------------------
# The validate_architecture gate and the LangGraph workflow
# ---------------------------------------------------------------------------


def gate_state(db, project, **overrides):
    (design,) = design_rows(db, project)
    run = db.get(AgentRun, design.agent_run_id)
    architecture = {
        "agent_run_id": run.id,
        "status": run.status,
        "requirements_run_id": design.requirements_run_id,
        "plan_run_id": design.plan_run_id,
        "reference_ids": context_of(db, project).references.to_dict(),
        "design": {"hld": design.hld, "lld": design.lld},
    }
    architecture.update(overrides)
    return {"architecture": architecture}


def test_gate_accepts_the_persisted_design(db, planned):
    run_architect(db, planned, good_provider())
    result = validate_architecture(gate_state(db, planned))
    assert result["passed"] is True and result["errors"] == []


def test_gate_rejects_missing_or_unfinished_architecture(db, planned):
    assert validate_architecture({})["passed"] is False
    run_architect(db, planned, good_provider())
    result = validate_architecture(gate_state(db, planned, status="FAILED"))
    assert result["passed"] is False and "did not complete" in result["errors"][0]


def test_gate_rejects_a_design_that_lost_required_content(db, planned):
    run_architect(db, planned, good_provider())
    state = gate_state(db, planned)
    del state["architecture"]["design"]["hld"]["style"]
    result = validate_architecture(state)
    assert result["passed"] is False and "missing required HLD/LLD content" in result["errors"][0]


def test_gate_rechecks_references_against_the_real_requirement_and_task_ids(db, planned):
    run_architect(db, planned, good_provider())
    state = gate_state(db, planned)
    state["architecture"]["design"]["lld"]["apis"][0]["requirement_ids"].append("REQ-999")
    state["architecture"]["design"]["hld"]["components"][0]["task_ids"].append("T999")
    errors = " ".join(validate_architecture(state)["errors"])
    assert "REQ-999" in errors and "T999" in errors


def test_gate_rejects_an_architecture_built_from_a_different_run(db, planned):
    run_architect(db, planned, good_provider())
    state = gate_state(db, planned)
    state["requirements"] = {"agent_run_id": state["architecture"]["requirements_run_id"] + 100}
    state["project_plan"] = {"agent_run_id": state["architecture"]["plan_run_id"]}
    result = validate_architecture(state)
    assert result["passed"] is False and "requirements run" in result["errors"][0]


def fake_analyst(monkeypatch, db, project, seed_requirements):
    """Replace only the Requirements Analyst's LLM call; its saved output matches the real agent's."""

    def run(db_session, proj, provider, vector_store):
        ids = seed_requirements(proj.id)
        analysis = SimpleNamespace(
            functional_requirements=[0] * 7, non_functional_requirements=[0] * 3, user_stories=[0] * 3,
            acceptance_criteria=[0] * 7, ambiguities=[0] * 4, risks=[],
        )
        return db_session.get(AgentRun, ids["run_id"]), analysis

    monkeypatch.setattr("app.workflow.stages.run_requirements_analysis", run)
    db.add(Document(project_id=project.id, filename="SRS.pdf", file_type="application/pdf", file_size=1,
                    storage_path="SRS.pdf", processing_status="COMPLETED"))
    db.commit()


class FullPipelineProvider(ScriptedArchitectProvider):
    """Plan responses for the Project Manager plus design responses for the Architect."""

    def __init__(self, hld, lld):
        super().__init__(hld=hld, lld=lld)
        self._plan = ScriptedProvider(registration_plan)

    def generate_project_plan(self, *args, **kwargs):
        return self._plan.generate_project_plan(*args, **kwargs)


def test_full_workflow_runs_ra_then_pm_then_architect_through_langgraph(db, bare_project, seed_requirements, monkeypatch):
    fake_analyst(monkeypatch, db, bare_project, seed_requirements)
    provider = FullPipelineProvider([registration_hld], [registration_lld])

    state = WorkflowService(db, provider).run(bare_project)

    assert state["workflow_status"] == "COMPLETED" and state["error"] is None
    assert state["current_agent"] == "System Architect AI"
    assert list(state["validation_results"]) == ["requirements", "project_plan", "architecture"]
    assert all(result["passed"] for result in state["validation_results"].values())
    # Hand-off through the shared state: each agent worked from the run before it.
    assert state["project_plan"]["requirements_run_id"] == state["requirements"]["agent_run_id"]
    assert state["architecture"]["requirements_run_id"] == state["requirements"]["agent_run_id"]
    assert state["architecture"]["plan_run_id"] == state["project_plan"]["agent_run_id"]
    assert state["architecture"]["counts"]["components"] == 4
    assert {"code", "test_results"} & set(state) == set()  # Developer / QA fields stay absent
    (design,) = design_rows(db, bare_project)
    assert design.agent_run_id == state["architecture"]["agent_run_id"]


def test_workflow_can_run_only_the_architect_stage_through_the_same_graph(db, planned):
    state = WorkflowService(db, good_provider()).run(planned, only=["architecture"])
    assert state["workflow_status"] == "COMPLETED"
    assert list(state["validation_results"]) == ["architecture"]
    assert state.get("requirements") is None and state.get("project_plan") is None


def test_workflow_stops_at_the_architect_when_the_design_is_invalid(db, bare_project, seed_requirements, monkeypatch):
    fake_analyst(monkeypatch, db, bare_project, seed_requirements)

    def bad_lld(d):
        d["apis"][0]["response_model_id"] = "DM404"

    provider = FullPipelineProvider([registration_hld], [mutated(registration_lld, bad_lld)])
    with pytest.raises(WorkflowFailure) as caught:
        WorkflowService(db, provider).run(bare_project)

    failure = caught.value
    assert failure.status_code == 422 and failure.kind == "architecture_invalid"
    assert "Completed stages: requirements, project_plan" in str(failure)
    assert design_rows(db, bare_project) == []
    assert failure.state["error"]["stage"] == "architecture"


def test_workflow_stops_when_the_validation_gate_rejects_the_design(db, planned):
    def tampered_stages(deps):
        stages = default_stages(deps)
        architect = stages[-1]

        def run(state):
            output = architect.run(state)
            output["architecture"]["design"]["hld"]["components"] = []  # design altered after it was generated
            return output

        return [dataclasses.replace(architect, run=run)]

    with pytest.raises(WorkflowFailure) as caught:
        WorkflowService(db, good_provider(), stage_factory=tampered_stages).run(planned)

    failure = caught.value
    assert failure.kind == "validation_failed" and failure.status_code == 422
    assert failure.state["workflow_status"] == "FAILED"
    assert failure.state["validation_results"]["architecture"]["passed"] is False


def test_workflow_reports_missing_plan_as_409_without_calling_gemini(db, requirements_only):
    provider = good_provider()
    with pytest.raises(WorkflowFailure) as caught:
        WorkflowService(db, provider).run(requirements_only, only=["architecture"])
    assert caught.value.status_code == 409 and caught.value.kind == "missing_input"
    assert provider.hld_calls == []


def test_gemini_failure_inside_the_workflow_is_a_503(db, planned):
    provider = ScriptedArchitectProvider(hld=[RuntimeError("Gemini is unavailable")], lld=[registration_lld])
    with pytest.raises(WorkflowFailure) as caught:
        WorkflowService(db, provider).run(planned, only=["architecture"])
    assert caught.value.status_code == 503 and "Gemini is unavailable" in str(caught.value)


# ---------------------------------------------------------------------------
# What Gemini is asked for (regression: INFERRED items without a rationale, empty data flows)
# ---------------------------------------------------------------------------


def optional_fields(schema):
    """Every ``Object.field`` that a JSON schema leaves out of ``required`` (Gemini may omit these)."""
    found = []

    def walk(node, owner):
        if isinstance(node, dict):
            if node.get("type") == "object" and isinstance(node.get("properties"), dict):
                found.extend(f"{owner}.{name}" for name in node["properties"] if name not in node.get("required", []))
            for key, value in node.items():
                if key == "$defs":
                    for name, definition in value.items():
                        walk(definition, name)
                else:
                    walk(value, owner)
        elif isinstance(node, list):
            for value in node:
                walk(value, owner)

    walk(schema, schema.get("title", "root"))
    return found


@pytest.mark.parametrize("model", [HighLevelDesign, LowLevelDesign])
def test_architect_schema_sent_to_gemini_requires_every_field(model):
    assert optional_fields(_architect_response_schema(model)) == []


def test_the_shared_schema_helper_is_left_alone_for_the_other_agents():
    # Pydantic omits fields with defaults from "required"; the Requirements Analyst and Project
    # Manager still use this helper unchanged. Only the Architect tightens it.
    optional = optional_fields(_gemini_response_schema(HighLevelDesign))
    assert "HighLevelDesign.data_flows" in optional and "ArchStyle.rationale" in optional
    assert optional_fields(_architect_response_schema(HighLevelDesign)) == []
    assert "HighLevelDesign.data_flows" in optional_fields(_gemini_response_schema(HighLevelDesign))  # not mutated


def test_prompts_spell_out_the_rationale_and_data_flow_rules(db, planned):
    ctx = context_of(db, planned)
    prompt = hld_prompt("Registration", "desc", ctx.requirements.payload, ctx.plan_payload, {}, None)
    assert "you MUST always fill it in" in prompt
    assert "empty or null rationale" in prompt
    assert "at least one flow" in prompt
    lld = lld_prompt("Registration", "desc", ctx.requirements.payload, ctx.plan_payload, hld_dict(ctx), {}, None)
    assert "you MUST always fill it in" in lld
    assert "Never use descriptive ids" in lld


def test_unknown_api_model_ids_are_reported_with_the_defined_ones_and_repaired(db, planned):
    """Regression: Gemini referenced descriptive ids (DM_USER_RESP) it never defined in data_models."""

    def invented_model_ids(d):
        d["apis"][0]["response_model_id"] = "DM_USER_RESP"
        d["apis"][0]["request_model_id"] = "DM_USER_REQ"

    provider = ScriptedArchitectProvider(
        hld=[registration_hld], lld=[mutated(registration_lld, invented_model_ids), registration_lld]
    )
    run = run_architect(db, planned, provider)

    assert run.status == "COMPLETED" and run.output_summary["attempts"] == {"hld": 1, "lld": 2}
    feedback = " ".join(provider.lld_calls[1]["feedback"])
    assert "unknown response model 'DM_USER_RESP'" in feedback
    assert "unknown request model 'DM_USER_REQ'" in feedback
    assert "Defined data model ids: DM1, DM2" in feedback  # tells the model which ids exist
    assert "use null" in feedback


def test_repair_messages_list_the_defined_ids_for_other_unknown_references(db, planned):
    ctx = context_of(db, planned)
    hld = HighLevelDesign.model_validate(hld_dict(ctx))
    data = lld_dict(ctx)
    data["modules"][0]["component_id"] = "C9"
    data["apis"][0]["module_id"] = "M9"
    data["sequence_flows"][0]["steps"][1]["api_id"] = "API9"
    errors = " ".join(validate_design(hld, LowLevelDesign.model_validate(data), ctx.references).errors)

    assert "Defined component ids: C1, C2, C3, C4." in errors
    assert "Defined module ids: M1, M2, M3." in errors
    assert "Defined API ids: API1." in errors


# ---------------------------------------------------------------------------
# Detailed architecture diagram (components with their modules, endpoints and tables)
# ---------------------------------------------------------------------------


def detailed_for(db, project, hld_edit=None, lld_edit=None):
    ctx = context_of(db, project)
    hld_data, lld_data = hld_dict(ctx), lld_dict(ctx)
    if hld_edit:
        hld_edit(hld_data)
    if lld_edit:
        lld_edit(lld_data)
    return build_detailed_diagram(HighLevelDesign.model_validate(hld_data), LowLevelDesign.model_validate(lld_data))


def test_detailed_diagram_nests_the_lld_inside_the_components(db, planned):
    detailed = detailed_for(db, planned)
    by_id = {c["id"]: c for c in detailed["containers"]}

    assert list(by_id) == ["C1", "C2", "C3", "C4"]  # one box per HLD component, nothing extra
    assert [m["id"] for m in by_id["C2"]["modules"]] == ["M1", "M2", "M3"]
    assert [m["kind"] for m in by_id["C2"]["modules"]] == ["CONTROLLER", "SERVICE", "REPOSITORY"]
    controller = by_id["C2"]["modules"][0]
    assert [(e["id"], e["method"], e["path"]) for e in controller["endpoints"]] == [("API1", "POST", "/api/register")]
    assert by_id["C2"]["endpoints"] == []  # the endpoint sits under its controller, not loose
    assert [t["name"] for t in by_id["C3"]["tables"]] == ["customer_accounts"]
    assert by_id["C3"]["tables"][0]["primary_key"] == ["id"]
    assert by_id["C1"]["modules"] == [] and by_id["C4"]["tables"] == []


def test_detailed_diagram_arrows_come_from_real_dependencies_and_relationships(db, planned):
    detailed = detailed_for(db, planned)
    assert [(r["id"], r["source"], r["target"], r["interaction"]) for r in detailed["relationships"]] == [
        ("R1", "C1", "C2", "HTTP"), ("R2", "C2", "C3", "DATABASE"), ("R3", "C2", "C4", "HTTP"),
    ]
    assert [(e["source"], e["target"]) for e in detailed["module_edges"]] == [("M1", "M2"), ("M2", "M3")]
    assert detailed["table_edges"] == []  # the design has a single table and no foreign keys


def test_detailed_diagram_follows_table_relationships(db, planned):
    def two_tables(d):
        second = {**d["tables"][0], "table_id": "TBL2", "name": "verification_codes",
                  "columns": [*d["tables"][0]["columns"], {"name": "account_id", "type": "uuid", "primary_key": False,
                                                           "nullable": False, "unique": False, "description": None}]}
        d["tables"].append(second)
        d["table_relationships"] = [{"relationship_id": "TR1", "source_table_id": "TBL2", "source_column": "account_id",
                                     "target_table_id": "TBL1", "target_column": "id", "cardinality": "ONE_TO_MANY",
                                     "description": None}]

    detailed = detailed_for(db, planned, lld_edit=two_tables)
    assert [(e["id"], e["source"], e["target"], e["source_column"], e["cardinality"]) for e in detailed["table_edges"]] == [
        ("TR1", "TBL2", "TBL1", "account_id", "ONE_TO_MANY")
    ]


def test_tables_are_not_guessed_into_a_component_when_there_is_no_single_database(db, planned):
    def no_database(d):
        d["components"][2]["type"] = "SERVICE"  # C3 is no longer a database

    detailed = detailed_for(db, planned, hld_edit=no_database)
    by_id = {c["id"]: c for c in detailed["containers"]}
    assert all(c["tables"] == [] for c in detailed["containers"] if c["id"] != "DATA_MODEL")
    assert by_id["DATA_MODEL"]["label"] == "Database tables"
    assert [t["name"] for t in by_id["DATA_MODEL"]["tables"]] == ["customer_accounts"]

    def two_databases(d):
        d["components"][3]["type"] = "DATABASE"  # C4 becomes a second database

    again = detailed_for(db, planned, hld_edit=two_databases)
    assert "DATA_MODEL" in {c["id"] for c in again["containers"]}  # ambiguous owner: still not guessed


def test_endpoint_without_a_controller_is_listed_under_its_component(db, planned):
    def loose(d):
        d["apis"][0]["module_id"] = None

    by_id = {c["id"]: c for c in detailed_for(db, planned, lld_edit=loose)["containers"]}
    assert [e["path"] for e in by_id["C2"]["endpoints"]] == ["/api/register"]
    assert by_id["C2"]["modules"][0]["endpoints"] == []


# ---------------------------------------------------------------------------
# Actors, deployment nodes and relationship protocols (inputs of the visual HLD diagrams)
# ---------------------------------------------------------------------------


def test_actors_and_deployment_are_stored_with_the_hld(db, planned):
    run_architect(db, planned, good_provider())
    (design,) = design_rows(db, planned)

    assert [(a["actor_id"], a["name"], a["component_ids"]) for a in design.hld["actors"]] == [("A1", "Customer", ["C1"])]
    assert [(n["node_id"], n["kind"], n["component_ids"]) for n in design.hld["deployment"]] == [
        ("DN1", "CLIENT_DEVICE", ["C1"]), ("DN2", "CONTAINER", ["C2"]), ("DN3", "SERVER", ["C3"]),
    ]
    assert [r["protocol"] for r in design.hld["relationships"]] == ["HTTPS/JSON", "SQL", "HTTPS"]
    run = architect_runs(db, planned)[0]
    assert run.output_summary["actors"] == 1 and run.output_summary["deployment_nodes"] == 3
    assert run.output_summary["warnings"] == [w for w in run.output_summary["warnings"] if "actors" not in w and "deployment" not in w.lower()]


def test_designs_saved_before_actors_and_deployment_existed_still_load(db, planned):
    old = hld_dict(context_of(db, planned))
    for key in ("actors", "deployment"):
        del old[key]
    for relationship in old["relationships"]:
        del relationship["protocol"]
    hld = HighLevelDesign.model_validate(old)
    assert hld.actors == [] and hld.deployment == [] and hld.relationships[0].protocol is None


def test_missing_actors_and_deployment_are_coverage_gaps_not_errors(db, planned):
    ctx = context_of(db, planned)
    data = hld_dict(ctx)
    data["actors"], data["deployment"] = [], []
    issues = validate_hld(HighLevelDesign.model_validate(data), ctx.references)

    assert issues.errors == []
    assert any("names no actors" in gap for gap in issues.coverage_gaps)
    assert any("no deployment nodes" in gap for gap in issues.coverage_gaps)


def test_components_missing_from_the_deployment_are_reported(db, planned):
    ctx = context_of(db, planned)
    data = hld_dict(ctx)
    data["deployment"] = data["deployment"][:2]  # the database (C3) is not placed; the external C4 never needs to be
    issues = validate_hld(HighLevelDesign.model_validate(data), ctx.references)
    assert issues.errors == [] and issues.coverage_gaps == ["Components not placed on any deployment node: C3."]


def test_a_missing_actor_list_is_fed_back_for_one_repair_and_then_accepted_with_a_warning(db, planned):
    def without_actors(d):
        d["actors"] = []

    repaired = ScriptedArchitectProvider(hld=[mutated(registration_hld, without_actors), registration_hld], lld=[registration_lld])
    run = run_architect(db, planned, repaired)
    assert run.output_summary["attempts"]["hld"] == 2
    assert any("names no actors" in problem for problem in repaired.hld_calls[1]["feedback"])
    assert design_rows(db, planned)[0].hld["actors"]

    stubborn = ScriptedArchitectProvider(hld=[mutated(registration_hld, without_actors)], lld=[registration_lld])
    run = run_architect(db, planned, stubborn)
    assert run.status == "COMPLETED" and run.output_summary["attempts"]["hld"] == 2
    assert any("Coverage gap" in w and "names no actors" in w for w in run.output_summary["warnings"])


def test_the_prompt_asks_for_actors_deployment_and_protocols(db, planned):
    ctx = context_of(db, planned)
    prompt = hld_prompt("Registration", "desc", ctx.requirements.payload, ctx.plan_payload, {}, None)
    for needle in ("actors  ", "deployment  ", "`protocol`", "ONLY when the requirements or your stated decisions support"):
        assert needle in prompt, needle
