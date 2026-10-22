"""Dashboard summary.

``GET /api/dashboard/summary`` is a read-only aggregation over tables that
already exist (projects, documents, Requirements Analyst output, Project
Manager plans/tasks/sprints and agent runs). It is scoped to the signed-in
user's projects and never writes anything.

The route only loads narrow column sets; all counting lives in
``build_summary`` which works on plain rows so it can be unit-tested without a
database.
"""

import re
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..database import get_db
from ..dependencies import get_current_user
from ..models import (
    AcceptanceCriteria,
    AgentRun,
    Ambiguity,
    Document,
    NonFunctionalRequirement,
    PMPlan,
    PMRisk,
    PMSprint,
    PMTask,
    PMTaskDependency,
    Project,
    Requirement,
    Risk,
    User,
    UserStory,
)
from ..schemas_dashboard import DashboardSummary

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])

# (key, display name, SDLC stage). Developer and QA are listed even though no
# backend code records runs for them yet; they simply report zero runs.
AGENTS = (
    ("requirements_analyst", "Requirements Analyst", "Requirements"),
    ("project_manager", "Project Manager", "Planning"),
    ("developer", "Developer", "Development"),
    ("qa", "QA", "Quality"),
)
TASK_STATUS_LABELS = {"TODO": "To do", "IN_PROGRESS": "In progress", "COMPLETED": "Completed"}
PRIORITIES = ("HIGH", "MEDIUM", "LOW")
SEVERITY_RANK = {"high": 0, "medium": 1, "info": 2}

_DONE = {"DONE", "COMPLETED", "COMPLETE", "CLOSED", "FINISHED"}
_DOING = {"IN_PROGRESS", "INPROGRESS", "DOING", "STARTED"}
_EPOCH = datetime.min.replace(tzinfo=timezone.utc)


# ---------------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------------


def _utc(value: datetime | None) -> datetime | None:
    """SQLite returns naive datetimes; PostgreSQL returns aware ones. Always emit UTC-aware."""
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _task_status(raw: str | None) -> str:
    key = re.sub(r"[\s\-]+", "_", (raw or "").strip().upper())
    if key in _DONE:
        return "COMPLETED"
    if key in _DOING:
        return "IN_PROGRESS"
    return key or "TODO"


def _status_label(key: str) -> str:
    return TASK_STATUS_LABELS.get(key, key.replace("_", " ").capitalize())


def _project_done(status: str | None) -> bool:
    return (status or "").strip().lower() in {"completed", "complete", "done", "closed"}


def _agent_key(agent_name: str | None) -> str | None:
    name = (agent_name or "").lower()
    if "requirement" in name:
        return "requirements_analyst"
    if "project manager" in name:
        return "project_manager"
    if "developer" in name:
        return "developer"
    if re.search(r"\bqa\b|quality", name):
        return "qa"
    return None


def _percent(part: int, whole: int) -> int | None:
    return round(100 * part / whole) if whole else None


def _plural(count: int, word: str) -> str:
    return f"{count} {word}" if count == 1 else f"{count} {word}s"


def _truncate(text: str | None, limit: int) -> str | None:
    text = (text or "").strip()
    if not text:
        return None
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "…"


def _ordered_counts(counter: Counter, canonical: tuple[str, ...], labeller=None) -> list[dict]:
    """Canonical keys first (always present, even at zero), then any others by count."""
    labeller = labeller or (lambda key: key.replace("_", " ").capitalize())
    extras = sorted((k for k in counter if k not in canonical), key=lambda k: (-counter[k], k))
    return [{"key": k, "label": labeller(k), "count": counter.get(k, 0)} for k in (*canonical, *extras)]


# ---------------------------------------------------------------------------
# Aggregation (pure: no database access)
# ---------------------------------------------------------------------------


