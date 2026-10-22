from datetime import date, datetime
from typing import Any

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, JSON, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    display_name: Mapped[str] = mapped_column(String(120))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    projects: Mapped[list["Project"]] = relationship(back_populates="owner", cascade="all, delete-orphan")


class Project(Base):
    __tablename__ = "projects"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    name: Mapped[str] = mapped_column(String(200))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    manager: Mapped[str | None] = mapped_column(String(120), nullable=True)
    start_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    due_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    status: Mapped[str] = mapped_column(String(40), default="Planning")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    owner: Mapped[User] = relationship(back_populates="projects")
    documents: Mapped[list["Document"]] = relationship(back_populates="project", cascade="all, delete-orphan")
    requirements: Mapped[list["Requirement"]] = relationship(back_populates="project", cascade="all, delete-orphan")
    non_functional_requirements: Mapped[list["NonFunctionalRequirement"]] = relationship(
        back_populates="project", cascade="all, delete-orphan"
    )
    user_stories: Mapped[list["UserStory"]] = relationship(back_populates="project", cascade="all, delete-orphan")
    acceptance_criteria: Mapped[list["AcceptanceCriteria"]] = relationship(
        back_populates="project", cascade="all, delete-orphan"
    )
    dependencies: Mapped[list["Dependency"]] = relationship(back_populates="project", cascade="all, delete-orphan")
    ambiguities: Mapped[list["Ambiguity"]] = relationship(back_populates="project", cascade="all, delete-orphan")
    constraints: Mapped[list["Constraint"]] = relationship(back_populates="project", cascade="all, delete-orphan")
    risks: Mapped[list["Risk"]] = relationship(back_populates="project", cascade="all, delete-orphan")
    agent_runs: Mapped[list["AgentRun"]] = relationship(back_populates="project", cascade="all, delete-orphan")
    pm_plans: Mapped[list["PMPlan"]] = relationship(back_populates="project", cascade="all, delete-orphan")
    arch_designs: Mapped[list["ArchDesign"]] = relationship(back_populates="project", cascade="all, delete-orphan")


class Document(Base):
    __tablename__ = "documents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), index=True)
    filename: Mapped[str] = mapped_column(String(255))
    file_type: Mapped[str] = mapped_column(String(80))
    file_size: Mapped[int] = mapped_column(Integer)
    page_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    storage_path: Mapped[str] = mapped_column(String(500))
    processing_status: Mapped[str] = mapped_column(String(30), default="UPLOADED")
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    upload_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    project: Mapped[Project] = relationship(back_populates="documents")
    chunks: Mapped[list["DocumentChunk"]] = relationship(back_populates="document", cascade="all, delete-orphan")


class DocumentChunk(Base):
    __tablename__ = "document_chunks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    document_id: Mapped[int] = mapped_column(ForeignKey("documents.id"), index=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), index=True)
    chunk_index: Mapped[int] = mapped_column(Integer)
    page: Mapped[int] = mapped_column(Integer)
    text: Mapped[str] = mapped_column(Text)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)

    document: Mapped[Document] = relationship(back_populates="chunks")


class Requirement(Base):
    __tablename__ = "requirements"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), index=True)
    title: Mapped[str] = mapped_column(String(300))
    description: Mapped[str] = mapped_column(Text)
    priority: Mapped[str | None] = mapped_column(String(20), nullable=True)
    priority_basis: Mapped[str | None] = mapped_column(String(30), nullable=True)
    source_references: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)

    project: Mapped[Project] = relationship(back_populates="requirements")
    user_stories: Mapped[list["UserStory"]] = relationship(back_populates="requirement")


class NonFunctionalRequirement(Base):
    __tablename__ = "non_functional_requirements"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), index=True)
    category: Mapped[str] = mapped_column(String(80))
    description: Mapped[str] = mapped_column(Text)
    priority: Mapped[str | None] = mapped_column(String(20), nullable=True)
    source_references: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)

    project: Mapped[Project] = relationship(back_populates="non_functional_requirements")


class UserStory(Base):
    __tablename__ = "user_stories"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), index=True)
    requirement_id: Mapped[int | None] = mapped_column(ForeignKey("requirements.id"), nullable=True)
    title: Mapped[str] = mapped_column(String(300))
    story: Mapped[str] = mapped_column(Text)
    priority: Mapped[str | None] = mapped_column(String(20), nullable=True)
    source_references: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)

    project: Mapped[Project] = relationship(back_populates="user_stories")
    requirement: Mapped[Requirement | None] = relationship(back_populates="user_stories")
    acceptance_criteria: Mapped[list["AcceptanceCriteria"]] = relationship(
        back_populates="user_story", cascade="all, delete-orphan"
    )


