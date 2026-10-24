# Developer Agent service

Turns one Project Manager task into working, tested code. It runs as its own service
because its LangChain stack needs a newer `google-genai` than the main backend pins.
The browser never calls it: the main AI Workforce backend authenticates the user,
checks project ownership and forwards requests with a shared key.

```text
Browser -> AI Workforce backend (:8000, JWT) -> Developer Agent (:8001, X-Service-Key)
```

## How a task runs

`generate` (Gemini, structured output) -> `validate` (syntax check, write files, install,
import check, tests, then **start the app and request `/`**) -> on failure the real error text goes
back to `generate`, up to `MAX_RETRIES` attempts -> `success` or `failed`.

Files are written only inside `workspaces/<project_id>/`. Commands are allowlisted by name and
always time-limited. Child processes get a scrubbed environment: they cannot read `GOOGLE_API_KEY`
or the service key.

## Stacks

A project uses one **stack profile** (`app/stacks.py`): it decides the rules Gemini receives, the
install/check/start commands, and the checks that run.

| Stack | Checks | App started with |
|---|---|---|
| `python-fastapi` (default) | syntax, `pip install`, import, `pytest`, smoke | `uvicorn app.main:app` |
| `node-express` | `npm install`, `require('./app')`, `npm test`, smoke | `node server.js` |
| `static-html` | `index.html` exists, local links resolve, smoke | a static file server |

The first task chooses the stack (from the Architect's technology list, or explicitly), and the project
keeps it. To add a stack, add a profile; the graph, API and UI need no change.

## Running commands: local or Docker

`RUNNER_MODE=local` (default) runs commands on this machine. `RUNNER_MODE=docker` runs every command in a
throw-away container with only the project folder mounted, memory/CPU limited, and **no network except
for installs**. Docker mode needs Docker running. Do not switch a project between modes: a Python
environment created in one cannot be used by the other (delete the project's `workspaces/` folder first).

## Preview app

`POST /projects/{id}/app/start` starts the generated app on a free port in `9100-9199`, bound to
`127.0.0.1`, and returns its URL. It stops by itself after `APP_TTL_SECONDS` (15 minutes), when a new task
starts, or on `POST .../app/stop`. From another machine the URL must be proxied; `APP_PUBLIC_HOST` sets the
host the browser is told to use.

**Security.** Local mode runs AI-written code on the host with your user's permissions. Use Docker mode for
anything beyond your own machine.

## Setup

```bash
cd Developer_Agent
python -m venv .venv && source .venv/bin/activate     # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env                                  # then fill in the values
python -m uvicorn app.main:app --host 127.0.0.1 --port 8001 --reload-dir app
```

| Variable | Purpose |
|---|---|
| `GOOGLE_API_KEY` | Gemini key (required) |
| `GEMINI_MODEL` | Model name; change it if a model's free quota is used up |
| `DEVELOPER_SERVICE_KEY` | Shared secret. Must equal `DEVELOPER_AGENT_KEY` in the main backend |
| `CONTEXT_MODE` | `all_files` (default) or `rag` |
| `RUNNER_MODE` | `local` (default) or `docker` |
| `PYTHON_IMAGE`, `NODE_IMAGE` | Docker images used in docker mode |
| `SMOKE_CHECK` | `true` (default): start the app after the tests and request `/` |
| `APP_TTL_SECONDS`, `APP_PUBLIC_HOST` | Preview lifetime, and the host used in the preview URL |
| `WORKSPACES_DIR`, `JOBS_DIR` | Where projects and job records are stored |

If `DEVELOPER_SERVICE_KEY` is empty the API is unauthenticated, so keep it bound to `127.0.0.1`.

## API (called by the main backend)

| Endpoint | Purpose |
|---|---|
| `POST /projects/{id}/tasks` | Start a task; returns a job (202). One active job per project |
| `GET /projects/{id}/jobs/{job_id}` | Status, attempts, progress log, changed files, errors |
| `GET /projects/{id}/files`, `GET /projects/{id}/file?path=` | Workspace browsing |
| `POST /projects/{id}/run` | Run an allowlisted command (`install`, `check_imports`, `test`) the project's stack supports |
| `GET /projects/{id}/stack`, `GET /stacks` | The project's stack and its commands; the supported stacks |
| `GET/POST /projects/{id}/app`, `/app/start`, `/app/stop` | Preview app status, start, stop |

## Tests

```bash
pytest tests        # fake model, no Gemini quota used
```
