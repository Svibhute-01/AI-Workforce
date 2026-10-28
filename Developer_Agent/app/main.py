"""Developer Agent service.

Runs next to the main AI Workforce backend (default port 8001). The browser never
calls this service: the main backend authenticates the user, checks project
ownership, and forwards requests here with the shared X-Service-Key.
"""

import hmac
import json
import logging

from fastapi import Depends, FastAPI, Header, HTTPException
from pydantic import BaseModel, Field

from app.apps import AppError, AppManager
from app.config import QA_AUTO_REPAIR_ROUNDS, RUNNER_MODE, SERVICE_KEY
from app.graph.builder import build_developer_graph
from app.jobs import JobConflict, JobStore
from app.projects import get_stack_id, set_stack_id
from app.qa.run import run_qa
from app.qa.reporting import write_report
from app.stacks import STACKS, check_contract, detect_stack, get_stack, infer_stack_from_files
from app.tools.runner import make_runner
from app.tools.workspace import Workspace, WorkspaceError

logger = logging.getLogger("developer_agent")
if not SERVICE_KEY:
    logger.warning("DEVELOPER_SERVICE_KEY is not set: the API is unauthenticated. Bind to 127.0.0.1 only.")


def require_service_key(x_service_key: str | None = Header(default=None)) -> None:
    if SERVICE_KEY and not hmac.compare_digest(x_service_key or "", SERVICE_KEY):
        raise HTTPException(status_code=401, detail="Invalid service key")


app = FastAPI(title="Developer Agent API", dependencies=[Depends(require_service_key)])

developer_graph = build_developer_graph()
jobs = JobStore()
apps = AppManager()


@app.on_event("shutdown")
def stop_previews():
    apps.stop_all()


class ProjectCreate(BaseModel):
    project_id: str


class ArchitectureItem(BaseModel):
    role: str            # frontend | backend | database | infrastructure
    technology: str
    component: str | None = None


class TaskRequest(BaseModel):
    task: str = Field(min_length=1, max_length=20000)
    tech_stack: str = "Python, FastAPI"
    stack: str | None = None   # a stack id, or None/"auto" to choose from tech_stack
    architecture: list[ArchitectureItem] = Field(default_factory=list)   # the System Architect's choices (binding)
    allow_deviation: bool = False   # build anyway when the architecture cannot be followed exactly


class QACriterion(BaseModel):
    id: str
    text: str


class QARequest(BaseModel):
    task_id: str
    task_title: str = ""
    criteria: list[QACriterion] = Field(min_length=1)
    design_text: str = ""


class RunRequest(BaseModel):
    command: str  # a NAME: create_venv, install, check_imports, test


def get_workspace(project_id: str) -> Workspace:
    try:
        return Workspace(project_id)
    except WorkspaceError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/projects")
def create_project(body: ProjectCreate):
    return {"project_id": body.project_id, "files": get_workspace(body.project_id).list_files()}


@app.get("/projects/{project_id}/files")
def list_files(project_id: str):
    return {"project_id": project_id, "files": get_workspace(project_id).list_files()}


@app.get("/projects/{project_id}/file")
def read_file(project_id: str, path: str):
    try:
        return {"path": path, "content": get_workspace(project_id).read_file(path)}
    except WorkspaceError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


def stack_info(project_id: str) -> dict:
    # A project made before stacks existed has files but no saved stack: work it out from the files.
    stack_id = get_stack_id(project_id) or infer_stack_from_files(get_workspace(project_id).list_files())
    stack = STACKS.get(stack_id) if stack_id else None
    return {
        "project_id": project_id,
        "stack": stack_id,
        "label": stack.label if stack else None,
        "commands": stack.visible_commands if stack else [],
        "can_start": bool(stack and stack.start),
        "runner": RUNNER_MODE,
        "available": [{"id": item.id, "label": item.label} for item in STACKS.values()],
    }


def resolve_stack(project_id: str, requested: str | None, tech_stack: str) -> str:
    """A project keeps the stack it started with. The first task decides it."""
    if requested and requested != "auto" and requested not in STACKS:
        raise HTTPException(status_code=400, detail=f"Unknown stack {requested!r}")
    saved = get_stack_id(project_id) or infer_stack_from_files(get_workspace(project_id).list_files())
    if saved and requested not in (None, "auto", saved):
        raise HTTPException(
            status_code=409,
            detail=f"This project already uses {STACKS[saved].label}. A project keeps one stack.",
        )
    return saved or (requested if requested not in (None, "auto") else detect_stack(tech_stack))