def build_summary(
    *,
    user_name: str | None,
    now: datetime,
    projects: list[Any],
    tasks: list[Any],
    sprints: list[Any],
    plans: list[Any],
    documents: list[Any],
    agent_runs: list[Any],
    totals: dict[str, Any],
) -> dict[str, Any]:
    today = now.date()
    week_ago = now - timedelta(days=7)

    projects = sorted(projects, key=lambda p: (_utc(p.created_at) or _EPOCH, p.id), reverse=True)
    names = {p.id: p.name for p in projects}
    sprint_by_key = {(s.project_id, s.sprint_id): s for s in sprints}
    plan_created = {pl.project_id: _utc(pl.created_at) for pl in plans}

    # ---- tasks ------------------------------------------------------------
    task_rows: list[dict[str, Any]] = []
    for t in tasks:
        status = _task_status(t.status)
        sprint = sprint_by_key.get((t.project_id, t.sprint_id))
        end_date = sprint.end_date if sprint else None
        task_rows.append(
            {
                "id": t.id,
                "project_id": t.project_id,
                "task_id": t.task_id,
                "title": t.title,
                "priority": (t.priority or "").upper(),
                "status": status,
                "story_points": t.story_points or 0,
                "suggested_role": t.suggested_role or "Unassigned",
                "sprint_id": t.sprint_id,
                "sprint_name": sprint.name if sprint else None,
                "sprint_end_date": end_date,
                "is_overdue": bool(end_date and end_date < today and status != "COMPLETED"),
                "execution_index": t.execution_index or 0,
            }
        )

    status_counts = Counter(r["status"] for r in task_rows)
    priority_counts = Counter(r["priority"] for r in task_rows)
    role_counts = Counter(r["suggested_role"] for r in task_rows)
    role_points: Counter = Counter()
    for r in task_rows:
        role_points[r["suggested_role"]] += r["story_points"]

    per_project: dict[int, dict[str, int]] = defaultdict(
        lambda: {"total": 0, "done": 0, "points": 0, "points_done": 0, "overdue": 0}
    )
    for r in task_rows:
        bucket = per_project[r["project_id"]]
        bucket["total"] += 1
        bucket["points"] += r["story_points"]
        if r["status"] == "COMPLETED":
            bucket["done"] += 1
            bucket["points_done"] += r["story_points"]
        if r["is_overdue"]:
            bucket["overdue"] += 1

    tasks_total = len(task_rows)
    tasks_completed = status_counts.get("COMPLETED", 0)
    by_role = [
        {"key": role, "label": role, "count": count, "story_points": role_points[role]}
        for role, count in sorted(role_counts.items(), key=lambda kv: (-kv[1], kv[0]))
    ]
    task_stats = {
        "total": tasks_total,
        "completed": tasks_completed,
        "in_progress": status_counts.get("IN_PROGRESS", 0),
        "todo": status_counts.get("TODO", 0),
        "overdue": sum(1 for r in task_rows if r["is_overdue"]),
        "planned_last_7_days": sum(
            1 for r in task_rows if (plan_created.get(r["project_id"]) or _EPOCH) >= week_ago
        ),
        "completion_rate": _percent(tasks_completed, tasks_total),
        "total_story_points": sum(r["story_points"] for r in task_rows),
        "completed_story_points": sum(r["story_points"] for r in task_rows if r["status"] == "COMPLETED"),
        "projects_with_plan": len(plan_created),
        "by_status": _ordered_counts(status_counts, tuple(TASK_STATUS_LABELS), _status_label),
        "by_priority": _ordered_counts(priority_counts, PRIORITIES),
        "by_role": by_role,
    }

    # ---- agent runs -------------------------------------------------------
    runs = []
    for r in agent_runs:
        started, completed = _utc(r.started_at), _utc(r.completed_at)
        duration = (completed - started).total_seconds() if started and completed else None
        runs.append(
            {
                "id": r.id,
                "project_id": r.project_id,
                "agent_name": r.agent_name,
                "agent_key": _agent_key(r.agent_name),
                "status": (r.status or "").upper(),
                "started_at": started,
                "completed_at": completed,
                "duration_seconds": duration if duration is not None and duration >= 0 else None,
                "error": r.error,
            }
        )
    runs.sort(key=lambda r: (r["started_at"] or _EPOCH, r["id"]), reverse=True)

    runs_by_project: dict[int, list[dict]] = defaultdict(list)
    for r in runs:
        runs_by_project[r["project_id"]].append(r)

    agents = []
    for key, name, stage in AGENTS:
        mine = [r for r in runs if r["agent_key"] == key]
        completed_runs = [r for r in mine if r["status"] == "COMPLETED"]
        failed = sum(1 for r in mine if r["status"] == "FAILED")
        durations = [r["duration_seconds"] for r in completed_runs if r["duration_seconds"] is not None]
        last = mine[0] if mine else None
        agents.append(
            {
                "key": key,
                "name": name,
                "stage": stage,
                "total_runs": len(mine),
                "completed": len(completed_runs),
                "failed": failed,
                "processing": len(mine) - len(completed_runs) - failed,
                "runs_last_7_days": sum(1 for r in mine if (r["started_at"] or _EPOCH) >= week_ago),
                "success_rate": _percent(len(completed_runs), len(completed_runs) + failed),
                "avg_duration_seconds": round(sum(durations) / len(durations), 1) if durations else None,
                "last_run_at": last["started_at"] if last else None,
                "last_run_status": last["status"] if last else None,
                "last_project": names.get(last["project_id"]) if last else None,
            }
        )

    recent_agent_runs = [
        {
            "id": r["id"],
            "agent_key": r["agent_key"],
            "agent_name": r["agent_name"],
            "status": r["status"],
            "project_id": r["project_id"],
            "project_name": names.get(r["project_id"], "Unknown project"),
            "started_at": r["started_at"],
            "completed_at": r["completed_at"],
            "duration_seconds": r["duration_seconds"],
            "error": _truncate(r["error"], 200),
        }
        for r in runs[:8]
    ]

    # ---- documents --------------------------------------------------------
    docs_by_project: dict[int, Counter] = defaultdict(Counter)
    for d in documents:
        docs_by_project[d.project_id][(d.processing_status or "").upper()] += d.n
    doc_status = Counter()
    for counter in docs_by_project.values():
        doc_status.update(counter)
    documents_total = sum(doc_status.values())

    # ---- projects ---------------------------------------------------------
    overview = []
    for p in projects:
        bucket = per_project.get(p.id) or {"total": 0, "done": 0, "points": 0, "points_done": 0, "overdue": 0}
        docs = docs_by_project.get(p.id, Counter())
        project_runs = runs_by_project.get(p.id, [])
        days_to_due = (p.due_date - today).days if p.due_date else None
        overview.append(
            {
                "id": p.id,
                "name": p.name,
                "status": p.status or "Planning",
                "manager": p.manager,
                "start_date": p.start_date,
                "due_date": p.due_date,
                "created_at": _utc(p.created_at),
                "days_to_due": days_to_due,
                "is_overdue": bool(days_to_due is not None and days_to_due < 0 and not _project_done(p.status)),
                "documents": sum(docs.values()),
                "documents_ready": docs.get("COMPLETED", 0),
                "requirements_ready": any(
                    r["agent_key"] == "requirements_analyst" and r["status"] == "COMPLETED" for r in project_runs
                ),
                "plan_ready": p.id in plan_created,
                "tasks_total": bucket["total"],
                "tasks_completed": bucket["done"],
                "story_points_total": bucket["points"],
                "story_points_completed": bucket["points_done"],
                "progress": _percent(bucket["done"], bucket["total"]),
                "overdue_tasks": bucket["overdue"],
                "latest_run_status": project_runs[0]["status"] if project_runs else None,
            }
        )

    project_status_counts = Counter(o["status"] for o in overview)
    project_stats = {
        "total": len(projects),
        "new_last_7_days": sum(1 for o in overview if (o["created_at"] or _EPOCH) >= week_ago),
        "overdue": sum(1 for o in overview if o["is_overdue"]),
        "by_status": [
            {"key": s, "label": s, "count": n}
            for s, n in sorted(project_status_counts.items(), key=lambda kv: (-kv[1], kv[0]))
        ],
    }

    # ---- recent tasks -----------------------------------------------------
    def plan_ts(row: dict) -> float:
        created = plan_created.get(row["project_id"])
        return created.timestamp() if created else 0.0

    recent_tasks = [
        {
            "id": r["id"],
            "task_id": r["task_id"],
            "title": r["title"],
            "priority": r["priority"],
            "status": r["status"],
            "story_points": r["story_points"],
            "suggested_role": r["suggested_role"],
            "sprint_name": r["sprint_name"],
            "sprint_end_date": r["sprint_end_date"],
            "is_overdue": r["is_overdue"],
            "project_id": r["project_id"],
            "project_name": names.get(r["project_id"], "Unknown project"),
        }
        for r in sorted(task_rows, key=lambda r: (-plan_ts(r), r["execution_index"], r["id"]))[:8]
    ]

    # ---- insights ---------------------------------------------------------
    pipeline = [
        {"key": "projects", "label": "Projects", "count": len(overview)},
        {"key": "documents", "label": "Documents uploaded", "count": sum(1 for o in overview if o["documents"])},
        {
            "key": "requirements",
            "label": "Requirements analyzed",
            "count": sum(1 for o in overview if o["requirements_ready"]),
        },
        {"key": "plan", "label": "Plan generated", "count": sum(1 for o in overview if o["plan_ready"])},
    ]

    severity = Counter()
    for value, n in totals.get("risk_severity", []):
        severity[(value or "").upper()] += n
    impact = Counter()
    for value, n in totals.get("pm_risk_impact", []):
        impact[(value or "").upper()] += n

    active_sprints = []
    for s in sorted(sprints, key=lambda s: (s.end_date or today, s.project_id)):
        if not (s.start_date and s.end_date and s.start_date <= today <= s.end_date):
            continue
        in_sprint = [r for r in task_rows if r["project_id"] == s.project_id and r["sprint_id"] == s.sprint_id]
        active_sprints.append(
            {
                "sprint_id": s.sprint_id,
                "name": s.name,
                "project_id": s.project_id,
                "project_name": names.get(s.project_id, "Unknown project"),
                "start_date": s.start_date,
                "end_date": s.end_date,
                "tasks_total": len(in_sprint),
                "tasks_completed": sum(1 for r in in_sprint if r["status"] == "COMPLETED"),
                "story_points": sum(r["story_points"] for r in in_sprint),
            }
        )

    attention: list[dict[str, Any]] = []
    for o in overview:
        if _project_done(o["status"]):
            continue
        base = {"project_id": o["id"], "project_name": o["name"]}
        if o["is_overdue"]:
            late = abs(o["days_to_due"])
            attention.append(
                {**base, "kind": "project_overdue", "severity": "high", "title": "Past its due date",
                 "detail": f"{_plural(late, 'day')} overdue"}
            )
        seen_agents = set()
        for r in runs_by_project.get(o["id"], []):
            if r["agent_name"] in seen_agents:
                continue
            seen_agents.add(r["agent_name"])
            if r["status"] == "FAILED":
                attention.append(
                    {**base, "kind": "agent_failed", "severity": "high",
                     "title": f"{r['agent_name']} run failed", "detail": _truncate(r["error"], 140)}
                )
        if o["overdue_tasks"]:
            attention.append(
                {**base, "kind": "tasks_overdue", "severity": "medium",
                 "title": f"{_plural(o['overdue_tasks'], 'task')} past sprint end",
                 "detail": "Sprint end dates have passed with work still open"}
            )
        if o["requirements_ready"] and not o["plan_ready"]:
            attention.append(
                {**base, "kind": "ready_for_planning", "severity": "info", "title": "Ready for planning",
                 "detail": "Requirements are analyzed. Run the Project Manager AI to create a plan."}
            )
        if not o["documents"]:
            attention.append(
                {**base, "kind": "no_documents", "severity": "info", "title": "No documents yet",
                 "detail": "Upload an SRS to start requirements analysis."}
            )
    attention.sort(key=lambda a: SEVERITY_RANK[a["severity"]])  # stable: keeps project order within a level

    return {
        "generated_at": now,
        "user_name": user_name,
        "projects": project_stats,
        "tasks": task_stats,
        "project_overview": overview[:8],
        "recent_tasks": recent_tasks,
        "agents": agents,
        "recent_agent_runs": recent_agent_runs,
        "insights": {
            "pipeline": pipeline,
            "requirements": {
                "functional": totals.get("functional", 0),
                "non_functional": totals.get("non_functional", 0),
                "user_stories": totals.get("user_stories", 0),
                "acceptance_criteria": totals.get("acceptance_criteria", 0),
            },
            "documents": {
                "total": documents_total,
                "processed": doc_status.get("COMPLETED", 0),
                "failed": doc_status.get("FAILED", 0),
                "pending": documents_total - doc_status.get("COMPLETED", 0) - doc_status.get("FAILED", 0),
            },
            "risks": {
                "high_risks": severity.get("HIGH", 0) + impact.get("HIGH", 0),
                "total_risks": sum(severity.values()) + sum(impact.values()),
                "open_ambiguities": sum(n for _, n in totals.get("ambiguity_impact", [])),
                "blocking_dependencies": totals.get("blocking_dependencies", 0),
            },
            "active_sprints": active_sprints[:4],
            "attention": attention[:6],
        },
    }


