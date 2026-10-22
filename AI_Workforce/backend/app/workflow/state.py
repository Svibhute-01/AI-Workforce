"""Shared state carried through the LangGraph workflow.

The state holds a small, JSON-friendly summary of each agent's output. The full
artifacts (requirements, tasks, sprints, ...) stay in PostgreSQL where the agents
already persist them; the state records what was produced and which run produced it.

Only agents that exist today populate their field. ``architecture``, ``code`` and
``test_results`` are declared so future agents can use them, and stay absent until
those agents exist.
"""

from typing import Any, TypedDict

# workflow_status
RUNNING = "RUNNING"
COMPLETED = "COMPLETED"
FAILED = "FAILED"

# error["kind"]
MISSING_INPUT = "missing_input"          # a prerequisite is missing (no SRS, no requirements)
IN_PROGRESS = "in_progress"              # the same agent is already running for this project
PLAN_INVALID = "plan_invalid"            # the Project Manager rejected its own plan after repair attempts
ARCHITECTURE_INVALID = "architecture_invalid"  # the Architect's design failed validation after repair attempts
VALIDATION_FAILED = "validation_failed"  # a workflow validation gate rejected an agent's output
AGENT_ERROR = "agent_error"              # unexpected failure inside an agent


class ValidationResult(TypedDict):
    passed: bool
    errors: list[str]
    warnings: list[str]


class ErrorInfo(TypedDict):
    stage: str
    kind: str
    message: str


class WorkflowState(TypedDict, total=False):
    project_id: int
    requirements: dict[str, Any] | None   # Requirements Analyst summary
    project_plan: dict[str, Any] | None   # Project Manager summary
    architecture: dict[str, Any] | None   # future: Software Architect
    code: dict[str, Any] | None           # future: Developer / Code Generation
    test_results: dict[str, Any] | None   # future: QA / Testing
    current_agent: str | None
    workflow_status: str
    error: ErrorInfo | None
    validation_results: dict[str, ValidationResult]


class StageError(Exception):
    """An expected, classified failure raised by a stage so the graph can route it."""

    def __init__(self, kind: str, message: str):
        super().__init__(message)
        self.kind = kind
        self.message = message

    def to_info(self, stage: str) -> ErrorInfo:
        return {"stage": stage, "kind": self.kind, "message": self.message}


def initial_state(project_id: int) -> WorkflowState:
    """Starting state: only bookkeeping fields, no agent output."""
    return WorkflowState(
        project_id=project_id,
        current_agent=None,
        workflow_status=RUNNING,
        error=None,
        validation_results={},
    )
