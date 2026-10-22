"""Developer Agent service.

Runs next to the main AI Workforce backend (default port 8001). The browser never
calls this service: the main backend authenticates the user, checks project
ownership, and forwards requests here with the shared X-Service-Key.
"""

import hmac
import logging

from fastapi import Depends, FastAPI, Header, HTTPException
from pydantic import BaseModel, Field

from app.config import SERVICE_KEY
from app.graph.builder import build_developer_graph
from app.jobs import JobConflict, JobStore
from app.tools.runner import LocalRunner
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


class ProjectCreate(BaseModel):
    project_id: str


class TaskRequest(BaseModel):
    task: str = Field(min_length=1, max_length=20000)
    tech_stack: str = "Python, FastAPI"


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


def _execute_job(job_id: str, project_id: str, task: str, tech_stack: str) -> None:
    """Run the LangGraph workflow, recording progress after every node."""
    jobs.update(job_id, status="running", log="Started")
    state = {
        "project_id": project_id,
        "task": task,
        "tech_stack": tech_stack,
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
    try:
        job = jobs.create(project_id, body.task, body.tech_stack)
    except JobConflict as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    jobs.submit(_execute_job, job["job_id"], project_id, body.task, body.tech_stack)
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


@app.post("/projects/{project_id}/run")
def run_command(project_id: str, body: RunRequest):
    runner = LocalRunner(get_workspace(project_id).root)
    try:
        result = runner.run(body.command)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return {"command": result.name, "ok": result.ok, "exit_code": result.exit_code, "output": result.summary()}
