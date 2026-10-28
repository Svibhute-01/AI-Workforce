"""Helpers for consistent QA summaries and developer-facing failure feedback."""
from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any


def build_developer_feedback(report: dict[str, Any]) -> dict[str, Any]:
    """Create concise, structured feedback that a Developer Agent can consume."""
    issues: list[dict[str, Any]] = []
    static = report.get("static_checks") or {}
    syntax = static.get("syntax") or {}
    for issue in syntax.get("issues", []):
        issues.append({"source": "static_syntax", "severity": "high", **issue})
    lint = static.get("lint") or {}
    for issue in lint.get("issues", []):
        issues.append({
            "source": "ruff",
            "severity": "medium",
            "file": issue.get("filename"),
            "line": (issue.get("location") or {}).get("row"),
            "message": issue.get("message", "Lint issue"),
            "code": issue.get("code"),
        })

    suite = report.get("test_suite") or {}
    if suite.get("status") in {"failed", "error"}:
        issues.append({
            "source": "pytest",
            "severity": "high",
            "message": suite.get("message") or "The pytest suite did not pass.",
            "failed": suite.get("failed", 0),
            "errors": suite.get("errors", 0),
            "stdout": (suite.get("stdout") or "")[-6000:],
            "stderr": (suite.get("stderr") or "")[-6000:],
        })

    for criterion in report.get("criteria", []):
        if criterion.get("verdict") == "FAIL":
            issues.append({
                "source": "acceptance_test",
                "severity": "high",
                "criterion_id": criterion.get("id"),
                "message": criterion.get("reason", "Acceptance criterion failed."),
            })

    return {
        "task": "Fix the reported issues, preserve the acceptance criteria, and rerun QA.",
        "issue_count": len(issues),
        "issues": issues[:300],
    }


def write_report(project_path: str, report: dict[str, Any], filename: str = "qa_report.json") -> str | None:
    """Atomically write a JSON QA report. Returns the path, or None on failure."""
    project = Path(project_path).resolve()
    if not project.is_dir():
        return None
    destination = project / filename
    try:
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=project, delete=False) as stream:
            json.dump(report, stream, indent=2, ensure_ascii=False, default=str)
            stream.write("\n")
            temporary = stream.name
        os.replace(temporary, destination)
        return str(destination)
    except OSError:
        try:
            if "temporary" in locals() and os.path.exists(temporary):
                os.unlink(temporary)
        except OSError:
            pass
        return None
