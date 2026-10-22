import logging
from pathlib import Path
from uuid import uuid4

from sqlalchemy.orm import Session

from ..config import Settings
from ..llm.base import LLMProvider
from ..models import Document, DocumentChunk
from .document_processor import chunk_pages, extract_pdf_pages
from .vector_store import ProjectVectorStore

logger = logging.getLogger(__name__)


def process_document(
    db: Session,
    settings: Settings,
    document: Document,
    content: bytes,
    provider: LLMProvider,
) -> None:
    store = ProjectVectorStore(settings)
    document.processing_status = "PROCESSING"
    db.commit()
    try:
        pages = extract_pdf_pages(content)
        chunks = chunk_pages(pages, document.filename)
        embeddings = provider.embed_texts([chunk.text for chunk in chunks])
        if len(embeddings) != len(chunks):
            raise ValueError("Embedding provider returned an unexpected number of vectors.")

        store.add_chunks(document.project_id, document.id, chunks, embeddings)
        db.query(DocumentChunk).filter(DocumentChunk.document_id == document.id).delete()
        db.add_all(
            [
                DocumentChunk(
                    document_id=document.id,
                    project_id=document.project_id,
                    chunk_index=chunk.index,
                    page=chunk.page,
                    text=chunk.text,
                    metadata_json={
                        "project_id": document.project_id,
                        "document_id": document.id,
                        "page": chunk.page,
                        "filename": chunk.filename,
                        "source": chunk.source,
                    },
                )
                for chunk in chunks
            ]
        )
        document.page_count = len(pages)
        document.processing_status = "COMPLETED"
        document.error_message = None
        db.commit()
    except Exception as exc:
        db.rollback()
        document = db.get(Document, document.id)
        if document:
            document.processing_status = "FAILED"
            document.error_message = str(exc)[:2000]
            db.commit()
        store.delete_document(document.project_id if document else 0, document.id if document else 0)
        logger.exception("Document processing failed for document %s", document.id if document else "unknown")
        raise


def save_upload(settings: Settings, filename: str, content: bytes) -> str:
    settings.ensure_directories()
    safe_name = Path(filename).name.replace(" ", "_")
    path = Path(settings.upload_directory) / f"{uuid4().hex}-{safe_name}"
    path.write_bytes(content)
    return str(path)