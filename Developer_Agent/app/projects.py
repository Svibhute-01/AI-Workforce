"""Remembers which stack each project uses. A project keeps one stack: its files and installed
dependencies only make sense for that stack."""

import json

from app.config import PROJECTS_DIR


def _path(project_id: str):
    PROJECTS_DIR.mkdir(parents=True, exist_ok=True)
    return PROJECTS_DIR / f"{project_id}.json"


def get_stack_id(project_id: str) -> str | None:
    try:
        return json.loads(_path(project_id).read_text(encoding="utf-8")).get("stack")
    except (OSError, ValueError):
        return None


def set_stack_id(project_id: str, stack_id: str) -> None:
    _path(project_id).write_text(json.dumps({"stack": stack_id}), encoding="utf-8")
