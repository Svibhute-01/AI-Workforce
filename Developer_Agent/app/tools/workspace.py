from pathlib import Path
from app.config import WORKSPACES_DIR
from app.schemas.developer import FileChange

# Folders the agent must never write to or delete from
PROTECTED = {".venv", ".git"}


class WorkspaceError(Exception):
    """Raised when a file operation is not allowed."""


class Workspace:
    """One project folder. All file operations stay inside it."""

    def __init__(self, project_id: str):
        if not project_id.replace("_", "").replace("-", "").isalnum():
            raise WorkspaceError(f"Invalid project id: {project_id!r}")

        self.root = (WORKSPACES_DIR / project_id).resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def _safe_path(self, relative_path: str) -> Path:
        """Turn a relative path into a full path, refusing escapes."""
        target = (self.root / relative_path).resolve()

        if self.root != target and self.root not in target.parents:
            raise WorkspaceError(f"Path escapes workspace: {relative_path!r}")

        # Refuse protected folders such as .venv
        if target != self.root and target.relative_to(self.root).parts[0] in PROTECTED:
            raise WorkspaceError(f"Protected path: {relative_path!r}")

        return target

    def write_file(self, relative_path: str, content: str) -> Path:
        target = self._safe_path(relative_path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        return target

    def delete_file(self, relative_path: str) -> bool:
        """Delete one file. Returns True if it existed."""
        target = self._safe_path(relative_path)
        if not target.is_file():
            return False  # already gone: not an error

        target.unlink()

        # Remove parent folders that are now empty (but never the root)
        parent = target.parent
        while parent != self.root and not any(parent.iterdir()):
            parent.rmdir()
            parent = parent.parent
        return True

    def read_file(self, relative_path: str) -> str:
        target = self._safe_path(relative_path)
        if not target.is_file():
            raise WorkspaceError(f"File not found: {relative_path!r}")
        return target.read_text(encoding="utf-8")

    def list_files(self) -> list[str]:
        """All project files, relative to the root, skipping generated noise."""
        skip = PROTECTED | {"__pycache__", ".pytest_cache"}
        result = []
        for p in self.root.rglob("*"):
            if not p.is_file():
                continue
            rel = p.relative_to(self.root)
            if any(part in skip for part in rel.parts):
                continue
            result.append(str(rel).replace("\\", "/"))
        return sorted(result)

    def apply_changes(self, changes: list[FileChange]) -> list[str]:
        """Apply every FileChange. Returns descriptions of what was done."""
        done = []
        for change in changes:
            if change.action == "delete":
                self.delete_file(change.path)
            else:
                self.write_file(change.path, change.content)
            done.append(f"{change.action} {change.path}")
        return done