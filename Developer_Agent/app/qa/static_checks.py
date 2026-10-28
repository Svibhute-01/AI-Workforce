"""Lightweight static checks for generated Python projects.

Always checks Python syntax without executing the project. If Ruff is installed
in the selected interpreter, also runs Ruff; otherwise linting is reported as skipped.
"""
from __future__ import annotations

import ast
import os
import subprocess
import sys
import time
from pathlib import Path

_EXCLUDED = {".git", ".venv", "venv", "node_modules", "__pycache__", "dist", "build"}


def _python_files(project: Path) -> list[Path]:
    files: list[Path] = []
    for current, dirs, names in os.walk(project):
        dirs[:] = [d for d in dirs if d not in _EXCLUDED]
        for name in names:
            if name.endswith(".py"):
                files.append(Path(current) / name)
    return files


def run_static_checks(project_path: str, timeout: int = 60) -> dict:
    """Return syntax and optional Ruff results without executing project code."""
    project = Path(project_path).resolve()
    if not project.is_dir():
        return {"status": "error", "message": "Project directory does not exist.", "syntax": {"status": "error", "checked": 0, "issues": []}, "lint": {"status": "skipped", "message": "Project directory does not exist."}}

    started = time.monotonic()
    files = _python_files(project)
    syntax_issues = []
    for path in files:
        try:
            source = path.read_text(encoding="utf-8")
            ast.parse(source, filename=str(path))
        except (SyntaxError, UnicodeDecodeError, OSError) as exc:
            syntax_issues.append({
                "file": str(path.relative_to(project)),
                "line": getattr(exc, "lineno", None),
                "message": str(exc),
            })

    syntax = {
        "status": "failed" if syntax_issues else "passed",
        "checked": len(files),
        "issues": syntax_issues[:200],
    }

    # Select the project's interpreter if it has a virtual environment.
    if os.name == "nt":
        project_python = project / ".venv" / "Scripts" / "python.exe"
    else:
        project_python = project / ".venv" / "bin" / "python"
    python_executable = str(project_python) if project_python.is_file() else sys.executable

    try:
        probe = subprocess.run(
            [python_executable, "-m", "ruff", "--version"],
            cwd=str(project), capture_output=True, text=True,
            timeout=min(timeout, 10), check=False, shell=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        probe = None

    if probe is None or probe.returncode != 0:
        lint = {"status": "skipped", "message": "Ruff is not installed in the selected Python environment."}
    else:
        try:
            result = subprocess.run(
                [python_executable, "-m", "ruff", "check", "--output-format", "json", "."],
                cwd=str(project), capture_output=True, text=True,
                timeout=timeout, check=False, shell=False,
            )
            # Ruff emits a JSON array. Keep bounded output for job/report payloads.
            import json
            try:
                issues = json.loads(result.stdout or "[]")
            except json.JSONDecodeError:
                issues = []
            lint = {
                "status": "passed" if result.returncode == 0 else "failed",
                "issue_count": len(issues),
                "issues": issues[:200],
                "stdout": (result.stdout or "")[-6000:],
                "stderr": (result.stderr or "")[-6000:],
            }
        except subprocess.TimeoutExpired:
            lint = {"status": "error", "message": f"Ruff timed out after {timeout} seconds."}
        except OSError as exc:
            lint = {"status": "error", "message": f"Could not run Ruff: {exc}"}

    statuses = [syntax["status"], lint["status"]]
    status = "failed" if "failed" in statuses else ("error" if "error" in statuses else "passed")
    return {
        "status": status,
        "syntax": syntax,
        "lint": lint,
        "python_files_checked": len(files),
        "duration_seconds": round(time.monotonic() - started, 2),
    }
