from langgraph.graph import END
from app.config import MAX_RETRIES
from app.graph.states import DeveloperState


def route_after_validate(state: DeveloperState) -> str:
    """Decide what happens after validation."""
    if not state["validation_errors"]:
        return END

    if state["retries"] >= MAX_RETRIES:
        print(f"[router] giving up after {state['retries']} attempts")
        return "give_up"

    print("[router] errors found, retrying...")
    return "generate"