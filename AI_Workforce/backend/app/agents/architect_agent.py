"""System Architect AI.

Workflow (each step is recorded in ``AgentRun.output_summary["steps"]``)::

    load_context -> generate_hld -> validate_hld -> generate_lld -> validate_design -> persist

* ``load_context`` loads the saved Requirements Analyst output and Project Manager plan for
  this project and refuses to run without them.
* ``generate_hld`` asks the LLM for the high-level design; ``validate_hld`` checks it against
  the real requirement / task ids. Problems are fed back for one repair attempt.
* ``generate_lld`` asks for the low-level design on top of the validated HLD;
  ``validate_design`` checks the LLD, its consistency with the HLD and requirement coverage,
  again with one repair attempt. Only coverage gaps may remain after that, as warnings.
* ``persist`` replaces the project's previous design in a single transaction, and derives the
  architecture diagram and traceability matrix from the validated design. If anything before
  it fails, the previous design is left untouched.

Run it through the workflow (``app.workflow``), which adds the shared-state hand-off and the
``validate_architecture`` gate.
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..llm.base import LLMProvider
from ..models import AgentRun, ArchDesign, Project
from ..schemas_architect import ARCHITECT_AGENT_NAME, HighLevelDesign, LowLevelDesign
from .architect_context import PREFERRED_STACK, ArchitectContext, MissingPlanError, build_architect_context
from .architect_validation import (
    build_diagram,
    build_traceability,
    design_counts,
    normalize_design,
    validate_design,
    validate_hld,
)
from .pm_context import MissingRequirementsError

logger = logging.getLogger(__name__)

MAX_ATTEMPTS = 2
STALE_RUN_AFTER = timedelta(minutes=20)

__all__ = [
    "ArchitectError",
    "ArchitectRunInProgressError",
    "ArchitectureValidationError",
    "MissingPlanError",
    "MissingRequirementsError",
    "run_architect",
]


class ArchitectError(RuntimeError):
    pass


class ArchitectRunInProgressError(ArchitectError):
    pass


class ArchitectureValidationError(ArchitectError):
    def __init__(self, message: str, problems: list[str] | None = None):
        super().__init__(message)
        self.problems = problems or []


@dataclass
class ArchitectState:
    project: Project
    context: ArchitectContext | None = None
    hld: HighLevelDesign | None = None
    lld: LowLevelDesign | None = None
    warnings: list[str] = field(default_factory=list)
    steps: list[dict] = field(default_factory=list)
    attempts: dict[str, int] = field(default_factory=dict)

    def record(self, node: str, status: str, **detail) -> None:
        self.steps.append({"node": node, "status": status, **detail})


def run_architect(db: Session, project: Project, provider: LLMProvider) -> AgentRun:
    _ensure_not_already_running(db, project.id)

    state = ArchitectState(project=project)
    # Loading the context runs before a run is recorded: with no inputs nothing was attempted.
    state.context = build_architect_context(db, project)
    state.warnings.extend(state.context.warnings)
    refs = state.context.references
    state.record(
        "load_context",
        "ok",
        requirements=len(refs.functional_ids),
        non_functional=len(refs.nfr_ids),
        tasks=len(refs.task_ids),
    )

    agent_run = AgentRun(
        project_id=project.id,
        agent_name=ARCHITECT_AGENT_NAME,
        status="PROCESSING",
        input_summary={
            "project_name": project.name,
            "requirements_run_id": state.context.requirements_run_id,
            "plan_run_id": state.context.plan_run_id,
            "requirements": len(refs.functional_ids),
            "tasks": len(refs.task_ids),
        },
    )
    db.add(agent_run)
    db.commit()

    try:
        _generate_hld_nodes(state, provider)
        _generate_lld_nodes(state, provider)
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


def _generate_hld_nodes(state: ArchitectState, provider: LLMProvider) -> None:
    project, context = state.project, state.context
    feedback: list[str] | None = None

    for attempt in range(1, MAX_ATTEMPTS + 1):
        state.attempts["hld"] = attempt
        final_attempt = attempt == MAX_ATTEMPTS

        try:
            generated = provider.generate_hld(
                project.name,
                project.description or "",
                context.requirements.payload,
                context.plan_payload,
                PREFERRED_STACK,
                feedback,
            )
        except ValidationError as exc:
            state.record("generate_hld", "malformed", attempt=attempt)
            if final_attempt:
                raise ArchitectureValidationError(
                    "The AI returned a malformed high-level design; nothing was saved.", [str(exc)[:1000]]
                ) from exc
            feedback = [f"Output was not valid against the schema: {str(exc)[:600]}"]
            continue
        state.record("generate_hld", "ok", attempt=attempt, components=len(generated.components))

        hld, _, notes = normalize_design(generated)
        issues = validate_hld(hld, context.references)
        state.record(
            "validate_hld",
            "ok" if not issues.needs_repair else "issues",
            attempt=attempt,
            errors=len(issues.errors),
            coverage_gaps=len(issues.coverage_gaps),
        )

        if not issues.needs_repair:
            state.hld = hld
            state.warnings.extend(notes)
            return
        if not final_attempt:
            feedback = issues.feedback()
            continue
        if issues.errors:
            raise ArchitectureValidationError(
                "The generated high-level design failed validation and was not saved: " + "; ".join(issues.errors[:5]),
                issues.errors,
            )
        # Only coverage gaps remain after the repair attempt (for example no actors): keep the design, but say so.
        state.hld = hld
        state.warnings.extend(notes)
        state.warnings.extend(f"Coverage gap: {gap}" for gap in issues.coverage_gaps)
        return


def _generate_lld_nodes(state: ArchitectState, provider: LLMProvider) -> None:
    project, context, hld = state.project, state.context, state.hld
    hld_payload = hld.model_dump(mode="json")
    feedback: list[str] | None = None

    for attempt in range(1, MAX_ATTEMPTS + 1):
        state.attempts["lld"] = attempt
        final_attempt = attempt == MAX_ATTEMPTS

        try:
            generated = provider.generate_lld(
                project.name,
                project.description or "",
                context.requirements.payload,
                context.plan_payload,
                hld_payload,
                PREFERRED_STACK,
                feedback,
            )
        except ValidationError as exc:
            state.record("generate_lld", "malformed", attempt=attempt)
            if final_attempt:
                raise ArchitectureValidationError(
                    "The AI returned a malformed low-level design; nothing was saved.", [str(exc)[:1000]]
                ) from exc
            feedback = [f"Output was not valid against the schema: {str(exc)[:600]}"]
            continue
        state.record("generate_lld", "ok", attempt=attempt, modules=len(generated.modules), apis=len(generated.apis))

        _, lld, notes = normalize_design(hld, generated)
        issues = validate_design(hld, lld, context.references)
        state.record(
            "validate_design",
            "ok" if not issues.needs_repair else "issues",
            attempt=attempt,
            errors=len(issues.errors),
            coverage_gaps=len(issues.coverage_gaps),
        )

        if not issues.needs_repair:
            _accept(state, lld, notes, issues)
            return
        if not final_attempt:
            feedback = issues.feedback()
            continue
        if issues.errors:
            raise ArchitectureValidationError(
                "The generated low-level design failed validation and was not saved: " + "; ".join(issues.errors[:5]),
                issues.errors,
            )
        # Only coverage gaps remain after the repair attempt: keep the design, but say so.
        state.warnings.extend(f"Coverage gap: {gap}" for gap in issues.coverage_gaps)
        _accept(state, lld, notes, issues)
        return


def _accept(state: ArchitectState, lld: LowLevelDesign, notes: list[str], issues) -> None:
    state.lld = lld
    state.warnings.extend(notes)
    state.warnings.extend(issues.warnings)


def _persist_node(db: Session, state: ArchitectState, agent_run: AgentRun) -> None:
    project, context, hld, lld = state.project, state.context, state.hld, state.lld
    assert hld is not None and lld is not None and context is not None

    previous = db.scalar(select(ArchDesign).where(ArchDesign.project_id == project.id))
    if previous is not None:
        db.delete(previous)
        db.flush()

    warnings = list(dict.fromkeys(state.warnings))
    traceability = build_traceability(hld, lld, context.references)
    db.add(
        ArchDesign(
            project_id=project.id,
            agent_run_id=agent_run.id,
            requirements_run_id=context.requirements_run_id,
            plan_run_id=context.plan_run_id,
            hld=hld.model_dump(mode="json"),
            lld=lld.model_dump(mode="json"),
            diagram=build_diagram(hld),
            traceability=traceability,
            open_items=[item.model_dump(mode="json") for item in [*hld.open_items, *lld.open_items]],
            warnings=warnings,
        )
    )

    covered = sum(1 for entry in traceability if entry["status"] == "COVERED")
    agent_run.status = "COMPLETED"
    agent_run.completed_at = datetime.now(timezone.utc)
    agent_run.output_summary = {
        "requirements_run_id": context.requirements_run_id,
        "plan_run_id": context.plan_run_id,
        **design_counts(hld, lld),
        "traced_requirements": covered,
        "total_requirements": len(traceability),
        "attempts": state.attempts,
        "steps": [*state.steps, {"node": "persist", "status": "ok"}],
        "warnings": warnings,
    }


def _ensure_not_already_running(db: Session, project_id: int) -> None:
    running = db.scalar(
        select(AgentRun)
        .where(
            AgentRun.project_id == project_id,
            AgentRun.agent_name == ARCHITECT_AGENT_NAME,
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
        raise ArchitectRunInProgressError("A System Architect run is already in progress for this project.")
