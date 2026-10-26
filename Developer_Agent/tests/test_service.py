import time

import pytest
from fastapi.testclient import TestClient

import app.graph.nodes as nodes
from app.main import app
from app.schemas.developer import DeveloperOutput, FileChange

HEADERS = {"X-Service-Key": "secret-key"}


class FakeChain:
    """Stands in for Gemini: first attempt has a syntax error, the second is fixed."""

    def __init__(self):
        self.calls = 0

    def invoke(self, inputs):
        self.calls += 1
        code = "def add(a, b)\n    return a + b\n" if self.calls == 1 else "def add(a, b):\n    return a + b\n"
        return DeveloperOutput(
            summary=f"attempt {self.calls}",
            changes=[
                FileChange(path="app/__init__.py", action="create", content="", explanation="pkg"),
                FileChange(path="app/main.py", action="create", content=code, explanation="add"),
                FileChange(path="requirements.txt", action="create", content="", explanation="deps"),
            ],
        )


class AlwaysBroken:
    def invoke(self, inputs):
        return DeveloperOutput(
            summary="broken",
            changes=[FileChange(path="a.py", action="create", content="def x(:\n", explanation="bad")],
        )


@pytest.fixture
def client():
    return TestClient(app)


def wait_for(client, project, job_id, timeout=60):
    deadline = time.time() + timeout
    while time.time() < deadline:
        job = client.get(f"/projects/{project}/jobs/{job_id}", headers=HEADERS).json()
        if job["status"] not in ("queued", "running"):
            return job
        time.sleep(0.2)
    raise AssertionError("job did not finish")


def test_requests_without_the_service_key_are_rejected(client):
    assert client.get("/health").status_code == 401
    assert client.get("/health", headers={"X-Service-Key": "wrong"}).status_code == 401
    assert client.get("/health", headers=HEADERS).status_code == 200


def test_file_endpoints_and_safety(client):
    client.post("/projects", json={"project_id": "p_files"}, headers=HEADERS)
    assert client.get("/projects/p_files/files", headers=HEADERS).json()["files"] == []
    assert client.get("/projects/p_files/file", params={"path": "../../x"}, headers=HEADERS).status_code == 404
    assert client.post("/projects", json={"project_id": "../hack"}, headers=HEADERS).status_code == 400


def test_run_endpoint_only_accepts_allowlisted_command_names(client):
    response = client.post("/projects/p_run/run", json={"command": "rm -rf /"}, headers=HEADERS)
    assert response.status_code == 400


def test_task_retries_after_a_syntax_error_and_reports_progress(client, monkeypatch):
    fake = FakeChain()
    monkeypatch.setattr(nodes, "developer_chain", fake)

    started = client.post("/projects/p_job/tasks", json={"task": "add function"}, headers=HEADERS)
    assert started.status_code == 202

    job = wait_for(client, "p_job", started.json()["job_id"])
    # The syntax check fails before any command runs; the retry's install/test steps then run for real,
    # which needs network, so only assert on what is deterministic here.
    assert fake.calls >= 2
    messages = [entry["message"] for entry in job["log"]]
    assert any("Checks failed" in m for m in messages)
    assert job["attempts"] >= 2


def test_retry_cap_marks_the_job_failed(client, monkeypatch):
    monkeypatch.setattr(nodes, "developer_chain", AlwaysBroken())
    started = client.post("/projects/p_cap/tasks", json={"task": "x"}, headers=HEADERS)
    job = wait_for(client, "p_cap", started.json()["job_id"])
    assert job["status"] == "failed"
    assert job["attempts"] == 3
    assert job["errors"]


def test_only_one_active_job_per_project(client, monkeypatch):
    import threading

    gate = threading.Event()

    class Slow:
        def invoke(self, inputs):
            gate.wait(10)
            return AlwaysBroken().invoke(inputs)

    monkeypatch.setattr(nodes, "developer_chain", Slow())
    first = client.post("/projects/p_busy/tasks", json={"task": "x"}, headers=HEADERS)
    assert first.status_code == 202
    assert client.post("/projects/p_busy/tasks", json={"task": "y"}, headers=HEADERS).status_code == 409
    gate.set()
    wait_for(client, "p_busy", first.json()["job_id"])


