"""Tests for the speed-ups: timings, live progress, skipping an unchanged install, the Docker package cache."""

import subprocess
import time

import pytest
from fastapi.testclient import TestClient

import app.graph.nodes as nodes
from app import progress
from app.config import _seconds
from app.main import app
from app.schemas.developer import DeveloperOutput, FileChange
from app.stacks import get_stack
from app.timing import Timings, format_timings
from app.tools import deps
from app.tools import runner as runner_module
from app.tools.checks import run_all_checks
from app.tools.runner import CommandResult, DockerRunner
from app.tools.workspace import Workspace

HEADERS = {"X-Service-Key": "secret-key"}
PYTHON = get_stack("python-fastapi")


# --- Timings ----------------------------------------------------------------------------------

def test_timings_add_up_across_retries_and_format_nicely():
    timings = Timings()
    timings.add("llm", 10.0)
    timings.add("install", 20.5)
    timings.add("llm", 5.0)
    assert timings.as_dict() == {"llm": 15.0, "install": 20.5}
    assert format_timings(timings.as_dict()) == "llm 15.0s, install 20.5s (total 35.5s)"
    assert format_timings({}) == "" and format_timings(None) == ""


def test_measure_records_the_time_even_when_the_step_raises():
    timings = Timings()
    with pytest.raises(RuntimeError):
        with timings.measure("test"):
            raise RuntimeError("boom")
    assert "test" in timings.as_dict()


def test_timings_resume_from_the_graph_state():
    carried = Timings({"llm": 3.0})
    carried.add("llm", 2.0)
    assert carried.as_dict()["llm"] == 5.0


# --- Progress ---------------------------------------------------------------------------------

def test_progress_reaches_the_listener_of_that_project_only():
    seen = []
    with progress.listening("p_prog_a", seen.append):
        progress.report("p_prog_a", "hello")
        progress.report("p_prog_b", "not for a")
    progress.report("p_prog_a", "after it ended")
    assert seen == ["hello"]


def test_a_broken_listener_never_breaks_a_run():
    def explode(message):
        raise RuntimeError("log disk full")

    with progress.listening("p_prog_c", explode):
        progress.report("p_prog_c", "still fine")   # must not raise


# --- Skipping an unchanged install ------------------------------------------------------------

def _write(root, name, text):
    path = root / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def test_the_stamp_follows_the_dependency_files(tmp_path):
    (tmp_path / ".venv").mkdir()
    _write(tmp_path, "requirements.txt", "fastapi\n")
    assert not deps.unchanged(tmp_path, PYTHON)           # never installed
    deps.record(tmp_path, PYTHON)
    assert deps.unchanged(tmp_path, PYTHON)
    _write(tmp_path, "requirements.txt", "fastapi\nuvicorn\n")
    assert not deps.unchanged(tmp_path, PYTHON)           # dependencies changed
    deps.record(tmp_path, PYTHON)
    deps.forget(tmp_path, PYTHON)
    assert not deps.unchanged(tmp_path, PYTHON)


def test_deleting_the_environment_deletes_the_stamp(tmp_path):
    (tmp_path / ".venv").mkdir()
    _write(tmp_path, "requirements.txt", "fastapi\n")
    deps.record(tmp_path, PYTHON)
    import shutil
    shutil.rmtree(tmp_path / ".venv")
    assert not deps.unchanged(tmp_path, PYTHON)


def test_node_stack_watches_package_json_and_the_lockfile(tmp_path):
    node = get_stack("node-express")
    (tmp_path / "node_modules").mkdir()
    _write(tmp_path, "package.json", "{}")
    deps.record(tmp_path, node)
    assert deps.unchanged(tmp_path, node)
    _write(tmp_path, "package-lock.json", "{}")
    assert not deps.unchanged(tmp_path, node)


def test_stacks_without_dependencies_never_skip_anything(tmp_path):
    static = get_stack("static-html")
    deps.record(tmp_path, static)
    assert not deps.unchanged(tmp_path, static) and deps.manifest_hash(tmp_path, static) is None


