"""A dropped connection to the model service is retried; real mistakes are not."""

import pytest

import app.graph.nodes as nodes
from app import llm_retry, progress
from app.llm_retry import call_with_retries, is_transient
from app.schemas.developer import DeveloperOutput, FileChange


class ReadError(Exception):
    """Same name as httpx.ReadError, which is what the real crash raised."""


@pytest.fixture(autouse=True)
def no_waiting(monkeypatch):
    monkeypatch.setattr(llm_retry.time, "sleep", lambda seconds: None)


def test_the_crash_from_the_field_is_recognised_as_temporary():
    wrapped = ReadError("[WinError 10054] An existing connection was forcibly closed by the remote host")
    outer = RuntimeError("generate failed")
    outer.__cause__ = wrapped
    assert is_transient(wrapped) and is_transient(outer) and is_transient(ConnectionResetError(10054, "reset"))


@pytest.mark.parametrize("error", [
    TimeoutError("slow"), Exception("429 RESOURCE_EXHAUSTED: quota"), Exception("503 Service Unavailable"),
    Exception("Server disconnected without sending a response"), type("ReadTimeout", (Exception,), {})("x"),
])
def test_busy_or_dropped_connections_are_temporary(error):
    assert is_transient(error)


@pytest.mark.parametrize("error", [
    PermissionError("access denied"), Exception("401 API key not valid"), Exception("400 bad request: invalid schema"),
    KeyError("task"),
    # a parsing failure quotes the model's own text, which may contain these words
    ValueError("could not parse: the app is unavailable and returned 429 and 503"),
])
def test_real_mistakes_are_never_retried(error):
    assert not is_transient(error)


def test_a_flaky_call_is_retried_until_it_works():
    calls, told = [], []

    def flaky():
        calls.append(1)
        if len(calls) < 3:
            raise ReadError("[WinError 10054] connection forcibly closed")
        return "answer"

    result = call_with_retries(flaky, attempts=3, on_retry=lambda *info: told.append(info))
    assert result == "answer" and len(calls) == 3 and [info[0] for info in told] == [1, 2]
    assert [info[3] for info in told] == [3, 8]            # the pauses, in seconds


def test_giving_up_explains_what_to_check():
    def always():
        raise ReadError("[WinError 10054] connection forcibly closed")

    with pytest.raises(RuntimeError) as error:
        call_with_retries(always, attempts=2)
    assert "after 2 attempts" in str(error.value) and "VPN" in str(error.value)
    assert isinstance(error.value.__cause__, ReadError)


def test_a_real_error_fails_immediately_and_unchanged():
    calls = []

    def wrong_key():
        calls.append(1)
        raise Exception("401 API key not valid")

    with pytest.raises(Exception) as error:
        call_with_retries(wrong_key, attempts=3)
    assert len(calls) == 1 and "401" in str(error.value)


def test_one_attempt_means_no_retrying_and_the_original_error():
    def always():
        raise ReadError("10054")

    with pytest.raises(ReadError):
        call_with_retries(always, attempts=1)


def test_the_attempt_count_comes_from_the_environment(monkeypatch):
    for value, expected in (("5", 5), ("0", 1), ("99", 6), ("abc", 3), ("1", 1)):
        monkeypatch.setenv("LLM_CALL_ATTEMPTS", value)
        assert llm_retry.attempts_from_env() == expected
    monkeypatch.delenv("LLM_CALL_ATTEMPTS")
    assert llm_retry.attempts_from_env() == 3


class DropsOnce:
    def __init__(self):
        self.calls = 0

    def invoke(self, inputs):
        self.calls += 1
        if self.calls == 1:
            raise ReadError("[WinError 10054] An existing connection was forcibly closed by the remote host")
        return DeveloperOutput(
            summary="ok", changes=[FileChange(path="a.py", action="create", content="x = 1\n", explanation="e")])


def test_the_generate_step_survives_a_dropped_connection_and_says_so(monkeypatch):
    chain = DropsOnce()
    monkeypatch.setattr(nodes, "developer_chain", chain)
    state = {"project_id": "p_retry", "task": "x", "tech_stack": "Python", "stack": "python-fastapi",
             "validation_errors": [], "retries": 0}
    seen = []
    with progress.listening("p_retry", seen.append):
        delta = nodes.generate_node(state)
    assert chain.calls == 2 and delta["output"].summary == "ok" and delta["retries"] == 1
    assert any("Model call failed (ReadError)" in message and "call 2 of 3" in message for message in seen)
