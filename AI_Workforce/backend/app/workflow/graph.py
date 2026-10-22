"""Generic LangGraph builder for the agent pipeline.

Every agent is a ``Stage``: a node that runs the agent and a validation gate that
checks its output. ``build_workflow`` wires the stages in order::

    START -> node_1 -> validate_1 -> node_2 -> validate_2 -> ... -> END

Each node and each gate has a conditional edge: success continues to the next step,
and any failure (agent error or failed validation) goes straight to END with
``workflow_status = FAILED`` and ``error`` set. LangGraph, not the caller, decides
what runs next, what is handed over through the shared state, and when to stop.

Adding an agent later is one more ``Stage`` in the list; this module does not change.
"""

import logging
from collections.abc import Callable, Sequence
from dataclasses import dataclass

from langgraph.graph import END, START, StateGraph

from .state import (
    AGENT_ERROR,
    COMPLETED,
    FAILED,
    VALIDATION_FAILED,
    StageError,
    ValidationResult,
    WorkflowState,
)

logger = logging.getLogger(__name__)

StageRun = Callable[[WorkflowState], dict]
StageValidate = Callable[[WorkflowState], ValidationResult]

_STATE_KEYS = set(WorkflowState.__annotations__)


@dataclass(frozen=True)
class Stage:
    key: str              # key in validation_results, e.g. "requirements"
    agent: str            # shown as current_agent while the stage runs
    node_name: str        # graph node that runs the agent, e.g. "requirements_analyst_node"
    validation_name: str  # graph node that validates it, e.g. "validate_requirements"
    run: StageRun         # state -> partial state update (the agent's output)
    validate: StageValidate


def build_workflow(stages: Sequence[Stage]):
    """Compile the ordered stages into a LangGraph workflow."""
    if not stages:
        raise ValueError("A workflow needs at least one stage.")
    names = [name for stage in stages for name in (stage.node_name, stage.validation_name)]
    keys = [stage.key for stage in stages]
    if len(set(names)) != len(names) or len(set(keys)) != len(keys):
        raise ValueError("Stage keys and node names must be unique.")

    graph = StateGraph(WorkflowState)
    for index, stage in enumerate(stages):
        graph.add_node(stage.node_name, _agent_node(stage))
        graph.add_node(stage.validation_name, _validation_node(stage, is_last=index == len(stages) - 1))

    graph.add_edge(START, stages[0].node_name)
    for index, stage in enumerate(stages):
        following = stages[index + 1].node_name if index + 1 < len(stages) else END
        graph.add_conditional_edges(stage.node_name, _route, {"ok": stage.validation_name, "failed": END})
        graph.add_conditional_edges(stage.validation_name, _route, {"ok": following, "failed": END})
    return graph.compile()


def _route(state: WorkflowState) -> str:
    return "failed" if state.get("error") else "ok"


def _agent_node(stage: Stage):
    def node(state: WorkflowState) -> dict:
        update: dict = {"current_agent": stage.agent}
        try:
            output = stage.run(state) or {}
            unknown = set(output) - _STATE_KEYS
            if unknown:
                raise ValueError(f"{stage.agent} returned unknown state fields: {sorted(unknown)}")
        except StageError as exc:
            return {**update, "workflow_status": FAILED, "error": exc.to_info(stage.key)}
        except Exception as exc:  # noqa: BLE001 - any agent failure becomes a workflow error
            logger.exception("Workflow stage %s failed", stage.key)
            message = str(exc) or exc.__class__.__name__
            return {**update, "workflow_status": FAILED, "error": {"stage": stage.key, "kind": AGENT_ERROR, "message": message}}
        return {**update, **output}

    return node


def _validation_node(stage: Stage, is_last: bool):
    def node(state: WorkflowState) -> dict:
        try:
            result = stage.validate(state)
        except Exception as exc:  # noqa: BLE001
            logger.exception("Workflow validation %s failed to run", stage.key)
            result = {"passed": False, "errors": [f"Validation could not run: {exc}"], "warnings": []}

        results = {**(state.get("validation_results") or {}), stage.key: result}
        if not result["passed"]:
            message = "; ".join(result["errors"]) or "Validation failed."
            return {
                "validation_results": results,
                "workflow_status": FAILED,
                "error": {"stage": stage.key, "kind": VALIDATION_FAILED, "message": message},
            }
        update: dict = {"validation_results": results}
        if is_last:
            update["workflow_status"] = COMPLETED
        return update

    return node
