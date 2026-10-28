
"""One QA run: start the app on a fresh database, write tests for each
acceptance criterion, run them over HTTP, repair broken test plans once,
run the project's pytest suite, and report the results.
"""

import time
from pathlib import Path

import httpx

from app.config import APPS_DIR
from app.qa import chain as chain_module
from app.qa.engine import aggregate, overall, run_plan
from app.qa.schemas import QAPlan
from app.tools.context import build_existing_files_context
from app.tools.runner import make_runner
from app.tools.smoke import find_free_port, wait_until_up
from .static_checks import run_static_checks
from .test_runner import run_pytest
from .reporting import build_developer_feedback, write_report


QA_DB = "qa_app.db"
CODE_CHARS = 30000
PLAN_ATTEMPTS = 2
PYTEST_TIMEOUT = 120


def summarize_openapi(spec: dict, limit: int = 6000) -> str:
    """Summarize real application endpoints for AI-generated tests."""
    lines = []

    for path, methods in (spec.get("paths") or {}).items():
        for method, detail in methods.items():
            if method.lower() not in (
                "get", "post", "put", "patch", "delete"
            ):
                continue

            line = (
                f"{method.upper()} {path}: "
                f"{detail.get('summary') or detail.get('operationId') or ''}"
            ).strip()

            body = (
                (detail.get("requestBody") or {})
                .get("content", {})
                .get("application/json", {})
                .get("schema", {})
            )

            if "$ref" in body:
                schema_name = body["$ref"].split("/")[-1]
                schema = (
                    spec.get("components", {})
                    .get("schemas", {})
                    .get(schema_name, {})
                )

                fields = ", ".join(
                    f"{key}{'*' if key in schema.get('required', []) else ''}"
                    for key in schema.get("properties", {})
                )
                line += f" | body: {fields}"

            codes = ", ".join(
                sorted((detail.get("responses") or {}).keys())
            )
            lines.append(f"{line} | responses: {codes}")

    return "\n".join(lines)[:limit] or (
        "(the app does not publish an OpenAPI description)"
    )


def _plan(chain, inputs: dict) -> QAPlan:
    """Generate a QA plan, retrying once if the model response is invalid."""
    last = None

    for _ in range(PLAN_ATTEMPTS):
        try:
            return chain.invoke(inputs)
        except Exception as exc:
            last = exc

    raise RuntimeError(
        f"The QA agent could not produce a test plan: "
        f"{last.__class__.__name__}: {last}"
    )