class FakeRunner:
    """Stands in for LocalRunner: records the steps, creates .venv like the real setup does."""

    def __init__(self, root, fail=()):
        self.root, self.fail, self.steps = root, set(fail), []

    def setup(self):
        (self.root / ".venv").mkdir(exist_ok=True)
        return None

    def run(self, name, timeout=None):
        self.steps.append(name)
        return CommandResult(name, 1 if name in self.fail else 0, "", "boom" if name in self.fail else "")


def project(requirements="fastapi\n", code="x = 1\n"):
    return [
        FileChange(path="requirements.txt", action="create", content=requirements, explanation="deps"),
        FileChange(path="app/__init__.py", action="create", content="", explanation="pkg"),
        FileChange(path="app/main.py", action="create", content=code, explanation="code"),
    ]


def test_a_retry_that_keeps_requirements_skips_install_and_a_changed_one_does_not():
    workspace = Workspace("p_skip")
    first, second, third = (FakeRunner(workspace.root) for _ in range(3))

    assert run_all_checks(workspace, project(), PYTHON, first) == []
    assert first.steps == ["install", "check_imports", "test"]

    assert run_all_checks(workspace, project(code="x = 2\n"), PYTHON, second) == []
    assert second.steps == ["check_imports", "test"]            # same requirements.txt: no install

    assert run_all_checks(workspace, project(requirements="fastapi\nuvicorn\n"), PYTHON, third) == []
    assert third.steps == ["install", "check_imports", "test"]  # requirements.txt changed: install again


def test_a_failed_install_is_never_trusted_next_time():
    workspace = Workspace("p_skip_fail")
    ok, broken, retry = FakeRunner(workspace.root), FakeRunner(workspace.root, fail={"install"}), FakeRunner(workspace.root)

    run_all_checks(workspace, project(), PYTHON, ok)
    errors = run_all_checks(workspace, project(requirements="nonexistent-pkg\n"), PYTHON, broken)
    assert errors and "Step 'install' failed" in errors[0]
    # The model "fixes" it by going back to the old file. The half-installed environment must not be trusted.
    run_all_checks(workspace, project(), PYTHON, retry)
    assert retry.steps[0] == "install"


def test_run_all_checks_measures_every_slow_step():
    workspace = Workspace("p_timed")
    timings = Timings()
    run_all_checks(workspace, project(), PYTHON, FakeRunner(workspace.root), timings=timings)
    assert {"setup", "install", "check_imports", "test"} <= set(timings.as_dict())


def test_run_all_checks_reports_progress_to_the_job():
    workspace = Workspace("p_progress")
    seen = []
    with progress.listening("p_progress", seen.append):
        run_all_checks(workspace, project(), PYTHON, FakeRunner(workspace.root))
        run_all_checks(workspace, project(code="x = 3\n"), PYTHON, FakeRunner(workspace.root))
    assert "Running install..." in seen and "Running test..." in seen
    assert "Dependencies unchanged - skipping install" in seen


# --- Docker package cache ---------------------------------------------------------------------

def docker(tmp_path):
    return DockerRunner(tmp_path / "project", PYTHON)


def test_install_containers_share_a_package_cache_and_the_others_never_see_it(tmp_path, monkeypatch):
    cache = tmp_path / "cache"
    monkeypatch.setattr(runner_module, "CACHE_DIR", cache)
    runner = docker(tmp_path)

    install = runner.docker_args("c1", ["pip"], network=True)
    assert f"{cache}:/cache" in install and "PIP_CACHE_DIR=/cache/pip" in install and "npm_config_cache=/cache/npm" in install
    assert (cache / "pip").is_dir() and (cache / "npm").is_dir()

    for detach in (False, True):   # the tests and the running app: no cache, or AI-written code could poison it
        offline = runner.docker_args("c2", ["pytest"], network=False, detach=detach, port=9101 if detach else None)
        assert not any("/cache" in part for part in offline)


