# Developer Agent service

Turns one Project Manager task into working, tested code. It runs as its own service
because its LangChain stack needs a newer `google-genai` than the main backend pins.
The browser never calls it: the main AI Workforce backend authenticates the user,
checks project ownership and forwards requests with a shared key.

```text
Browser -> AI Workforce backend (:8000, JWT) -> Developer Agent (:8001, X-Service-Key)
```

## How a task runs

`generate` (Gemini, structured output) -> `validate` (syntax check, write files, create a
per-project venv, `pip install`, import check, `pytest`) -> on failure the real error text
goes back to `generate`, up to `MAX_RETRIES` attempts -> `success` or `failed`.

Files are written only inside `workspaces/<project_id>/`. Commands are allowlisted by name
(`create_venv`, `install`, `check_imports`, `test`) and always time-limited.
**There is no sandbox**: generated code runs with your user's permissions. Run this service on
a machine you are willing to run AI-written code on (a container or VM is the safe option).

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
| `WORKSPACES_DIR`, `JOBS_DIR` | Where projects and job records are stored |

If `DEVELOPER_SERVICE_KEY` is empty the API is unauthenticated, so keep it bound to `127.0.0.1`.

## API (called by the main backend)

| Endpoint | Purpose |
|---|---|
| `POST /projects/{id}/tasks` | Start a task; returns a job (202). One active job per project |
| `GET /projects/{id}/jobs/{job_id}` | Status, attempts, progress log, changed files, errors |
| `GET /projects/{id}/files`, `GET /projects/{id}/file?path=` | Workspace browsing |
| `POST /projects/{id}/run` | Run an allowlisted command by name |

## Tests

```bash
pytest tests        # fake model, no Gemini quota used
```
