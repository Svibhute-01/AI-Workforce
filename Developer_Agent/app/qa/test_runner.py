"""Run an existing pytest suite and parse its JUnit XML report."""
from __future__ import annotations

import os
import subprocess
import sys
import time
import xml.etree.ElementTree as ET
from pathlib import Path


def _python_for_project(project: Path) -> str:
    if os.name == "nt":
        candidate = project / ".venv" / "Scripts" / "python.exe"
    else:
        candidate = project / ".venv" / "bin" / "python"
    return str(candidate) if candidate.is_file() else sys.executable


def run_pytest(project_path: str, timeout: int = 120) -> dict:
    """Execute tests/ using the project's venv when available.

    Only run this against trusted workspaces: a timeout is not a security sandbox.
    """
    project = Path(project_path).resolve()
    if not project.is_dir():
        return {"status": "error", "message": "Project directory does not exist."}
    test_dir = project / "tests"
    if not test_dir.is_dir():
        return {
            "status": "inconclusive",
            "message": "No tests directory found.",
            "passed": 0, "failed": 0, "errors": 0, "skipped": 0, "total": 0,
        }

    report_path = project / "qa_junit_report.xml"
    # Never accidentally parse a previous run's report.
    report_path.unlink(missing_ok=True)
    command = [
        _python_for_project(project), "-m", "pytest", str(test_dir),
        "-v", "--tb=short", f"--junitxml={report_path}",
    ]
    started = time.monotonic()
    try:
        result = subprocess.run(
            command, cwd=str(project), capture_output=True, text=True,
            timeout=timeout, check=False, shell=False,
        )
        duration = round(time.monotonic() - started, 2)
    except subprocess.TimeoutExpired as exc:
        stdout = exc.stdout or ""
        stderr = exc.stderr or ""
        if isinstance(stdout, bytes):
            stdout = stdout.decode("utf-8", errors="replace")
        if isinstance(stderr, bytes):
            stderr = stderr.decode("utf-8", errors="replace")
        return {
            "status": "error",
            "message": f"Pytest timed out after {timeout} seconds.",
            "duration_seconds": round(time.monotonic() - started, 2),
            "stdout": stdout[-12000:], "stderr": stderr[-12000:],
            "passed": 0, "failed": 0, "errors": 0, "skipped": 0, "total": 0,
        }
    except OSError as exc:
        return {
            "status": "error", "message": f"Could not start pytest: {exc}",
            "passed": 0, "failed": 0, "errors": 0, "skipped": 0, "total": 0,
        }

    stdout, stderr = result.stdout or "", result.stderr or ""
    report = {
        "status": "error", "exit_code": result.returncode,
        "passed": 0, "failed": 0, "errors": 0, "skipped": 0, "total": 0,
        "duration_seconds": duration,
        "stdout": stdout[-12000:], "stderr": stderr[-12000:],
    }

    if report_path.is_file():
        try:
            root = ET.parse(report_path).getroot()
            suites = list(root) if root.tag == "testsuites" else [root]
            report["total"] = sum(int(s.attrib.get("tests", 0)) for s in suites)
            report["failed"] = sum(int(s.attrib.get("failures", 0)) for s in suites)
            report["errors"] = sum(int(s.attrib.get("errors", 0)) for s in suites)
            report["skipped"] = sum(int(s.attrib.get("skipped", 0)) for s in suites)
            report["passed"] = max(0, report["total"] - report["failed"] - report["errors"] - report["skipped"])
        except (ET.ParseError, ValueError, OSError):
            report["message"] = "Pytest ran, but its XML report could not be parsed."

    if result.returncode == 0 and report["total"] > 0:
        report["status"] = "passed" if report["failed"] == 0 and report["errors"] == 0 else "failed"
    elif result.returncode == 0:
        report["status"] = "inconclusive"
        report["message"] = "No tests were collected."
    else:
        report["status"] = "failed"
        if report["total"] == 0 and not report.get("message"):
            report["message"] = "Pytest exited unsuccessfully before reporting collected tests."
    return report
