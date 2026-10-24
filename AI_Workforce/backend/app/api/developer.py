"""Developer AI endpoints.

The Developer Agent runs as its own service. This router is the only way the browser
reaches it: it authenticates the user, checks project ownership, turns a Project Manager
task plus the Architect's design into the agent's instructions, and records every run as
an ``AgentRun`` so it appears next to the other agents' runs.
"""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database import get_db
from ..dependencies import get_current_user, get_project_or_404
from ..developer.export import runs_to_csv
from ..developer.client import DeveloperAgentClient, DeveloperServiceError, get_developer_client
from ..developer.prompt import blocking_dependencies, build_task_text, tech_stack, workspace_id
from ..models import AgentRun, ArchDesign, PMTask, Project, User
from ..schemas_developer import (
    DEVELOPER_AGENT_NAME,
    CommandRequest,
    CommandResponse,
    DeveloperRunResponse,
    DeveloperTaskRunRequest,
    FileContentResponse,
    AppStatus,
    FileListResponse,
    StackInfo,
)

router = APIRouter(prefix="/api/projects/{project_id}/developer", tags=["developer"])

ACTIVE = "PROCESSING"


def _call(fn, *args):
    try:
        return fn(*args)
    except DeveloperServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc


def _find_task(db: Session, project: Project, task_id: str) -> PMTask:
    task = db.scalar(
        select(PMTask).where(PMTask.project_id == project.id, PMTask.task_id == task_id).order_by(PMTask.plan_id.desc())
    )
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return task


def _developer_runs(db: Session, project: Project, limit: int = 20) -> list[AgentRun]:
    return list(db.scalars(
        select(AgentRun)
        .where(AgentRun.project_id == project.id, AgentRun.agent_name == DEVELOPER_AGENT_NAME)
        .order_by(AgentRun.started_at.desc(), AgentRun.id.desc())
        .limit(limit)
    ))


def _set_task_status(db: Session, project: Project, run: AgentRun, status: str) -> None:
    task_id = (run.input_summary or {}).get("task_id")
    if not task_id:
        return
    task = db.scalar(
        select(PMTask).where(PMTask.project_id == project.id, PMTask.task_id == task_id).order_by(PMTask.plan_id.desc())
    )
    if task:
        task.status = status


def _sync(db: Session, project: Project, run: AgentRun, client: DeveloperAgentClient) -> None:
    """Copy the Developer service's job state into the run, finishing it when the job is done."""
    if run.status != ACTIVE:
        return
    info = run.input_summary or {}
    try:
        job = client.get_job(info.get("workspace", workspace_id(project.id)), info.get("job_id", ""))
    except DeveloperServiceError as exc:
        if exc.status_code != 404:
            return  # service temporarily unreachable: stay PROCESSING and try again on the next poll
        job = {"status": "error", "errors": ["The Developer service no longer knows this job."], "log": []}

    run.output_summary = {
        "job_status": job["status"],
        "attempts": job.get("attempts", 0),
        "summary": job.get("summary"),
        "changes": job.get("changes", []),
        "errors": job.get("errors", []),
        "log": job.get("log", []),
    }
    if job["status"] in ("queued", "running"):
        db.commit()
        return

    succeeded = job["status"] == "success"
    run.status = "COMPLETED" if succeeded else "FAILED"
    run.completed_at = datetime.now(timezone.utc)
    run.error = None if succeeded else ("\n".join(job.get("errors") or []) or "The Developer agent did not finish")[:4000]
    _set_task_status(db, project, run, "COMPLETED" if succeeded else "TODO")
    db.commit()


def _to_response(run: AgentRun) -> DeveloperRunResponse:
    info, output = run.input_summary or {}, run.output_summary or {}
    return DeveloperRunResponse(
        id=run.id,
        task_id=info.get("task_id"),
        task_title=info.get("task_title"),
        status=run.status,
        attempts=output.get("attempts", 0),
        summary=output.get("summary"),
        changes=output.get("changes", []),
        errors=output.get("errors", []),
        log=output.get("log", []),
        started_at=run.started_at,
        completed_at=run.completed_at,
    )


def _sync_active(db: Session, project: Project, client: DeveloperAgentClient, limit: int = 20) -> list[AgentRun]:
    runs = _developer_runs(db, project, limit)
    for run in runs:
        _sync(db, project, run, client)
    return runs


@router.get("/workspace/files", response_model=FileListResponse)
def list_workspace_files(
    project_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    client: DeveloperAgentClient = Depends(get_developer_client),
):
    project = get_project_or_404(project_id, user, db)
    return FileListResponse(files=_call(client.list_files, workspace_id(project.id)))


@router.get("/workspace/file", response_model=FileContentResponse)
def read_workspace_file(
    project_id: int,
    path: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    client: DeveloperAgentClient = Depends(get_developer_client),
):
    project = get_project_or_404(project_id, user, db)
    return FileContentResponse(path=path, content=_call(client.read_file, workspace_id(project.id), path))


