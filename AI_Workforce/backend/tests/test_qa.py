import csv
import io

import pytest

from app.api.developer import get_developer_client
from app.developer.client import DeveloperServiceError
from app.developer.qa import build_brief, build_fix_text
from app.developer.qa_export import qa_runs_to_csv
from app.main import app
from app.models import AgentRun, ArchDesign, PMTask, Project
from tests.test_developer import FakeDeveloperClient, project  # noqa: F401  (the fixture builds a project with tasks T1 and T2)

BASE = "/api/projects/{}/qa"
DEV = "/api/projects/{}/developer"

PASS_REPORT = {
    "verdict": "PASS", "counts": {"PASS": 2, "FAIL": 0, "UNVERIFIED": 0}, "total": 2, "coverage": 100.0, "repaired": 0,
    "blocked": None, "app_log": "", "seconds": 12.5,
    "criteria": [{"id": "C1", "text": "Returns 201 on success", "verdict": "PASS", "reason": "1 scenario(s) passed", "scenarios": []},
                 {"id": "C2", "text": "Rejects duplicate emails", "verdict": "PASS", "reason": "1 scenario(s) passed", "scenarios": []}],
}
FAIL_REPORT = {
    "verdict": "FAIL", "counts": {"PASS": 1, "FAIL": 1, "UNVERIFIED": 0}, "total": 2, "coverage": 100.0, "repaired": 1,
    "blocked": None, "app_log": "", "seconds": 20.0,
    "criteria": [
        {"id": "C1", "text": "Returns 201 on success", "verdict": "PASS", "reason": "1 scenario(s) passed", "scenarios": []},
        {"id": "C2", "text": "Rejects duplicate emails", "verdict": "FAIL",
         "reason": "step 'register again': expected status [409], got 201",
         "scenarios": [{"title": "duplicate", "verdict": "FAIL", "message": "x", "steps": [
             {"name": "register again", "request": "POST /register", "status": 201, "passed": False,
              "failures": ["expected status [409], got 201"], "excerpt": '{"id": 2, "email": "a@b.c"}'}]}]},
    ],
}


class QAFake(FakeDeveloperClient):
    def __init__(self):
        super().__init__()
        self.qa_started, self.qa_conflict = [], ""
        self.qa_job = {"status": "running", "errors": [], "log": []}

    def start_qa(self, workspace, brief):
        if self.unreachable:
            raise DeveloperServiceError(503, "The Developer Agent service is not reachable.")
        if self.qa_conflict:
            raise DeveloperServiceError(409, self.qa_conflict)
        self.qa_started.append({"workspace": workspace, **brief})
        return {"job_id": f"qa{len(self.qa_started)}", "kind": "qa"}

    def get_job(self, workspace, job_id):
        if job_id.startswith("qa"):
            if self.unreachable:
                raise DeveloperServiceError(503, "unreachable")
            return self.qa_job
        return super().get_job(workspace, job_id)


@pytest.fixture
def fake(client):
    service = QAFake()
    app.dependency_overrides[get_developer_client] = lambda: service
    return service


def run_qa(client, project, task_id="T1"):
    return client.post(f"{BASE.format(project.id)}/tasks/{task_id}/run", headers=project.headers)


def finish(fake, report, status="success"):
    fake.qa_job = {"status": status, "errors": [] if status == "success" else ["x"], "log": [{"time": "t", "message": "m"}],
                   "report": report}


def task_status(db, project, task_id="T1"):
    db.expire_all()
    return db.query(PMTask).filter_by(project_id=project.id, task_id=task_id).one().status


# --- what QA is given ------------------------------------------------------------------------------

def test_the_brief_numbers_the_acceptance_criteria_and_adds_the_traced_design(db, project):
    db.add(ArchDesign(project_id=project.id, hld={}, lld={"apis": [
        {"task_ids": ["T1"], "method": "POST", "path": "/register", "summary": "Register", "validation_rules": ["email valid"]},
        {"task_ids": ["T9"], "method": "GET", "path": "/other", "summary": "Unrelated"}]}))
    db.commit()
    task = db.query(PMTask).filter_by(project_id=project.id, task_id="T1").one()
    brief = build_brief(db, db.get(Project, project.id), task)
    assert brief["criteria"] == [{"id": "C1", "text": "Returns 201 on success"}, {"id": "C2", "text": "Rejects duplicate emails"}]
    assert "POST /register" in brief["design_text"] and "/other" not in brief["design_text"]
    assert not brief["design_text"].startswith("Architecture to follow")


def test_the_defect_text_carries_the_criterion_and_the_evidence():
    text = build_fix_text(FAIL_REPORT["criteria"])
    assert "C2" in text and "Rejects duplicate emails" in text and "POST /register answered 201" in text
    assert "expected status [409], got 201" in text and "keep the architecture" in text
    assert "- C1" not in text and "Returns 201" not in text        # passing criteria are not mentioned
    assert build_fix_text(PASS_REPORT["criteria"]) == ""
    assert len(build_fix_text(FAIL_REPORT["criteria"] * 200)) <= 6000


