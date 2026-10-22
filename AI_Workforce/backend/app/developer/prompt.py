"""Turn a Project Manager task plus the Architect's design into the Developer Agent's task text."""

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import ArchDesign, PMTask, PMTaskDependency, Project

DEFAULT_STACK = "Python, FastAPI"
MAX_ITEMS = 12


def workspace_id(project_id: int) -> str:
    """Workspace folder name for a project. Fixed pattern, so it always passes the service's id check."""
    return f"project_{project_id}"


def _traced(items: list[dict[str, Any]], task: PMTask) -> list[dict[str, Any]]:
    """Design items that trace to this task, or to the requirement it implements."""
    return [
        item for item in items or []
        if task.task_id in (item.get("task_ids") or [])
        or (task.related_requirement_id and task.related_requirement_id in (item.get("requirement_ids") or []))
    ][:MAX_ITEMS]


def tech_stack(design: ArchDesign | None) -> str:
    if not design:
        return DEFAULT_STACK
    seen: list[str] = []
    for component in (design.hld or {}).get("components", []):
        tech = (component.get("technology") or "").strip()
        if tech and tech not in seen:
            seen.append(tech)
    return ", ".join(seen[:6]) or DEFAULT_STACK


def _design_section(design: ArchDesign | None, task: PMTask) -> list[str]:
    if not design:
        return []
    hld, lld = design.hld or {}, design.lld or {}
    lines = ["", "Architecture to follow:"]
    style = (hld.get("style") or {}).get("name")
    if style:
        lines.append(f"- Style: {style}")
    for module in _traced(lld.get("modules"), task):
        lines.append(f"- Module {module.get('name')} ({module.get('kind')}): {module.get('description')}")
    for api in _traced(lld.get("apis"), task):
        lines.append(f"- API {api.get('method')} {api.get('path')}: {api.get('summary')}")
        for rule in api.get("validation_rules") or []:
            lines.append(f"    validation: {rule}")
    for model in _traced(lld.get("data_models"), task):
        fields = ", ".join(f"{f.get('name')}: {f.get('type')}" for f in model.get("fields") or [])
        lines.append(f"- Data model {model.get('name')}: {fields}")
    for table in _traced(lld.get("tables"), task):
        columns = ", ".join(f"{c.get('name')} {c.get('type')}" for c in table.get("columns") or [])
        lines.append(f"- Table {table.get('name')}: {columns}")
    for rule in _traced(lld.get("business_rules"), task):
        lines.append(f"- Business rule {rule.get('title')}: {rule.get('description')}")
    return lines if len(lines) > 2 else []


def build_task_text(db: Session, project: Project, task: PMTask) -> str:
    design = db.scalar(select(ArchDesign).where(ArchDesign.project_id == project.id))
    lines = [
        f"Project: {project.name}",
        f"Project description: {project.description or 'n/a'}",
        "",
        f"Task {task.task_id}: {task.title}",
        task.description,
    ]
    if task.acceptance_criteria:
        lines += ["", "Acceptance criteria (the code and tests must satisfy these):"]
        lines += [f"- {criterion}" for criterion in task.acceptance_criteria]
    lines += _design_section(design, task)
    lines += [
        "",
        "Scope: implement only the Python backend part of this task, plus pytest tests that cover the "
        "acceptance criteria. Frontend work, deployment files and external services are out of scope for this run.",
    ]
    return "\n".join(lines)


def blocking_dependencies(db: Session, task: PMTask) -> list[PMTask]:
    """Blocking prerequisites of ``task`` that are not completed yet."""
    prerequisite_ids = db.scalars(
        select(PMTaskDependency.depends_on_task_id).where(
            PMTaskDependency.plan_id == task.plan_id,
            PMTaskDependency.task_id == task.task_id,
            PMTaskDependency.is_blocking.is_(True),
            PMTaskDependency.depends_on_task_id.is_not(None),
        )
    ).all()
    if not prerequisite_ids:
        return []
    return list(db.scalars(
        select(PMTask).where(
            PMTask.plan_id == task.plan_id, PMTask.task_id.in_(prerequisite_ids), PMTask.status != "COMPLETED"
        )
    ))
