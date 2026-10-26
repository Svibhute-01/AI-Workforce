"""One QA run: start the app on a fresh database, write tests for each acceptance criterion, run them
over HTTP, repair tests that are themselves broken (once), and report a verdict per criterion."""

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

QA_DB = "qa_app.db"
CODE_CHARS = 30000
PLAN_ATTEMPTS = 2


def summarize_openapi(spec: dict, limit: int = 6000) -> str:
    """The app's real endpoints as short text, so the tests only use paths that exist."""
    lines = []
    for path, methods in (spec.get("paths") or {}).items():
        for method, detail in methods.items():
            if method.lower() not in ("get", "post", "put", "patch", "delete"):
                continue
            line = f"{method.upper()} {path}: {detail.get('summary') or detail.get('operationId') or ''}".strip()
            body = ((detail.get("requestBody") or {}).get("content") or {}).get("application/json", {}).get("schema", {})
            if "$ref" in body:
                schema = (spec.get("components", {}).get("schemas", {})).get(body["$ref"].split("/")[-1], {})
                fields = ", ".join(f"{k}{'*' if k in schema.get('required', []) else ''}" for k in schema.get("properties", {}))
                line += f" | body: {fields}"
            codes = ", ".join(sorted((detail.get("responses") or {}).keys()))
            lines.append(f"{line} | responses: {codes}")
    return "\n".join(lines)[:limit] or "(the app does not publish an OpenAPI description)"


def _plan(chain, inputs: dict) -> QAPlan:
    last = None
    for attempt in range(PLAN_ATTEMPTS):
        try:
            return chain.invoke(inputs)
        except Exception as exc:  # noqa: BLE001 - a malformed model answer is retried once
            last = exc
    raise RuntimeError(f"The QA agent could not produce a test plan: {last.__class__.__name__}: {last}")


def run_qa(jobs, job_id: str, project_id: str, workspace, stack, brief: dict, runner=None) -> dict:
    def log(message: str, **fields):
        jobs.update(job_id, log=message, **fields)

    criteria = [{"id": c["id"], "text": c["text"]} for c in brief["criteria"]]
    runner = runner or make_runner(workspace.root, stack)
    qa_db = Path(workspace.root) / QA_DB
    env = {"DATABASE_URL": f"sqlite:///./{QA_DB}"} if "DATABASE_URL" in stack.check_env else {}
    started = time.time()

    def blocked(reason: str, app_log: str = "") -> dict:
        rows = [{**c, "verdict": "UNVERIFIED", "reason": reason, "scenarios": []} for c in criteria]
        return {**overall(rows), "verdict": "BLOCKED", "criteria": rows, "repaired": 0, "blocked": reason,
                "app_log": app_log, "seconds": round(time.time() - started, 1)}

    qa_db.unlink(missing_ok=True)   # every QA run starts from an empty database
    log("Starting the app on a fresh database")
    port = find_free_port()
    try:
        handle = runner.start_app(port, APPS_DIR / f"{project_id}-qa.log", env)
    except (OSError, RuntimeError) as exc:
        return blocked(f"The app could not be started: {exc}")
    try:
        problem = wait_until_up(handle, port, stack, seconds=30)
        if problem:
            return blocked("The app did not start, so nothing could be tested.", problem)

        base = f"http://127.0.0.1:{port}"
        try:
            spec = httpx.get(f"{base}/openapi.json", timeout=5).json()
            openapi = summarize_openapi(spec)
        except (httpx.HTTPError, ValueError):
            openapi = "(the app does not publish an OpenAPI description)"

        inputs = {
            "task": f"{brief['task_id']}: {brief.get('task_title', '')}",
            "criteria": "\n".join(f"{c['id']}: {c['text']}" for c in criteria),
            "stack": stack.label,
            "design": brief.get("design_text") or "(none)",
            "openapi": openapi,
            "code": build_existing_files_context(workspace)[:CODE_CHARS] or "(no files)",
            "repair": "",
        }
        log(f"Writing tests for {len(criteria)} acceptance criteria")
        plan = _plan(chain_module.qa_chain, inputs)

        log(f"Running {len(plan.scenarios)} scenario(s)")
        results = run_plan(base, plan.scenarios)

        broken = [r for r in results if r.verdict == "ERROR" and r.kind == "spec"]
        repaired = 0
        if broken:   # tests that are wrong themselves are fixed once, before anything is blamed on the app
            log(f"{len(broken)} test(s) were themselves wrong; asking QA to repair them once")
            inputs["repair"] = (
                "Some of your scenarios could not run because the TEST was wrong. Rewrite ONLY these scenarios "
                "(same criterion ids) and return them in `scenarios`:\n"
                + "\n".join(f"- criterion {r.criterion_id}, '{r.title}': {r.message}" for r in broken) + "\n\n"
            )
            try:
                fixed = _plan(chain_module.qa_chain, inputs)
                targets = {r.criterion_id.lower() for r in broken}
                retest = [s for s in fixed.scenarios if s.criterion_id.lower() in targets]
                if retest:
                    results = [r for r in results if r not in broken] + run_plan(base, retest)
                    repaired = len(broken)
            except RuntimeError:
                pass   # keep the original results: those criteria stay UNVERIFIED with the reason

        rows = aggregate(criteria, plan, results)
        for row in rows:
            log(f"{row['id']}: {row['verdict']}")
        return {**overall(rows), "criteria": rows, "repaired": repaired, "blocked": None,
                "app_log": "", "seconds": round(time.time() - started, 1)}
    finally:
        handle.stop()
        qa_db.unlink(missing_ok=True)
