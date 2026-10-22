import re
from langchain_chroma import Chroma
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter

from app.config import VECTORSTORE_DIR, RETRIEVAL_K
from app.tools.workspace import Workspace
from app.tools.context import TEXT_EXTENSIONS
from app.rag.embeddings import get_embeddings


def _collection_name(project_id: str) -> str:
    # Chroma names: letters, digits, _ and - only
    return "ws_" + re.sub(r"[^a-zA-Z0-9_-]", "_", project_id)


class ProjectIndex:
    """A vector index of one project's files."""

    def __init__(self, project_id: str, embeddings=None):
        self.workspace = Workspace(project_id)
        self.store = Chroma(
            collection_name=_collection_name(project_id),
            embedding_function=embeddings or get_embeddings(),
            persist_directory=str(VECTORSTORE_DIR),
        )
        self.splitter = RecursiveCharacterTextSplitter(
            chunk_size=800, chunk_overlap=100
        )

    def rebuild(self) -> int:
        """Re-index every text file. Returns the number of chunks stored."""
        # Clear old chunks so deleted/changed files don't linger
        existing = self.store.get()
        if existing["ids"]:
            self.store.delete(ids=existing["ids"])

        docs = []
        for path in self.workspace.list_files():
            if not any(path.endswith(e) for e in TEXT_EXTENSIONS):
                continue
            content = self.workspace.read_file(path)
            for i, chunk in enumerate(self.splitter.split_text(content)):
                docs.append(Document(
                    page_content=chunk,
                    metadata={"path": path, "chunk": i},
                ))

        if docs:
            self.store.add_documents(docs)
        return len(docs)

    def search(self, query: str, k: int = RETRIEVAL_K) -> list[Document]:
        return self.store.similarity_search(query, k=k)


def format_chunks(docs: list[Document]) -> str:
    """Format retrieved chunks for the prompt. Empty if nothing found."""
    if not docs:
        return ""
    parts = [
        f"--- FILE: {d.metadata['path']} (chunk {d.metadata['chunk']}) ---\n{d.page_content}\n"
        for d in docs
    ]
    return "Relevant existing code:\n\n" + "\n".join(parts) + "\n"