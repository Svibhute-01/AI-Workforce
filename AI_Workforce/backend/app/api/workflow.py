from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..config import get_settings
from ..database import get_db
from ..dependencies import get_current_user, get_project_or_404
from ..llm.base import LLMProvider
from ..models import User
from ..rag.vector_store import ProjectVectorStore
from ..schemas_workflow import WorkflowRunResponse
from ..workflow.service import WorkflowFailure, WorkflowService
from .project_manager import get_llm_provider

router = APIRouter(prefix="/api/projects/{project_id}", tags=["workflow"])


def get_vector_store() -> ProjectVectorStore:
    """Dependency so tests can substitute the vector store."""
    return ProjectVectorStore(get_settings())


@router.post("/workflow/run", response_model=WorkflowRunResponse)
def run_workflow(
    project_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    provider: LLMProvider = Depends(get_llm_provider),
    vector_store: ProjectVectorStore = Depends(get_vector_store),
):
    """Run Requirements Analyst -> validation -> Project Manager -> validation through LangGraph."""
    project = get_project_or_404(project_id, user, db)
    try:
        state = WorkflowService(db, provider, vector_store).run(project)
    except WorkflowFailure as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc
    return WorkflowRunResponse.from_state(state)
