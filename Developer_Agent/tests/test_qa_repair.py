from types import SimpleNamespace

import app.main as main


class FakeJobs:
    def __init__(self):
        self.updates = []

    def update(self, job_id, log=None, **fields):
        self.updates.append((job_id, log, fields))


class FakeGraph:
    def __init__(self):
        self.initial_state = None

    def stream(self, state, stream_mode):
        assert stream_mode == "updates"
        self.initial_state = dict(state)
        change = SimpleNamespace(
            path="app/service.py",
            action="update",
            explanation="Fix QA-reported issue",
        )
        output = SimpleNamespace(summary="Applied targeted QA fixes", changes=[change])
        yield {"generate": {"output": output, "retries": 1}}
        yield {"validate": {"validation_errors": [], "status": "success"}}


def test_qa_feedback_is_passed_to_existing_developer_graph(monkeypatch):
    graph = FakeGraph()
    jobs = FakeJobs()
    monkeypatch.setattr(main, "developer_graph", graph)
    monkeypatch.setattr(main, "jobs", jobs)
    monkeypatch.setattr(main, "get_stack", lambda stack_id: SimpleNamespace(label="Python / FastAPI"))

    feedback = {
        "task": "Fix the reported issues",
        "issue_count": 1,
        "issues": [{"source": "pytest", "message": "Expected 201, received 500"}],
    }
    brief = {
        "task_id": "T-42",
        "task_title": "Create account endpoint",
        "criteria": [{"id": "C1", "text": "Registration returns HTTP 201"}],
    }

    result = main._run_developer_repair(
        job_id="job-1",
        project_id="project-1",
        stack_id="python-fastapi",
        brief=brief,
        feedback=feedback,
        round_number=1,
    )

    assert result["status"] == "success"
    assert result["summary"] == "Applied targeted QA fixes"
    assert result["changes"][0]["path"] == "app/service.py"
    assert "Expected 201, received 500" in graph.initial_state["task"]
    assert "C1: Registration returns HTTP 201" in graph.initial_state["task"]
    assert graph.initial_state["validation_errors"]
    assert any("Developer checks passed" in (entry[1] or "") for entry in jobs.updates)
