"""Builds the Project Manager's input from the saved Requirements Analyst output.

The Project Manager never reads the SRS. Its only input is what the Requirements
Analyst persisted for *this project*. Every query below is filtered by
``project_id``, so another project's requirements can never reach the prompt, and
the set of valid IDs built here is what the plan validator later checks the LLM's
references against.
"""

from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import (
    AcceptanceCriteria,
    AgentRun,
    Ambiguity,
    Constraint,
    Dependency,
    NonFunctionalRequirement,
    Project,
    Requirement,
    Risk,
    UserStory,
)

REQUIREMENTS_AGENT_NAME = "Requirements Analyst AI"

# ID prefix per artifact kind. IDs are "<prefix>-<database id>", e.g. REQ-12.
REQ, STORY, AC, NFR, CON, DEP, AMB, RISK = "REQ", "US", "AC", "NFR", "CON", "DEP", "AMB", "RISK"


class MissingRequirementsError(RuntimeError):
    """The project has no usable Requirements Analyst output."""


@dataclass
class RequirementsContext:
    requirements_run_id: int
    payload: dict
    source_refs: dict[str, list[dict]] = field(default_factory=dict)
    titles: dict[str, str] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)

    def ids_of(self, *prefixes: str) -> set[str]:
        return {key for key in self.source_refs if key.split("-", 1)[0] in prefixes}

    @property
    def requirement_ids(self) -> set[str]:
        return self.ids_of(REQ)

    @property
    def story_ids(self) -> set[str]:
        return self.ids_of(STORY)

    @property
    def artifact_ids(self) -> set[str]:
        """Every id a task may cite as its grounding."""
        return set(self.source_refs)


def latest_requirements_run(db: Session, project_id: int) -> AgentRun | None:
    return db.scalar(
        select(AgentRun)
        .where(
            AgentRun.project_id == project_id,
            AgentRun.agent_name == REQUIREMENTS_AGENT_NAME,
            AgentRun.status == "COMPLETED",
        )
        .order_by(AgentRun.completed_at.desc(), AgentRun.id.desc())
    )


def build_requirements_context(db: Session, project: Project) -> RequirementsContext:
    """Load and validate the Requirements Analyst output for one project."""
    run = latest_requirements_run(db, project.id)
    if run is None:
        raise MissingRequirementsError(
            "No completed Requirements Analyst output exists for this project. "
            "Run the Requirements Analyst first."
        )

    def rows(model):
        return db.scalars(select(model).where(model.project_id == project.id).order_by(model.id)).all()

    requirements = rows(Requirement)
    if not requirements:
        raise MissingRequirementsError(
            "The Requirements Analyst run produced no functional requirements, so there is nothing to plan."
        )
    nfrs = rows(NonFunctionalRequirement)
    stories = rows(UserStory)
    criteria = rows(AcceptanceCriteria)
    dependencies = rows(Dependency)
    constraints = rows(Constraint)
    ambiguities = rows(Ambiguity)
    risks = rows(Risk)

    refs: dict[str, list[dict]] = {}
    titles: dict[str, str] = {}

    def register(key: str, source_references, title: str) -> str:
        refs[key] = list(source_references or [])
        titles[key] = title
        return key

    payload = {
        "project_summary": (run.output_summary or {}).get("project_summary", {}),
        "functional_requirements": [
            {
                "id": register(f"{REQ}-{r.id}", r.source_references, r.title),
                "title": r.title,
                "description": r.description,
                "priority": r.priority,
                "priority_basis": r.priority_basis,
            }
            for r in requirements
        ],
        "non_functional_requirements": [
            {
                "id": register(f"{NFR}-{n.id}", n.source_references, n.category),
                "category": n.category,
                "description": n.description,
                "priority": n.priority,
            }
            for n in nfrs
        ],
        "user_stories": [
            {
                "id": register(f"{STORY}-{s.id}", s.source_references, s.title),
                "requirement_id": f"{REQ}-{s.requirement_id}" if s.requirement_id else None,
                "title": s.title,
                "story": s.story,
                "priority": s.priority,
            }
            for s in stories
        ],
        "acceptance_criteria": [
            {
                "id": register(f"{AC}-{a.id}", a.source_references, a.description[:80]),
                "user_story_id": f"{STORY}-{a.user_story_id}" if a.user_story_id else None,
                "description": a.description,
            }
            for a in criteria
        ],
        "dependencies": [
            {
                "id": register(f"{DEP}-{d.id}", d.source_references, d.description[:80]),
                "description": d.description,
                "related_requirement": d.related_requirement,
            }
            for d in dependencies
        ],
        "constraints": [
            {
                "id": register(f"{CON}-{c.id}", c.source_references, c.description[:80]),
                "description": c.description,
            }
            for c in constraints
        ],
        "ambiguities": [
            {
                "id": register(f"{AMB}-{a.id}", a.source_references, a.description[:80]),
                "description": a.description,
                "impact": a.impact,
                "related_requirement": a.related_requirement,
            }
            for a in ambiguities
        ],
        "risks": [
            {
                "id": register(f"{RISK}-{r.id}", r.source_references, r.description[:80]),
                "description": r.description,
                "severity": r.severity,
                "related_requirement": r.related_requirement,
            }
            for r in risks
        ],
    }

    warnings: list[str] = []
    if not stories:
        warnings.append("The Requirements Analyst produced no user stories; tasks are derived from requirements only.")
    if not criteria:
        warnings.append("The Requirements Analyst produced no acceptance criteria.")

    return RequirementsContext(
        requirements_run_id=run.id,
        payload=payload,
        source_refs=refs,
        titles=titles,
        warnings=warnings,
    )
