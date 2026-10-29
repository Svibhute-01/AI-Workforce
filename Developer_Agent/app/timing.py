"""A tiny stopwatch that shows where a Developer run spends its time.

Every slow step (the Gemini call, install, import check, tests, smoke check) is measured and the
totals are written to the job log, so "why is it slow?" can be answered from the job itself.
"""

import time
from contextlib import contextmanager


class Timings:
    """Seconds spent per label. Values are summed when a label is measured more than once (retries)."""

    def __init__(self, seen: dict[str, float] | None = None):
        self._seconds: dict[str, float] = dict(seen or {})

    def add(self, label: str, seconds: float) -> None:
        self._seconds[label] = round(self._seconds.get(label, 0.0) + seconds, 2)

    @contextmanager
    def measure(self, label: str):
        started = time.perf_counter()
        try:
            yield
        finally:
            self.add(label, time.perf_counter() - started)

    def as_dict(self) -> dict[str, float]:
        return dict(self._seconds)


def format_timings(seconds: dict[str, float] | None) -> str:
    """'llm 42.1s, install 80.3s, test 12.0s (total 134.4s)' - empty string when nothing was measured."""
    if not seconds:
        return ""
    parts = ", ".join(f"{label} {value:.1f}s" for label, value in seconds.items())
    return f"{parts} (total {sum(seconds.values()):.1f}s)"