def test_an_unwritable_cache_folder_does_not_stop_installs(tmp_path, monkeypatch):
    blocker = tmp_path / "blocker"
    blocker.write_text("a file, so a folder cannot be created under it")
    monkeypatch.setattr(runner_module, "CACHE_DIR", blocker / "cache")
    args = docker(tmp_path).docker_args("c3", ["pip"], network=True)
    assert not any("/cache" in part for part in args)


def test_the_real_install_command_gets_the_cache(tmp_path, monkeypatch):
    monkeypatch.setattr(runner_module, "CACHE_DIR", tmp_path / "cache")
    seen = []

    def fake_run(args, **kwargs):
        seen.append(args)
        return subprocess.CompletedProcess(args, 0, "", "")

    monkeypatch.setattr(runner_module.subprocess, "run", fake_run)
    runner = docker(tmp_path)
    runner.run("install")
    runner.run("test")
    install = next(args for args in seen if "pip" in args)
    test = next(args for args in seen if "pytest" in args)
    assert "PIP_CACHE_DIR=/cache/pip" in install and not any("/cache" in part for part in test)


# --- Configurable time limits -----------------------------------------------------------------

def test_time_limits_can_be_lowered_and_bad_values_fall_back(monkeypatch):
    monkeypatch.setenv("TEST_LIMIT_PROBE", "90")
    assert _seconds("TEST_LIMIT_PROBE", 300) == 90
    for bad in ("abc", "0", "-5", ""):
        monkeypatch.setenv("TEST_LIMIT_PROBE", bad)
        assert _seconds("TEST_LIMIT_PROBE", 300) == 300
    monkeypatch.delenv("TEST_LIMIT_PROBE")
    assert _seconds("TEST_LIMIT_PROBE", 300) == 300


# --- Through the graph and the service --------------------------------------------------------

class AlwaysBroken:
    def invoke(self, inputs):
        return DeveloperOutput(
            summary="broken",
            changes=[FileChange(path="a.py", action="create", content="def x(:\n", explanation="bad")],
        )


def test_the_generate_node_returns_the_time_spent_in_the_model(monkeypatch):
    monkeypatch.setattr(nodes, "developer_chain", AlwaysBroken())
    state = {"project_id": "p_node", "task": "x", "tech_stack": "Python", "stack": "python-fastapi",
             "validation_errors": [], "retries": 0, "timings": {"llm": 4.0}}
    delta = nodes.generate_node(state)
    assert delta["retries"] == 1 and delta["timings"]["llm"] >= 4.0


def test_a_state_without_timings_still_works(monkeypatch):
    """Older callers (scripts, QA repair fakes) build states with no 'timings' key."""
    monkeypatch.setattr(nodes, "developer_chain", AlwaysBroken())
    state = {"project_id": "p_node2", "task": "x", "tech_stack": "Python", "stack": "python-fastapi",
             "validation_errors": [], "retries": 0}
    assert "llm" in nodes.generate_node(state)["timings"]


def wait_for(client, project_id, job_id, timeout=60):
    deadline = time.time() + timeout
    while time.time() < deadline:
        job = client.get(f"/projects/{project_id}/jobs/{job_id}", headers=HEADERS).json()
        if job["status"] not in ("queued", "running"):
            return job
        time.sleep(0.2)
    raise AssertionError("job did not finish")


def test_the_job_log_says_where_the_time_went(monkeypatch):
    monkeypatch.setattr(nodes, "developer_chain", AlwaysBroken())
    client = TestClient(app)
    started = client.post("/projects/p_time/tasks", json={"task": "x"}, headers=HEADERS)
    job = wait_for(client, "p_time", started.json()["job_id"])
    messages = [entry["message"] for entry in job["log"]]
    assert any("asking Gemini" in message for message in messages)          # live progress
    assert any(message.startswith("Time spent: llm") for message in messages)
    assert "llm" in job["timings"]
    assert messages[-1].startswith("Finished:")                               # existing contract unchanged
    assert "p_time" not in progress._listeners                                # the job cleaned up after itself
