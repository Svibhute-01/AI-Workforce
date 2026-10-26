"""Runs QA scenarios against a running app over real HTTP and turns the outcomes into verdicts."""

import json
import re
import uuid
from dataclasses import dataclass, field

import httpx

from app.qa.schemas import QAPlan, Scenario, Step

EXCERPT_CHARS = 1500
REQUEST_TIMEOUT = 10
VARIABLE = re.compile(r"\{\{\s*([A-Za-z_][A-Za-z0-9_]*)\s*\}\}")
MISSING = object()
SKIPPED_HEADERS = {"host", "content-length", "connection", "transfer-encoding"}


class SpecError(Exception):
    """The test itself is wrong (bad JSON, unknown variable...). That is not a defect in the app."""


# --- small helpers -------------------------------------------------------------------------------

def get_path(data, path: str):
    """Read $.a.b[0].c from parsed JSON. Returns MISSING when the path does not exist."""
    if not path.startswith("$"):
        raise SpecError(f"JSON path '{path}' must start with $")
    current = data
    for key, index in re.findall(r"\.([A-Za-z0-9_\-]+)|\[(\d+)\]", path[1:]):
        try:
            current = current[int(index)] if index != "" else current[key]
        except (KeyError, IndexError, TypeError):
            return MISSING
    return current


def as_text(value) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if value is None:
        return "null"
    if isinstance(value, (dict, list)):
        return json.dumps(value, sort_keys=True)
    return str(value)


def same_value(actual, expected: str) -> bool:
    if as_text(actual) == expected.strip():
        return True
    try:   # 3 and 3.0 are the same number
        return float(as_text(actual)) == float(expected)
    except ValueError:
        return False


def render(text: str, variables: dict[str, str]) -> str:
    def fill(match):
        name = match.group(1)
        if name not in variables:
            raise SpecError(f"variable '{name}' is used before any step saved it")
        return variables[name]
    return VARIABLE.sub(fill, text)


# --- results ------------------------------------------------------------------------------------

@dataclass
class StepResult:
    name: str
    request: str
    status: int | None = None
    passed: bool = False
    failures: list[str] = field(default_factory=list)
    excerpt: str = ""


@dataclass
class ScenarioResult:
    criterion_id: str
    title: str
    verdict: str            # PASS | FAIL | ERROR
    kind: str = ""          # for ERROR: "spec" (the test is wrong) or "network" (the app did not answer)
    message: str = ""
    steps: list[StepResult] = field(default_factory=list)


def _check_path(path: str) -> None:
    if not path.startswith("$"):
        raise SpecError(f"JSON path '{path}' must start with $")


def _check(step: Step, status: int, body_text: str, body_json, variables: dict[str, str]) -> list[str]:
    expect, failures = step.expect, []
    if not expect.status_in:
        raise SpecError("expect.status_in is empty")
    # A malformed path is a mistake in the TEST, whatever the response looks like (a web page has no JSON).
    for path in [a.path for a in expect.json_equals] + expect.json_present + expect.json_absent + [s.path for s in step.save]:
        _check_path(path)
    if status not in expect.status_in:
        failures.append(f"expected status {expect.status_in}, got {status}")
    for item in expect.json_equals:
        wanted = render(item.value, variables)   # expected values may use {{uniq}} and saved variables too
        actual = get_path(body_json, item.path) if body_json is not None else MISSING
        if actual is MISSING:
            failures.append(f"{item.path} is missing from the response (expected {wanted})")
        elif not same_value(actual, wanted):
            failures.append(f"{item.path}: expected {wanted}, got {as_text(actual)}")
    for path in expect.json_present:
        if body_json is None or get_path(body_json, path) is MISSING:
            failures.append(f"{path} should be in the response but is missing")
    for path in expect.json_absent:
        if body_json is not None and get_path(body_json, path) is not MISSING:
            failures.append(f"{path} must not be in the response but is present")
    for text in expect.body_contains:
        wanted = render(text, variables)
        if wanted not in body_text:
            failures.append(f"the response does not contain '{wanted}'")
    for text in expect.body_absent:
        unwanted = render(text, variables)
        if unwanted in body_text:
            failures.append(f"the response must not contain '{unwanted}' but does")
    return failures


def _build_request(step: Step, variables: dict[str, str]) -> tuple[str, dict, object]:
    path = render(step.path, variables)
    if not path.startswith("/") or path.startswith("//") or "://" in path:
        raise SpecError(f"path '{path}' must start with a single / and stay on the app under test")
    headers = {h.name: render(h.value, variables) for h in step.headers if h.name.lower() not in SKIPPED_HEADERS}
    body = None
    if step.json_body.strip():
        try:
            body = json.loads(render(step.json_body, variables))
        except json.JSONDecodeError as exc:
            raise SpecError(f"json_body is not valid JSON ({exc.msg})")
    return path, headers, body


