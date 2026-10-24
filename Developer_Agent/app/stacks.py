"""Stack profiles: everything that differs between kinds of project.

The graph, the retry loop and the API are the same for every stack. A profile supplies the
instructions Gemini receives, the commands that install, check and start the project, and the
checks that run before the commands.

Command templates use these tokens, filled in by the runner:
  {py}           the project's own Python (virtual environment)
  {host_python}  a Python able to create that environment
  {node} {npm}   the Node tools
  {host} {port}  where a started app listens
"""

import re
from dataclasses import dataclass, field
from typing import Callable

from app.config import NODE_IMAGE, PYTHON_IMAGE
from app.tools.validators import validate_python_syntax, validate_static_site

DEFAULT_STACK = "python-fastapi"


@dataclass(frozen=True)
class Stack:
    id: str
    label: str
    image: str
    rules: str
    commands: dict[str, list[str]]                 # name -> command template (an allowlist)
    steps: tuple[str, ...]                         # commands every check run executes, in order
    start: list[str] | None                        # how to start the app; None = cannot be started
    needs_env: str | None = None                   # folder that proves dependencies are installed
    setup: list[str] | None = None                 # one-off command that creates that environment
    syntax: Callable | None = None                 # in-process check before anything is written
    structure: Callable | None = None              # in-process check after the files are written
    probe_ok: Callable[[int], bool] = field(default=lambda status: status < 500)
    keywords: tuple[str, ...] = ()

    @property
    def visible_commands(self) -> list[str]:
        return [name for name in ("install", "check_imports", "test") if name in self.commands]


PYTHON_RULES = (
    "ENVIRONMENT RULES (your code is installed and tested automatically, so follow these exactly): "
    "1. Python {python_version}, on Windows or Linux. Packages come from PyPI into a fresh virtual environment "
    "with a time limit. "
    "2. Layout: ONE requirements.txt in the project root; a Python package app/ (with __init__.py) whose "
    "app/main.py defines the FastAPI object named 'app'; tests in tests/ that run with 'python -m pytest' from "
    "the project root. Do not use backend/ or frontend/ folders and do not create a second requirements file. "
    "3. requirements.txt: list only packages the code really imports, with NO exact version pins "
    "(plain names or '>=' ranges), and always include fastapi, uvicorn and pytest, plus httpx if tests use a "
    "TestClient. Never use packages that compile from source (psycopg2, psycopg2-binary, mysqlclient, and similar). "
    "4. Database: use SQLAlchemy and make the database URL configurable through an environment variable "
    "that defaults to SQLite, so tests run without any server. "
    "5. Hash passwords with the 'bcrypt' package directly, not passlib. "
    "6. After the tests pass, the app is started with 'uvicorn app.main:app' and GET / is requested, so the app "
    "must import and start with no setup. If the task needs a web page, serve HTML from the same app "
    "(HTMLResponse, or Jinja2 templates with jinja2 in requirements.txt, or StaticFiles) and make GET / return it. "
    "7. Write only the files this stack needs. Do not create Docker or deployment files: they cannot be verified here. "
    "8. Tests must not need the network, secrets or external services. "
    "9. If the feedback says installing failed, the cause is almost always requirements.txt: shorten it, "
    "remove pins and compiled packages."
)

NODE_RULES = (
    "ENVIRONMENT RULES (your code is installed and tested automatically, so follow these exactly): "
    "1. Node.js 20 with npm, CommonJS modules (require / module.exports). Packages come from the npm registry. "
    "2. Layout: package.json in the project root with the scripts \"start\": \"node server.js\" and "
    "\"test\": \"node --test\"; app.js creates the Express app and exports it with module.exports = app WITHOUT "
    "calling listen; server.js requires ./app and listens on process.env.PORT (default 3000) and host "
    "process.env.HOST (default 127.0.0.1); tests live in test/ and end in .test.js. "
    "3. package.json dependencies: list only packages the code really requires; use \"*\" as the version unless "
    "you are sure a range exists. Do not use native modules that compile (better-sqlite3, bcrypt, sqlite3): keep "
    "data in memory or in a JSON file, and use 'crypto' (scrypt) for password hashing. "
    "4. Tests use the built-in node:test and node:assert. To test HTTP, start the app with app.listen(0) inside the "
    "test and call it with the built-in fetch; close the server at the end. Tests must not need the network, "
    "secrets or external services. "
    "5. After the tests pass, 'node server.js' is started and GET / is requested, so the app must start with no "
    "setup and GET / must answer. If the task needs a web page, serve it from the same app (express.static on a "
    "public/ folder, or res.send of HTML). "
    "6. Write only the files this stack needs. Do not create Docker or deployment files. "
    "7. If the feedback says installing failed, the cause is almost always package.json: remove packages and "
    "version pins."
)

