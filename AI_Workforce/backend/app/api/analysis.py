from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..agents.requirements_agent import run_requirements_analysis
from ..config import get_settings
from ..database import get_db
from ..dependencies import get_current_user, get_project_or_404
from ..llm.gemini_provider import GeminiProvider
from ..models import (
    AcceptanceCriteria,
    AgentRun,
    Ambiguity,
    Constraint,
    Dependency,
    Document,
    NonFunctionalRequirement,
    Project,
    Requirement,
    Risk,
    User,
    UserStory,
)
from ..rag.vector_store import ProjectVectorStore
from ..schemas import (
    AcceptanceCriteriaResponse,
    AgentRunResponse,
    AnalysisResponse,
    AmbiguityResponse,
    ConstraintResponse,
    DependencyResponse,
    NonFunctionalRequirementResponse,
    ProjectSummary,
    RagQuery,
    RagResponse,
    RagSource,
    RequirementResponse,
    RiskResponse,
    SourceReference,
    UserStoryResponse,
)

router = APIRouter(prefix="/api/projects/{project_id}", tags=["requirements-analysis"])


@router.post("/analyze", response_model=AnalysisResponse)
def analyze(
    project_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    project = get_project_or_404(project_id, user, db)
    has_completed_document = db.scalar(
        select(Document.id).where(Document.project_id == project.id, Document.processing_status == "COMPLETED")
    )
    if not has_completed_document:
        raise HTTPException(status_code=409, detail="Upload and finish processing an SRS before analysis")
    try:
        provider = GeminiProvider(get_settings())
        run_requirements_analysis(db, project, provider, ProjectVectorStore(get_settings()))
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return _build_analysis(db, project)


@router.get("/requirements", response_model=list[RequirementResponse])
def requirements(project_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    project = get_project_or_404(project_id, user, db)
    return db.scalars(select(Requirement).where(Requirement.project_id == project.id).order_by(Requirement.id)).all()


@router.get("/user-stories", response_model=list[UserStoryResponse])
def user_stories(project_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    project = get_project_or_404(project_id, user, db)
    return db.scalars(select(UserStory).where(UserStory.project_id == project.id).order_by(UserStory.id)).all()


@router.get("/acceptance-criteria", response_model=list[AcceptanceCriteriaResponse])
def acceptance_criteria(project_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    project = get_project_or_404(project_id, user, db)
    return db.scalars(select(AcceptanceCriteria).where(AcceptanceCriteria.project_id == project.id).order_by(AcceptanceCriteria.id)).all()


@router.get("/agent-runs", response_model=list[AgentRunResponse])
def agent_runs(project_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    project = get_project_or_404(project_id, user, db)
    return db.scalars(select(AgentRun).where(AgentRun.project_id == project.id).order_by(AgentRun.started_at.desc())).all()


@router.get("/analysis", response_model=AnalysisResponse)
def analysis(project_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    project = get_project_or_404(project_id, user, db)
    return _build_analysis(db, project)


@router.post("/rag/query", response_model=RagResponse)
def rag_query(
    project_id: int,
    payload: RagQuery,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    project = get_project_or_404(project_id, user, db)
    settings = get_settings()
    try:
        provider = GeminiProvider(settings)
        query_embedding = provider.embed_texts([payload.query])[0]
        chunks = ProjectVectorStore(settings).query(project.id, query_embedding, limit=8)
        if not chunks:
            raise HTTPException(status_code=404, detail="No processed SRS content is available for this project")
        contexts = [
            {
                "text": chunk.text,
                "filename": chunk.filename,
                "page": chunk.page,
                "source": chunk.source,
                "document_id": chunk.document_id,
            }
            for chunk in chunks
        ]
        answer = provider.answer_question(payload.query, contexts)
        return RagResponse(
            answer=answer,
            sources=[
                RagSource(document=chunk.filename, page=chunk.page, source=chunk.source)
                for chunk in chunks
            ],
        )
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


def _build_analysis(db: Session, project: Project) -> AnalysisResponse:
    latest_run = db.scalar(
        select(AgentRun)
        .where(
            AgentRun.project_id == project.id,
            AgentRun.agent_name == "Requirements Analyst AI",
            AgentRun.status == "COMPLETED",
        )
        .order_by(AgentRun.completed_at.desc())
    )
    summary_data = (latest_run.output_summary or {}).get("project_summary", {}) if latest_run else {}
    if not summary_data:
        summary_data = {"summary": "No completed requirements analysis is available yet."}

    return AnalysisResponse(
        project_summary=ProjectSummary.model_validate(summary_data),
        functional_requirements=[
            RequirementResponse.model_validate(item) for item in db.scalars(
                select(Requirement).where(Requirement.project_id == project.id).order_by(Requirement.id)
            ).all()
        ],
        non_functional_requirements=[
            NonFunctionalRequirementResponse.model_validate(item) for item in db.scalars(
                select(NonFunctionalRequirement).where(NonFunctionalRequirement.project_id == project.id).order_by(NonFunctionalRequirement.id)
            ).all()
        ],
        user_stories=[
            UserStoryResponse.model_validate(item) for item in db.scalars(
                select(UserStory).where(UserStory.project_id == project.id).order_by(UserStory.id)
            ).all()
        ],
        acceptance_criteria=[
            AcceptanceCriteriaResponse.model_validate(item) for item in db.scalars(
                select(AcceptanceCriteria).where(AcceptanceCriteria.project_id == project.id).order_by(AcceptanceCriteria.id)
            ).all()
        ],
        dependencies=[
            DependencyResponse.model_validate(item) for item in db.scalars(
                select(Dependency).where(Dependency.project_id == project.id).order_by(Dependency.id)
            ).all()
        ],
        ambiguities=[
            AmbiguityResponse.model_validate(item) for item in db.scalars(
                select(Ambiguity).where(Ambiguity.project_id == project.id).order_by(Ambiguity.id)
            ).all()
        ],
        constraints=[
            ConstraintResponse.model_validate(item) for item in db.scalars(
                select(Constraint).where(Constraint.project_id == project.id).order_by(Constraint.id)
            ).all()
        ],
        risks=[
            RiskResponse.model_validate(item) for item in db.scalars(
                select(Risk).where(Risk.project_id == project.id).order_by(Risk.id)
            ).all()
        ],
        source_references=_latest_sources(latest_run),
        latest_agent_run=AgentRunResponse.model_validate(latest_run) if latest_run else None,
    )


def _latest_sources(run: AgentRun | None) -> list[SourceReference]:
    if not run or not run.output_summary:
        return []
    return [SourceReference.model_validate(item) for item in run.output_summary.get("source_references", [])]