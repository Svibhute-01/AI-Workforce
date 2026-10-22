from datetime import datetime, timezone

from sqlalchemy import delete, select
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
from ..schemas import RequirementsAnalysis
from ..llm.base import LLMProvider
from ..rag.vector_store import ProjectVectorStore


class RequirementsAgentError(RuntimeError):
    pass


def run_requirements_analysis(
    db: Session,
    project: Project,
    provider: LLMProvider,
    vector_store: ProjectVectorStore,
) -> tuple[AgentRun, RequirementsAnalysis]:
    agent_run = AgentRun(
        project_id=project.id,
        agent_name="Requirements Analyst AI",
        status="PROCESSING",
        input_summary={"project_name": project.name},
    )
    db.add(agent_run)
    db.commit()

    try:
        contexts = _retrieve_context(provider, vector_store, project.id)
        if not contexts:
            raise RequirementsAgentError("No processed SRS chunks are available for this project.")
        analysis = provider.generate_analysis(project.name, project.description or "", contexts)
        analysis = _keep_only_real_sources(analysis, contexts)
        _replace_saved_analysis(db, project, analysis)
        agent_run.status = "COMPLETED"
        agent_run.completed_at = datetime.now(timezone.utc)
        agent_run.output_summary = {
            "documents_analyzed": len({item["document_id"] for item in contexts}),
            "chunks_retrieved": len(contexts),
            "requirements_generated": len(analysis.functional_requirements),
            "user_stories_generated": len(analysis.user_stories),
            "ambiguities_identified": len(analysis.ambiguities),
            "project_summary": analysis.project_summary.model_dump(),
            "source_references": [ref.model_dump() for ref in analysis.source_references],
        }
        db.commit()
        return agent_run, analysis
    except Exception as exc:
        db.rollback()
        failed_run = db.get(AgentRun, agent_run.id)
        if failed_run:
            failed_run.status = "FAILED"
            failed_run.completed_at = datetime.now(timezone.utc)
            failed_run.error = str(exc)[:4000]
            db.commit()
        raise


def _retrieve_context(provider: LLMProvider, vector_store: ProjectVectorStore, project_id: int) -> list[dict]:
    embedding = provider.embed_texts(
        ["Analyze all explicit functional and non-functional requirements in this project's SRS."]
    )[0]
    chunks = vector_store.query(project_id, embedding, limit=20)
    return [
        {
            "text": chunk.text,
            "filename": chunk.filename,
            "page": chunk.page,
            "source": chunk.source,
            "document_id": chunk.document_id,
        }
        for chunk in chunks
    ]


def _keep_only_real_sources(analysis: RequirementsAnalysis, contexts: list[dict]) -> RequirementsAnalysis:
    valid_by_document_page = {
        (item["filename"], item["page"]): item["source"]
        for item in contexts
    }
    contexts_by_page: dict[int, list[dict]] = {}
    for item in contexts:
        contexts_by_page.setdefault(item["page"], []).append(item)

    def clean(refs):
        cleaned = []
        seen = set()
        for ref in refs:
            actual_document_page = (ref.document, ref.page)
            actual_source = valid_by_document_page.get(actual_document_page)
            if not actual_source:
                page_matches = contexts_by_page.get(ref.page, [])
                if len(page_matches) == 1:
                    actual_document_page = (page_matches[0]["filename"], ref.page)
                    actual_source = page_matches[0]["source"]
            if actual_source and actual_document_page not in seen:
                cleaned.append(
                    ref.model_copy(
                        update={
                            "document": actual_document_page[0],
                            "source": actual_source,
                        }
                    )
                )
                seen.add(actual_document_page)
        return cleaned

    analysis.source_references = clean(analysis.source_references)
    for item in analysis.functional_requirements:
        item.source_references = clean(item.source_references)
    for item in analysis.non_functional_requirements:
        item.source_references = clean(item.source_references)
    for item in analysis.user_stories:
        item.source_references = clean(item.source_references)
    for item in analysis.acceptance_criteria:
        item.source_references = clean(item.source_references)
    for item in analysis.dependencies:
        item.source_references = clean(item.source_references)
    for item in analysis.ambiguities:
        item.source_references = clean(item.source_references)
    for item in analysis.constraints:
        item.source_references = clean(item.source_references)
    for item in analysis.risks:
        item.source_references = clean(item.source_references)
    return analysis


def _replace_saved_analysis(db: Session, project: Project, analysis: RequirementsAnalysis) -> None:
    for model in (
        AcceptanceCriteria,
        UserStory,
        Requirement,
        NonFunctionalRequirement,
        Dependency,
        Ambiguity,
        Constraint,
        Risk,
    ):
        db.execute(delete(model).where(model.project_id == project.id))
    db.flush()

    requirements = []
    for item in analysis.functional_requirements:
        requirement = Requirement(
            project_id=project.id,
            title=item.title,
            description=item.description,
            priority=item.priority,
            priority_basis=item.priority_basis,
            source_references=[ref.model_dump() for ref in item.source_references],
        )
        db.add(requirement)
        requirements.append(requirement)
    db.flush()

    requirement_by_title = {item.title.casefold(): item for item in requirements}
    stories = []
    for item in analysis.user_stories:
        requirement = requirement_by_title.get((item.requirement_title or "").casefold())
        story = UserStory(
            project_id=project.id,
            requirement_id=requirement.id if requirement else None,
            title=item.title,
            story=item.story,
            priority=item.priority,
            source_references=[ref.model_dump() for ref in item.source_references],
        )
        db.add(story)
        stories.append(story)
    db.flush()

    story_by_title = {item.title.casefold(): item for item in stories}
    for item in analysis.acceptance_criteria:
        story = story_by_title.get((item.user_story_title or "").casefold())
        db.add(
            AcceptanceCriteria(
                project_id=project.id,
                user_story_id=story.id if story else None,
                description=item.description,
                source_references=[ref.model_dump() for ref in item.source_references],
            )
        )
    for item in analysis.non_functional_requirements:
        db.add(
            NonFunctionalRequirement(
                project_id=project.id,
                category=item.category,
                description=item.description,
                priority=item.priority,
                source_references=[ref.model_dump() for ref in item.source_references],
            )
        )
    for item in analysis.dependencies:
        db.add(
            Dependency(
                project_id=project.id,
                description=item.description,
                related_requirement=item.related_requirement,
                source_references=[ref.model_dump() for ref in item.source_references],
            )
        )
    for item in analysis.ambiguities:
        db.add(
            Ambiguity(
                project_id=project.id,
                description=item.description,
                impact=item.impact,
                related_requirement=item.related_requirement,
                source_references=[ref.model_dump() for ref in item.source_references],
            )
        )
    for item in analysis.constraints:
        db.add(
            Constraint(
                project_id=project.id,
                description=item.description,
                source_references=[ref.model_dump() for ref in item.source_references],
            )
        )
    for item in analysis.risks:
        db.add(
            Risk(
                project_id=project.id,
                description=item.description,
                severity=item.severity,
                related_requirement=item.related_requirement,
                source_references=[ref.model_dump() for ref in item.source_references],
            )
        )