@router.post("/tasks/{task_id}/run", response_model=DeveloperRunResponse, status_code=202)
def run_task(
    project_id: int,
    task_id: str,
    body: DeveloperTaskRunRequest | None = None,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    client: DeveloperAgentClient = Depends(get_developer_client),
):
    """Start the Developer agent on one Project Manager task. Poll the run for progress."""
    project = get_project_or_404(project_id, user, db)
    task = _find_task(db, project, task_id)

    if any(run.status == ACTIVE for run in _sync_active(db, project, client)):
        raise HTTPException(status_code=409, detail="The Developer agent is already working on this project.")

    blockers = blocking_dependencies(db, task)
    if blockers and not (body and body.force):
        names = ", ".join(blocker.task_id for blocker in blockers)
        raise HTTPException(status_code=409, detail=f"Complete these prerequisite tasks first: {names}")

    design = db.scalar(select(ArchDesign).where(ArchDesign.project_id == project.id))
    workspace = workspace_id(project.id)
    stack = tech_stack(design)
    run = AgentRun(
        project_id=project.id,
        agent_name=DEVELOPER_AGENT_NAME,
        status=ACTIVE,
        input_summary={"task_id": task.task_id, "task_title": task.title, "workspace": workspace, "tech_stack": stack},
    )
    db.add(run)
    db.commit()

    try:
        job = client.start_task(workspace, build_task_text(db, project, task), stack, body.stack if body else None)
    except DeveloperServiceError as exc:
        run.status = "FAILED"
        run.error = exc.detail[:4000]
        run.completed_at = datetime.now(timezone.utc)
        db.commit()
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc

    run.input_summary = {**run.input_summary, "job_id": job["job_id"], "stack": job.get("stack")}
    task.status = "IN_PROGRESS"
    db.commit()
    return _to_response(run)


@router.get("/runs", response_model=list[DeveloperRunResponse])
def list_runs(
    project_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    client: DeveloperAgentClient = Depends(get_developer_client),
):
    project = get_project_or_404(project_id, user, db)
    return [_to_response(run) for run in _sync_active(db, project, client)]


# Declared before "/runs/{run_id}" so that "export" is not parsed as a run id.
@router.get("/runs/export")
def export_runs(
    project_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    client: DeveloperAgentClient = Depends(get_developer_client),
):
    """Download every Developer run of the project as a CSV file, with a summary block."""
    project = get_project_or_404(project_id, user, db)
    runs = _sync_active(db, project, client, limit=100000)
    return Response(
        content=runs_to_csv(runs),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="developer-runs-project-{project.id}.csv"'},
    )


@router.get("/runs/{run_id}", response_model=DeveloperRunResponse)
def get_run(
    project_id: int,
    run_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    client: DeveloperAgentClient = Depends(get_developer_client),
):
    project = get_project_or_404(project_id, user, db)
    run = db.scalar(
        select(AgentRun).where(
            AgentRun.id == run_id, AgentRun.project_id == project.id, AgentRun.agent_name == DEVELOPER_AGENT_NAME
        )
    )
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    _sync(db, project, run, client)
    return _to_response(run)


@router.post("/commands", response_model=CommandResponse)
def run_command(
    project_id: int,
    body: CommandRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    client: DeveloperAgentClient = Depends(get_developer_client),
):
    """Run install / import check / tests in the project's workspace and return the output."""
    project = get_project_or_404(project_id, user, db)
    if any(run.status == ACTIVE for run in _sync_active(db, project, client)):
        raise HTTPException(status_code=409, detail="Wait for the Developer agent to finish before running commands.")
    return CommandResponse(**_call(client.run_command, workspace_id(project.id), body.command))


@router.get("/stack", response_model=StackInfo)
def get_stack(
    project_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    client: DeveloperAgentClient = Depends(get_developer_client),
):
    """The project's stack (None until its first run) and the stacks the Developer agent supports."""
    project = get_project_or_404(project_id, user, db)
    return _call(client.get_stack, workspace_id(project.id))


@router.get("/app", response_model=AppStatus)
def get_app(
    project_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    client: DeveloperAgentClient = Depends(get_developer_client),
):
    project = get_project_or_404(project_id, user, db)
    return _call(client.get_app, workspace_id(project.id))


@router.post("/app/start", response_model=AppStatus)
def start_app(
    project_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    client: DeveloperAgentClient = Depends(get_developer_client),
):
    """Start the generated app so the user can open it. It stops by itself after a while."""
    project = get_project_or_404(project_id, user, db)
    if any(run.status == ACTIVE for run in _sync_active(db, project, client)):
        raise HTTPException(status_code=409, detail="Wait for the Developer agent to finish before starting the app.")
    return _call(client.start_app, workspace_id(project.id))


@router.post("/app/stop")
def stop_app(
    project_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    client: DeveloperAgentClient = Depends(get_developer_client),
):
    project = get_project_or_404(project_id, user, db)
    return _call(client.stop_app, workspace_id(project.id))