class AcceptanceCriteria(Base):
    __tablename__ = "acceptance_criteria"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), index=True)
    user_story_id: Mapped[int | None] = mapped_column(ForeignKey("user_stories.id"), nullable=True)
    description: Mapped[str] = mapped_column(Text)
    source_references: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)

    project: Mapped[Project] = relationship(back_populates="acceptance_criteria")
    user_story: Mapped[UserStory | None] = relationship(back_populates="acceptance_criteria")


class Dependency(Base):
    __tablename__ = "dependencies"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), index=True)
    description: Mapped[str] = mapped_column(Text)
    related_requirement: Mapped[str | None] = mapped_column(String(300), nullable=True)
    source_references: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)

    project: Mapped[Project] = relationship(back_populates="dependencies")


class Ambiguity(Base):
    __tablename__ = "ambiguities"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), index=True)
    description: Mapped[str] = mapped_column(Text)
    impact: Mapped[str | None] = mapped_column(String(20), nullable=True)
    related_requirement: Mapped[str | None] = mapped_column(String(300), nullable=True)
    source_references: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)

    project: Mapped[Project] = relationship(back_populates="ambiguities")


class Constraint(Base):
    __tablename__ = "constraints"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), index=True)
    description: Mapped[str] = mapped_column(Text)
    source_references: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)

    project: Mapped[Project] = relationship(back_populates="constraints")


class Risk(Base):
    __tablename__ = "risks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), index=True)
    description: Mapped[str] = mapped_column(Text)
    severity: Mapped[str | None] = mapped_column(String(20), nullable=True)
    related_requirement: Mapped[str | None] = mapped_column(String(300), nullable=True)
    source_references: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)

    project: Mapped[Project] = relationship(back_populates="risks")


class AgentRun(Base):
    __tablename__ = "agent_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), index=True)
    agent_name: Mapped[str] = mapped_column(String(120))
    status: Mapped[str] = mapped_column(String(30))
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    input_summary: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    output_summary: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)

    project: Mapped[Project] = relationship(back_populates="agent_runs")


# --- Project Manager AI -----------------------------------------------------
# Tables are prefixed "pm_" because `dependencies` and `risks` already belong to
# the Requirements Analyst. Every row carries project_id so queries can always be
# scoped to a single project.


class PMPlan(Base):
    __tablename__ = "pm_plans"
    __table_args__ = (UniqueConstraint("project_id", name="uq_pm_plans_project"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), index=True)
    agent_run_id: Mapped[int | None] = mapped_column(ForeignKey("agent_runs.id"), nullable=True)
    requirements_run_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    execution_summary: Mapped[str] = mapped_column(Text)
    definition_of_done: Mapped[list[str]] = mapped_column(JSON, default=list)
    assumptions: Mapped[list[str]] = mapped_column(JSON, default=list)
    execution_order: Mapped[list[str]] = mapped_column(JSON, default=list)
    warnings: Mapped[list[str]] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    project: Mapped[Project] = relationship(back_populates="pm_plans")
    epics: Mapped[list["PMEpic"]] = relationship(back_populates="plan", cascade="all, delete-orphan")
    tasks: Mapped[list["PMTask"]] = relationship(back_populates="plan", cascade="all, delete-orphan")
    task_dependencies: Mapped[list["PMTaskDependency"]] = relationship(
        back_populates="plan", cascade="all, delete-orphan"
    )
    sprints: Mapped[list["PMSprint"]] = relationship(back_populates="plan", cascade="all, delete-orphan")
    milestones: Mapped[list["PMMilestone"]] = relationship(back_populates="plan", cascade="all, delete-orphan")
    risks: Mapped[list["PMRisk"]] = relationship(back_populates="plan", cascade="all, delete-orphan")


class PMEpic(Base):
    __tablename__ = "pm_epics"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), index=True)
    plan_id: Mapped[int] = mapped_column(ForeignKey("pm_plans.id"), index=True)
    epic_id: Mapped[str] = mapped_column(String(40))
    title: Mapped[str] = mapped_column(String(300))
    description: Mapped[str] = mapped_column(Text)
    priority: Mapped[str | None] = mapped_column(String(20), nullable=True)
    related_requirement_ids: Mapped[list[str]] = mapped_column(JSON, default=list)

    plan: Mapped[PMPlan] = relationship(back_populates="epics")