def _execute_job(job_id: str, project_id: str, task: str, tech_stack: str, stack_id: str,
                 architecture: list[dict], deviations: list[str]) -> None:
    """Run the LangGraph workflow, recording progress after every node."""
    jobs.update(job_id, status="running", log="Started")
    state = {
        "project_id": project_id,
        "task": task,
        "tech_stack": tech_stack,
        "stack": stack_id,
        "architecture": architecture,
        "deviations": deviations,
        "output": None,
        "validation_errors": [],
        "retries": 0,
        "status": "running",
    }
    try:
        for update in developer_graph.stream(state, stream_mode="updates"):
            for node, delta in update.items():
                state.update(delta)
                if node == "generate":
                    count = len(delta["output"].changes)
                    jobs.update(job_id, attempts=delta["retries"], log=f"Attempt {delta['retries']}: generated {count} file change(s)")
                elif node == "validate":
                    errors = delta["validation_errors"]
                    first = errors[0].splitlines()[0] if errors else ""
                    jobs.update(job_id, errors=errors, log="Checks passed" if not errors else f"Checks failed: {first}")
                elif node == "give_up":
                    jobs.update(job_id, log="Retry limit reached")

        output = state["output"]
        jobs.update(
            job_id,
            status="success" if state["status"] == "success" else "failed",
            attempts=state["retries"],
            summary=output.summary if output else None,
            changes=[
                {"path": c.path, "action": c.action, "explanation": c.explanation}
                for c in (output.changes if output else [])
            ],
            errors=state["validation_errors"],
            log="Finished: " + ("success" if state["status"] == "success" else "failed"),
        )
    except Exception as exc:  # noqa: BLE001 - surface any failure to the caller
        logger.exception("Developer job %s crashed", job_id)
        jobs.update(job_id, status="error", errors=[f"{exc.__class__.__name__}: {exc}"], log="Crashed")


@app.post("/projects/{project_id}/tasks", status_code=202)
def start_task(project_id: str, body: TaskRequest):
    get_workspace(project_id)  # validates the id
    stack_id = resolve_stack(project_id, body.stack, body.tech_stack)
    architecture = [item.model_dump() for item in body.architecture]
    contract = check_contract(get_stack(stack_id), architecture)
    deviations = contract["unsupported"]
    if deviations and not body.allow_deviation:
        raise HTTPException(
            status_code=409,
            detail=(
                f"Stack conflict: the System Architect chose technologies that {STACKS[stack_id].label} cannot build "
                f"and verify: {'; '.join(deviations)}. Change the architecture, or allow a recorded deviation."
            ),
        )
    try:
        job = jobs.create(project_id, body.task, body.tech_stack)
    except JobConflict as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    set_stack_id(project_id, stack_id)
    apps.stop(project_id)   # the files are about to change under a running preview
    job["stack"] = stack_id
    job["deviations"] = deviations
    job["architecture_notes"] = contract["notes"]
    jobs.update(job["job_id"], deviations=deviations, architecture_notes=contract["notes"])
    jobs.submit(_execute_job, job["job_id"], project_id, body.task, body.tech_stack, stack_id, architecture, deviations)
    return job


@app.get("/projects/{project_id}/jobs")
def list_jobs(project_id: str):
    get_workspace(project_id)
    return {"jobs": jobs.list(project_id)}


