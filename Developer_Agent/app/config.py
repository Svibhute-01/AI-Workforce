import os 
from dotenv import load_dotenv

load_dotenv()
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
MODEL_NAME = os.getenv("GEMINI_MODEL", "gemini-3.8-flash")
MAX_RETRIES = 3   # we'll use this in stage 4

if not GOOGLE_API_KEY:
    raise ValueError("GOOGLE_API_KEY is missing. Check your .env file.")

from pathlib import Path

# All generated projects live under this folder
WORKSPACES_DIR = Path(os.getenv("WORKSPACES_DIR") or Path(__file__).resolve().parent.parent / "workspaces")

# Job records (JSON) live outside the workspaces so they never show up as project files
JOBS_DIR = Path(os.getenv("JOBS_DIR") or Path(__file__).resolve().parent.parent / "jobs")

# Shared secret the main AI Workforce backend sends in the X-Service-Key header
SERVICE_KEY = os.getenv("DEVELOPER_SERVICE_KEY", "")

VECTORSTORE_DIR = Path(__file__).resolve().parent.parent / "vectorstore"
EMBEDDING_MODEL = "models/gemini-embedding-001"
RETRIEVAL_K = 5

# "all_files" = send every file, "rag" = retrieve relevant chunks
CONTEXT_MODE = os.getenv("CONTEXT_MODE", "all_files")
# --- Stacks, runners and the preview app ------------------------------------------------------
# "local": run commands on this machine (venv / npm in the project folder). "docker": run every
# command in a throw-away container with the project folder mounted, so generated code cannot see
# this machine's files or secrets.
RUNNER_MODE = os.getenv("RUNNER_MODE", "local").lower()
PYTHON_IMAGE = os.getenv("PYTHON_IMAGE", "python:3.12-slim")
NODE_IMAGE = os.getenv("NODE_IMAGE", "node:20-slim")
DOCKER_MEMORY = os.getenv("DOCKER_MEMORY", "1g")
DOCKER_CPUS = os.getenv("DOCKER_CPUS", "2")

# After the tests pass, start the app and check that it answers on "/".
SMOKE_CHECK = os.getenv("SMOKE_CHECK", "true").lower() != "false"

APP_PORT_RANGE = (9100, 9199)
APP_TTL_SECONDS = int(os.getenv("APP_TTL_SECONDS", "900"))      # a preview stops by itself after this
APP_PUBLIC_HOST = os.getenv("APP_PUBLIC_HOST", "127.0.0.1")     # host the browser uses to open it
APPS_DIR = Path(os.getenv("APPS_DIR") or Path(__file__).resolve().parent.parent / "jobs" / "apps")
PROJECTS_DIR = Path(os.getenv("PROJECTS_DIR") or Path(__file__).resolve().parent.parent / "jobs" / "projects")
