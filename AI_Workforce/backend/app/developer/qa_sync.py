"""Keeps QA AI runs in step with the Developer service's QA jobs."""

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import AgentRun, PMTask, Project
from .client import DeveloperAgentClient, DeveloperServiceError

QA_AGENT_NAME = "QA AI"
ACTIVE = "PROCESSING"


def qa_runs(db: Session, project: Project, limit: int = 20) -> list[AgentRun]:
    return list(db.scalars(
        select(AgentRun)
        .where(AgentRun.project_id == project.id, AgentRun.agent_name == QA_AGENT_NAME)
        .order_by(AgentRun.started_at.desc(), AgentRun.id.desc())
        .limit(limit)
    ))


def _set_task_status(db: Session, project: Project, task_id: str | None, status: str) -> None:
    if not task_id:
        return
    task = db.scalar(
        select(PMTask).where(PMTask.project_id == project.id, PMTask.task_id == task_id).order_by(PMTask.plan_id.desc())
    )
    if task:
        task.status = status


def sync_qa_run(db: Session, project: Project, run: AgentRun, client: DeveloperAgentClient) -> None:
    """Copy the QA job's state into the run. A finished run settles the task: PASS completes it,
    FAIL sends it back to IN_PROGRESS because defects were found."""
    if run.status != ACTIVE:
        return
    info = run.input_summary or {}
    try:
        job = client.get_job(info.get("workspace", ""), info.get("job_id", ""))
    except DeveloperServiceError as exc:
        if exc.status_code != 404:
            return   # service temporarily unreachable: stay PROCESSING and try again on the next poll
        job = {"status": "error", "errors": ["The Developer service no longer knows this QA job."], "log": []}

    report = job.get("report") or {}
    run.output_summary = {
        "job_status": job["status"], "log": job.get("log", []), "errors": job.get("errors", []),
        "verdict": report.get("verdict"), "counts": report.get("counts", {}), "total": report.get("total", 0),
        "coverage": report.get("coverage", 0), "criteria": report.get("criteria", []),
        "repaired": report.get("repaired", 0), "blocked": report.get("blocked"), "app_log": report.get("app_log", ""),
        "seconds": report.get("seconds"), "defects_sent": (run.output_summary or {}).get("defects_sent", False),
    }
    if job["status"] in ("queued", "running"):
        db.commit()
        return

    finished = job["status"] == "success"
    run.status = "COMPLETED" if finished else "FAILED"
    run.completed_at = datetime.now(timezone.utc)
    run.error = None if finished else ("\n".join(job.get("errors") or []) or "QA did not finish")[:4000]
    verdict = report.get("verdict")
    if verdict == "PASS":
        _set_task_status(db, project, info.get("task_id"), "COMPLETED")
    elif verdict == "FAIL":
        _set_task_status(db, project, info.get("task_id"), "IN_PROGRESS")
    db.commit()


def any_qa_active(db: Session, project: Project, client: DeveloperAgentClient) -> bool:
    runs = qa_runs(db, project)
    for run in runs:
        sync_qa_run(db, project, run, client)
    return any(run.status == ACTIVE for run in runs)