# --- running QA -------------------------------------------------------------------------------------

def test_a_qa_run_is_recorded_and_the_brief_goes_to_the_service(client, project, fake, db):
    response = run_qa(client, project)
    assert response.status_code == 202 and response.json()["status"] == "PROCESSING" and response.json()["task_id"] == "T1"
    sent = fake.qa_started[0]
    assert sent["workspace"] == f"project_{project.id}" and len(sent["criteria"]) == 2
    assert db.get(AgentRun, response.json()["id"]).agent_name == "QA AI"


def test_a_task_without_criteria_cannot_be_tested(client, project, fake, db):
    db.query(PMTask).filter_by(project_id=project.id, task_id="T1").one().acceptance_criteria = []
    db.commit()
    response = run_qa(client, project)
    assert response.status_code == 409 and "no acceptance criteria" in response.json()["detail"]
    assert fake.qa_started == []


def test_unknown_tasks_are_404(client, project, fake):
    assert run_qa(client, project, "NOPE").status_code == 404


def test_only_one_qa_run_at_a_time(client, project, fake):
    assert run_qa(client, project).status_code == 202
    assert run_qa(client, project, "T2").status_code == 409


def test_qa_waits_for_the_developer_and_the_developer_waits_for_qa(client, project, fake):
    client.post(f"{DEV.format(project.id)}/tasks/T1/run", json=None, headers=project.headers)
    assert run_qa(client, project).status_code == 409                         # the Developer is working
    fake.job = {"status": "success", "attempts": 1, "summary": "", "errors": [], "log": [], "changes": []}
    client.get(f"{DEV.format(project.id)}/runs", headers=project.headers)     # the poll finishes that run
    assert run_qa(client, project).status_code == 202
    blocked = client.post(f"{DEV.format(project.id)}/tasks/T2/run", json={"force": True}, headers=project.headers)
    assert blocked.status_code == 409 and "QA is testing" in blocked.json()["detail"]
    assert client.post(f"{DEV.format(project.id)}/commands", json={"command": "test"}, headers=project.headers).status_code == 409
    assert client.post(f"{DEV.format(project.id)}/app/start", headers=project.headers).status_code == 409


def test_a_service_problem_fails_the_run_and_passes_the_message_on(client, project, fake, db):
    fake.unreachable = True
    assert run_qa(client, project).status_code == 503
    fake.unreachable = False
    fake.qa_conflict = "Dependencies are not installed yet. Run a Developer task first."
    response = run_qa(client, project)
    assert response.status_code == 409 and "not installed" in response.json()["detail"]
    assert [r.status for r in db.query(AgentRun).filter_by(project_id=project.id, agent_name="QA AI")] == ["FAILED", "FAILED"]


# --- settling the task from the verdict -----------------------------------------------------------------

def test_a_pass_completes_the_task(client, project, fake, db):
    run_id = run_qa(client, project).json()["id"]
    finish(fake, PASS_REPORT)
    body = client.get(f"{BASE.format(project.id)}/runs/{run_id}", headers=project.headers).json()
    assert body["status"] == "COMPLETED" and body["verdict"] == "PASS" and body["coverage"] == 100.0
    assert body["counts"]["PASS"] == 2 and task_status(db, project) == "COMPLETED"


def test_a_fail_sends_the_task_back_to_in_progress_with_the_evidence(client, project, fake, db):
    db.query(PMTask).filter_by(project_id=project.id, task_id="T1").one().status = "COMPLETED"
    db.commit()
    run_id = run_qa(client, project).json()["id"]
    finish(fake, FAIL_REPORT)
    body = client.get(f"{BASE.format(project.id)}/runs/{run_id}", headers=project.headers).json()
    assert body["verdict"] == "FAIL" and body["repaired"] == 1 and body["criteria"][1]["verdict"] == "FAIL"
    assert task_status(db, project) == "IN_PROGRESS"


def test_a_blocked_run_does_not_change_the_task(client, project, fake, db):
    run_id = run_qa(client, project).json()["id"]
    finish(fake, {**PASS_REPORT, "verdict": "BLOCKED", "blocked": "The app did not start", "app_log": "boom"}, status="error")
    before = task_status(db, project)
    body = client.get(f"{BASE.format(project.id)}/runs/{run_id}", headers=project.headers).json()
    assert body["status"] == "FAILED" and body["verdict"] == "BLOCKED" and body["app_log"] == "boom"
    assert task_status(db, project) == before


def test_a_short_outage_while_polling_keeps_the_run_going(client, project, fake):
    run_id = run_qa(client, project).json()["id"]
    fake.unreachable = True
    assert client.get(f"{BASE.format(project.id)}/runs/{run_id}", headers=project.headers).json()["status"] == "PROCESSING"