@app.get("/projects/{project_id}/jobs/{job_id}")
def get_job(project_id: str, job_id: str):
    job = jobs.get(project_id, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


@app.get("/stacks")
def list_stacks():
    return {"runner": RUNNER_MODE, "available": [{"id": s.id, "label": s.label} for s in STACKS.values()]}


@app.get("/projects/{project_id}/stack")
def project_stack(project_id: str):
    get_workspace(project_id)
    return stack_info(project_id)


@app.post("/projects/{project_id}/run")
def run_command(project_id: str, body: RunRequest):
    workspace = get_workspace(project_id)
    stack = get_stack(get_stack_id(project_id) or infer_stack_from_files(workspace.list_files()))
    if body.command not in stack.visible_commands:
        raise HTTPException(status_code=400, detail=f"Command not available for {stack.label}: {body.command!r}")
    try:
        result = make_runner(workspace.root, stack).run(body.command)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return {"command": result.name, "ok": result.ok, "exit_code": result.exit_code, "output": result.summary()}


@app.get("/projects/{project_id}/app")
def app_status(project_id: str):
    get_workspace(project_id)
    return apps.status(project_id)


@app.post("/projects/{project_id}/app/start")
def start_app(project_id: str):
    workspace = get_workspace(project_id)
    stack_id = get_stack_id(project_id) or infer_stack_from_files(workspace.list_files())
    if not stack_id:
        raise HTTPException(status_code=409, detail="This project has no files yet. Run a task first.")
    if any(job["status"] in ("queued", "running") for job in jobs.list(project_id)):
        raise HTTPException(status_code=409, detail="Wait for the Developer agent to finish first.")
    try:
        return apps.start(project_id, workspace, get_stack(stack_id))
    except AppError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc))


@app.post("/projects/{project_id}/app/stop")
def stop_app(project_id: str):
    get_workspace(project_id)
    return {"stopped": apps.stop(project_id)}


def _run_developer_repair(
    job_id: str,
    project_id: str,
    stack_id: str,
    brief: dict,
    feedback: dict,
    round_number: int,
) -> dict:
    """Pass QA findings through the existing Developer graph for a bounded repair run."""
    stack = get_stack(stack_id)
    feedback_text = json.dumps(feedback, indent=2, ensure_ascii=False)[:24000]
    criteria_text = "\n".join(
        f"- {item.get('id', '?')}: {item.get('text', '')}"
        for item in brief.get("criteria", [])
    )
    task = (
        f"Repair pass {round_number} for QA task {brief.get('task_id', 'unknown')}: "
        f"{brief.get('task_title', '')}\n\n"
        "The QA Agent tested the existing application and found issues. Fix the underlying "
        "application code where appropriate. Preserve the acceptance criteria and existing "
        "working behavior. Do not delete, weaken, or rewrite tests merely to make them pass. "
        "Avoid unrelated refactors. After making targeted fixes, ensure the project still "
        "starts and its existing checks pass.\n\n"
        f"Acceptance criteria:\n{criteria_text or '(not supplied)'}\n\n"
        f"QA feedback (JSON):\n{feedback_text}"
    )

    state = {
        "project_id": project_id,
        "task": task,
        "tech_stack": stack.label,
        "stack": stack_id,
        "architecture": [],
        "deviations": [],
        "output": None,
        "validation_errors": [
            "Fix these issues reported by the QA Agent; prioritize the specific files and failures in this feedback:\n"
            + feedback_text
        ],
        "retries": 0,
        "status": "running",
    }

    jobs.update(job_id, log=f"Starting Developer Agent repair round {round_number}")
    try:
        for update in developer_graph.stream(state, stream_mode="updates"):
            for node, delta in update.items():
                state.update(delta)
                if node == "generate":
                    generated = delta.get("output")
                    change_count = len(generated.changes) if generated else 0
                    jobs.update(
                        job_id,
                        attempts=delta.get("retries", 0),
                        log=f"Repair round {round_number}: Developer generated {change_count} file change(s)",
                    )
                elif node == "validate":
                    errors = delta.get("validation_errors", [])
                    first = errors[0].splitlines()[0] if errors else ""
                    jobs.update(
                        job_id,
                        errors=errors,
                        log=(
                            f"Repair round {round_number}: Developer checks passed"
                            if not errors
                            else f"Repair round {round_number}: Developer checks failed: {first}"
                        ),
                    )
                elif node == "give_up":
                    jobs.update(job_id, log=f"Repair round {round_number}: Developer retry limit reached")

        output = state.get("output")
        return {
            "status": state.get("status", "failed"),
            "summary": output.summary if output else None,
            "changes": [
                {"path": item.path, "action": item.action, "explanation": item.explanation}
                for item in (output.changes if output else [])
            ],
            "errors": state.get("validation_errors", []),
            "attempts": state.get("retries", 0),
        }
    except Exception as exc:  # noqa: BLE001 - report repair failures in the QA job
        logger.exception("Developer repair round %s failed for QA job %s", round_number, job_id)
        return {
            "status": "error",
            "summary": None,
            "changes": [],
            "errors": [f"{type(exc).__name__}: {exc}"],
            "attempts": state.get("retries", 0),
        }


