import logging

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import get_settings
from ..database import get_db
from ..dependencies import get_current_user, get_project_or_404
from ..llm.gemini_provider import GeminiProvider
from ..models import Document, User
from ..rag.service import process_document, save_upload
from ..schemas import DocumentResponse

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/projects/{project_id}/documents", tags=["documents"])


@router.get("", response_model=list[DocumentResponse])
def list_documents(project_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    get_project_or_404(project_id, user, db)
    return db.scalars(select(Document).where(Document.project_id == project_id).order_by(Document.upload_time.desc())).all()


@router.post("", response_model=DocumentResponse, status_code=status.HTTP_201_CREATED)
async def upload_document(
    project_id: int,
    file: UploadFile = File(...),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    project = get_project_or_404(project_id, user, db)
    settings = get_settings()
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=415, detail="Only PDF SRS files are supported")
    content = await file.read()
    if len(content) > settings.max_upload_size_bytes:
        raise HTTPException(
            status_code=413,
            detail=f"File exceeds the {settings.max_upload_size_bytes // (1024 * 1024)} MB upload limit",
        )
    if not content.startswith(b"%PDF"):
        raise HTTPException(status_code=415, detail="The uploaded file is not a valid PDF")

    document = Document(
        project_id=project.id,
        filename=file.filename,
        file_type=file.content_type or "application/pdf",
        file_size=len(content),
        storage_path="",
        processing_status="UPLOADED",
    )
    db.add(document)
    db.commit()
    db.refresh(document)
    document.storage_path = save_upload(settings, file.filename, content)
    db.commit()

    try:
        provider = GeminiProvider(settings)
        process_document(db, settings, document, content, provider)
    except Exception as exc:
        logger.exception("SRS upload processing failed")
        document = db.get(Document, document.id)
        if document:
            document.error_message = str(exc)[:2000]
            db.commit()
        if isinstance(exc, ValueError) and "PDF" in str(exc):
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    return db.get(Document, document.id)