def test_job_of_another_project_is_not_readable(client, monkeypatch):
    monkeypatch.setattr(nodes, "developer_chain", AlwaysBroken())
    started = client.post("/projects/p_one/tasks", json={"task": "x"}, headers=HEADERS)
    wait_for(client, "p_one", started.json()["job_id"])
    assert client.get(f"/projects/p_two/jobs/{started.json()['job_id']}", headers=HEADERS).status_code == 404


# --- Stacks and the preview app ---------------------------------------------------------------

from app.tools.smoke import probe


class StaticSite:
    def invoke(self, inputs):
        # The prompt must carry the stack's own rules, not the Python ones.
        assert "static website" in inputs["rules"]
        return DeveloperOutput(
            summary="site",
            changes=[
                FileChange(path="index.html", action="create", content='<h1>Hi</h1><link href="s.css" rel="stylesheet">', explanation="page"),
                FileChange(path="s.css", action="create", content="h1{color:red}", explanation="style"),
            ],
        )


def test_stack_is_detected_saved_and_cannot_be_switched(client, monkeypatch):
    monkeypatch.setattr(nodes, "developer_chain", StaticSite())
    started = client.post("/projects/p_stack/tasks", json={"task": "x", "tech_stack": "HTML, CSS"}, headers=HEADERS)
    assert started.status_code == 202 and started.json()["stack"] == "static-html"
    job = wait_for(client, "p_stack", started.json()["job_id"])
    assert job["status"] == "success"

    info = client.get("/projects/p_stack/stack", headers=HEADERS).json()
    assert info["stack"] == "static-html" and info["commands"] == [] and info["can_start"] is True

    clash = client.post("/projects/p_stack/tasks", json={"task": "y", "stack": "node-express"}, headers=HEADERS)
    assert clash.status_code == 409 and "one stack" in clash.json()["detail"]
    assert client.post("/projects/p_new/tasks", json={"task": "y", "stack": "cobol"}, headers=HEADERS).status_code == 400


def test_commands_are_limited_to_what_the_stack_supports(client, monkeypatch):
    monkeypatch.setattr(nodes, "developer_chain", StaticSite())
    started = client.post("/projects/p_nocmd/tasks", json={"task": "x", "stack": "static-html"}, headers=HEADERS)
    wait_for(client, "p_nocmd", started.json()["job_id"])
    response = client.post("/projects/p_nocmd/run", json={"command": "test"}, headers=HEADERS)
    assert response.status_code == 400 and "not available" in response.json()["detail"]


def test_a_preview_can_be_started_opened_and_stopped(client, monkeypatch):
    monkeypatch.setattr(nodes, "developer_chain", StaticSite())
    started = client.post("/projects/p_preview/tasks", json={"task": "x", "stack": "static-html"}, headers=HEADERS)
    wait_for(client, "p_preview", started.json()["job_id"])

    assert client.get("/projects/p_preview/app", headers=HEADERS).json()["running"] is False
    running = client.post("/projects/p_preview/app/start", headers=HEADERS)
    assert running.status_code == 200, running.text
    url = running.json()["url"]
    try:
        assert probe(url) == 200
        assert client.get("/projects/p_preview/app", headers=HEADERS).json()["running"] is True
    finally:
        assert client.post("/projects/p_preview/app/stop", headers=HEADERS).json() == {"stopped": True}
    assert probe(url, timeout=1) is None