# ---------------------------------------------------------------------------
# Route
# ---------------------------------------------------------------------------


def _load_totals(db: Session, project_ids: list[int]) -> dict[str, Any]:
    def count(model) -> int:
        return db.scalar(select(func.count()).select_from(model).where(model.project_id.in_(project_ids))) or 0

    def grouped(column, model) -> list[tuple[str | None, int]]:
        stmt = select(column, func.count()).where(model.project_id.in_(project_ids)).group_by(column)
        return [(value, n) for value, n in db.execute(stmt).all()]

    blocking = db.scalar(
        select(func.count())
        .select_from(PMTaskDependency)
        .where(PMTaskDependency.project_id.in_(project_ids), PMTaskDependency.is_blocking.is_(True))
    )
    return {
        "functional": count(Requirement),
        "non_functional": count(NonFunctionalRequirement),
        "user_stories": count(UserStory),
        "acceptance_criteria": count(AcceptanceCriteria),
        "risk_severity": grouped(Risk.severity, Risk),
        "pm_risk_impact": grouped(PMRisk.impact, PMRisk),
        "ambiguity_impact": grouped(Ambiguity.impact, Ambiguity),
        "blocking_dependencies": blocking or 0,
    }


@router.get("/summary", response_model=DashboardSummary)
def dashboard_summary(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    projects = db.scalars(
        select(Project).where(Project.owner_id == user.id).order_by(Project.created_at.desc(), Project.id.desc())
    ).all()
    ids = [p.id for p in projects]

    tasks = db.execute(
        select(
            PMTask.id, PMTask.project_id, PMTask.task_id, PMTask.title, PMTask.priority, PMTask.status,
            PMTask.story_points, PMTask.suggested_role, PMTask.sprint_id, PMTask.execution_index,
        ).where(PMTask.project_id.in_(ids))
    ).all()
    sprints = db.execute(
        select(PMSprint.project_id, PMSprint.sprint_id, PMSprint.name, PMSprint.start_date, PMSprint.end_date)
        .where(PMSprint.project_id.in_(ids))
    ).all()
    plans = db.execute(select(PMPlan.project_id, PMPlan.created_at).where(PMPlan.project_id.in_(ids))).all()
    documents = db.execute(
        select(Document.project_id, Document.processing_status, func.count().label("n"))
        .where(Document.project_id.in_(ids))
        .group_by(Document.project_id, Document.processing_status)
    ).all()
    agent_runs = db.execute(
        select(
            AgentRun.id, AgentRun.project_id, AgentRun.agent_name, AgentRun.status,
            AgentRun.started_at, AgentRun.completed_at, AgentRun.error,
        ).where(AgentRun.project_id.in_(ids))
    ).all()

    return build_summary(
        user_name=user.display_name,
        now=datetime.now(timezone.utc),
        projects=projects,
        tasks=tasks,
        sprints=sprints,
        plans=plans,
        documents=documents,
        agent_runs=agent_runs,
        totals=_load_totals(db, ids),
    )
