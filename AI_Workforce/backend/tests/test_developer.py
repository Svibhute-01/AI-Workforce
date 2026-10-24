from types import SimpleNamespace

import httpx
import pytest

from app.api.developer import get_developer_client
from app.developer.client import DeveloperAgentClient, DeveloperServiceError
from app.developer.prompt import build_task_text, tech_stack, workspace_id
from app.models import AgentRun, ArchDesign, PMPlan, PMTask, PMTaskDependency, Project
from app.main import app


class FakeDeveloperClient:
    """Stands in for the Developer Agent service."""

    def __init__(self):
        self.started: list[dict] = []
        self.job = {"status": "running", "attempts": 1, "summary": None, "changes": [], "errors": [], "log": []}
        self.unreachable = False
        self.app_running = False
        self.app_error = ""

    def start_task(self, workspace, task, tech_stack, stack=None):
        if self.unreachable:
            raise DeveloperServiceError(503, "The Developer Agent service is not reachable.")
        self.started.append({"workspace": workspace, "task": task, "tech_stack": tech_stack, "stack": stack})
        return {"job_id": f"job{len(self.started)}", "stack": stack or "python-fastapi"}

    def get_stack(self, workspace):
        return {"stack": "python-fastapi", "label": "Python / FastAPI", "commands": ["install", "test"],
                "can_start": True, "runner": "local", "available": [{"id": "python-fastapi", "label": "Python / FastAPI"}]}

    def get_app(self, workspace):
        return {"running": self.app_running, "url": "http://127.0.0.1:9100/" if self.app_running else None, "log": ""}

    def start_app(self, workspace):
        if self.app_error:
            raise DeveloperServiceError(409, self.app_error)
        self.app_running = True
        return self.get_app(workspace)

    def stop_app(self, workspace):
        was, self.app_running = self.app_running, False
        return {"stopped": was}

    def get_job(self, workspace, job_id):
        if self.unreachable:
            raise DeveloperServiceError(503, "unreachable")
        return self.job

    def list_files(self, workspace):
        return ["app/main.py"]

    def read_file(self, workspace, path):
        if ".." in path:
            raise DeveloperServiceError(404, "Path escapes workspace")
        return "print(1)\n"

    def run_command(self, workspace, command):
        return {"command": command, "ok": True, "exit_code": 0, "output": "1 passed"}


@pytest.fixture
def fake(client):
    service = FakeDeveloperClient()
    app.dependency_overrides[get_developer_client] = lambda: service
    return service


@pytest.fixture
def project(client, make_user, make_project, db):
    user = make_user()
    project_id = make_project(user)
    plan = PMPlan(project_id=project_id, execution_summary="plan")
    db.add(plan)
    db.flush()

    def task(task_id, title, status="TODO"):
        return PMTask(
            project_id=project_id, plan_id=plan.id, task_id=task_id, title=title,
            description=f"Implement {title}", priority="HIGH", story_points=3, suggested_role="Backend",
            sprint_id="S1", status=status, grounding="SOURCE",
            acceptance_criteria=["Returns 201 on success", "Rejects duplicate emails"],
        )

    db.add_all([task("T1", "User model"), task("T2", "Registration endpoint")])
    db.add(PMTaskDependency(
        project_id=project_id, plan_id=plan.id, task_id="T2", depends_on_task_id="T1",
        dependency_type="FINISH_TO_START", description="needs the model", is_blocking=True,
    ))
    db.commit()
    return SimpleNamespace(id=project_id, headers=user["headers"], plan_id=plan.id)


BASE = "/api/projects/{}/developer"


def start(client, project, task_id="T1", **body):
    return client.post(f"{BASE.format(project.id)}/tasks/{task_id}/run", json=body or None, headers=project.headers)


def test_start_run_records_an_agent_run_and_sends_the_task_context(client, project, fake, db):
    response = start(client, project)
    assert response.status_code == 202, response.text
    body = response.json()
    assert body["status"] == "PROCESSING" and body["task_id"] == "T1"

    sent = fake.started[0]
    assert sent["workspace"] == workspace_id(project.id)
    assert "Implement User model" in sent["task"]
    assert "Rejects duplicate emails" in sent["task"]
    assert db.get(AgentRun, body["id"]).agent_name == "Developer AI"
    assert db.query(PMTask).filter_by(project_id=project.id, task_id="T1").one().status == "IN_PROGRESS"


