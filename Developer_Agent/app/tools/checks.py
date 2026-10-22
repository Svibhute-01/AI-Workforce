from app.schemas.developer import FileChange
from app.tools.validators import validate_python_syntax
from app.tools.workspace import Workspace
from app.tools.runner import LocalRunner

# The steps we run, in order. We stop at the first failure.
STEPS = ["install", "check_imports", "test"]


def run_all_checks(workspace: Workspace, changes: list[FileChange]) -> list[str]:
    """Write files, run real checks. Returns error messages (empty = all good)."""

    # 1. Syntax check first: free and instant
    errors = validate_python_syntax(changes)
    if errors:
        return errors

    # 2. Write files to disk
    workspace.apply_changes(changes)

    # 3. Make sure the project has its own virtual environment
    runner = LocalRunner(workspace.root)
    if not runner.venv_dir.exists():
        result = runner.run("create_venv")
        if not result.ok:
            return [f"create_venv failed:\n{result.summary()}"]

    # 4. Run each step; stop at the first failure
    for step in STEPS:
        result = runner.run(step)
        print(f"[checks] {step}: {'ok' if result.ok else 'FAILED'}")
        if not result.ok:
            return [f"Step '{step}' failed:\n{result.summary()}"]

    return []