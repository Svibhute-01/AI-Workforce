from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..agents.pm_context import MissingRequirementsError, latest_requirements_run
from ..agents.project_manager_agent import (
    PlanValidationError,
    RunInProgressError,
    run_project_manager,
)
from ..config import get_settings
from ..database import get_db
from ..dependencies import get_current_user, get_project_or_404
from ..llm.base import LLMProvider
from ..llm.gemini_provider import GeminiProvider, ProviderConfigurationError
from ..models import (
    AgentRun,
    PMEpic,
    PMMilestone,
    PMPlan,
    PMRisk,
    PMSprint,
    PMTask,
    PMTaskDependency,
    Project,
    Requirement,
    User,
    UserStory,
)
from ..schemas import AgentRunResponse
from ..schemas_pm import (
    PM_AGENT_NAME,
    PMDependencyResponse,
    PMEpicResponse,
    PMMilestoneResponse,
    PMPlanInfo,
    PMPlanResponse,
    PMRiskResponse,
    PMSprintResponse,
    PMTaskResponse,
)

router = APIRouter(prefix="/api/projects/{project_id}", tags=["project-manager"])


def get_llm_provider() -> LLMProvider:
    """Dependency so tests can substitute a deterministic provider."""
    try:
        return GeminiProvider(get_settings())
    except ProviderConfigurationError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.post("/project-manager/run", response_model=PMPlanResponse)
def run_plan(
    project_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    provider: LLMProvider = Depends(get_llm_provider),
):
    project = get_project_or_404(project_id, user, db)
    try:
        run_project_manager(db, project, provider)
    except MissingRequirementsError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except RunInProgressError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except PlanValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return _build_plan_response(db, project)


@router.get("/project-manager", response_model=PMPlanResponse)
def get_plan(project_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    project = get_project_or_404(project_id, user, db)
    return _build_plan_response(db, project)


@router.get("/tasks", response_model=list[PMTaskResponse])
def list_tasks(project_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return _build_plan_response(db, get_project_or_404(project_id, user, db)).tasks


@router.get("/sprints", response_model=list[PMSprintResponse])
def list_sprints(project_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return _build_plan_response(db, get_project_or_404(project_id, user, db)).sprints


@router.get("/milestones", response_model=list[PMMilestoneResponse])
def list_milestones(project_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return _build_plan_response(db, get_project_or_404(project_id, user, db)).milestones


@router.get("/risks", response_model=list[PMRiskResponse])
def list_risks(project_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return _build_plan_response(db, get_project_or_404(project_id, user, db)).risks


@router.get("/dependencies", response_model=list[PMDependencyResponse])
def list_dependencies(project_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return _build_plan_response(db, get_project_or_404(project_id, user, db)).dependencies


def _build_plan_response(db: Session, project: Project) -> PMPlanResponse:
    latest_run = db.scalar(
        select(AgentRun)
        .where(AgentRun.project_id == project.id, AgentRun.agent_name == PM_AGENT_NAME)
        .order_by(AgentRun.started_at.desc(), AgentRun.id.desc())
    )
    plan = db.scalar(select(PMPlan).where(PMPlan.project_id == project.id))
    run_response = AgentRunResponse.model_validate(latest_run) if latest_run else None
    status = latest_run.status if latest_run else "NOT_GENERATED"
    if plan is None:
        return PMPlanResponse(status=status, latest_agent_run=run_response)

    def rows(model, *order):
        return db.scalars(
            select(model).where(model.project_id == project.id, model.plan_id == plan.id).order_by(*order)
        ).all()

    tasks = rows(PMTask, PMTask.execution_index, PMTask.id)
    dependencies = rows(PMTaskDependency, PMTaskDependency.id)
    sprints = rows(PMSprint, PMSprint.sequence)
    epics = rows(PMEpic, PMEpic.id)

    depends_on: dict[str, list[str]] = {}
    for dep in dependencies:
        if dep.depends_on_task_id:
            depends_on.setdefault(dep.task_id, []).append(dep.depends_on_task_id)

    requirement_titles = {
        f"REQ-{r.id}": r.title
        for r in db.scalars(select(Requirement).where(Requirement.project_id == project.id)).all()
    }
    story_titles = {
        f"US-{s.id}": s.title
        for s in db.scalars(select(UserStory).where(UserStory.project_id == project.id)).all()
    }

    task_responses = []
    for task in tasks:
        response = PMTaskResponse.model_validate(task)
        response.dependencies = depends_on.get(task.task_id, [])
        response.related_requirement_title = requirement_titles.get(task.related_requirement_id or "")
        response.related_story_title = story_titles.get(task.related_story_id or "")
        task_responses.append(response)

    sprint_responses = []
    for sprint in sprints:
        response = PMSprintResponse.model_validate(sprint)
        in_sprint = [t for t in tasks if t.sprint_id == sprint.sprint_id]
        response.tasks = [t.task_id for t in in_sprint]
        response.total_story_points = sum(t.story_points for t in in_sprint)
        sprint_responses.append(response)

    epic_responses = []
    for epic in epics:
        response = PMEpicResponse.model_validate(epic)
        response.task_ids = [t.task_id for t in tasks if t.epic_id == epic.epic_id]
        epic_responses.append(response)

    dependency_responses = [PMDependencyResponse.model_validate(d) for d in dependencies]
    requirements_run = latest_requirements_run(db, project.id)
    info = PMPlanInfo(
        id=plan.id,
        execution_summary=plan.execution_summary,
        definition_of_done=plan.definition_of_done or [],
        assumptions=plan.assumptions or [],
        execution_order=plan.execution_order or [],
        warnings=plan.warnings or [],
        created_at=plan.created_at,
        requirements_changed=bool(requirements_run and requirements_run.id != plan.requirements_run_id),
    )
    return PMPlanResponse(
        status=status,
        plan=info,
        epics=epic_responses,
        tasks=task_responses,
        sprints=sprint_responses,
        dependencies=dependency_responses,
        blocking_dependencies=[d for d in dependency_responses if d.is_blocking],
        milestones=[PMMilestoneResponse.model_validate(m) for m in rows(PMMilestone, PMMilestone.sequence)],
        risks=[PMRiskResponse.model_validate(r) for r in rows(PMRisk, PMRisk.id)],
        latest_agent_run=run_response,
    )
