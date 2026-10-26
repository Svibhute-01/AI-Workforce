"""Background jobs for long-running Developer Agent tasks.

A task (generate -> write files -> install -> test -> retry) can take minutes, so
the HTTP request returns a job id immediately and the caller polls for progress.
Job records are saved as JSON files so a service restart does not lose history.
"""

import json
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

from app.config import JOBS_DIR

ACTIVE = {"queued", "running"}


class JobConflict(Exception):
    """Another job is already active for this project."""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class JobStore:
    def __init__(self, directory: Path = JOBS_DIR, workers: int = 2):
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._pool = ThreadPoolExecutor(max_workers=workers)
        self._jobs: dict[str, dict] = {}
        self._load()

    def _load(self) -> None:
        for path in self.directory.glob("*.json"):
            try:
                job = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                continue
            if job.get("status") in ACTIVE:  # the process that ran it is gone
                job["status"] = "error"
                job["errors"] = ["The Developer service restarted while this job was running."]
                self._write(job)
            self._jobs[job["job_id"]] = job

    def _write(self, job: dict) -> None:
        tmp = self.directory / f"{job['job_id']}.json.tmp"
        tmp.write_text(json.dumps(job), encoding="utf-8")
        tmp.replace(self.directory / f"{job['job_id']}.json")

    def create(self, project_id: str, task: str, tech_stack: str, kind: str = "developer") -> dict:
        with self._lock:
            if any(j["project_id"] == project_id and j["status"] in ACTIVE for j in self._jobs.values()):
                raise JobConflict(f"A task is already running for project {project_id!r}.")
            job = {
                "job_id": uuid.uuid4().hex,
                "kind": kind,                # developer | qa
                "project_id": project_id,
                "task": task,
                "tech_stack": tech_stack,
                "status": "queued",   # queued | running | success | failed | error
                "attempts": 0,
                "summary": None,
                "changes": [],
                "errors": [],
                "log": [],
                "created_at": _now(),
                "updated_at": _now(),
            }
            self._jobs[job["job_id"]] = job
            self._write(job)
            return dict(job)

    def update(self, job_id: str, log: str | None = None, **fields) -> None:
        with self._lock:
            job = self._jobs[job_id]
            job.update(fields)
            if log:
                job["log"].append({"time": _now(), "message": log})
            job["updated_at"] = _now()
            self._write(job)

    def get(self, project_id: str, job_id: str) -> dict | None:
        with self._lock:
            job = self._jobs.get(job_id)
            if job and job["project_id"] == project_id:
                return json.loads(json.dumps(job))
        return None

    def list(self, project_id: str, limit: int = 20) -> list[dict]:
        with self._lock:
            jobs = [j for j in self._jobs.values() if j["project_id"] == project_id]
        jobs.sort(key=lambda j: j["created_at"], reverse=True)
        return [{k: v for k, v in j.items() if k != "log"} for j in jobs[:limit]]

    def submit(self, fn, *args) -> None:
        self._pool.submit(fn, *args)
