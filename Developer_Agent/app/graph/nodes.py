from app import progress
from app.chains.developer_chain import build_developer_chain
from app.graph.states import DeveloperState
from app.tools.workspace import Workspace
from app.tools.checks import run_all_checks
from app.stacks import contract_text, get_stack, rules_for
from app.tools.context import build_existing_files_context
from app.tools.context import build_context
from app.timing import Timings
from app.llm_retry import call_with_retries

# Build the chain ONCE when this file loads.
developer_chain = build_developer_chain()


def generate_node(state: DeveloperState) -> dict:
    """Ask Gemini to implement the task, with existing files and error feedback."""
    attempt = state["retries"] + 1
    timings = Timings(state.get("timings"))
    print(f"[generate] attempt {attempt}: calling Gemini...")
    progress.report(state["project_id"], f"Attempt {attempt}: asking Gemini to write the code...")

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

    def ask_model():
        return developer_chain.invoke({
            "task": state["task"],
            "tech_stack": state["tech_stack"],
            "rules": rules_for(get_stack(state.get("stack"))) + "\n\n" + contract_text(state.get("architecture") or [], state.get("deviations") or []),
            "existing_files": existing_files,
            "feedback": feedback,
        })

    def note_retry(failed: int, attempts: int, error: BaseException, delay: int) -> None:
        message = f"Model call failed ({type(error).__name__}); trying again in {delay}s (call {failed + 1} of {attempts})"
        print(f"[generate] {message}")
        progress.report(state["project_id"], message)

    # A dropped connection is retried here instead of crashing the whole job.
    with timings.measure("llm"):
        result = call_with_retries(ask_model, on_retry=note_retry)

    print(f"[generate] got {len(result.changes)} file(s) in {timings.as_dict().get('llm', 0):.1f}s (all attempts)")
    return {"output": result, "retries": attempt, "timings": timings.as_dict()}

def validate_node(state: DeveloperState) -> dict:
    """Write the files and run real checks (syntax, install, imports, tests)."""
    workspace = Workspace(state["project_id"])
    timings = Timings(state.get("timings"))
    errors = run_all_checks(workspace, state["output"].changes, get_stack(state.get("stack")), timings=timings)

    if errors:
        print(f"[validate] FAILED:\n{errors[0][:500]}")
    else:
        print("[validate] all checks passed")

    status = "success" if not errors else "running"
    return {"validation_errors": errors, "status": status, "timings": timings.as_dict()}

def give_up_node(state: DeveloperState) -> dict:
    """Mark the run as failed after the retry cap."""
    return {"status": "failed"}