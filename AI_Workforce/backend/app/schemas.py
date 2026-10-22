from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field


Priority = Literal["HIGH", "MEDIUM", "LOW"]
Impact = Literal["HIGH", "MEDIUM", "LOW"]


class UserCreate(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    display_name: str = Field(min_length=1, max_length=120)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: EmailStr
    display_name: str


class AuthResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse


class ProjectCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    description: str | None = None
    manager: str | None = Field(default=None, max_length=120)
    start_date: date | None = None
    due_date: date | None = None
    status: str = Field(default="Planning", max_length=40)


class ProjectResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    description: str | None
    manager: str | None
    start_date: date | None
    due_date: date | None
    status: str
    created_at: datetime | None


class DocumentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    project_id: int
    filename: str
    file_type: str
    file_size: int
    page_count: int | None
    upload_time: datetime | None
    processing_status: str
    error_message: str | None


class SourceReference(BaseModel):
    document: str
    page: int
    source: str


class FunctionalRequirement(BaseModel):
    title: str
    description: str
    priority: Priority | None = None
    priority_basis: Literal["EXPLICIT", "INFERRED", "UNSPECIFIED"] = "UNSPECIFIED"
    source_references: list[SourceReference] = Field(default_factory=list)


class NonFunctionalRequirement(BaseModel):
    category: str
    description: str
    priority: Priority | None = None
    source_references: list[SourceReference] = Field(default_factory=list)


class UserStoryArtifact(BaseModel):
    title: str
    story: str
    priority: Priority | None = None
    requirement_title: str | None = None
    source_references: list[SourceReference] = Field(default_factory=list)


class AcceptanceCriteriaArtifact(BaseModel):
    description: str
    user_story_title: str | None = None
    source_references: list[SourceReference] = Field(default_factory=list)


class DependencyArtifact(BaseModel):
    description: str
    related_requirement: str | None = None
    source_references: list[SourceReference] = Field(default_factory=list)


class AmbiguityArtifact(BaseModel):
    description: str
    impact: Impact | None = None
    related_requirement: str | None = None
    source_references: list[SourceReference] = Field(default_factory=list)


class ConstraintArtifact(BaseModel):
    description: str
    source_references: list[SourceReference] = Field(default_factory=list)


class RiskArtifact(BaseModel):
    description: str
    severity: Impact | None = None
    related_requirement: str | None = None
    source_references: list[SourceReference] = Field(default_factory=list)


class ProjectSummary(BaseModel):
    summary: str
    scope: str | None = None
    actors: list[str] = Field(default_factory=list)


class RequirementsAnalysis(BaseModel):
    project_summary: ProjectSummary
    functional_requirements: list[FunctionalRequirement] = Field(default_factory=list)
    non_functional_requirements: list[NonFunctionalRequirement] = Field(default_factory=list)
    user_stories: list[UserStoryArtifact] = Field(default_factory=list)
    acceptance_criteria: list[AcceptanceCriteriaArtifact] = Field(default_factory=list)
    dependencies: list[DependencyArtifact] = Field(default_factory=list)
    ambiguities: list[AmbiguityArtifact] = Field(default_factory=list)
    constraints: list[ConstraintArtifact] = Field(default_factory=list)
    risks: list[RiskArtifact] = Field(default_factory=list)
    source_references: list[SourceReference] = Field(default_factory=list)


class RequirementResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    project_id: int
    title: str
    description: str
    priority: str | None
    priority_basis: str | None
    source_references: list[SourceReference]


class NonFunctionalRequirementResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    project_id: int
    category: str
    description: str
    priority: str | None
    source_references: list[SourceReference]


class UserStoryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    project_id: int
    requirement_id: int | None
    title: str
    story: str
    priority: str | None
    source_references: list[SourceReference]


class AcceptanceCriteriaResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    project_id: int
    user_story_id: int | None
    description: str
    source_references: list[SourceReference]


class DependencyResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    project_id: int
    description: str
    related_requirement: str | None
    source_references: list[SourceReference]


class AmbiguityResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    project_id: int
    description: str
    impact: str | None
    related_requirement: str | None
    source_references: list[SourceReference]


class ConstraintResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    project_id: int
    description: str
    source_references: list[SourceReference]


class RiskResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    project_id: int
    description: str
    severity: str | None
    related_requirement: str | None
    source_references: list[SourceReference]


class AgentRunResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    project_id: int
    agent_name: str
    status: str
    started_at: datetime | None
    completed_at: datetime | None
    input_summary: dict | None
    output_summary: dict | None
    error: str | None


class AnalysisResponse(BaseModel):
    project_summary: ProjectSummary
    functional_requirements: list[RequirementResponse]
    non_functional_requirements: list[NonFunctionalRequirementResponse]
    user_stories: list[UserStoryResponse]
    acceptance_criteria: list[AcceptanceCriteriaResponse]
    dependencies: list[DependencyResponse]
    ambiguities: list[AmbiguityResponse]
    constraints: list[ConstraintResponse]
    risks: list[RiskResponse]
    source_references: list[SourceReference]
    latest_agent_run: AgentRunResponse | None = None


class RagQuery(BaseModel):
    query: str = Field(min_length=1, max_length=4000)


class RagSource(BaseModel):
    document: str
    page: int
    source: str


class RagResponse(BaseModel):
    answer: str
    sources: list[RagSource]