def test_run_completes_when_the_job_succeeds_and_marks_the_task_completed(client, project, fake, db):
    run_id = start(client, project).json()["id"]
    fake.job = {
        "status": "success", "attempts": 2, "summary": "done", "errors": [], "log": [{"time": "t", "message": "ok"}],
        "changes": [{"path": "app/models.py", "action": "create", "explanation": "model"}],
    }
    body = client.get(f"{BASE.format(project.id)}/runs/{run_id}", headers=project.headers).json()
    assert body["status"] == "COMPLETED" and body["attempts"] == 2
    assert body["changes"][0]["path"] == "app/models.py"
    db.expire_all()
    assert db.query(PMTask).filter_by(project_id=project.id, task_id="T1").one().status == "COMPLETED"


def test_failed_job_marks_the_run_failed_and_returns_the_task_to_todo(client, project, fake, db):
    run_id = start(client, project).json()["id"]
    fake.job = {"status": "failed", "attempts": 3, "errors": ["Step 'test' failed"], "log": [], "changes": []}
    body = client.get(f"{BASE.format(project.id)}/runs/{run_id}", headers=project.headers).json()
    assert body["status"] == "FAILED" and "Step 'test' failed" in body["errors"][0]
    db.expire_all()
    assert db.query(PMTask).filter_by(project_id=project.id, task_id="T1").one().status == "TODO"


def test_only_one_active_run_per_project(client, project, fake):
    assert start(client, project).status_code == 202
    assert start(client, project, "T1").status_code == 409


def test_blocking_prerequisites_must_be_completed_unless_forced(client, project, fake):
    blocked = start(client, project, "T2")
    assert blocked.status_code == 409 and "T1" in blocked.json()["detail"]
    assert start(client, project, "T2", force=True).status_code == 202


def test_unknown_task_is_404(client, project, fake):
    assert start(client, project, "NOPE").status_code == 404


def test_service_down_fails_the_run_cleanly(client, project, fake, db):
    fake.unreachable = True
    response = start(client, project)
    assert response.status_code == 503
    assert db.query(AgentRun).filter_by(project_id=project.id).one().status == "FAILED"


def test_a_transient_outage_while_polling_keeps_the_run_processing(client, project, fake):
    run_id = start(client, project).json()["id"]
    fake.unreachable = True
    body = client.get(f"{BASE.format(project.id)}/runs/{run_id}", headers=project.headers).json()
    assert body["status"] == "PROCESSING"


def test_workspace_files_and_commands(client, project, fake):
    base = BASE.format(project.id)
    assert client.get(f"{base}/workspace/files", headers=project.headers).json() == {"files": ["app/main.py"]}
    assert client.get(f"{base}/workspace/file", params={"path": "app/main.py"}, headers=project.headers).json()["content"]
    assert client.get(f"{base}/workspace/file", params={"path": "../x"}, headers=project.headers).status_code == 404
    ok = client.post(f"{base}/commands", json={"command": "test"}, headers=project.headers)
    assert ok.status_code == 200 and ok.json()["ok"] is True
    assert client.post(f"{base}/commands", json={"command": "rm -rf /"}, headers=project.headers).status_code == 422


def test_commands_are_refused_while_the_agent_is_working(client, project, fake):
    start(client, project)
    response = client.post(f"{BASE.format(project.id)}/commands", json={"command": "test"}, headers=project.headers)
    assert response.status_code == 409


def test_other_users_cannot_reach_the_project(client, project, fake, make_user):
    outsider = make_user()
    base = BASE.format(project.id)
    assert client.get(f"{base}/workspace/files", headers=outsider["headers"]).status_code == 404
    assert client.post(f"{base}/tasks/T1/run", headers=outsider["headers"]).status_code == 404


def test_authentication_is_required(client, project, fake):
    assert client.get(f"{BASE.format(project.id)}/runs").status_code == 401


