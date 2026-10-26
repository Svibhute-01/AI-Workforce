"""CSV export of QA AI runs, for the project report."""

import csv
import io
from datetime import datetime, timezone

from ..models import AgentRun
from .export import _aware, _safe

COLUMNS = [
    "run_id", "task_id", "task_title", "status", "verdict", "criteria_total", "passed", "failed", "unverified",
    "coverage_percent", "tests_repaired", "duration_seconds", "started_at", "completed_at", "defects_sent_to_developer",
    "blocked_reason",
]


def qa_row(run: AgentRun) -> dict:
    info, output = run.input_summary or {}, run.output_summary or {}
    counts = output.get("counts") or {}
    start, end = _aware(run.started_at), _aware(run.completed_at)
    return {
        "run_id": run.id, "task_id": info.get("task_id"), "task_title": info.get("task_title"), "status": run.status,
        "verdict": output.get("verdict") or "", "criteria_total": output.get("total", 0),
        "passed": counts.get("PASS", 0), "failed": counts.get("FAIL", 0), "unverified": counts.get("UNVERIFIED", 0),
        "coverage_percent": output.get("coverage", 0), "tests_repaired": output.get("repaired", 0),
        "duration_seconds": round((end - start).total_seconds(), 1) if start and end and run.status != "PROCESSING" else None,
        "started_at": start.isoformat() if start else "", "completed_at": end.isoformat() if end else "",
        "defects_sent_to_developer": "yes" if output.get("defects_sent") else "no",
        "blocked_reason": (output.get("blocked") or "")[:300],
    }


def summarize(rows: list[dict]) -> list[tuple[str, object]]:
    finished = [r for r in rows if r["status"] == "COMPLETED"]
    passed_runs = [r for r in finished if r["verdict"] == "PASS"]
    failed_runs = [r for r in finished if r["verdict"] == "FAIL"]
    criteria_verified = sum(r["passed"] + r["failed"] for r in finished)
    criteria_passed = sum(r["passed"] for r in finished)

    def pct(part, whole):
        return round(100 * part / whole, 1) if whole else "n/a"

    coverages = [r["coverage_percent"] for r in finished]
    return [
        ("QA runs", len(rows)), ("Finished runs", len(finished)), ("Runs with verdict PASS", len(passed_runs)),
        ("Runs with verdict FAIL", len(failed_runs)),
        ("Blocked or failed to run", sum(1 for r in rows if r["status"] == "FAILED")),
        ("Criteria verified", criteria_verified), ("Criteria passed", criteria_passed),
        ("Defects found (criteria failed)", sum(r["failed"] for r in finished)),
        ("Criterion pass rate (%)", pct(criteria_passed, criteria_verified)),
        ("Average coverage (%)", round(sum(coverages) / len(coverages), 1) if coverages else "n/a"),
        ("Tests repaired by QA itself", sum(r["tests_repaired"] for r in finished)),
        ("Runs whose defects went back to the Developer", sum(1 for r in rows if r["defects_sent_to_developer"] == "yes")),
    ]


def qa_runs_to_csv(runs: list[AgentRun]) -> str:
    rows = [qa_row(run) for run in sorted(runs, key=lambda item: item.id)]
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
