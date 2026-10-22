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