STATIC_RULES = (
    "ENVIRONMENT RULES (your files are checked and then served as a static website): "
    "1. Plain HTML, CSS and JavaScript only. No build step, no npm, no frameworks that need compiling, no "
    "backend code. "
    "2. index.html must be in the project root. Link other files with relative paths (css/style.css, js/app.js); "
    "every file you reference must be one you create. Avoid external CDNs and remote fonts: the page must work "
    "offline. "
    "3. Keep state in the browser (localStorage) when the task needs to remember things. "
    "4. After the files are written, the folder is served and GET / must return index.html with status 200. "
    "5. Write only the files this stack needs. Do not create Docker or deployment files."
)

STACKS: dict[str, Stack] = {
    "python-fastapi": Stack(
        id="python-fastapi",
        label="Python / FastAPI",
        image=PYTHON_IMAGE,
        rules=PYTHON_RULES,
        needs_env=".venv",
        setup=["{host_python}", "-m", "venv", ".venv"],
        commands={
            "install": ["{py}", "-m", "pip", "install", "--prefer-binary", "--disable-pip-version-check",
                        "--no-input", "-r", "requirements.txt"],
            "check_imports": ["{py}", "-c", "import app.main"],
            "test": ["{py}", "-m", "pytest", "-x", "-q"],
        },
        steps=("install", "check_imports", "test"),
        start=["{py}", "-m", "uvicorn", "app.main:app", "--host", "{host}", "--port", "{port}"],
        syntax=validate_python_syntax,
        keywords=("fastapi", "python", "flask", "django", "uvicorn", "pydantic", "sqlalchemy"),
    ),
    "node-express": Stack(
        id="node-express",
        label="Node.js / Express",
        image=NODE_IMAGE,
        rules=NODE_RULES,
        needs_env="node_modules",
        commands={
            "install": ["{npm}", "install", "--no-audit", "--no-fund", "--loglevel=error"],
            "check_imports": ["{node}", "-e", "require('./app')"],
            "test": ["{npm}", "test", "--silent"],
        },
        steps=("install", "check_imports", "test"),
        start=["{node}", "server.js"],
        keywords=("express", "node", "nodejs", "node.js", "npm"),
    ),
    "static-html": Stack(
        id="static-html",
        label="Static HTML / CSS / JS",
        image=PYTHON_IMAGE,
        rules=STATIC_RULES,
        commands={},
        steps=(),
        start=["{host_python}", "-m", "http.server", "{port}", "--bind", "{host}"],
        structure=validate_static_site,
        probe_ok=lambda status: status == 200,
        keywords=("html", "css", "static", "vanilla", "javascript website"),
    ),
}


def rules_for(stack: Stack) -> str:
    import sys
    return stack.rules.replace("{python_version}", f"{sys.version_info.major}.{sys.version_info.minor}")


def get_stack(stack_id: str | None) -> Stack:
    return STACKS[stack_id or DEFAULT_STACK]


def detect_stack(tech_stack: str) -> str:
    """Pick a stack from the Architect's technology list. Python wins when both are named,
    because a Python API is the part the agent can fully verify."""
    words = set(re.findall(r"[a-z0-9.+#]+", (tech_stack or "").lower()))
    scores = {
        stack.id: sum(1 for keyword in stack.keywords if keyword in words or keyword in (tech_stack or "").lower())
        for stack in STACKS.values()
    }
    if scores["python-fastapi"] and scores["python-fastapi"] >= scores["node-express"]:
        return "python-fastapi"
    if scores["node-express"]:
        return "node-express"
    if scores["static-html"]:
        return "static-html"
    return DEFAULT_STACK


def infer_stack_from_files(files: list[str]) -> str | None:
    """Best guess for a project that has files but no recorded stack (made before stacks existed)."""
    if "package.json" in files:
        return "node-express"
    if any(name.endswith(".py") for name in files) or "requirements.txt" in files:
        return "python-fastapi"
    if "index.html" in files:
        return "static-html"
    return None
