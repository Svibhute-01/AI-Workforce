"""Project Manager AI.

Workflow (each step is recorded in ``AgentRun.output_summary["steps"]``)::

    validate_requirements -> generate_plan -> validate_plan -> persist

* ``validate_requirements`` loads the saved Requirements Analyst output for this
  project and refuses to run without it.
* ``generate_plan`` asks the LLM for a structured ``ProjectPlan``.
* ``validate_plan`` checks the plan against the real requirement ids, the
  dependency graph and sprint order. Problems are fed back to the LLM for one
  repair attempt.
* ``persist`` replaces the project's previous plan in a single transaction. If
  anything before it fails, the previous plan is left untouched.
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..llm.base import LLMProvider
from ..models import (
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
from ..schemas_pm import PM_AGENT_NAME, ProjectPlan
from .pm_context import MissingRequirementsError, RequirementsContext, build_requirements_context
from .pm_validation import PlanIssues, compute_execution_order, normalize_plan, validate_plan, _parse_date

logger = logging.getLogger(__name__)

MAX_ATTEMPTS = 2
STALE_RUN_AFTER = timedelta(minutes=15)

__all__ = [
    "MissingRequirementsError",
    "PlanValidationError",
    "ProjectManagerError",
    "RunInProgressError",
    "run_project_manager",
]


class ProjectManagerError(RuntimeError):
    pass


class RunInProgressError(ProjectManagerError):
    pass


class PlanValidationError(ProjectManagerError):
    def __init__(self, message: str, problems: list[str] | None = None):
        super().__init__(message)
        self.problems = problems or []


@dataclass
class PMState:
    project: Project
    context: RequirementsContext | None = None
    plan: ProjectPlan | None = None
    execution_order: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    steps: list[dict] = field(default_factory=list)
    attempts: int = 0

    def record(self, node: str, status: str, **detail) -> None:
        self.steps.append({"node": node, "status": status, **detail})


def run_project_manager(db: Session, project: Project, provider: LLMProvider) -> AgentRun:
    _ensure_not_already_running(db, project.id)

    state = PMState(project=project)
    # Step 1 runs before a run is recorded: with no requirements nothing was attempted.
    state.context = _validate_requirements_node(db, state)

    agent_run = AgentRun(
        project_id=project.id,
        agent_name=PM_AGENT_NAME,
        status="PROCESSING",
        input_summary={
            "project_name": project.name,
            "requirements_run_id": state.context.requirements_run_id,
            "requirements": len(state.context.payload["functional_requirements"]),
            "user_stories": len(state.context.payload["user_stories"]),
        },
    )
    db.add(agent_run)
    db.commit()

    try:
        _generate_and_validate_nodes(state, provider)
        _persist_node(db, state, agent_run)
        db.commit()
        return agent_run
    except Exception as exc:
        db.rollback()
        failed_run = db.get(AgentRun, agent_run.id)
        if failed_run:
            failed_run.status = "FAILED"
            failed_run.completed_at = datetime.now(timezone.utc)
            failed_run.error = str(exc)[:4000]
            failed_run.output_summary = {"steps": state.steps, "attempts": state.attempts}
            db.commit()
        raise


# --- nodes ------------------------------------------------------------------


def _validate_requirements_node(db: Session, state: PMState) -> RequirementsContext:
    context = build_requirements_context(db, state.project)
    state.warnings.extend(context.warnings)
    state.record(
        "validate_requirements",
        "ok",
        requirements=len(context.payload["functional_requirements"]),
        user_stories=len(context.payload["user_stories"]),
    )
    return context


def _generate_and_validate_nodes(state: PMState, provider: LLMProvider) -> None:
    project, context = state.project, state.context
    project_info = {
        "start_date": project.start_date.isoformat() if project.start_date else None,
        "due_date": project.due_date.isoformat() if project.due_date else None,
    }
    feedback: list[str] | None = None

    for attempt in range(1, MAX_ATTEMPTS + 1):
        state.attempts = attempt
        final_attempt = attempt == MAX_ATTEMPTS

        try:
            generated = provider.generate_project_plan(
                project.name, project.description or "", context.payload, project_info, feedback
            )
        except ValidationError as exc:
            state.record("generate_plan", "malformed", attempt=attempt)
            if final_attempt:
                raise PlanValidationError(
                    "The AI returned a malformed project plan; nothing was saved.", [str(exc)[:1000]]
                ) from exc
            feedback = [f"Output was not valid against the schema: {str(exc)[:600]}"]
            continue
        state.record("generate_plan", "ok", attempt=attempt, tasks=len(generated.tasks))

        plan, normalize_warnings = normalize_plan(generated, project.start_date, project.due_date)
        issues: PlanIssues = validate_plan(plan, context)
        state.record(
            "validate_plan",
            "ok" if not issues.needs_repair else "issues",
            attempt=attempt,
            errors=len(issues.errors),
            coverage_gaps=len(issues.coverage_gaps),
        )

        if not issues.needs_repair:
            _accept(state, plan, normalize_warnings, issues)
            return
        if not final_attempt:
            feedback = issues.feedback()
            continue
        if issues.errors:
            raise PlanValidationError(
                "The generated project plan failed validation and was not saved: " + "; ".join(issues.errors[:5]),
                issues.errors,
            )
        # Only coverage gaps remain after the repair attempt: keep the plan, but say so.
        state.warnings.extend(f"Coverage gap: {gap}" for gap in issues.coverage_gaps)
        _accept(state, plan, normalize_warnings, issues)
        return


def _accept(state: PMState, plan: ProjectPlan, normalize_warnings: list[str], issues: PlanIssues) -> None:
    state.warnings.extend(normalize_warnings)
    state.warnings.extend(issues.warnings)
    state.plan = plan
    state.execution_order = compute_execution_order(plan)


def _persist_node(db: Session, state: PMState, agent_run: AgentRun) -> None:
    project, context, plan = state.project, state.context, state.plan
    assert plan is not None and context is not None

    previous = db.scalar(select(PMPlan).where(PMPlan.project_id == project.id))
    if previous is not None:
        db.delete(previous)
        db.flush()

    record = PMPlan(
        project_id=project.id,
        agent_run_id=agent_run.id,
        requirements_run_id=context.requirements_run_id,
        execution_summary=plan.execution_summary,
        definition_of_done=plan.definition_of_done.items,
        assumptions=[a.strip() for a in plan.assumptions if a and a.strip()],
        execution_order=state.execution_order,
        warnings=state.warnings,
    )
    db.add(record)
    db.flush()

    common = {"project_id": project.id, "plan_id": record.id}
    for epic in plan.epics:
        db.add(PMEpic(**common, **epic.model_dump()))

    position = {task_id: index for index, task_id in enumerate(state.execution_order)}
    for task in plan.tasks:
        data = task.model_dump()
        sprint = data.pop("sprint")
        db.add(
            PMTask(
                **common,
                **data,
                sprint_id=sprint,
                status="TODO",
                source_references=_task_sources(task, context),
                execution_index=position.get(task.task_id, len(position)),
            )
        )
    for dependency in plan.dependencies:
        db.add(PMTaskDependency(**common, **dependency.model_dump()))
    for index, sprint in enumerate(plan.sprints):
        data = sprint.model_dump()
        data["start_date"] = _parse_date(data["start_date"])
        data["end_date"] = _parse_date(data["end_date"])
        db.add(PMSprint(**common, sequence=index, **data))
    for index, milestone in enumerate(plan.milestones):
        data = milestone.model_dump()
        target = data.pop("target_sprint")
        db.add(PMMilestone(**common, sequence=index, target_sprint_id=target, **data))
    for risk in plan.risks:
        db.add(PMRisk(**common, **risk.model_dump()))

    agent_run.status = "COMPLETED"
    agent_run.completed_at = datetime.now(timezone.utc)
    agent_run.output_summary = {
        "requirements_run_id": context.requirements_run_id,
        "epics": len(plan.epics),
        "tasks_generated": len(plan.tasks),
        "sprints": len(plan.sprints),
        "milestones": len(plan.milestones),
        "risks": len(plan.risks),
        "total_story_points": sum(t.story_points for t in plan.tasks),
        "attempts": state.attempts,
        "steps": [*state.steps, {"node": "persist", "status": "ok"}],
        "warnings": state.warnings,
    }


def _task_sources(task, context: RequirementsContext) -> list[dict]:
    """Source references come from the cited requirements, never from the LLM."""
    cited = [task.related_requirement_id, task.related_story_id, *task.related_artifact_ids]
    seen: set[tuple] = set()
    result: list[dict] = []
    for key in cited:
        for ref in context.source_refs.get(key or "", []):
            identity = (ref.get("document"), ref.get("page"))
            if identity not in seen:
                seen.add(identity)
                result.append(ref)
    return result


def _ensure_not_already_running(db: Session, project_id: int) -> None:
    running = db.scalar(
        select(AgentRun)
        .where(
            AgentRun.project_id == project_id,
            AgentRun.agent_name == PM_AGENT_NAME,
            AgentRun.status == "PROCESSING",
        )
        .order_by(AgentRun.started_at.desc())
    )
    if running is None:
        return
    started = running.started_at
    if started is not None and started.tzinfo is None:
        started = started.replace(tzinfo=timezone.utc)
    if started is None or datetime.now(timezone.utc) - started < STALE_RUN_AFTER:
        raise RunInProgressError("A Project Manager run is already in progress for this project.")
