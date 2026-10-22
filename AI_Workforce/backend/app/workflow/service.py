"""Workflow service: the layer between FastAPI and LangGraph."""

from collections.abc import Callable, Sequence
from sqlalchemy.orm import Session

from ..llm.base import LLMProvider
from ..models import Project
from ..rag.vector_store import ProjectVectorStore
from .graph import Stage, build_workflow
from .stages import WorkflowDeps, default_stages
from .state import (
    ARCHITECTURE_INVALID,
    COMPLETED,
    IN_PROGRESS,
    MISSING_INPUT,
    PLAN_INVALID,
    VALIDATION_FAILED,
    WorkflowState,
    initial_state,
)

_HTTP_STATUS = {
    MISSING_INPUT: 409,
    IN_PROGRESS: 409,
    PLAN_INVALID: 422,
    ARCHITECTURE_INVALID: 422,
    VALIDATION_FAILED: 422,
}


class WorkflowFailure(RuntimeError):
    """The graph ended without completing. Carries the final state for the caller."""

    def __init__(self, state: WorkflowState):
        error = state.get("error") or {"stage": "unknown", "kind": "agent_error", "message": "The workflow did not complete."}
        passed = [key for key, result in (state.get("validation_results") or {}).items() if result.get("passed")]
        message = f"Workflow stopped at '{error['stage']}': {error['message']}"
        if passed:
            message += f" Completed stages: {', '.join(passed)}."
        super().__init__(message)
        self.state = state
        self.kind = error["kind"]
        self.status_code = _HTTP_STATUS.get(error["kind"], 503)


class WorkflowService:
    def __init__(
        self,
        db: Session,
        provider: LLMProvider,
        vector_store: ProjectVectorStore | None = None,
        stage_factory: Callable[[WorkflowDeps], list[Stage]] = default_stages,
    ):
        self._deps_args = (db, provider, vector_store)
        self._stage_factory = stage_factory

    def run(self, project: Project, only: Sequence[str] | None = None) -> WorkflowState:
        """Run the pipeline for one project through LangGraph; raise WorkflowFailure if it stops early.

        ``only`` limits the graph to the named stages (for example ``["architecture"]`` to
        re-run just the Architect from the saved requirements and plan). It is still the
        same LangGraph workflow: the stage's node and its validation gate both run.
        """
        db, provider, vector_store = self._deps_args
        stages = self._stage_factory(WorkflowDeps(db=db, project=project, provider=provider, vector_store=vector_store))
        if only is not None:
            stages = [stage for stage in stages if stage.key in set(only)]
            if not stages:
                raise ValueError(f"No workflow stage matches {list(only)}.")
        final = build_workflow(stages).invoke(initial_state(project.id))
        if final.get("workflow_status") != COMPLETED:
            raise WorkflowFailure(final)
        return final
