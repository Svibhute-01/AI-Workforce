"""Validation of the LLM's project plan (the "Validate Project Plan" step).

Pydantic already guarantees shape and types. This module checks *meaning*:

* every reference points at something that really exists for this project
* every task is grounded (traceable to requirements, or a justified inference)
* dependencies form a DAG and sprints respect them
* requirements / stories / NFRs are actually covered by tasks

Errors block persistence. Coverage gaps trigger one repair attempt and are then
recorded as warnings, so a long tail of low-value gaps cannot make the whole run
fail. Nothing here generates plan content: the only derived value is the
execution order, computed from the validated dependency graph.
"""

import heapq
from dataclasses import dataclass, field
from datetime import date

from .pm_context import RequirementsContext
from ..schemas_pm import ProjectPlan

_PRIORITY_RANK = {"HIGH": 0, "MEDIUM": 1, "LOW": 2}


@dataclass
class PlanIssues:
    errors: list[str] = field(default_factory=list)
    coverage_gaps: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def needs_repair(self) -> bool:
        return bool(self.errors or self.coverage_gaps)

    def feedback(self) -> list[str]:
        return [*self.errors, *self.coverage_gaps]


def normalize_plan(
    plan: ProjectPlan,
    project_start: date | None,
    project_due: date | None,
) -> tuple[ProjectPlan, list[str]]:
    """Clean harmless issues and never let fabricated dates through.

    Sprint dates are only kept when the project itself has a start date and the
    dates parse and fall inside the project window. Otherwise they are dropped.
    """
    plan = plan.model_copy(deep=True)
    warnings: list[str] = []

    seen_edges: set[tuple] = set()
    unique_dependencies = []
    for dependency in plan.dependencies:
        key = (dependency.task_id, dependency.depends_on_task_id, dependency.dependency_type)
        if key in seen_edges:
            continue
        seen_edges.add(key)
        unique_dependencies.append(dependency)
    plan.dependencies = unique_dependencies

    dropped = False
    for sprint in plan.sprints:
        if not (sprint.start_date or sprint.end_date):
            continue
        start = _parse_date(sprint.start_date)
        end = _parse_date(sprint.end_date)
        valid = (
            project_start is not None
            and start is not None
            and end is not None
            and start <= end
            and start >= project_start
            and (project_due is None or end <= project_due)
        )
        if not valid:
            sprint.start_date = None
            sprint.end_date = None
            dropped = True
    if dropped:
        warnings.append(
            "Sprint dates were removed because the project has no start date or the generated dates were "
            "invalid; no dates are assumed."
        )
    return plan, warnings


