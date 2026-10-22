"""Response models for ``GET /api/dashboard/summary``.

Everything here is derived from existing tables; nothing is stored or mocked.
"""

from datetime import date, datetime

from pydantic import BaseModel


class CountItem(BaseModel):
    key: str
    label: str
    count: int
    story_points: int | None = None


class ProjectStats(BaseModel):
    total: int
    new_last_7_days: int
    overdue: int
    by_status: list[CountItem]


class TaskStats(BaseModel):
    total: int
    completed: int
    in_progress: int
    todo: int
    overdue: int
    planned_last_7_days: int
    completion_rate: int | None
    total_story_points: int
    completed_story_points: int
    projects_with_plan: int
    by_status: list[CountItem]
    by_priority: list[CountItem]
    by_role: list[CountItem]


class ProjectOverview(BaseModel):
    id: int
    name: str
    status: str
    manager: str | None
    start_date: date | None
    due_date: date | None
    created_at: datetime | None
    days_to_due: int | None
    is_overdue: bool
    documents: int
    documents_ready: int
    requirements_ready: bool
    plan_ready: bool
    tasks_total: int
    tasks_completed: int
    story_points_total: int
    story_points_completed: int
    progress: int | None
    overdue_tasks: int
    latest_run_status: str | None


class RecentTask(BaseModel):
    id: int
    task_id: str
    title: str
    priority: str
    status: str
    story_points: int
    suggested_role: str
    sprint_name: str | None
    sprint_end_date: date | None
    is_overdue: bool
    project_id: int
    project_name: str


class AgentSummary(BaseModel):
    key: str
    name: str
    stage: str
    total_runs: int
    completed: int
    failed: int
    processing: int
    runs_last_7_days: int
    success_rate: int | None
    avg_duration_seconds: float | None
    last_run_at: datetime | None
    last_run_status: str | None
    last_project: str | None


class AgentRunItem(BaseModel):
    id: int
    agent_key: str | None
    agent_name: str
    status: str
    project_id: int
    project_name: str
    started_at: datetime | None
    completed_at: datetime | None
    duration_seconds: float | None
    error: str | None


class PipelineStage(BaseModel):
    key: str
    label: str
    count: int


class RequirementTotals(BaseModel):
    functional: int
    non_functional: int
    user_stories: int
    acceptance_criteria: int


class DocumentTotals(BaseModel):
    total: int
    processed: int
    pending: int
    failed: int


class RiskTotals(BaseModel):
    high_risks: int
    total_risks: int
    open_ambiguities: int
    blocking_dependencies: int


class ActiveSprint(BaseModel):
    sprint_id: str
    name: str
    project_id: int
    project_name: str
    start_date: date | None
    end_date: date | None
    tasks_total: int
    tasks_completed: int
    story_points: int


class AttentionItem(BaseModel):
    kind: str
    severity: str
    title: str
    detail: str | None
    project_id: int
    project_name: str


class Insights(BaseModel):
    pipeline: list[PipelineStage]
    requirements: RequirementTotals
    documents: DocumentTotals
    risks: RiskTotals
    active_sprints: list[ActiveSprint]
    attention: list[AttentionItem]


class DashboardSummary(BaseModel):
    generated_at: datetime
    user_name: str | None
    projects: ProjectStats
    tasks: TaskStats
    project_overview: list[ProjectOverview]
    recent_tasks: list[RecentTask]
    agents: list[AgentSummary]
    recent_agent_runs: list[AgentRunItem]
    insights: Insights
