from app.config import SMOKE_CHECK
from app.schemas.developer import FileChange
from app.stacks import get_stack
from app.tools.runner import make_runner
from app.tools.smoke import smoke_check
from app.tools.workspace import Workspace


def run_all_checks(workspace: Workspace, changes: list[FileChange], stack=None, runner=None) -> list[str]:
    """Write files, run the stack's real checks. Returns error messages (empty = all good)."""
    stack = stack or get_stack(None)

    # 1. Syntax check first: free and instant, and nothing is written when it fails
    if stack.syntax:
        errors = stack.syntax(changes)
        if errors:
            return errors

    # 2. Write files to disk
    workspace.apply_changes(changes)

    # 3. Checks that need the files on disk (for example: does the page link to files that exist?)
    if stack.structure:
        errors = stack.structure(workspace)
        if errors:
            return errors

    # 4. Make sure the project has its own environment (a virtual environment for Python)
    runner = runner or make_runner(workspace.root, stack)
    created = runner.setup()
    if created is not None and not created.ok:
        return [f"Creating the project environment failed:\n{created.summary()}"]

    # 5. Run each step; stop at the first failure
    for step in stack.steps:
        result = runner.run(step)
        print(f"[checks] {step}: {'ok' if result.ok else 'FAILED'}")
        if not result.ok:
            return [f"Step '{step}' failed:\n{result.summary()}"]

    # 6. Start the app and ask for "/"
    if SMOKE_CHECK:
        problem = smoke_check(runner, stack)
        print(f"[checks] smoke: {'FAILED' if problem else 'ok'}")
        if problem:
            return [problem]

    return []
