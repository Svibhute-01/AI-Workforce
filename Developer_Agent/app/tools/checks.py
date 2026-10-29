from app import progress
from app.config import SMOKE_CHECK
from app.schemas.developer import FileChange
from app.stacks import get_stack
from app.timing import Timings
from app.tools import deps
from app.tools.runner import make_runner
from app.tools.smoke import smoke_check
from app.tools.workspace import Workspace


def run_all_checks(workspace: Workspace, changes: list[FileChange], stack=None, runner=None,
                   timings: Timings | None = None) -> list[str]:
    """Write files, run the stack's real checks. Returns error messages (empty = all good).

    `timings` (optional) collects how long each slow step took; progress messages go to the job log.
    """
    stack = stack or get_stack(None)
    timings = timings if timings is not None else Timings()
    project_id = workspace.root.name

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
    with timings.measure("setup"):
        created = runner.setup()
    if created is not None and not created.ok:
        return [f"Creating the project environment failed:\n{created.summary()}"]

    # 5. Run each step; stop at the first failure
    for step in stack.steps:
        # A retry that did not touch the dependency files must not pay for a full install again.
        if step == "install" and deps.unchanged(workspace.root, stack):
            print("[checks] install: skipped (dependency files unchanged since the last successful install)")
            progress.report(project_id, "Dependencies unchanged - skipping install")
            continue
        progress.report(project_id, f"Running {step}...")
        with timings.measure(step):
            result = runner.run(step)
        print(f"[checks] {step}: {'ok' if result.ok else 'FAILED'}")
        if step == "install":
            # Trust the environment only after a fully successful install.
            deps.record(workspace.root, stack) if result.ok else deps.forget(workspace.root, stack)
        if not result.ok:
            return [f"Step '{step}' failed:\n{result.summary()}"]

    # 6. Start the app and ask for "/"
    if SMOKE_CHECK:
        progress.report(project_id, "Starting the app to check that it answers...")
        with timings.measure("smoke"):
            problem = smoke_check(runner, stack)
        print(f"[checks] smoke: {'FAILED' if problem else 'ok'}")
        if problem:
            return [problem]

    return []