def run_qa(
    jobs,
    job_id: str,
    project_id: str,
    workspace,
    stack,
    brief: dict,
    runner=None,
) -> dict:
    """Run HTTP acceptance tests and the project's pytest suite."""

    def log(message: str, **fields):
        jobs.update(job_id, log=message, **fields)

    criteria = [
        {"id": c["id"], "text": c["text"]}
        for c in brief["criteria"]
    ]

    runner = runner or make_runner(workspace.root, stack)
    qa_db = Path(workspace.root) / QA_DB

    env = (
        {"DATABASE_URL": f"sqlite:///./{QA_DB}"}
        if "DATABASE_URL" in stack.check_env
        else {}
    )

    started = time.time()

    def blocked(reason: str, app_log: str = "") -> dict:
        rows = [
            {
                **criterion,
                "verdict": "UNVERIFIED",
                "reason": reason,
                "scenarios": [],
            }
            for criterion in criteria
        ]

        return {
            **overall(rows),
            "verdict": "BLOCKED",
            "criteria": rows,
            "test_suite": {
                "status": "not_run",
                "message": reason,
                "passed": 0,
                "failed": 0,
                "errors": 0,
                "skipped": 0,
                "total": 0,
            },
            "repaired": 0,
            "blocked": reason,
            "app_log": app_log,
            "seconds": round(time.time() - started, 1),
        }

    # Start each QA run with an empty SQLite database.
    qa_db.unlink(missing_ok=True)

    log("Starting the app on a fresh database")
    port = find_free_port()

    try:
        handle = runner.start_app(
            port,
            APPS_DIR / f"{project_id}-qa.log",
            env,
        )
    except (OSError, RuntimeError) as exc:
        return blocked(f"The app could not be started: {exc}")

    try:
        problem = wait_until_up(
            handle,
            port,
            stack,
            seconds=30,
        )

        if problem:
            return blocked(
                "The app did not start, so nothing could be tested.",
                problem,
            )

        base = f"http://127.0.0.1:{port}"

        try:
            spec = httpx.get(
                f"{base}/openapi.json",
                timeout=5,
            ).json()

            openapi = summarize_openapi(spec)

        except (httpx.HTTPError, ValueError):
            openapi = (
                "(the app does not publish an OpenAPI description)"
            )

        inputs = {
            "task": (
                f"{brief['task_id']}: "
                f"{brief.get('task_title', '')}"
            ),
            "criteria": "\n".join(
                f"{c['id']}: {c['text']}"
                for c in criteria
            ),
            "stack": stack.label,
            "design": brief.get("design_text") or "(none)",
            "openapi": openapi,
            "code": (
                build_existing_files_context(workspace)[:CODE_CHARS]
                or "(no files)"
            ),
            "repair": "",
        }

        # Stage 1: AI-generated HTTP acceptance tests.
        log(f"Writing tests for {len(criteria)} acceptance criteria")
        plan = _plan(chain_module.qa_chain, inputs)

        log(f"Running {len(plan.scenarios)} HTTP scenario(s)")
        results = run_plan(base, plan.scenarios)

        # Repair malformed test scenarios once.
        broken = [
            result
            for result in results
            if result.verdict == "ERROR" and result.kind == "spec"
        ]

        repaired = 0

        if broken:
            log(
                f"{len(broken)} test(s) were themselves wrong; "
                "asking QA to repair them once"
            )

            inputs["repair"] = (
                "Some of your scenarios could not run because the TEST "
                "was wrong. Rewrite ONLY these scenarios "
                "(same criterion ids) and return them in `scenarios`:\n"
                + "\n".join(
                    f"- criterion {result.criterion_id}, "
                    f"'{result.title}': {result.message}"
                    for result in broken
                )
                + "\n\n"
            )

            try:
                fixed = _plan(chain_module.qa_chain, inputs)

                targets = {
                    result.criterion_id.lower()
                    for result in broken
                }

                retest = [
                    scenario
                    for scenario in fixed.scenarios
                    if scenario.criterion_id.lower() in targets
                ]

                if retest:
                    results = [
                        result
                        for result in results
                        if result not in broken
                    ] + run_plan(base, retest)

                    repaired = len(broken)

            except RuntimeError:
                # Preserve original results if plan repair fails.
                pass

        # Stage 2: Static checks. Syntax checks never execute project code;
        # Ruff runs only when installed in the selected Python environment.
        log("Running Python syntax and optional Ruff checks")
        try:
            static_result = run_static_checks(
                project_path=str(workspace.root),
                timeout=60,
            )
        except Exception as exc:
            static_result = {
                "status": "error",
                "message": f"Static checks failed to run: {type(exc).__name__}: {exc}",
                "syntax": {"status": "error", "checked": 0, "issues": []},
                "lint": {"status": "skipped", "message": "Static-check runner failed."},
            }
        log(
            f"Static checks finished: {static_result.get('status', 'unknown')}"
        )

        # Stage 3: Execute the generated project's existing pytest suite.
        log("Running the project's pytest test suite")

        try:
            test_suite_result = run_pytest(
                project_path=str(workspace.root),
                timeout=PYTEST_TIMEOUT,
            )

        except Exception as exc:
            # A runner failure must not erase the HTTP test results.
            test_suite_result = {
                "status": "error",
                "message": (
                    f"Pytest runner failed: "
                    f"{type(exc).__name__}: {exc}"
                ),
                "passed": 0,
                "failed": 0,
                "errors": 0,
                "skipped": 0,
                "total": 0,
            }

        log(
            "Pytest finished: "
            f"{test_suite_result.get('status', 'unknown')} "
            f"({test_suite_result.get('passed', 0)} passed, "
            f"{test_suite_result.get('failed', 0)} failed)"
        )

        # Aggregate acceptance-criterion results.
        rows = aggregate(criteria, plan, results)

        for row in rows:
            log(f"{row['id']}: {row['verdict']}")

        summary = overall(rows)

        # Test failures and syntax errors must not be hidden by passing HTTP tests.
        if test_suite_result.get("status") == "failed" or static_result.get("status") == "failed":
            summary["verdict"] = "FAIL"
        elif test_suite_result.get("status") in ("error", "inconclusive") or static_result.get("status") == "error":
            if summary.get("verdict") != "FAIL":
                summary["verdict"] = "INCONCLUSIVE"

        report = {
            **summary,
            "criteria": rows,
            "static_checks": static_result,
            "test_suite": test_suite_result,
            "repaired": repaired,
            "blocked": None,
            "app_log": "",
            "seconds": round(time.time() - started, 1),
        }

        # Structured failure handoff for the Developer Agent. The caller can
        # pass this object to its existing developer chain; this module does
        # not assume an undocumented Developer Agent API.
        report["developer_feedback"] = build_developer_feedback(report)
        report_path = write_report(str(workspace.root), report)
        if report_path:
            report["report_path"] = report_path
            # Persist the path too, so the JSON on disk matches the returned result.
            write_report(str(workspace.root), report)

        log(
            f"QA finished: {report['verdict']} | "
            f"static={static_result.get('status', 'unknown')} | "
            f"pytest={test_suite_result.get('status', 'unknown')} | "
            f"developer issues={report['developer_feedback']['issue_count']}"
        )
        return report

    finally:
        handle.stop()
        qa_db.unlink(missing_ok=True)
