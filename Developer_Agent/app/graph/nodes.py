from app.chains.developer_chain import build_developer_chain
from app.graph.states import DeveloperState
from app.tools.workspace import Workspace
from app.tools.checks import run_all_checks
from app.stacks import get_stack, rules_for
from app.tools.context import build_existing_files_context
from app.tools.context import build_context

# Build the chain ONCE when this file loads.
developer_chain = build_developer_chain()


def generate_node(state: DeveloperState) -> dict:
    """Ask Gemini to implement the task, with existing files and error feedback."""
    attempt = state["retries"] + 1
    print(f"[generate] attempt {attempt}: calling Gemini...")

    workspace = Workspace(state["project_id"])
    existing_files = build_context(workspace, state["task"])
    print(f"[generate] existing context: {len(existing_files)} chars")

    feedback = ""
    if state["validation_errors"]:
        error_text = "\n".join(state["validation_errors"])
        feedback = (
            "Your previous attempt had these errors. Fix them:\n"
            f"{error_text}\n\n"
        )

    result = developer_chain.invoke({
        "task": state["task"],
        "tech_stack": state["tech_stack"],
        "rules": rules_for(get_stack(state.get("stack"))),
        "existing_files": existing_files,
        "feedback": feedback,
    })

    print(f"[generate] got {len(result.changes)} file(s)")
    return {"output": result, "retries": attempt}

def validate_node(state: DeveloperState) -> dict:
    """Write the files and run real checks (syntax, install, imports, tests)."""
    workspace = Workspace(state["project_id"])
    errors = run_all_checks(workspace, state["output"].changes, get_stack(state.get("stack")))

    if errors:
        print(f"[validate] FAILED:\n{errors[0][:500]}")
    else:
        print("[validate] all checks passed")

    status = "success" if not errors else "running"
    return {"validation_errors": errors, "status": status}

def give_up_node(state: DeveloperState) -> dict:
    """Mark the run as failed after the retry cap."""
    return {"status": "failed"}