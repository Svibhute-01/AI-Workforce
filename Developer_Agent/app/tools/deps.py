"""Remember which dependency files were installed, so an unchanged set is not installed again.

A retry usually changes one source or test file and leaves requirements.txt alone, yet the old flow
ran the whole install again. A stamp (hash of the dependency files) is stored INSIDE the
environment folder (.venv or node_modules), so deleting the environment also deletes the stamp.
The stamp is written only after an install succeeds and removed when one fails, so a half-installed
environment is never trusted.
"""

import hashlib
from pathlib import Path

STAMP_NAME = ".deps-hash"


def _stamp_path(root: Path, stack) -> Path | None:
    if not stack.needs_env or not stack.manifest:
        return None
    return Path(root) / stack.needs_env / STAMP_NAME


def manifest_hash(root: Path, stack) -> str | None:
    """Hash of the stack's dependency files; None when the stack has none."""
    if not stack.manifest:
        return None
    digest = hashlib.sha256()
    for name in stack.manifest:
        path = Path(root) / name
        digest.update(name.encode("utf-8") + b"\0")
        digest.update(path.read_bytes() if path.is_file() else b"<missing>")
        digest.update(b"\0")
    return digest.hexdigest()


def unchanged(root: Path, stack) -> bool:
    """True when the dependency files match the last successful install and the environment still exists."""
    stamp = _stamp_path(root, stack)
    if stamp is None or not stamp.is_file():
        return False
    try:
        return stamp.read_text(encoding="utf-8").strip() == manifest_hash(root, stack)
    except OSError:
        return False


def record(root: Path, stack) -> None:
    stamp = _stamp_path(root, stack)
    if stamp is None or not stamp.parent.is_dir():
        return
    try:
        stamp.write_text(manifest_hash(root, stack) or "", encoding="utf-8")
    except OSError:
        pass   # only costs a repeated install next time


def forget(root: Path, stack) -> None:
    stamp = _stamp_path(root, stack)
    if stamp is None:
        return
    try:
        stamp.unlink(missing_ok=True)
    except OSError:
        pass
