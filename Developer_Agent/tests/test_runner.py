import subprocess

import pytest

from app.prompts.developer import ENVIRONMENT_RULES
from app.tools import runner as runner_module
from app.tools.runner import TIMEOUTS, LocalRunner


def test_timeout_keeps_the_partial_output(tmp_path, monkeypatch):
    def slow(*args, **kwargs):
        raise subprocess.TimeoutExpired(args[0], kwargs["timeout"], output=b"Collecting fastapi\n", stderr=b"building wheel")

    monkeypatch.setattr(runner_module.subprocess, "run", slow)
    result = LocalRunner(tmp_path).run("install")
    assert not result.ok
    summary = result.summary()
    assert "Collecting fastapi" in summary and "building wheel" in summary
    assert f"Timed out after {TIMEOUTS['install']}s" in summary


def test_install_prefers_wheels_and_has_the_longest_limit(tmp_path):
    command = LocalRunner(tmp_path)._commands()["install"]
    assert "--prefer-binary" in command
    assert TIMEOUTS["install"] > TIMEOUTS["test"] > TIMEOUTS["check_imports"]


def test_unknown_commands_are_still_refused(tmp_path):
    with pytest.raises(ValueError):
        LocalRunner(tmp_path).run("rm -rf /")


def test_the_prompt_tells_the_model_about_the_environment():
    for rule in ("requirements.txt", "psycopg2", "bcrypt", "SQLite", "tests/"):
        assert rule in ENVIRONMENT_RULES
