import pytest

from app.schemas.developer import FileChange
from app.stacks import STACKS, detect_stack, infer_stack_from_files
from app.tools.workspace import Workspace


@pytest.mark.parametrize("technologies, expected", [
    ("FastAPI, PostgreSQL, React", "python-fastapi"),
    ("Flask, SQLAlchemy", "python-fastapi"),
    ("Express, MongoDB", "node-express"),
    ("React, Node.js", "node-express"),
    ("HTML, CSS", "static-html"),
    ("Flask, Node", "python-fastapi"),   # Python wins when both are named
    ("", "python-fastapi"),
    ("Cobol", "python-fastapi"),
])
def test_stack_detection(technologies, expected):
    assert detect_stack(technologies) == expected


@pytest.mark.parametrize("files, expected", [
    (["package.json", "app.js"], "node-express"),
    (["requirements.txt", "app/main.py"], "python-fastapi"),
    (["index.html", "style.css"], "static-html"),
    ([], None),
])
def test_stack_is_inferred_from_existing_files(files, expected):
    assert infer_stack_from_files(files) == expected


def static_workspace(files: dict[str, str]):
    import uuid
    ws = Workspace("s_" + uuid.uuid4().hex[:8])
    ws.apply_changes([FileChange(path=p, action="create", content=c, explanation="t") for p, c in files.items()])
    return ws


def test_static_site_needs_an_index():
    errors = STACKS["static-html"].structure(static_workspace({"about.html": "<p>x</p>"}))
    assert errors == ["index.html is missing from the project root."]


def test_static_site_links_must_exist():
    page = '<link href="css/style.css" rel="stylesheet"><script src="js/app.js"></script><a href="https://x.dev">x</a><a href="#top">t</a>'
    errors = STACKS["static-html"].structure(static_workspace({"index.html": page, "css/style.css": "a{}"}))
    assert errors == ["index.html links to 'js/app.js', which does not exist in the project."]


def test_static_site_with_all_files_passes_and_handles_nested_pages():
    ws = static_workspace({
        "index.html": '<script src="/js/app.js"></script><a href="docs/page.html">d</a>',
        "docs/page.html": '<link href="../css/s.css" rel="stylesheet">',
        "js/app.js": "1", "css/s.css": "a{}",
    })
    assert STACKS["static-html"].structure(ws) == []


def test_only_python_is_syntax_checked_in_process():
    assert STACKS["python-fastapi"].syntax and not STACKS["node-express"].syntax
    bad = FileChange(path="a.py", action="create", content="def x(:\n", explanation="t")
    assert STACKS["python-fastapi"].syntax([bad])


def test_probe_rules_differ_per_stack():
    assert STACKS["python-fastapi"].probe_ok(404)      # an API may have no page at "/"
    assert not STACKS["python-fastapi"].probe_ok(500)
    assert STACKS["static-html"].probe_ok(200) and not STACKS["static-html"].probe_ok(404)
