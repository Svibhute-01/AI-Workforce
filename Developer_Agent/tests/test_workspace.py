import sys

import pytest

from app.schemas.developer import FileChange
from app.tools.workspace import Workspace, WorkspaceError


def fc(path, content="x = 1\n", action="create"):
    return FileChange(path=path, action=action, content=content, explanation="t")


@pytest.fixture
def ws():
    import uuid
    return Workspace("t_" + uuid.uuid4().hex[:8])


def test_write_read_and_list(ws):
    ws.apply_changes([fc("app/main.py"), fc("requirements.txt", "fastapi\n")])
    assert ws.list_files() == ["app/main.py", "requirements.txt"]
    assert ws.read_file("app/main.py") == "x = 1\n"


WINDOWS_DRIVE = pytest.param(
    "C:/Windows/x.txt", marks=pytest.mark.skipif(sys.platform != "win32", reason="a drive path is only absolute on Windows")
)


@pytest.mark.parametrize("bad", ["../escape.txt", "../../escape.txt", "app/../../escape.txt", "/etc/passwd", WINDOWS_DRIVE])
def test_paths_escaping_the_workspace_are_refused(ws, bad):
    with pytest.raises(WorkspaceError):
        ws.write_file(bad, "no")


def test_protected_folders_are_refused(ws):
    with pytest.raises(WorkspaceError):
        ws.write_file(".venv/x.py", "no")


@pytest.mark.parametrize("bad_id", ["../hack", "a/b", "", "a b"])
def test_invalid_project_ids_are_refused(bad_id):
    with pytest.raises(WorkspaceError):
        Workspace(bad_id)


def test_delete_removes_file_and_empty_folders(ws):
    ws.apply_changes([fc("app/routers/auth.py"), fc("app/routes/auth.py")])
    ws.apply_changes([fc("app/routers/auth.py", "", "delete")])
    assert ws.list_files() == ["app/routes/auth.py"]
    assert not (ws.root / "app" / "routers").exists()
    assert ws.delete_file("missing.py") is False
