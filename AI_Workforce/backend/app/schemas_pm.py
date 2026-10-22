"""Schemas for the Project Manager AI.

Two groups live here:

* ``ProjectPlan`` and its parts: the contract the LLM must satisfy. Every field
  is validated before anything is stored.
* ``PM*Response`` models: what the API returns.

Constraints are enforced with validators instead of ``Field(ge=..., min_length=...)``
so the JSON schema sent to Gemini stays simple (Gemini rejects several keywords).
"""

from datetime import date, datetime
from typing import Literal

from pydantic import AliasChoices, BaseModel, ConfigDict, Field, field_validator

from .schemas import AgentRunResponse, SourceReference

Priority = Literal["HIGH", "MEDIUM", "LOW"]
Grounding = Literal["EXPLICIT", "INFERRED", "AMBIGUOUS", "UNKNOWN"]
SuggestedRole = Literal[
    "Frontend Developer",
    "Backend Developer",
    "Full Stack Developer",
    "Database Engineer",
    "AI/ML Engineer",
    "DevOps Engineer",
    "QA Engineer",
    "Security Engineer",
    "UI/UX Designer",
]
DependencyType = Literal["TECHNICAL", "DATA", "INTEGRATION", "PREREQUISITE", "EXTERNAL"]

FIBONACCI_POINTS = (1, 2, 3, 5, 8, 13)
PM_AGENT_NAME = "Project Manager AI"


def _required_text(value: str) -> str:
    value = (value or "").strip()
    if not value:
        raise ValueError("must not be empty")
    return value


# ---------------------------------------------------------------------------
# LLM output contract
# ---------------------------------------------------------------------------


class PlanEpic(BaseModel):
    epic_id: str
    title: str
    description: str
    priority: Priority
    related_requirement_ids: list[str] = Field(default_factory=list)

    clean_text = field_validator("epic_id", "title", "description")(_required_text)


class PlanTask(BaseModel):
    task_id: str
    epic_id: str | None = None
    title: str
    description: str
    related_story_id: str | None = None
    related_requirement_id: str | None = None
    related_artifact_ids: list[str] = Field(default_factory=list)
    priority: Priority
    story_points: int
    suggested_role: SuggestedRole
    acceptance_criteria: list[str] = Field(default_factory=list)
    sprint: str
    grounding: Grounding
    rationale: str | None = None

    clean_text = field_validator("task_id", "title", "description", "sprint")(_required_text)

    @field_validator("story_points")
    @classmethod
    def _fibonacci(cls, value: int) -> int:
        if value not in FIBONACCI_POINTS:
            raise ValueError(f"story_points must be one of {list(FIBONACCI_POINTS)}, got {value}")
        return value


class PlanDependency(BaseModel):
    task_id: str
    depends_on_task_id: str | None = None
    dependency_type: DependencyType
    description: str
    is_blocking: bool = False

    clean_text = field_validator("task_id", "description")(_required_text)


class PlanSprint(BaseModel):
    sprint_id: str
    name: str
    goal: str
    start_date: str | None = None
    end_date: str | None = None
    capacity_notes: str | None = None

    clean_text = field_validator("sprint_id", "name", "goal")(_required_text)


class PlanMilestone(BaseModel):
    milestone_id: str
    title: str
    description: str
    task_ids: list[str] = Field(default_factory=list)
    target_sprint: str | None = None

    clean_text = field_validator("milestone_id", "title", "description")(_required_text)


class PlanRisk(BaseModel):
    risk_id: str
    title: str
    description: str
    impact: Priority
    likelihood: Priority
    mitigation: str
    related_tasks: list[str] = Field(default_factory=list)

    clean_text = field_validator("risk_id", "title", "description", "mitigation")(_required_text)


class DefinitionOfDone(BaseModel):
    items: list[str] = Field(default_factory=list)

    @field_validator("items")
    @classmethod
    def _not_empty(cls, value: list[str]) -> list[str]:
        cleaned = [item.strip() for item in value if item and item.strip()]
        if not cleaned:
            raise ValueError("definition of done needs at least one item")
        return cleaned


class ProjectPlan(BaseModel):
    execution_summary: str
    epics: list[PlanEpic] = Field(default_factory=list)
    tasks: list[PlanTask] = Field(default_factory=list)
    dependencies: list[PlanDependency] = Field(default_factory=list)
    sprints: list[PlanSprint] = Field(default_factory=list)
    milestones: list[PlanMilestone] = Field(default_factory=list)
    risks: list[PlanRisk] = Field(default_factory=list)
    definition_of_done: DefinitionOfDone
    assumptions: list[str] = Field(default_factory=list)

    clean_text = field_validator("execution_summary")(_required_text)


# ---------------------------------------------------------------------------
# API responses
# ---------------------------------------------------------------------------


class PMEpicResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    epic_id: str
    title: str
    description: str
    priority: str | None
    related_requirement_ids: list[str]
    task_ids: list[str] = Field(default_factory=list)


class PMTaskResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    task_id: str
    epic_id: str | None
    title: str
    description: str
    related_story_id: str | None
    related_story_title: str | None = None
    related_requirement_id: str | None
    related_requirement_title: str | None = None
    related_artifact_ids: list[str]
    priority: str
    story_points: int
    suggested_role: str
    dependencies: list[str] = Field(default_factory=list)
    acceptance_criteria: list[str]
    sprint: str = Field(validation_alias=AliasChoices("sprint", "sprint_id"))
    status: str
    grounding: str
    rationale: str | None
    source_references: list[SourceReference]
    execution_index: int


class PMDependencyResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    task_id: str
    depends_on_task_id: str | None
    dependency_type: str
    description: str
    is_blocking: bool


class PMSprintResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    sprint_id: str
    sequence: int
    name: str
    goal: str
    start_date: date | None
    end_date: date | None
    capacity_notes: str | None
    tasks: list[str] = Field(default_factory=list)
    total_story_points: int = 0


class PMMilestoneResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    milestone_id: str
    sequence: int
    title: str
    description: str
    task_ids: list[str]
    target_sprint_id: str | None


class PMRiskResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    risk_id: str
    title: str
    description: str
    impact: str
    likelihood: str
    mitigation: str
    related_tasks: list[str]


class PMPlanInfo(BaseModel):
    id: int
    execution_summary: str
    definition_of_done: list[str]
    assumptions: list[str]
    execution_order: list[str]
    warnings: list[str]
    created_at: datetime | None
    requirements_changed: bool = False


class PMPlanResponse(BaseModel):
    """Everything the frontend needs in one call.

    ``status`` reflects the most recent Project Manager run. If a regeneration
    failed, ``plan`` still holds the previous valid plan and ``status`` is FAILED.
    """

    status: Literal["NOT_GENERATED", "PROCESSING", "COMPLETED", "FAILED"]
    plan: PMPlanInfo | None = None
    epics: list[PMEpicResponse] = Field(default_factory=list)
    tasks: list[PMTaskResponse] = Field(default_factory=list)
    sprints: list[PMSprintResponse] = Field(default_factory=list)
    dependencies: list[PMDependencyResponse] = Field(default_factory=list)
    blocking_dependencies: list[PMDependencyResponse] = Field(default_factory=list)
    milestones: list[PMMilestoneResponse] = Field(default_factory=list)
    risks: list[PMRiskResponse] = Field(default_factory=list)
    latest_agent_run: AgentRunResponse | None = None
