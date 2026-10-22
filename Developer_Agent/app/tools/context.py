from app.config import CONTEXT_MODE
from app.tools.workspace import Workspace

# Only include text/code files, and cap sizes so the prompt stays reasonable
TEXT_EXTENSIONS = {".py", ".txt", ".md", ".json", ".toml", ".yaml", ".yml", ".ini", ".cfg", ".html", ".css", ".js"}
MAX_FILE_CHARS = 8000
MAX_TOTAL_CHARS = 60000


def build_existing_files_context(workspace: Workspace) -> str:
    """Format the workspace's files as text for the prompt. Empty if no files."""
    parts = []
    total = 0

    for path in workspace.list_files():
        if not any(path.endswith(ext) for ext in TEXT_EXTENSIONS):
            continue

        content = workspace.read_file(path)[:MAX_FILE_CHARS]
        block = f"--- FILE: {path} ---\n{content}\n"

        if total + len(block) > MAX_TOTAL_CHARS:
            parts.append("--- (more files omitted: size limit) ---\n")
            break

        parts.append(block)
        total += len(block)

    if not parts:
        return ""

    return "Existing project files:\n\n" + "\n".join(parts) + "\n"


def build_context(workspace: Workspace, task: str, index=None) -> str:
    """Pick the context strategy based on CONTEXT_MODE.

    `index` is an optional ProjectIndex; tests pass one with fake embeddings.
    """
    if CONTEXT_MODE == "rag":
        # Imported here so "all_files" mode never loads Chroma
        from app.rag.store import ProjectIndex, format_chunks

        if index is None:
            index = ProjectIndex(workspace.root.name)
        index.rebuild()                 # simple and correct for small projects
        return format_chunks(index.search(task))

    return build_existing_files_context(workspace)