def test_a_new_task_stops_the_running_preview(client, monkeypatch):
    monkeypatch.setattr(nodes, "developer_chain", StaticSite())
    first = client.post("/projects/p_restart/tasks", json={"task": "x", "stack": "static-html"}, headers=HEADERS)
    wait_for(client, "p_restart", first.json()["job_id"])
    url = client.post("/projects/p_restart/app/start", headers=HEADERS).json()["url"]
    second = client.post("/projects/p_restart/tasks", json={"task": "y"}, headers=HEADERS)
    wait_for(client, "p_restart", second.json()["job_id"])
    assert client.get("/projects/p_restart/app", headers=HEADERS).json()["running"] is False
    assert probe(url, timeout=1) is None


def test_the_preview_needs_files_and_no_running_job(client):
    assert client.post("/projects/p_empty/app/start", headers=HEADERS).status_code == 409
    assert client.get("/projects/p_empty/app", headers=HEADERS).status_code == 200


def test_a_project_without_a_saved_stack_gets_one_from_its_files(client):
    from app.tools.workspace import Workspace
    ws = Workspace("p_legacy")
    ws.write_file("requirements.txt", "fastapi\n")
    ws.write_file("app/main.py", "x = 1\n")
    info = client.get("/projects/p_legacy/stack", headers=HEADERS).json()
    assert info["stack"] == "python-fastapi"
    assert info["commands"] == ["install", "check_imports", "test"] and info["can_start"] is True
    assert client.get("/projects/p_empty_stack/stack", headers=HEADERS).json()["stack"] is None


# --- The System Architect's stack is binding ---------------------------------------------------------

ARCH = [
    {"role": "frontend", "technology": "React (Vite) with Tailwind CSS", "component": "Web App"},
    {"role": "backend", "technology": "Python with FastAPI and SQLAlchemy", "component": "API"},
    {"role": "database", "technology": "PostgreSQL", "component": "Database"},
]


def test_a_task_is_refused_when_the_architecture_cannot_be_built(client):
    response = client.post("/projects/p_gate/tasks", json={"task": "x", "stack": "python-fastapi", "architecture": ARCH}, headers=HEADERS)
    assert response.status_code == 409
    detail = response.json()["detail"]
    assert detail.startswith("Stack conflict:") and "React (Vite) with Tailwind CSS" in detail
    assert client.get("/projects/p_gate/jobs", headers=HEADERS).json()["jobs"] == []   # nothing started


def test_an_explicit_deviation_is_allowed_recorded_and_told_to_the_model(client, monkeypatch):
    seen = {}

    class Spy(StaticSite):
        def invoke(self, inputs):
            seen["rules"] = inputs["rules"]
            return DeveloperOutput(summary="ok", changes=[
                FileChange(path="app/__init__.py", action="create", content="", explanation="p")])

    monkeypatch.setattr(nodes, "developer_chain", Spy())
    started = client.post(
        "/projects/p_dev/tasks",
        json={"task": "x", "stack": "python-fastapi", "architecture": ARCH, "allow_deviation": True},
        headers=HEADERS,
    )
    assert started.status_code == 202
    assert started.json()["deviations"] == ["frontend - Web App: React (Vite) with Tailwind CSS"]
    job = wait_for(client, "p_dev", started.json()["job_id"])
    assert job["deviations"] == started.json()["deviations"]
    assert "follow it exactly" in seen["rules"] and "PostgreSQL" in seen["rules"] and "could NOT build" in seen["rules"]


def test_a_buildable_architecture_starts_without_any_deviation(client, monkeypatch):
    monkeypatch.setattr(nodes, "developer_chain", AlwaysBroken())
    items = [{"role": "backend", "technology": "Python with FastAPI", "component": "API"},
             {"role": "database", "technology": "PostgreSQL", "component": "DB"}]
    response = client.post("/projects/p_ok/tasks", json={"task": "x", "stack": "python-fastapi", "architecture": items}, headers=HEADERS)
    assert response.status_code == 202 and response.json()["deviations"] == []
    wait_for(client, "p_ok", response.json()["job_id"])


