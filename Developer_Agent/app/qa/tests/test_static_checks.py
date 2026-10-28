from pathlib import Path

from app.qa.static_checks import run_static_checks
from app.qa.reporting import build_developer_feedback, write_report


def test_static_checks_detect_python_syntax_error(tmp_path: Path):
    (tmp_path / "broken.py").write_text("def broken(:\n    pass\n", encoding="utf-8")
    result = run_static_checks(str(tmp_path))
    assert result["syntax"]["status"] == "failed"
    assert result["syntax"]["issues"][0]["file"] == "broken.py"


def test_static_checks_pass_valid_python(tmp_path: Path):
    (tmp_path / "valid.py").write_text("answer = 42\n", encoding="utf-8")
    result = run_static_checks(str(tmp_path))
    assert result["syntax"]["status"] == "passed"
    assert result["syntax"]["checked"] == 1


def test_feedback_includes_failed_criterion():
    result = build_developer_feedback({
        "criteria": [{"id": "C1", "verdict": "FAIL", "reason": "Expected 201, got 500"}],
        "static_checks": {},
        "test_suite": {"status": "passed"},
    })
    assert result["issue_count"] == 1
    assert result["issues"][0]["criterion_id"] == "C1"


def test_report_is_written_as_json(tmp_path: Path):
    path = write_report(str(tmp_path), {"verdict": "PASS"})
    assert path is not None
    assert Path(path).read_text(encoding="utf-8").find('"verdict": "PASS"') >= 0
