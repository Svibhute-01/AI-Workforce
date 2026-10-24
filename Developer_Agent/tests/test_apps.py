import time
import uuid

import pytest

from app.apps import AppError, AppManager
from app.schemas.developer import FileChange
from app.stacks import get_stack
from app.tools.checks import run_all_checks
from app.tools.runner import LocalRunner
from app.tools.smoke import probe, smoke_check, wait_until_up
from app.tools.workspace import Workspace


def site(extra=None):
    ws = Workspace("a_" + uuid.uuid4().hex[:8])
    files = {"index.html": "<html><body><h1>Hello preview</h1></body></html>"}
    files.update(extra or {})
    ws.apply_changes([FileChange(path=p, action="create", content=c, explanation="t") for p, c in files.items()])
    return ws


def test_smoke_check_passes_for_a_working_static_site():
    ws = site()
    assert smoke_check(LocalRunner(ws.root, get_stack("static-html")), get_stack("static-html")) is None


class _Alive:
    def alive(self):
        return True

    def log_tail(self, max_chars=3000):
        return "server log"


def _serve_status(status):
    import threading
    from http.server import BaseHTTPRequestHandler, HTTPServer

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(status)
            self.end_headers()

        def log_message(self, *args):
            pass

    server = HTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server


def test_a_server_error_at_the_root_fails_the_smoke_check():
    server = _serve_status(500)
    try:
        message = wait_until_up(_Alive(), server.server_address[1], get_stack("python-fastapi"), seconds=5)
    finally:
        server.shutdown()
    assert message and "500" in message and "server log" in message


def test_an_api_with_no_page_at_the_root_still_counts_as_up():
    server = _serve_status(404)
    try:
        assert wait_until_up(_Alive(), server.server_address[1], get_stack("python-fastapi"), seconds=5) is None
        assert "404" in wait_until_up(_Alive(), server.server_address[1], get_stack("static-html"), seconds=5)
    finally:
        server.shutdown()


def test_an_app_that_never_answers_times_out_with_its_log():
    message = wait_until_up(_Alive(), 1, get_stack("python-fastapi"), seconds=1)
    assert "did not answer" in message and "server log" in message


def test_smoke_check_reports_an_app_that_crashes_at_start():
    ws = Workspace("a_" + uuid.uuid4().hex[:8])
    stack = get_stack("python-fastapi")
    runner = LocalRunner(ws.root, stack)
    # No virtual environment exists, so the start command cannot run at all.
    problem = smoke_check(runner, stack)
    assert problem and "Smoke check failed" in problem


def test_full_checks_for_a_static_site_include_the_smoke_check(monkeypatch):
    monkeypatch.setattr("app.tools.checks.SMOKE_CHECK", True)
    ws = Workspace("a_" + uuid.uuid4().hex[:8])
    changes = [FileChange(path="index.html", action="create", content="<h1>ok</h1>", explanation="t")]
    assert run_all_checks(ws, changes, get_stack("static-html")) == []
    broken = [FileChange(path="index.html", action="create", content='<script src="x.js"></script>', explanation="t")]
    assert "does not exist" in run_all_checks(ws, broken, get_stack("static-html"))[0]


def test_preview_starts_serves_and_stops():
    manager = AppManager(ttl=60)
    ws = site()
    stack = get_stack("static-html")
    status = manager.start(ws.root.name, ws, stack)
    try:
        assert status["running"] and status["url"].startswith("http://127.0.0.1:91")
        assert probe(status["url"]) == 200
        assert manager.status(ws.root.name)["running"]
    finally:
        assert manager.stop(ws.root.name) is True
    assert manager.status(ws.root.name)["running"] is False
    assert probe(status["url"], timeout=1) is None
    assert manager.stop(ws.root.name) is False


def test_starting_again_replaces_the_previous_preview():
    manager = AppManager(ttl=60)
    ws = site()
    first = manager.start(ws.root.name, ws, get_stack("static-html"))
    second = manager.start(ws.root.name, ws, get_stack("static-html"))
    try:
        assert probe(second["url"]) == 200
        assert probe(first["url"], timeout=1) is None or first["port"] == second["port"]
    finally:
        manager.stop_all()


def test_preview_stops_by_itself_after_the_time_limit():
    manager = AppManager(ttl=1)
    ws = site()
    manager.start(ws.root.name, ws, get_stack("static-html"))
    time.sleep(2.5)
    assert manager.status(ws.root.name)["running"] is False


def test_preview_refuses_an_empty_project_or_missing_dependencies():
    manager = AppManager()
    with pytest.raises(AppError, match="no files"):
        manager.start("x", Workspace("a_" + uuid.uuid4().hex[:8]), get_stack("static-html"))
    ws = site({"requirements.txt": "fastapi\n"})
    with pytest.raises(AppError, match="not installed"):
        manager.start(ws.root.name, ws, get_stack("python-fastapi"))