def run_scenario(client: httpx.Client, scenario: Scenario) -> ScenarioResult:
    variables = {"uniq": uuid.uuid4().hex[:8]}
    result = ScenarioResult(scenario.criterion_id, scenario.title, "PASS")
    if not scenario.steps:
        return ScenarioResult(scenario.criterion_id, scenario.title, "ERROR", "spec", "the scenario has no steps")

    for step in scenario.steps:
        record = StepResult(step.name, f"{step.method} {step.path}")
        result.steps.append(record)
        try:
            path, headers, body = _build_request(step, variables)
            record.request = f"{step.method} {path}"
            response = client.request(step.method, path, headers=headers, json=body)
        except SpecError as exc:
            return ScenarioResult(scenario.criterion_id, scenario.title, "ERROR", "spec", str(exc), result.steps)
        except httpx.HTTPError as exc:
            return ScenarioResult(scenario.criterion_id, scenario.title, "ERROR", "network",
                                  f"the app did not answer ({exc.__class__.__name__})", result.steps)

        record.status = response.status_code
        record.excerpt = response.text[:EXCERPT_CHARS]
        try:
            body_json = response.json()
        except ValueError:
            body_json = None
        try:
            record.failures = _check(step, response.status_code, response.text, body_json, variables)
            for save in step.save:
                value = get_path(body_json, save.path) if body_json is not None else MISSING
                if value is MISSING:
                    record.failures.append(f"could not read {save.path} from the response, so '{save.variable}' is unavailable")
                else:
                    variables[save.variable] = as_text(value)
        except SpecError as exc:
            return ScenarioResult(scenario.criterion_id, scenario.title, "ERROR", "spec", str(exc), result.steps)

        record.passed = not record.failures
        if not record.passed:
            result.verdict = "FAIL"
            result.message = f"step '{step.name}': " + "; ".join(record.failures)
            return result
    return result


def run_plan(base_url: str, scenarios: list[Scenario]) -> list[ScenarioResult]:
    with httpx.Client(base_url=base_url, timeout=REQUEST_TIMEOUT, follow_redirects=False) as client:
        return [run_scenario(client, scenario) for scenario in scenarios]


# --- verdicts -----------------------------------------------------------------------------------

def aggregate(criteria: list[dict], plan: QAPlan, results: list[ScenarioResult]) -> list[dict]:
    """One verdict per acceptance criterion: PASS, FAIL or UNVERIFIED, always with the reason."""
    untestable = {item.criterion_id.strip().lower(): item.reason for item in plan.untestable}
    rows = []
    for criterion in criteria:
        key = criterion["id"].strip().lower()
        mine = [r for r in results if r.criterion_id.strip().lower() == key]
        failed = [r for r in mine if r.verdict == "FAIL"]
        errors = [r for r in mine if r.verdict == "ERROR"]
        if failed:
            verdict, reason = "FAIL", failed[0].message
        elif mine and all(r.verdict == "PASS" for r in mine):
            verdict, reason = "PASS", f"{len(mine)} scenario(s) passed"
        elif errors:
            verdict, reason = "UNVERIFIED", "the test could not run: " + errors[0].message
        elif key in untestable:
            verdict, reason = "UNVERIFIED", "not testable over HTTP: " + untestable[key]
        else:
            verdict, reason = "UNVERIFIED", "no test was produced for this criterion"
        rows.append({
            "id": criterion["id"], "text": criterion["text"], "verdict": verdict, "reason": reason,
            "scenarios": [
                {"title": r.title, "verdict": r.verdict, "message": r.message,
                 "steps": [{"name": s.name, "request": s.request, "status": s.status, "passed": s.passed,
                            "failures": s.failures, "excerpt": s.excerpt} for s in r.steps]}
                for r in mine
            ],
        })
    return rows


def overall(rows: list[dict]) -> dict:
    counts = {name: sum(1 for row in rows if row["verdict"] == name) for name in ("PASS", "FAIL", "UNVERIFIED")}
    verified = counts["PASS"] + counts["FAIL"]
    if counts["FAIL"]:
        verdict = "FAIL"
    elif counts["PASS"]:
        verdict = "PASS"
    else:
        verdict = "INCONCLUSIVE"
    return {
        "verdict": verdict, "counts": counts, "total": len(rows),
        "coverage": round(100 * verified / len(rows), 1) if rows else 0.0,
    }
