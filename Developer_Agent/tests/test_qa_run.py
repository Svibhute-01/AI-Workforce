import uuid

import pytest

import app.qa.chain as chain_module
from app.jobs import JobStore
from app.qa.run import QA_DB, run_qa, summarize_openapi
from app.qa.schemas import Assertion, Expect, QAPlan, Scenario, Step, Untestable
from app.schemas.developer import FileChange
from app.stacks import get_stack
from app.tools.workspace import Workspace


def expect(**kwargs):
    base = dict(status_in=[200], json_equals=[], json_present=[], json_absent=[], body_contains=[], body_absent=[])
    base.update(kwargs)
    return Expect(**base)


def get_step(path="/", **kwargs):
    return Step(name="open", method="GET", path=path, json_body="", headers=[], expect=expect(**kwargs), save=[])


def plan(*scenarios, untestable=()):
    return QAPlan(scenarios=list(scenarios), untestable=[Untestable(criterion_id=i, reason=r) for i, r in untestable])


class ScriptedChain:
    """Stands in for Gemini: returns the next scripted plan (or raises it)."""

    def __init__(self, *answers):
        self.answers, self.inputs = list(answers), []

    def invoke(self, inputs):
        self.inputs.append(dict(inputs))
        answer = self.answers.pop(0)
        if isinstance(answer, Exception):
            raise answer
        return answer


@pytest.fixture
def site(tmp_path):
    ws = Workspace("q_" + uuid.uuid4().hex[:8])
    ws.apply_changes([FileChange(path="index.html", action="create", content="<h1>Welcome home</h1>", explanation="t")])
    store = JobStore(tmp_path / "jobs")
    return ws, store, store.create(ws.root.name, "QA T1", "", kind="qa")


BRIEF = {
    "task_id": "T1", "task_title": "Home page", "design_text": "- page: home",
    "criteria": [{"id": "C1", "text": "The home page welcomes the visitor"},
                 {"id": "C2", "text": "The home page has a login link"},
                 {"id": "C3", "text": "A confirmation email is sent"}],
}


def run(site, *answers, brief=BRIEF):
    ws, store, job = site
    chain = ScriptedChain(*answers)
    chain_module.qa_chain, original = chain, chain_module.qa_chain
    try:
        report = run_qa(store, job["job_id"], ws.root.name, ws, get_stack("static-html"), brief)
    finally:
        chain_module.qa_chain = original
    return report, chain, store.get(ws.root.name, job["job_id"])


def test_a_qa_run_reports_a_verdict_for_every_criterion(site):
    answer = plan(
        Scenario(criterion_id="C1", title="welcome", steps=[get_step(body_contains=["Welcome"])]),
        Scenario(criterion_id="C2", title="login link", steps=[get_step(body_contains=["Login"])]),
        untestable=[("C3", "email delivery")],
    )
    report, chain, job = run(site, answer)
    rows = {row["id"]: row for row in report["criteria"]}
    assert report["verdict"] == "FAIL" and report["counts"] == {"PASS": 1, "FAIL": 1, "UNVERIFIED": 1}
    assert report["coverage"] == 66.7 and report["blocked"] is None and report["repaired"] == 0
    assert rows["C1"]["verdict"] == "PASS" and rows["C2"]["verdict"] == "FAIL"
    assert "does not contain 'Login'" in rows["C2"]["reason"] and "email delivery" in rows["C3"]["reason"]
    messages = [entry["message"] for entry in job["log"]]
    assert "C1: PASS" in messages and "C2: FAIL" in messages


def test_the_planner_gets_the_criteria_the_stack_and_the_code(site):
    _, chain, _ = run(site, plan(untestable=[("C1", "x"), ("C2", "x"), ("C3", "x")]))
    given = chain.inputs[0]
    assert "C2: The home page has a login link" in given["criteria"]
    assert given["stack"] == "Static HTML / CSS / JS" and "Welcome home" in given["code"]
    assert given["task"] == "T1: Home page" and given["design"] == "- page: home" and given["repair"] == ""


def test_a_broken_test_is_repaired_once_before_anything_is_blamed_on_the_app(site):
    bad = Scenario(criterion_id="C1", title="welcome", steps=[get_step(path="http://evil.example/")])
    good = Scenario(criterion_id="C1", title="welcome", steps=[get_step(body_contains=["Welcome"])])
    report, chain, job = run(site, plan(bad), plan(good))
    assert report["repaired"] == 1
    assert {row["id"]: row["verdict"] for row in report["criteria"]}["C1"] == "PASS"
    assert "must start with a single /" in chain.inputs[1]["repair"] and "criterion C1" in chain.inputs[1]["repair"]
    assert any("repair" in entry["message"] for entry in job["log"])


def test_a_test_that_cannot_be_repaired_leaves_the_criterion_unverified_not_failed(site):
    bad = Scenario(criterion_id="C1", title="welcome", steps=[get_step(path="http://evil.example/")])
    report, _, _ = run(site, plan(bad), RuntimeError("model down"), RuntimeError("model down"))
    row = {row["id"]: row for row in report["criteria"]}["C1"]
    assert row["verdict"] == "UNVERIFIED" and "could not run" in row["reason"] and report["repaired"] == 0


def test_a_planner_that_fails_twice_is_reported(site):
    with pytest.raises(RuntimeError, match="could not produce a test plan"):
        run(site, ValueError("bad json"), ValueError("bad json"))


def test_a_malformed_first_answer_is_retried(site):
    answer = plan(Scenario(criterion_id="C1", title="welcome", steps=[get_step(body_contains=["Welcome"])]))
    report, chain, _ = run(site, ValueError("bad json"), answer)
    assert len(chain.inputs) == 2 and report["counts"]["PASS"] == 1


def test_every_run_starts_from_an_empty_database_and_cleans_up(site):
    ws, _, _ = site
    leftover = ws.root / QA_DB
    leftover.write_text("old data")
    run(site, plan(untestable=[("C1", "x"), ("C2", "x"), ("C3", "x")]))
    assert not leftover.exists()


def test_an_app_that_cannot_start_blocks_the_run_instead_of_failing_criteria(tmp_path):
    ws = Workspace("q_" + uuid.uuid4().hex[:8])
    ws.write_file("requirements.txt", "fastapi\n")        # no virtual environment: nothing can start
    store = JobStore(tmp_path / "jobs")
    job = store.create(ws.root.name, "QA", "", kind="qa")
    report = run_qa(store, job["job_id"], ws.root.name, ws, get_stack("python-fastapi"), BRIEF)
    assert report["verdict"] == "BLOCKED" and report["blocked"]
    assert all(row["verdict"] == "UNVERIFIED" for row in report["criteria"]) and report["counts"]["FAIL"] == 0


SPEC = {"paths": {
    "/register": {"post": {"summary": "Register", "requestBody": {"content": {"application/json": {"schema": {"$ref": "#/components/schemas/UserIn"}}}},
                           "responses": {"201": {}, "409": {}}}},
    "/health": {"get": {"summary": "Health", "responses": {"200": {}}}},
    "/ignored": {"parameters": []},
}, "components": {"schemas": {"UserIn": {"required": ["email"], "properties": {"email": {}, "password": {}}}}}}


def test_the_openapi_summary_lists_real_endpoints_with_their_fields():
    text = summarize_openapi(SPEC)
    assert "POST /register: Register | body: email*, password | responses: 201, 409" in text
    assert "GET /health: Health | responses: 200" in text and "ignored" not in text
    assert "does not publish" in summarize_openapi({})
    assert len(summarize_openapi(SPEC, limit=20)) == 20
