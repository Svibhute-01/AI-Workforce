from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class QARunResponse(BaseModel):
    id: int
    task_id: str | None = None
    task_title: str | None = None
    status: str                       # PROCESSING | COMPLETED | FAILED
    verdict: str | None = None        # PASS | FAIL | INCONCLUSIVE | BLOCKED
    counts: dict[str, int] = Field(default_factory=dict)
    total: int = 0
    coverage: float = 0
    criteria: list[dict[str, Any]] = Field(default_factory=list)
    repaired: int = 0
    blocked: str | None = None
    app_log: str = ""
    errors: list[str] = Field(default_factory=list)
    log: list[dict[str, Any]] = Field(default_factory=list)
    defects_sent: bool = False
    started_at: datetime | None = None
    completed_at: datetime | None = None
