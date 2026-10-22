# AI Workforce backend

This backend serves the Requirements Analyst, Project Manager, System Architect and
Developer AI agents. Developer AI runs as a separate service (see below); QA AI is not built yet.

## Architecture

1. An authenticated user creates a project.
2. The existing Documents page uploads an SRS PDF to FastAPI.
3. `pypdf` extracts page-level text and a bounded chunker preserves page/source metadata.
4. Gemini creates embeddings; Chroma stores vectors in a collection isolated by project ID.
5. The Requirements Analyst retrieves only that project's chunks and asks Gemini for
   validated structured output.
6. Requirements, user stories, acceptance criteria, dependencies, ambiguities,
   constraints, risks, and agent runs are saved as relational PostgreSQL records.
7. The existing React application reads the API records.

## Secrets and environment

Set these in Replit Secrets/environment variables:

- `DATABASE_URL`: Replit PostgreSQL connection string (provided by the managed database).
- `JWT_SECRET`: a long random signing secret.
- `GEMINI_API_KEY`: Gemini API key.
- `CHROMA_PERSIST_DIRECTORY`: usually `./data/chroma`.
- `CORS_ORIGINS`: comma-separated frontend origins.

Optional settings are documented in `.env.example`. The app uses a local SQLite
development fallback when `DATABASE_URL` is absent, but PostgreSQL is required
for a real deployment. Document processing and analysis fail clearly when
`GEMINI_API_KEY` is absent; the backend never fabricates results.

## Run

From the repository root:

```bash
python -m uvicorn app.main:app --app-dir backend --host 0.0.0.0 --port 8000
```

The interactive API documentation is available at `/docs`.

The frontend runs separately with:

```bash
cd frontend
npm run dev
```

Vite proxies `/api` requests to the backend on port 8000.

## Test

```bash
PYTHONPATH=backend pytest backend/tests
```

The unit tests cover PDF validation, page/source-preserving chunking, and
structured output validation. Provider-backed integration tests should use a
real Gemini secret and a test PostgreSQL/Chroma directory.

## Current limitations

- Analysis is synchronous during the request; a queue/worker can be added later.
- Gemini is the only configured production provider, behind the `LLMProvider`
  interface.
- The current frontend has only the minimum Requirements Analyst result views.

## Future modules

Project Manager AI, Developer AI, QA AI, code execution, Git automation, and
external integrations are intentionally out of scope for this milestone.

## Developer AI

The Developer Agent lives in `Developer_Agent/` and runs as its own service on port 8001
(it needs a newer `google-genai` than this backend pins). This backend is the only door to it:

| Endpoint | Purpose |
|---|---|
| `POST /api/projects/{id}/developer/tasks/{task_id}/run` | Start the agent on one PM task (202). Refuses (409) while another run is active or blocking prerequisite tasks are not completed (`{"force": true}` overrides the latter) |
| `GET /api/projects/{id}/developer/runs`, `/runs/{run_id}` | Progress, attempts, log, changed files. Polling also syncs the run and the task status |
| `GET /api/projects/{id}/developer/workspace/files`, `/workspace/file?path=` | Browse the generated code |
| `POST /api/projects/{id}/developer/commands` | `install`, `check_imports` or `test` in the project's workspace |

Every run is stored as an `AgentRun` named "Developer AI", so it appears in the agent activity
list and the dashboard. The task text sent to the agent contains the task, its acceptance
criteria and only the Architect's design items traced to that task. A successful run sets the
PM task to `COMPLETED`; a failed run returns it to `TODO`.

Start both services (set `DEVELOPER_AGENT_KEY` here and `DEVELOPER_SERVICE_KEY` there to the same value):

```bash
python -m uvicorn app.main:app --app-dir backend --port 8000
cd Developer_Agent && python -m uvicorn app.main:app --host 127.0.0.1 --port 8001 --reload-dir app
```
