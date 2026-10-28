from pathlib import Path

from app.qa.test_runner import run_pytest


def test_missing_tests_directory_is_inconclusive(tmp_path: Path):
    result = run_pytest(str(tmp_path))
    assert result["status"] == "inconclusive"
    assert "No tests directory" in result["message"]


def test_pytest_runner_reports_real_test_counts(tmp_path: Path):
    tests = tmp_path / "tests"
    tests.mkdir()
    (tests / "test_example.py").write_text(
        "def test_example():\n    assert 2 + 2 == 4\n",
        encoding="utf-8",
    )
    result = run_pytest(str(tmp_path), timeout=30)
    # The host running this test suite is expected to have pytest installed.
    assert result["status"] == "passed", result
    assert result["passed"] == 1
    assert result["failed"] == 0
    assert result["total"] == 1
