from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

DEVELOPER_AGENT_NAME = "Developer AI"


class DeveloperTaskRunRequest(BaseModel):
    force: bool = False  # run even if blocking prerequisite tasks are not completed
    stack: str | None = None  # a stack id, or None to choose from the architecture. Fixed after the first run


class FileListResponse(BaseModel):
    files: list[str]


class FileContentResponse(BaseModel):
    path: str
    content: str


class StackOption(BaseModel):
    id: str
    label: str


class StackInfo(BaseModel):
    stack: str | None = None       # the project's stack once it has one
    label: str | None = None
    commands: list[str] = Field(default_factory=list)
    can_start: bool = False
    runner: str = "local"
    available: list[StackOption] = Field(default_factory=list)


class AppStatus(BaseModel):
    running: bool
    url: str | None = None
    expires_at: float | None = None
    log: str = ""
    note: str = ""


class CommandRequest(BaseModel):
    command: str = Field(pattern="^(install|check_imports|test)$")


class CommandResponse(BaseModel):
    command: str
    ok: bool
    exit_code: int
    output: str


class FileChangeResponse(BaseModel):
    path: str
    action: str
    explanation: str | None = None


class DeveloperRunResponse(BaseModel):
    id: int
    task_id: str | None = None
    task_title: str | None = None
    status: str  # PROCESSING | COMPLETED | FAILED
    attempts: int = 0
    summary: str | None = None
    changes: list[FileChangeResponse] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
    log: list[dict[str, Any]] = Field(default_factory=list)
    started_at: datetime | None = None
    completed_at: datetime | None = None
