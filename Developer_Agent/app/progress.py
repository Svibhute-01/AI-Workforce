"""Live progress messages from deep inside a run (for example "Running install...").

A job registers a listener for its project before the graph starts; code that is far from the job
(the check runner) reports through the project id. Only one job can be active per project, so the
project id is a safe key. Reporting never raises, and does nothing when nobody is listening.
"""

import threading
from collections.abc import Callable
from contextlib import contextmanager

_lock = threading.Lock()
_listeners: dict[str, Callable[[str], None]] = {}


def register(project_id: str, listener: Callable[[str], None]) -> None:
    with _lock:
        _listeners[project_id] = listener


def unregister(project_id: str) -> None:
    with _lock:
        _listeners.pop(project_id, None)


@contextmanager
def listening(project_id: str, listener: Callable[[str], None]):
    register(project_id, listener)
    try:
        yield
    finally:
        unregister(project_id)


def report(project_id: str, message: str) -> None:
    with _lock:
        listener = _listeners.get(project_id)
    if listener is None:
        return
    try:
        listener(message)
    except Exception:  # noqa: BLE001 - progress is best effort and must never break a run
        pass
