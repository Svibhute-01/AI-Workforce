import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .api import analysis, architect, auth, dashboard, developer, documents, project_manager, projects, user_settings, workflow
from .config import get_settings
from .database import init_db

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
settings = get_settings()

app = FastAPI(
    title="AI Workforce API",
    description="Project-scoped SRS processing, RAG, Requirements Analyst AI, Project Manager AI and System Architect AI.",
    version="1.0.0",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(auth.router)
app.include_router(projects.router)
app.include_router(documents.router)
app.include_router(analysis.router)
app.include_router(project_manager.router)
app.include_router(architect.router)
app.include_router(dashboard.router)
app.include_router(user_settings.router)
app.include_router(workflow.router)
app.include_router(developer.router)


@app.on_event("startup")
def startup() -> None:
    settings.ensure_directories()
    init_db()


@app.get("/health", tags=["system"])
def health() -> dict:
    return {
        "status": "ok",
        "database_configured": bool(settings.database_url),
        "gemini_configured": bool(settings.gemini_api_key),
        "jwt_configured": bool(settings.effective_jwt_secret),
        "provider": "Gemini",
    }