def _execute_qa(job_id: str, project_id: str, brief: dict) -> None:
    jobs.update(job_id, status="running", log="QA started")
    try:
        workspace = get_workspace(project_id)
        stack_id = get_stack_id(project_id) or infer_stack_from_files(workspace.list_files())
        stack = get_stack(stack_id)
        report = run_qa(jobs, job_id, project_id, workspace, stack, brief)
        repair_history = []

        # A QA failure is handed to the Developer graph, then QA is rerun. The
        # bounded loop prevents repeated AI edits if the same defect persists.
        for round_number in range(1, QA_AUTO_REPAIR_ROUNDS + 1):
            if report.get("verdict") != "FAIL":
                break
            feedback = report.get("developer_feedback") or {}
            if not feedback.get("issues"):
                break

            jobs.update(
                job_id,
                log=(
                    f"QA found {feedback.get('issue_count', len(feedback['issues']))} issue(s); "
                    f"sending feedback to Developer Agent (repair round {round_number}/{QA_AUTO_REPAIR_ROUNDS})"
                ),
            )
            repair_result = _run_developer_repair(
                job_id=job_id,
                project_id=project_id,
                stack_id=stack_id,
                brief=brief,
                feedback=feedback,
                round_number=round_number,
            )
            repair_history.append({"round": round_number, **repair_result})

            if repair_result.get("status") != "success":
                jobs.update(job_id, log=f"Developer repair round {round_number} did not pass its validation checks")
                break

            jobs.update(job_id, log=f"Rerunning QA after repair round {round_number}")
            report = run_qa(jobs, job_id, project_id, workspace, stack, brief)

        if report.get("verdict") == "PASS":
            repair_status = "resolved" if repair_history else "not_needed"
        elif not repair_history:
            repair_status = "not_needed" if report.get("verdict") != "FAIL" else "no_actionable_feedback"
        elif repair_history[-1].get("status") != "success":
            repair_status = "repair_failed"
        elif len(repair_history) >= QA_AUTO_REPAIR_ROUNDS:
            repair_status = "limit_reached"
        else:
            repair_status = "unresolved"

        report["auto_repair"] = {
            "enabled": QA_AUTO_REPAIR_ROUNDS > 0,
            "max_rounds": QA_AUTO_REPAIR_ROUNDS,
            "rounds_attempted": repair_history,
            "status": repair_status,
        }
        # run_qa writes its own report; rewrite it to include repair history too.
        report_path = write_report(str(workspace.root), report)
        if report_path:
            report["report_path"] = report_path
            write_report(str(workspace.root), report)

        finished = report["verdict"] != "BLOCKED"
        jobs.update(
            job_id,
            status="success" if finished else "error",
            report=report,
            errors=[] if finished else [report["blocked"]],
            log=f"QA finished: {report['verdict']} (auto-repair: {repair_status})",
        )
    except Exception as exc:  # noqa: BLE001 - surface any failure to the caller
        logger.exception("QA job %s crashed", job_id)
        jobs.update(job_id, status="error", errors=[f"{exc.__class__.__name__}: {exc}"], log="QA crashed")


@app.post("/projects/{project_id}/qa", status_code=202)
def start_qa(project_id: str, body: QARequest):
    """Test the project's running app against one task's acceptance criteria."""
    workspace = get_workspace(project_id)
    stack_id = get_stack_id(project_id) or infer_stack_from_files(workspace.list_files())
    if not stack_id or not workspace.list_files():
        raise HTTPException(status_code=409, detail="This project has no code yet. Run a Developer task first.")
    stack = get_stack(stack_id)
    if not stack.start:
        raise HTTPException(status_code=409, detail=f"{stack.label} projects cannot be started, so they cannot be tested.")
    if not make_runner(workspace.root, stack).env_ready():
        raise HTTPException(status_code=409, detail="Dependencies are not installed yet. Run a Developer task first.")
    try:
        job = jobs.create(project_id, f"QA {body.task_id}", "", kind="qa")
    except JobConflict as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    apps.stop(project_id)   # the preview and the QA run must not share the project's files and database
    jobs.submit(_execute_qa, job["job_id"], project_id, body.model_dump())
    return job
