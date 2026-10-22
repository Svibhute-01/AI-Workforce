import logging
import os
from dataclasses import dataclass

# Chroma's anonymous telemetry is not needed by this application and can emit
# incompatible client warnings in restricted environments.
os.environ.setdefault("ANONYMIZED_TELEMETRY", "False")
import chromadb
from chromadb.config import Settings as ChromaSettings

from ..config import Settings

logger = logging.getLogger(__name__)


@dataclass
class RetrievedChunk:
    text: str
    filename: str
    page: int
    source: str
    document_id: int


class ProjectVectorStore:
    def __init__(self, settings: Settings):
        settings.ensure_directories()
        self._client = chromadb.PersistentClient(
            path=settings.chroma_persist_directory,
            settings=ChromaSettings(anonymized_telemetry=False),
        )

    def _collection(self, project_id: int):
        return self._client.get_or_create_collection(
            name=f"project_{project_id}",
            metadata={"hnsw:space": "cosine"},
        )

    def add_chunks(self, project_id: int, document_id: int, chunks: list, embeddings: list[list[float]]) -> None:
        if not chunks:
            return
        collection = self._collection(project_id)
        collection.add(
            ids=[f"{document_id}:{chunk.index}" for chunk in chunks],
            documents=[chunk.text for chunk in chunks],
            embeddings=embeddings,
            metadatas=[
                {
                    "project_id": str(project_id),
                    "document_id": str(document_id),
                    "page": chunk.page,
                    "filename": chunk.filename,
                    "source": chunk.source,
                }
                for chunk in chunks
            ],
        )

    def query(self, project_id: int, embedding: list[float], limit: int = 12) -> list[RetrievedChunk]:
        try:
            collection = self._client.get_collection(name=f"project_{project_id}")
        except Exception:
            return []
        if collection.count() == 0:
            return []
        results = collection.query(query_embeddings=[embedding], n_results=min(limit, collection.count()))
        documents = results.get("documents", [[]])[0]
        metadatas = results.get("metadatas", [[]])[0]
        retrieved: list[RetrievedChunk] = []
        for text, metadata in zip(documents, metadatas):
            retrieved.append(
                RetrievedChunk(
                    text=text,
                    filename=str(metadata["filename"]),
                    page=int(metadata["page"]),
                    source=str(metadata["source"]),
                    document_id=int(metadata["document_id"]),
                )
            )
        return retrieved

    def delete_document(self, project_id: int, document_id: int) -> None:
        try:
            collection = self._client.get_collection(name=f"project_{project_id}")
            collection.delete(where={"document_id": str(document_id)})
        except Exception:
            logger.warning("Unable to remove Chroma records for document %s", document_id, exc_info=True)