def validate_plan(plan: ProjectPlan, context: RequirementsContext) -> PlanIssues:
    issues = PlanIssues()
    errors = issues.errors

    if not plan.tasks:
        errors.append("The plan contains no tasks.")
        return issues

    task_ids = _unique_ids("task", [t.task_id for t in plan.tasks], errors)
    epic_ids = _unique_ids("epic", [e.epic_id for e in plan.epics], errors)
    sprint_ids = _unique_ids("sprint", [s.sprint_id for s in plan.sprints], errors)
    _unique_ids("milestone", [m.milestone_id for m in plan.milestones], errors)
    _unique_ids("risk", [r.risk_id for r in plan.risks], errors)

    if not plan.sprints:
        errors.append("The plan contains no sprints.")
    sprint_index = {s.sprint_id: i for i, s in enumerate(plan.sprints)}

    valid_requirements = context.requirement_ids
    valid_stories = context.story_ids
    valid_artifacts = context.artifact_ids

    for epic in plan.epics:
        for ref in epic.related_requirement_ids:
            if ref not in valid_requirements:
                errors.append(f"Epic {epic.epic_id} references unknown requirement id '{ref}'.")

    # Dependency edges (validated first: grounding rules use them).
    internal_edges: list[tuple[str, str]] = []
    touched_by_edge: set[str] = set()
    for dep in plan.dependencies:
        label = f"Dependency {dep.task_id} -> {dep.depends_on_task_id or dep.dependency_type}"
        if dep.task_id not in task_ids:
            errors.append(f"{label}: task '{dep.task_id}' does not exist.")
            continue
        touched_by_edge.add(dep.task_id)
        if dep.dependency_type == "EXTERNAL":
            if dep.depends_on_task_id is not None:
                errors.append(f"{label}: an EXTERNAL dependency must not name a task; describe it in the description.")
            continue
        if not dep.depends_on_task_id:
            errors.append(f"{label}: non-EXTERNAL dependencies must set depends_on_task_id.")
        elif dep.depends_on_task_id not in task_ids:
            errors.append(f"{label}: depends_on_task_id '{dep.depends_on_task_id}' does not exist.")
        elif dep.depends_on_task_id == dep.task_id:
            errors.append(f"{label}: a task cannot depend on itself.")
        else:
            internal_edges.append((dep.task_id, dep.depends_on_task_id))
            touched_by_edge.add(dep.depends_on_task_id)

    # Per-task checks.
    for task in plan.tasks:
        where = f"Task {task.task_id}"
        if task.epic_id is not None and task.epic_id not in epic_ids:
            errors.append(f"{where}: epic '{task.epic_id}' does not exist.")
        if task.sprint not in sprint_ids:
            errors.append(f"{where}: sprint '{task.sprint}' does not exist.")
        if task.related_requirement_id and task.related_requirement_id not in valid_requirements:
            errors.append(f"{where}: related_requirement_id '{task.related_requirement_id}' is not a requirement of this project.")
        if task.related_story_id and task.related_story_id not in valid_stories:
            errors.append(f"{where}: related_story_id '{task.related_story_id}' is not a user story of this project.")
        for ref in task.related_artifact_ids:
            if ref not in valid_artifacts:
                errors.append(f"{where}: related artifact id '{ref}' does not exist in this project's requirements.")

        has_link = bool(task.related_requirement_id or task.related_story_id or task.related_artifact_ids)
        has_rationale = bool((task.rationale or "").strip())
        if task.grounding == "EXPLICIT" and not has_link:
            errors.append(f"{where}: grounding is EXPLICIT but the task cites no requirement, story or artifact.")
        elif task.grounding == "INFERRED":
            if not has_rationale:
                errors.append(f"{where}: INFERRED tasks need a rationale explaining the engineering inference.")
            if not (has_link or task.task_id in touched_by_edge):
                errors.append(
                    f"{where}: INFERRED task is not traceable; link it to a requirement/artifact or to a task that needs it."
                )
        elif task.grounding in ("AMBIGUOUS", "UNKNOWN") and not has_rationale:
            errors.append(f"{where}: {task.grounding} tasks need a rationale stating what information is missing.")

    # Dependency graph: cycles and sprint ordering.
    cycle_tasks = _tasks_in_cycles(task_ids, internal_edges)
    if cycle_tasks:
        errors.append(f"Dependency cycle detected involving tasks: {', '.join(sorted(cycle_tasks))}.")
    task_sprint = {t.task_id: t.sprint for t in plan.tasks}
    for task_id, depends_on in internal_edges:
        a, b = task_sprint.get(task_id), task_sprint.get(depends_on)
        if a in sprint_index and b in sprint_index and sprint_index[a] < sprint_index[b]:
            errors.append(
                f"Task {task_id} is in sprint {a} but depends on {depends_on} which is scheduled later in sprint {b}."
            )

    for milestone in plan.milestones:
        if not milestone.task_ids:
            errors.append(f"Milestone {milestone.milestone_id} has no tasks.")
        for ref in milestone.task_ids:
            if ref not in task_ids:
                errors.append(f"Milestone {milestone.milestone_id} references unknown task '{ref}'.")
        if milestone.target_sprint and milestone.target_sprint not in sprint_ids:
            errors.append(f"Milestone {milestone.milestone_id} targets unknown sprint '{milestone.target_sprint}'.")
    for risk in plan.risks:
        for ref in risk.related_tasks:
            if ref not in task_ids:
                errors.append(f"Risk {risk.risk_id} references unknown task '{ref}'.")

    # Soft findings.
    used_sprints = {t.sprint for t in plan.tasks}
    for sprint in plan.sprints:
        if sprint.sprint_id not in used_sprints:
            issues.warnings.append(f"Sprint {sprint.sprint_id} has no tasks.")
    used_epics = {t.epic_id for t in plan.tasks}
    for epic in plan.epics:
        if epic.epic_id not in used_epics:
            issues.warnings.append(f"Epic {epic.epic_id} has no tasks.")
    if not plan.milestones:
        issues.warnings.append("The plan defines no milestones.")
    if not plan.risks:
        issues.warnings.append("The plan defines no risks.")

    _check_coverage(plan, context, issues)
    return issues


