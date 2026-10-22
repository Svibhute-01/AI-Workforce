from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..agents.architect_validation import build_detailed_diagram, design_counts
from ..agents.pm_context import latest_requirements_run
from ..database import get_db
from ..dependencies import get_current_user, get_project_or_404
from ..llm.base import LLMProvider
from ..models import AgentRun, ArchDesign, PMPlan, Project, User
from ..schemas import AgentRunResponse
from ..schemas_architect import (
    ARCHITECT_AGENT_NAME,
    ArchitectureDiagram,
    ArchitectureInfo,
    ArchitectureResponse,
    ArchOpenItem,
    HighLevelDesign,
    LowLevelDesign,
    TraceabilityEntry,
)
from ..workflow.service import WorkflowFailure, WorkflowService
from .project_manager import get_llm_provider

router = APIRouter(prefix="/api/projects/{project_id}", tags=["system-architect"])


@router.post("/architect/run", response_model=ArchitectureResponse)
def run_architecture(
    project_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    provider: LLMProvider = Depends(get_llm_provider),
):
    """Generate the HLD and LLD from the saved requirements and project plan.

    Runs through the same LangGraph workflow as the full pipeline, limited to the
    architecture stage: ``architect_node`` then the ``validate_architecture`` gate.
    """
    project = get_project_or_404(project_id, user, db)
    try:
        WorkflowService(db, provider).run(project, only=["architecture"])
    except WorkflowFailure as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc
    return _build_architecture_response(db, project)


@router.get("/architecture", response_model=ArchitectureResponse)
def get_architecture(project_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    project = get_project_or_404(project_id, user, db)
    return _build_architecture_response(db, project)


def _build_architecture_response(db: Session, project: Project) -> ArchitectureResponse:
    latest_run = db.scalar(
        select(AgentRun)
        .where(AgentRun.project_id == project.id, AgentRun.agent_name == ARCHITECT_AGENT_NAME)
        .order_by(AgentRun.started_at.desc(), AgentRun.id.desc())
    )
    design = db.scalar(select(ArchDesign).where(ArchDesign.project_id == project.id))
    run_response = AgentRunResponse.model_validate(latest_run) if latest_run else None
    status = latest_run.status if latest_run else "NOT_GENERATED"
    if design is None:
        return ArchitectureResponse(status=status, latest_agent_run=run_response)

    hld = HighLevelDesign.model_validate(design.hld)
    lld = LowLevelDesign.model_validate(design.lld)
    requirements_run = latest_requirements_run(db, project.id)
    plan = db.scalar(select(PMPlan).where(PMPlan.project_id == project.id))
    info = ArchitectureInfo(
        id=design.id,
        overview=hld.overview,
        warnings=design.warnings or [],
        counts=design_counts(hld, lld),
        created_at=design.created_at,
        requirements_changed=bool(requirements_run and requirements_run.id != design.requirements_run_id),
        plan_changed=bool(plan and plan.agent_run_id != design.plan_run_id),
    )
    diagram = ArchitectureDiagram.model_validate(design.diagram or {})
    try:
        diagram.detailed = build_detailed_diagram(hld, lld)
    except Exception:  # noqa: BLE001 - a drawing aid must never break serving the design itself
        diagram.detailed = None
    return ArchitectureResponse(
        status=status,
        architecture=info,
        hld=hld,
        lld=lld,
        diagram=diagram,
        traceability=[TraceabilityEntry.model_validate(entry) for entry in design.traceability or []],
        open_items=[ArchOpenItem.model_validate(item) for item in design.open_items or []],
        latest_agent_run=run_response,
    )