def test_task_text_includes_only_design_items_traced_to_the_task(db, project):
    design = ArchDesign(
        project_id=project.id,
        hld={"style": {"name": "Layered"}, "components": [{"technology": "FastAPI"}, {"technology": "PostgreSQL"}]},
        lld={
            "apis": [
                {"task_ids": ["T1"], "method": "POST", "path": "/register", "summary": "Register", "validation_rules": ["email valid"]},
                {"task_ids": ["T9"], "method": "GET", "path": "/other", "summary": "Unrelated"},
            ],
            "tables": [{"task_ids": ["T1"], "name": "users", "columns": [{"name": "id", "type": "int"}]}],
        },
    )
    db.add(design)
    db.commit()
    task = db.query(PMTask).filter_by(project_id=project.id, task_id="T1").one()
    text = build_task_text(db, db.get(Project, project.id), task)
    assert "POST /register" in text and "email valid" in text and "Table users" in text
    assert "/other" not in text
    assert "environment rules" in text
    assert tech_stack(design) == "FastAPI, PostgreSQL"


def test_client_hides_service_credentials_problems_and_network_errors():
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/files"):
            return httpx.Response(401, json={"detail": "Invalid service key"})
        raise httpx.ConnectError("refused")

    api = DeveloperAgentClient(transport=httpx.MockTransport(handler))
    with pytest.raises(DeveloperServiceError) as bad_key:
        api.list_files("project_1")
    assert bad_key.value.status_code == 503  # a wrong service key is our configuration problem, not the user's
    with pytest.raises(DeveloperServiceError) as down:
        api.get_job("project_1", "x")
    assert down.value.status_code == 503


# --- CSV export ---------------------------------------------------------------------------------

import csv as csv_module
import io
from datetime import datetime, timedelta, timezone

from app.developer.export import run_row, runs_to_csv


def _finished_run(db, project, task_id, status, attempts, seconds, errors=None, title="Task"):
    started = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
    run = AgentRun(
        project_id=project.id, agent_name="Developer AI", status=status,
        started_at=started, completed_at=started + timedelta(seconds=seconds),
        input_summary={"task_id": task_id, "task_title": title, "tech_stack": "FastAPI"},
        output_summary={"attempts": attempts, "changes": [{"path": "a.py"}, {"path": "b.py"}], "errors": errors or []},
    )
    db.add(run)
    db.commit()
    return run


def _parse(text):
    body, _, summary = text.partition("\r\n\r\n")
    rows = list(csv_module.DictReader(io.StringIO(body)))
    stats = dict(row for row in csv_module.reader(io.StringIO(summary)) if len(row) == 2)
    return rows, stats


def test_export_lists_every_run_with_a_summary(client, project, fake, db):
    _finished_run(db, project, "T1", "COMPLETED", 1, 60, title="First")
    _finished_run(db, project, "T2", "COMPLETED", 3, 240, title="Second")
    _finished_run(db, project, "T3", "FAILED", 3, 300, errors=["Step 'install' failed:\nTimed out"], title="Third")

    response = client.get(f"{BASE.format(project.id)}/runs/export", headers=project.headers)
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/csv")
    assert "attachment" in response.headers["content-disposition"]

    rows, stats = _parse(response.text)
    assert [row["task_id"] for row in rows] == ["T1", "T2", "T3"]
    assert [row["first_try_success"] for row in rows] == ["yes", "no", "no"]
    assert rows[0]["duration_seconds"] == "60.0" and rows[0]["files_changed"] == "2"
    assert rows[2]["final_error"] == "Step 'install' failed:"
    assert rows[1]["final_error"] == ""
    assert stats["Total runs"] == "3" and stats["Completed"] == "2" and stats["Failed"] == "1"
    assert stats["Success rate (%)"] == "66.7"
    assert stats["First-try success rate (%)"] == "33.3"
    assert stats["Average attempts"] == "2.3"
    assert stats["Average duration (seconds)"] == "200.0"