def test_a_task_without_architecture_is_not_gated(client, monkeypatch):
    monkeypatch.setattr(nodes, "developer_chain", AlwaysBroken())
    response = client.post("/projects/p_nogate/tasks", json={"task": "x"}, headers=HEADERS)
    assert response.status_code == 202
    wait_for(client, "p_nogate", response.json()["job_id"])


# --- The QA agent ------------------------------------------------------------------------------------

import threading

import app.qa.chain as qa_chain_module
from app.qa.schemas import Expect, QAPlan, Scenario, Step, Untestable

QA_BODY = {
    "task_id": "T1", "task_title": "Home page", "design_text": "",
    "criteria": [{"id": "C1", "text": "The page greets the visitor"}, {"id": "C2", "text": "Mail is sent"}],
}


def _home_plan():
    expect = Expect(status_in=[200], json_equals=[], json_present=[], json_absent=[], body_contains=["Hi"], body_absent=[])
    step = Step(name="open", method="GET", path="/", json_body="", headers=[], expect=expect, save=[])
    return QAPlan(scenarios=[Scenario(criterion_id="C1", title="greets", steps=[step])],
                  untestable=[Untestable(criterion_id="C2", reason="needs a mail server")])


class HomePlan:
    def __init__(self, hold=None):
        self.hold = hold

    def invoke(self, inputs):
        if self.hold:
            self.hold.wait(10)
        return _home_plan()


def _site(client, monkeypatch, project):
    monkeypatch.setattr(nodes, "developer_chain", StaticSite())
    started = client.post(f"/projects/{project}/tasks", json={"task": "x", "stack": "static-html"}, headers=HEADERS)
    wait_for(client, project, started.json()["job_id"])


def test_qa_needs_code_to_test(client):
    response = client.post("/projects/q_empty/qa", json=QA_BODY, headers=HEADERS)
    assert response.status_code == 409 and "no code yet" in response.json()["detail"]


def test_qa_needs_installed_dependencies(client):
    from app.tools.workspace import Workspace
    Workspace("q_nodeps").write_file("requirements.txt", "fastapi\n")
    response = client.post("/projects/q_nodeps/qa", json=QA_BODY, headers=HEADERS)
    assert response.status_code == 409 and "not installed" in response.json()["detail"]


def test_qa_needs_at_least_one_criterion(client):
    assert client.post("/projects/q_x/qa", json={**QA_BODY, "criteria": []}, headers=HEADERS).status_code == 422


def test_a_qa_job_runs_and_returns_the_report(client, monkeypatch):
    _site(client, monkeypatch, "q_site")
    monkeypatch.setattr(qa_chain_module, "qa_chain", HomePlan())
    started = client.post("/projects/q_site/qa", json=QA_BODY, headers=HEADERS)
    assert started.status_code == 202 and started.json()["kind"] == "qa"
    job = wait_for(client, "q_site", started.json()["job_id"])
    assert job["status"] == "success"
    report = job["report"]
    assert report["verdict"] == "PASS" and report["coverage"] == 50.0      # one criterion verified, one not testable
    assert {row["id"]: row["verdict"] for row in report["criteria"]} == {"C1": "PASS", "C2": "UNVERIFIED"}
    assert "QA finished" in job["log"][-1]["message"]


def test_the_developer_cannot_start_while_qa_is_running_and_the_reverse(client, monkeypatch):
    _site(client, monkeypatch, "q_busy")
    gate = threading.Event()
    monkeypatch.setattr(qa_chain_module, "qa_chain", HomePlan(hold=gate))
    qa = client.post("/projects/q_busy/qa", json=QA_BODY, headers=HEADERS)
    try:
        assert client.post("/projects/q_busy/tasks", json={"task": "y"}, headers=HEADERS).status_code == 409
        assert client.post("/projects/q_busy/qa", json=QA_BODY, headers=HEADERS).status_code == 409
        assert client.post("/projects/q_busy/app/start", headers=HEADERS).status_code == 409
    finally:
        gate.set()
    wait_for(client, "q_busy", qa.json()["job_id"])