def compute_execution_order(plan: ProjectPlan) -> list[str]:
    """Dependency-aware order (Kahn). Ties: earlier sprint, higher priority, plan order."""
    sprint_index = {s.sprint_id: i for i, s in enumerate(plan.sprints)}
    task_ids = {t.task_id for t in plan.tasks}
    blockers: dict[str, set[str]] = {t.task_id: set() for t in plan.tasks}
    dependents: dict[str, set[str]] = {t.task_id: set() for t in plan.tasks}
    for dep in plan.dependencies:
        if dep.depends_on_task_id in task_ids and dep.task_id in task_ids and dep.depends_on_task_id != dep.task_id:
            blockers[dep.task_id].add(dep.depends_on_task_id)
            dependents[dep.depends_on_task_id].add(dep.task_id)

    def key(position: int, task) -> tuple:
        return (sprint_index.get(task.sprint, 10**6), _PRIORITY_RANK.get(task.priority, 3), position)

    by_id = {t.task_id: (i, t) for i, t in enumerate(plan.tasks)}
    ready = [key(i, t) + (t.task_id,) for i, t in by_id.values() if not blockers[t.task_id]]
    heapq.heapify(ready)
    order: list[str] = []
    while ready:
        *_, task_id = heapq.heappop(ready)
        order.append(task_id)
        for child in dependents[task_id]:
            blockers[child].discard(task_id)
            if not blockers[child]:
                i, t = by_id[child]
                heapq.heappush(ready, key(i, t) + (child,))
    return order


# ---------------------------------------------------------------------------


def _check_coverage(plan: ProjectPlan, context: RequirementsContext, issues: PlanIssues) -> None:
    story_to_requirement = {
        s["id"]: s.get("requirement_id") for s in context.payload.get("user_stories", [])
    }
    covered: set[str] = set()
    for task in plan.tasks:
        if task.related_requirement_id:
            covered.add(task.related_requirement_id)
        if task.related_story_id:
            covered.add(task.related_story_id)
            parent = story_to_requirement.get(task.related_story_id)
            if parent:
                covered.add(parent)
        covered.update(task.related_artifact_ids)

    for item in context.payload.get("functional_requirements", []):
        if item["id"] not in covered:
            issues.coverage_gaps.append(f"Requirement {item['id']} ('{item['title']}') has no task.")
    for item in context.payload.get("user_stories", []):
        if item["id"] not in covered:
            issues.coverage_gaps.append(f"User story {item['id']} ('{item['title']}') has no task.")
    for item in context.payload.get("non_functional_requirements", []):
        if item["id"] not in covered:
            issues.coverage_gaps.append(
                f"Non-functional requirement {item['id']} ({item['category']}) is not addressed by any task."
            )


def _unique_ids(kind: str, ids: list[str], errors: list[str]) -> set[str]:
    seen: set[str] = set()
    for value in ids:
        if value in seen:
            errors.append(f"Duplicate {kind} id '{value}'.")
        seen.add(value)
    return seen


def _tasks_in_cycles(task_ids: set[str], edges: list[tuple[str, str]]) -> set[str]:
    blockers = {t: set() for t in task_ids}
    dependents = {t: set() for t in task_ids}
    for task, depends_on in edges:
        blockers[task].add(depends_on)
        dependents[depends_on].add(task)
    queue = [t for t in task_ids if not blockers[t]]
    resolved = 0
    while queue:
        node = queue.pop()
        resolved += 1
        for child in dependents[node]:
            blockers[child].discard(node)
            if not blockers[child]:
                queue.append(child)
    return {t for t in task_ids if blockers[t]} if resolved < len(task_ids) else set()


def _parse_date(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(value.strip())
    except ValueError:
        return None