def test_export_of_a_project_without_runs_is_valid(client, project, fake):
    response = client.get(f"{BASE.format(project.id)}/runs/export", headers=project.headers)
    assert response.status_code == 200
    _, stats = _parse(response.text)
    assert stats["Total runs"] == "0" and stats["Success rate (%)"] == "n/a"


def test_running_runs_are_counted_but_not_in_the_rates(client, project, fake):
    start(client, project)  # stays PROCESSING because the fake job is "running"
    _, stats = _parse(client.get(f"{BASE.format(project.id)}/runs/export", headers=project.headers).text)
    assert stats["Total runs"] == "1" and stats["Still running"] == "1" and stats["Finished runs"] == "0"


def test_cells_that_look_like_formulas_are_neutralised(db, project):
    run = _finished_run(db, project, "T1", "FAILED", 3, 10, errors=["=HYPERLINK(\"http://x\")"], title="=SUM(A1)")
    csv_text = runs_to_csv([run])
    assert "'=SUM(A1)" in csv_text and "'=HYPERLINK" in csv_text


def test_naive_database_timestamps_do_not_break_the_duration(db, project):
    run = _finished_run(db, project, "T1", "COMPLETED", 1, 90)
    run.started_at, run.completed_at = run.started_at.replace(tzinfo=None), run.completed_at.replace(tzinfo=None)
    assert run_row(run)["duration_seconds"] == 90.0


def test_export_requires_login_and_ownership(client, project, fake, make_user):
    assert client.get(f"{BASE.format(project.id)}/runs/export").status_code == 401
    outsider = make_user()
    assert client.get(f"{BASE.format(project.id)}/runs/export", headers=outsider["headers"]).status_code == 404


# --- Stacks and the preview app ------------------------------------------------------------------

def test_the_requested_stack_is_forwarded_and_recorded(client, project, fake, db):
    response = start(client, project, stack="node-express")
    assert response.status_code == 202
    assert fake.started[0]["stack"] == "node-express"
    assert db.get(AgentRun, response.json()["id"]).input_summary["stack"] == "node-express"


def test_stack_endpoint_lists_options_and_commands(client, project, fake):
    body = client.get(f"{BASE.format(project.id)}/stack", headers=project.headers).json()
    assert body["stack"] == "python-fastapi" and body["commands"] == ["install", "test"] and body["can_start"] is True


def test_app_can_be_started_inspected_and_stopped(client, project, fake):
    base = BASE.format(project.id)
    assert client.get(f"{base}/app", headers=project.headers).json()["running"] is False
    started = client.post(f"{base}/app/start", headers=project.headers)
    assert started.status_code == 200 and started.json()["url"] == "http://127.0.0.1:9100/"
    assert client.post(f"{base}/app/stop", headers=project.headers).json() == {"stopped": True}


def test_app_errors_from_the_service_reach_the_user(client, project, fake):
    fake.app_error = "Dependencies are not installed yet. Run a task first (or press Install)."
    response = client.post(f"{BASE.format(project.id)}/app/start", headers=project.headers)
    assert response.status_code == 409 and "not installed" in response.json()["detail"]


def test_app_cannot_start_while_the_agent_is_working(client, project, fake):
    start(client, project)
    assert client.post(f"{BASE.format(project.id)}/app/start", headers=project.headers).status_code == 409


def test_app_endpoints_are_protected(client, project, fake, make_user):
    base = BASE.format(project.id)
    assert client.get(f"{base}/app").status_code == 401
    outsider = make_user()
    for method, path in (("get", "app"), ("post", "app/start"), ("post", "app/stop"), ("get", "stack")):
        assert getattr(client, method)(f"{base}/{path}", headers=outsider["headers"]).status_code == 404


def test_export_has_a_stack_column(client, project, fake, db):
    _finished_run(db, project, "T1", "COMPLETED", 1, 30)
    run = db.query(AgentRun).filter_by(project_id=project.id).one()
    run.input_summary = {**run.input_summary, "stack": "node-express"}
    db.commit()
    rows, _ = _parse(client.get(f"{BASE.format(project.id)}/runs/export", headers=project.headers).text)
    assert rows[0]["stack"] == "node-express"
