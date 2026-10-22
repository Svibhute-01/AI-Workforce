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