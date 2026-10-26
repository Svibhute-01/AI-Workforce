"""QA AI endpoints.

QA tests the project's RUNNING app against one task's acceptance criteria and reports a verdict per
criterion. The tests are produced and run by the Developer service; this router authenticates the user,
checks ownership, builds the brief, and records every run as an ``AgentRun`` named 'QA AI'.
"""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database import get_db
from ..dependencies import get_current_user, get_project_or_404
from ..developer.client import DeveloperAgentClient, DeveloperServiceError, get_developer_client
from ..developer.prompt import workspace_id
from ..developer.qa import build_brief, build_fix_text
from ..developer.qa_export import qa_runs_to_csv
from ..developer.qa_sync import ACTIVE, QA_AGENT_NAME, any_qa_active, qa_runs, sync_qa_run
from ..models import AgentRun, PMTask, Project, User
from ..schemas_developer import DeveloperRunResponse
from ..schemas_qa import QARunResponse
from .developer import _find_task, _sync_active, start_developer_run

router = APIRouter(prefix="/api/projects/{project_id}/qa", tags=["qa"])


def _to_response(run: AgentRun) -> QARunResponse:
    info, output = run.input_summary or {}, run.output_summary or {}
    return QARunResponse(
        id=run.id, task_id=info.get("task_id"), task_title=info.get("task_title"), status=run.status,
        verdict=output.get("verdict"), counts=output.get("counts") or {}, total=output.get("total", 0),
        coverage=output.get("coverage", 0), criteria=output.get("criteria") or [], repaired=output.get("repaired", 0),
        blocked=output.get("blocked"), app_log=output.get("app_log") or "", errors=output.get("errors") or [],
        log=output.get("log") or [], defects_sent=bool(output.get("defects_sent")),
        started_at=run.started_at, completed_at=run.completed_at,
    )


def _get_run(db: Session, project: Project, run_id: int) -> AgentRun:
    run = db.scalar(select(AgentRun).where(
        AgentRun.id == run_id, AgentRun.project_id == project.id, AgentRun.agent_name == QA_AGENT_NAME))
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    return run


@router.post("/tasks/{task_id}/run", response_model=QARunResponse, status_code=202)
def run_qa(
    project_id: int,
    task_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    client: DeveloperAgentClient = Depends(get_developer_client),
):
    """Test the running app against one task's acceptance criteria. Poll the run for the report."""
    project = get_project_or_404(project_id, user, db)
    task = _find_task(db, project, task_id)
    brief = build_brief(db, project, task)
    if not brief["criteria"]:
        raise HTTPException(status_code=409, detail="This task has no acceptance criteria, so there is nothing to test it against.")
    if any(run.status == ACTIVE for run in _sync_active(db, project, client)):
        raise HTTPException(status_code=409, detail="The Developer agent is working on this project. Wait for it to finish.")
    if any_qa_active(db, project, client):
        raise HTTPException(status_code=409, detail="QA is already testing this project.")

    workspace = workspace_id(project.id)
    run = AgentRun(
        project_id=project.id, agent_name=QA_AGENT_NAME, status=ACTIVE,
        input_summary={"task_id": task.task_id, "task_title": task.title, "workspace": workspace,
                       "criteria_count": len(brief["criteria"])},
    )
    db.add(run)
    db.commit()
    try:
        job = client.start_qa(workspace, brief)
    except DeveloperServiceError as exc:
        run.status, run.error, run.completed_at = "FAILED", exc.detail[:4000], datetime.now(timezone.utc)
        db.commit()
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc

    run.input_summary = {**run.input_summary, "job_id": job["job_id"]}
    db.commit()
    return _to_response(run)


@router.get("/runs", response_model=list[QARunResponse])
def list_runs(
    project_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    client: DeveloperAgentClient = Depends(get_developer_client),
):
    project = get_project_or_404(project_id, user, db)
    runs = qa_runs(db, project)
    for run in runs:
        sync_qa_run(db, project, run, client)
    return [_to_response(run) for run in runs]


# Declared before "/runs/{run_id}" so that "export" is not parsed as a run id.
@router.get("/runs/export")
def export_runs(
    project_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    client: DeveloperAgentClient = Depends(get_developer_client),
):
    """Download every QA run of the project as a CSV file, with a summary block."""
    project = get_project_or_404(project_id, user, db)
    runs = qa_runs(db, project, limit=100000)
    for run in runs:
        sync_qa_run(db, project, run, client)
    return Response(
        content=qa_runs_to_csv(runs), media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="qa-runs-project-{project.id}.csv"'},
    )


@router.get("/runs/{run_id}", response_model=QARunResponse)
def get_run(
    project_id: int,
    run_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    client: DeveloperAgentClient = Depends(get_developer_client),
):
    project = get_project_or_404(project_id, user, db)
    run = _get_run(db, project, run_id)
    sync_qa_run(db, project, run, client)
    return _to_response(run)


@router.post("/runs/{run_id}/fix", response_model=DeveloperRunResponse, status_code=202)
def send_defects_to_developer(
    project_id: int,
    run_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    client: DeveloperAgentClient = Depends(get_developer_client),
):
    """Start the Developer agent on the same task again, with QA's failed criteria and evidence as instructions."""
    project = get_project_or_404(project_id, user, db)
    run = _get_run(db, project, run_id)
    sync_qa_run(db, project, run, client)
    output = run.output_summary or {}
    fix_text = build_fix_text(output.get("criteria") or []) if output.get("verdict") == "FAIL" else ""
    if not fix_text:
        raise HTTPException(status_code=409, detail="This QA run found no defects to send to the Developer.")
    task = _find_task(db, project, (run.input_summary or {}).get("task_id", ""))

    started = start_developer_run(db, project, task, client, force=True, extra_text=fix_text, extra_input={"qa_run_id": run.id})
    run.output_summary = {**output, "defects_sent": True}
    db.commit()
    return started
