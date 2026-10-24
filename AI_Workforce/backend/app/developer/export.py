"""CSV export of Developer AI runs, for the project report."""

import csv
import io
from datetime import datetime, timezone

from ..models import AgentRun

COLUMNS = [
    "run_id", "task_id", "task_title", "status", "attempts", "first_try_success",
    "started_at", "completed_at", "duration_seconds", "files_changed", "stack", "tech_stack", "final_error",
]
FINISHED = ("COMPLETED", "FAILED")


def _aware(value: datetime | None) -> datetime | None:
    """SQLite returns naive datetimes; treat them as UTC so they can be subtracted."""
    if value is not None and value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


def _safe(value) -> str:
    """Stop spreadsheet programs from running a cell that starts like a formula."""
    text = "" if value is None else str(value)
    return "'" + text if text[:1] in ("=", "+", "-", "@", "\t", "\r") else text


def _duration(run: AgentRun) -> float | None:
    start, end = _aware(run.started_at), _aware(run.completed_at)
    if run.status in FINISHED and start and end:
        return round((end - start).total_seconds(), 1)
    return None


def run_row(run: AgentRun) -> dict:
    info, output = run.input_summary or {}, run.output_summary or {}
    attempts = output.get("attempts", 0)
    errors = output.get("errors") or []
    final_error = (run.error or (errors[0] if errors else "")).strip().splitlines()
    return {
        "run_id": run.id,
        "task_id": info.get("task_id"),
        "task_title": info.get("task_title"),
        "status": run.status,
        "attempts": attempts,
        "first_try_success": "yes" if run.status == "COMPLETED" and attempts == 1 else "no" if run.status in FINISHED else "",
        "started_at": _aware(run.started_at).isoformat() if run.started_at else "",
        "completed_at": _aware(run.completed_at).isoformat() if run.completed_at else "",
        "duration_seconds": _duration(run),
        "files_changed": len(output.get("changes") or []),
        "stack": info.get("stack"),
        "tech_stack": info.get("tech_stack"),
        "final_error": (final_error[0][:300] if final_error and run.status != "COMPLETED" else ""),
    }


def summarize(rows: list[dict]) -> list[tuple[str, object]]:
    finished = [row for row in rows if row["status"] in FINISHED]
    completed = [row for row in finished if row["status"] == "COMPLETED"]
    durations = [row["duration_seconds"] for row in finished if row["duration_seconds"] is not None]

    def percent(part: int, whole: int):
        return round(100 * part / whole, 1) if whole else "n/a"

    def average(values):
        return round(sum(values) / len(values), 1) if values else "n/a"

    return [
        ("Total runs", len(rows)),
        ("Finished runs", len(finished)),
        ("Completed", len(completed)),
        ("Failed", len(finished) - len(completed)),
        ("Still running", len(rows) - len(finished)),
        ("Success rate (%)", percent(len(completed), len(finished))),
        ("First-try success rate (%)", percent(sum(row["first_try_success"] == "yes" for row in finished), len(finished))),
        ("Average attempts", average([row["attempts"] for row in finished])),
        ("Average duration (seconds)", average(durations)),
    ]


def runs_to_csv(runs: list[AgentRun]) -> str:
    rows = [run_row(run) for run in sorted(runs, key=lambda item: item.id)]
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(COLUMNS)
    for row in rows:
        writer.writerow([_safe(row[column]) for column in COLUMNS])
    writer.writerow([])
    writer.writerow(["Summary"])
    for label, value in summarize(rows):
        writer.writerow([label, value])
    return buffer.getvalue()
