from fastapi import APIRouter, Depends, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database import get_db
from ..dependencies import get_current_user, get_project_or_404
from ..models import Project, User
from ..schemas import ProjectCreate, ProjectResponse

router = APIRouter(prefix="/api/projects", tags=["projects"])


@router.post("", response_model=ProjectResponse, status_code=status.HTTP_201_CREATED)
def create_project(
    payload: ProjectCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    project = Project(owner_id=user.id, **payload.model_dump())
    db.add(project)
    db.commit()
    db.refresh(project)
    return project


@router.get("", response_model=list[ProjectResponse])
def list_projects(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return db.scalars(select(Project).where(Project.owner_id == user.id).order_by(Project.created_at.desc())).all()


@router.get("/{project_id}", response_model=ProjectResponse)
def get_project(project_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return get_project_or_404(project_id, user, db)