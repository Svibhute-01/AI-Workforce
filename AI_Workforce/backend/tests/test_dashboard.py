from types import SimpleNamespace

import pytest
from sqlalchemy import func, select

from app.models import AgentRun, PMTask

from .conftest import ScriptedProvider
from .plan_fixtures import registration_plan

SUMMARY = "/api/dashboard/summary"
RUN = "/api/projects/{}/project-manager/run"


@pytest.fixture
def planned(client, make_user, make_project, seed_requirements, use_provider):
    """A user with one project that has analyzed requirements and a generated plan."""
    user = make_user()
    project_id = make_project(user, name="Customer Registration")
    seed_requirements(project_id)
    use_provider(ScriptedProvider(registration_plan))
    response = client.post(RUN.format(project_id), headers=user["headers"])
    assert response.status_code == 200, response.text
    return SimpleNamespace(user=user, id=project_id, headers=user["headers"])


def test_requires_authentication(client):
    assert client.get(SUMMARY).status_code == 401


def test_new_user_gets_an_empty_but_complete_summary(client, make_user):
    user = make_user()
    body = client.get(SUMMARY, headers=user["headers"]).json()

    assert body["projects"]["total"] == 0
    assert body["tasks"]["total"] == 0
    assert body["tasks"]["completion_rate"] is None
    assert body["project_overview"] == []
    assert body["recent_tasks"] == []
    assert body["recent_agent_runs"] == []
    assert [a["key"] for a in body["agents"]] == ["requirements_analyst", "project_manager", "developer", "qa"]
    assert all(a["total_runs"] == 0 for a in body["agents"])


def test_numbers_match_the_database(client, db, planned):
    body = client.get(SUMMARY, headers=planned.headers).json()

    task_count = db.scalar(select(func.count()).select_from(PMTask).where(PMTask.project_id == planned.id))
    points = db.scalar(select(func.sum(PMTask.story_points)).where(PMTask.project_id == planned.id))
    assert task_count > 0

    assert body["projects"]["total"] == 1
    assert body["tasks"]["total"] == task_count
    assert body["tasks"]["total_story_points"] == points
    assert body["tasks"]["todo"] == task_count
    assert body["tasks"]["completed"] == 0
    assert sum(item["count"] for item in body["tasks"]["by_status"]) == task_count
    assert sum(item["count"] for item in body["tasks"]["by_priority"]) == task_count

    overview = body["project_overview"][0]
    assert overview["id"] == planned.id
    assert overview["requirements_ready"] is True
    assert overview["plan_ready"] is True
    assert overview["tasks_total"] == task_count
    assert overview["progress"] == 0

    agents = {a["key"]: a for a in body["agents"]}
    assert agents["requirements_analyst"]["total_runs"] == 1
    assert agents["project_manager"]["total_runs"] == 1
    assert agents["project_manager"]["completed"] == 1
    assert agents["developer"]["total_runs"] == 0
    assert body["insights"]["requirements"]["functional"] == 7
    assert body["insights"]["pipeline"][-1] == {"key": "plan", "label": "Plan generated", "count": 1}


def test_completing_a_task_moves_progress(client, db, planned):
    task = db.scalars(select(PMTask).where(PMTask.project_id == planned.id).order_by(PMTask.id)).first()
    task.status = "COMPLETED"
    db.commit()

    body = client.get(SUMMARY, headers=planned.headers).json()
    assert body["tasks"]["completed"] == 1
    assert body["tasks"]["completion_rate"] > 0
    assert body["project_overview"][0]["tasks_completed"] == 1
    assert body["project_overview"][0]["progress"] > 0


def test_failed_agent_run_is_reported(client, db, planned):
    db.add(AgentRun(project_id=planned.id, agent_name="Project Manager AI", status="FAILED", error="provider timeout"))
    db.commit()

    body = client.get(SUMMARY, headers=planned.headers).json()
    pm = next(a for a in body["agents"] if a["key"] == "project_manager")
    assert pm["failed"] == 1
    assert body["recent_agent_runs"][0]["status"] in {"FAILED", "COMPLETED"}
    assert any(item["kind"] == "agent_failed" for item in body["insights"]["attention"])


def test_summary_is_scoped_to_the_signed_in_user(client, make_user, planned):
    other = make_user()
    body = client.get(SUMMARY, headers=other["headers"]).json()

    assert body["projects"]["total"] == 0
    assert body["tasks"]["total"] == 0
    assert body["project_overview"] == []
    assert all(a["total_runs"] == 0 for a in body["agents"])