def test_runs_are_listed_newest_first_and_belong_to_their_project(client, project, fake, make_user):
    first = run_qa(client, project).json()["id"]
    finish(fake, PASS_REPORT)
    client.get(f"{BASE.format(project.id)}/runs/{first}", headers=project.headers)
    second = run_qa(client, project, "T2").json()["id"]
    ids = [r["id"] for r in client.get(f"{BASE.format(project.id)}/runs", headers=project.headers).json()]
    assert ids == [second, first]
    outsider = make_user()
    assert client.get(f"{BASE.format(project.id)}/runs/{first}", headers=outsider["headers"]).status_code == 404


def test_qa_endpoints_need_a_login_and_ownership(client, project, fake, make_user):
    base = BASE.format(project.id)
    assert client.get(f"{base}/runs").status_code == 401
    outsider = make_user()
    for method, path in (("get", "runs"), ("get", "runs/export"), ("post", "tasks/T1/run"), ("post", "runs/1/fix")):
        assert getattr(client, method)(f"{base}/{path}", headers=outsider["headers"]).status_code == 404


# --- sending defects back to the Developer ---------------------------------------------------------------

def test_defects_go_back_to_the_developer_with_the_evidence(client, project, fake, db):
    run_id = run_qa(client, project).json()["id"]
    finish(fake, FAIL_REPORT)
    fake.job = {"status": "success", "attempts": 1, "summary": "", "errors": [], "log": [], "changes": []}
    response = client.post(f"{BASE.format(project.id)}/runs/{run_id}/fix", headers=project.headers)
    assert response.status_code == 202, response.text
    sent = fake.started[-1]["task"]
    assert "QA TESTED THE RUNNING APP AND FOUND DEFECTS" in sent and "Rejects duplicate emails" in sent
    assert "POST /register answered 201" in sent and "Implement User model" in sent        # the original task is still there
    dev_run = db.get(AgentRun, response.json()["id"])
    assert dev_run.agent_name == "Developer AI" and dev_run.input_summary["qa_run_id"] == run_id
    assert db.get(AgentRun, run_id).output_summary["defects_sent"] is True


def test_there_is_nothing_to_send_when_qa_found_no_defects(client, project, fake):
    run_id = run_qa(client, project).json()["id"]
    finish(fake, PASS_REPORT)
    response = client.post(f"{BASE.format(project.id)}/runs/{run_id}/fix", headers=project.headers)
    assert response.status_code == 409 and "no defects" in response.json()["detail"]


def test_defects_cannot_be_sent_while_the_developer_is_busy(client, project, fake):
    run_id = run_qa(client, project).json()["id"]
    finish(fake, FAIL_REPORT)
    fake.job = {"status": "running", "attempts": 1, "summary": "", "errors": [], "log": [], "changes": []}
    assert client.post(f"{BASE.format(project.id)}/runs/{run_id}/fix", headers=project.headers).status_code == 202
    assert client.post(f"{BASE.format(project.id)}/runs/{run_id}/fix", headers=project.headers).status_code == 409


# --- export ----------------------------------------------------------------------------------------------

def test_the_export_lists_runs_with_a_summary(client, project, fake, db):
    first = run_qa(client, project).json()["id"]
    finish(fake, PASS_REPORT)
    client.get(f"{BASE.format(project.id)}/runs/{first}", headers=project.headers)
    second = run_qa(client, project, "T2").json()["id"]
    finish(fake, FAIL_REPORT)
    client.get(f"{BASE.format(project.id)}/runs/{second}", headers=project.headers)

    response = client.get(f"{BASE.format(project.id)}/runs/export", headers=project.headers)
    assert response.status_code == 200 and response.headers["content-type"].startswith("text/csv")
    body, _, summary = response.text.partition("\r\n\r\n")
    rows = list(csv.DictReader(io.StringIO(body)))
    stats = dict(row for row in csv.reader(io.StringIO(summary)) if len(row) == 2)
    assert [r["verdict"] for r in rows] == ["PASS", "FAIL"] and rows[1]["failed"] == "1" and rows[1]["tests_repaired"] == "1"
    assert stats["QA runs"] == "2" and stats["Runs with verdict FAIL"] == "1" and stats["Defects found (criteria failed)"] == "1"
    assert stats["Criteria verified"] == "4" and stats["Criterion pass rate (%)"] == "75.0"


def test_an_empty_export_is_valid_and_formulas_are_neutralised(db, project):
    assert "n/a" in qa_runs_to_csv([])
    run = AgentRun(project_id=project.id, agent_name="QA AI", status="COMPLETED",
                   input_summary={"task_id": "T1", "task_title": "=SUM(A1)"}, output_summary={"verdict": "PASS", "counts": {}})
    db.add(run)
    db.commit()
    assert "'=SUM(A1)" in qa_runs_to_csv([run])