class PMTask(Base):
    __tablename__ = "pm_tasks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), index=True)
    plan_id: Mapped[int] = mapped_column(ForeignKey("pm_plans.id"), index=True)
    task_id: Mapped[str] = mapped_column(String(40))
    epic_id: Mapped[str | None] = mapped_column(String(40), nullable=True)
    title: Mapped[str] = mapped_column(String(300))
    description: Mapped[str] = mapped_column(Text)
    related_story_id: Mapped[str | None] = mapped_column(String(40), nullable=True)
    related_requirement_id: Mapped[str | None] = mapped_column(String(40), nullable=True)
    related_artifact_ids: Mapped[list[str]] = mapped_column(JSON, default=list)
    priority: Mapped[str] = mapped_column(String(20))
    story_points: Mapped[int] = mapped_column(Integer)
    suggested_role: Mapped[str] = mapped_column(String(60))
    acceptance_criteria: Mapped[list[str]] = mapped_column(JSON, default=list)
    sprint_id: Mapped[str] = mapped_column(String(40))
    status: Mapped[str] = mapped_column(String(30), default="TODO")
    grounding: Mapped[str] = mapped_column(String(20))
    rationale: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_references: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    execution_index: Mapped[int] = mapped_column(Integer, default=0)

    plan: Mapped[PMPlan] = relationship(back_populates="tasks")


class PMTaskDependency(Base):
    __tablename__ = "pm_task_dependencies"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), index=True)
    plan_id: Mapped[int] = mapped_column(ForeignKey("pm_plans.id"), index=True)
    task_id: Mapped[str] = mapped_column(String(40))
    depends_on_task_id: Mapped[str | None] = mapped_column(String(40), nullable=True)
    dependency_type: Mapped[str] = mapped_column(String(30))
    description: Mapped[str] = mapped_column(Text)
    is_blocking: Mapped[bool] = mapped_column(Boolean, default=False)

    plan: Mapped[PMPlan] = relationship(back_populates="task_dependencies")


class PMSprint(Base):
    __tablename__ = "pm_sprints"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), index=True)
    plan_id: Mapped[int] = mapped_column(ForeignKey("pm_plans.id"), index=True)
    sprint_id: Mapped[str] = mapped_column(String(40))
    sequence: Mapped[int] = mapped_column(Integer)
    name: Mapped[str] = mapped_column(String(200))
    goal: Mapped[str] = mapped_column(Text)
    start_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    end_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    capacity_notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    plan: Mapped[PMPlan] = relationship(back_populates="sprints")


class PMMilestone(Base):
    __tablename__ = "pm_milestones"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), index=True)
    plan_id: Mapped[int] = mapped_column(ForeignKey("pm_plans.id"), index=True)
    milestone_id: Mapped[str] = mapped_column(String(40))
    sequence: Mapped[int] = mapped_column(Integer)
    title: Mapped[str] = mapped_column(String(300))
    description: Mapped[str] = mapped_column(Text)
    task_ids: Mapped[list[str]] = mapped_column(JSON, default=list)
    target_sprint_id: Mapped[str | None] = mapped_column(String(40), nullable=True)

    plan: Mapped[PMPlan] = relationship(back_populates="milestones")


class PMRisk(Base):
    __tablename__ = "pm_risks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), index=True)
    plan_id: Mapped[int] = mapped_column(ForeignKey("pm_plans.id"), index=True)
    risk_id: Mapped[str] = mapped_column(String(40))
    title: Mapped[str] = mapped_column(String(300))
    description: Mapped[str] = mapped_column(Text)
    impact: Mapped[str] = mapped_column(String(20))
    likelihood: Mapped[str] = mapped_column(String(20))
    mitigation: Mapped[str] = mapped_column(Text)
    related_tasks: Mapped[list[str]] = mapped_column(JSON, default=list)

    plan: Mapped[PMPlan] = relationship(back_populates="risks")


# --- System Architect AI ----------------------------------------------------
# One row per project holding the whole validated design. The HLD and LLD are deeply
# nested documents that are always read and replaced as a unit, so they are stored as
# JSON (like the lists on the PM tables) instead of a dozen child tables. Regenerating
# replaces the row in a single transaction; a failed run leaves the previous design.


class ArchDesign(Base):
    __tablename__ = "arch_designs"
    __table_args__ = (UniqueConstraint("project_id", name="uq_arch_designs_project"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), index=True)
    agent_run_id: Mapped[int | None] = mapped_column(ForeignKey("agent_runs.id"), nullable=True)
    requirements_run_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    plan_run_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    hld: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    lld: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    diagram: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    traceability: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    open_items: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    warnings: Mapped[list[str]] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    project: Mapped[Project] = relationship(back_populates="arch_designs")


class UserSettings(Base):
    """Per-user preferences. A separate table so the existing ``users`` table is untouched.

    Holds no secrets: just the theme, notification toggles and the time the password
    was last changed through Settings.
    """

    __tablename__ = "user_settings"

    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    theme: Mapped[str] = mapped_column(String(10), default="system")
    notifications: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    password_changed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
