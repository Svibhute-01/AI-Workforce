"""Starts, watches and stops the preview app of a project (the thing the user opens in a browser)."""

import socket
import threading
import time

from app.config import APP_PORT_RANGE, APP_PUBLIC_HOST, APP_TTL_SECONDS, APPS_DIR
from app.tools.runner import make_runner
from app.tools.smoke import wait_until_up


class AppError(Exception):
    def __init__(self, message: str, status_code: int = 409):
        super().__init__(message)
        self.status_code = status_code


def _port_is_free(port: int) -> bool:
    with socket.socket() as sock:
        try:
            sock.bind(("127.0.0.1", port))
            return True
        except OSError:
            return False


class AppManager:
    """At most one running preview per project. It stops by itself after APP_TTL_SECONDS."""

    def __init__(self, ttl: int = APP_TTL_SECONDS, port_range: tuple[int, int] = APP_PORT_RANGE):
        self._ttl, self._range = ttl, port_range
        self._lock = threading.Lock()
        self._apps: dict[str, dict] = {}

    def _free_port(self) -> int:
        used = {entry["port"] for entry in self._apps.values()}
        for port in range(self._range[0], self._range[1] + 1):
            if port not in used and _port_is_free(port):
                return port
        raise AppError("No free port is available for a preview right now.")

    def start(self, project_id: str, workspace, stack) -> dict:
        if not stack.start:
            raise AppError("This stack cannot be started.", 400)
        runner = make_runner(workspace.root, stack)
        if not workspace.list_files():
            raise AppError("This project has no files yet. Run a task first.")
        if not runner.env_ready():
            raise AppError("Dependencies are not installed yet. Run a task first (or press Install).")

        with self._lock:
            self._stop_locked(project_id)
            port = self._free_port()
            try:
                handle = runner.start_app(port, APPS_DIR / f"{project_id}.log")
            except (OSError, RuntimeError) as exc:
                raise AppError(f"The app could not be started: {exc}")
            timer = threading.Timer(self._ttl, self.stop, [project_id])
            timer.daemon = True
            timer.start()
            self._apps[project_id] = {"handle": handle, "port": port, "started": time.time(), "timer": timer}

        problem = wait_until_up(handle, port, stack, seconds=30)
        if problem:
            log = handle.log_tail()
            self.stop(project_id)
            raise AppError(f"The app started but is not usable. {problem}", 422 if log else 409)
        return self.status(project_id)

    def _stop_locked(self, project_id: str) -> bool:
        entry = self._apps.pop(project_id, None)
        if not entry:
            return False
        entry["timer"].cancel()
        entry["handle"].stop()
        return True

    def stop(self, project_id: str) -> bool:
        with self._lock:
            return self._stop_locked(project_id)

    def stop_all(self) -> None:
        with self._lock:
            for project_id in list(self._apps):
                self._stop_locked(project_id)

    def status(self, project_id: str) -> dict:
        with self._lock:
            entry = self._apps.get(project_id)
            if entry and not entry["handle"].alive():   # it crashed after starting
                log = entry["handle"].log_tail()
                self._stop_locked(project_id)
                return {"running": False, "log": log, "note": "The app stopped on its own."}
            if not entry:
                return {"running": False, "log": "", "note": ""}
            return {
                "running": True,
                "port": entry["port"],
                "url": f"http://{APP_PUBLIC_HOST}:{entry['port']}/",
                "started_at": entry["started"],
                "expires_at": entry["started"] + self._ttl,
                "log": entry["handle"].log_tail(),
                "note": "",
            }
