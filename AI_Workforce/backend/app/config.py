from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str = ""
    jwt_secret: str = ""
    session_secret: str = ""
    gemini_api_key: str = ""
    chroma_persist_directory: str = "./data/chroma"
    upload_directory: str = "./data/uploads"
    cors_origins: str = "http://localhost:5000,http://localhost:5173"
    max_upload_size_bytes: int = 10 * 1024 * 1024
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60 * 24
    gemini_model: str = "gemini-3.1-flash-lite"
    gemini_embedding_model: str = "gemini-embedding-001"
    environment: str = "development"
    # Developer Agent service (runs separately because its LangChain stack needs a newer google-genai)
    developer_agent_url: str = "http://127.0.0.1:8001"
    developer_agent_key: str = ""
    developer_agent_timeout_seconds: int = 30
    developer_agent_command_timeout_seconds: int = 660  # must exceed the install limit in Developer_Agent

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def effective_jwt_secret(self) -> str:
        return self.jwt_secret or self.session_secret

    @property
    def effective_database_url(self) -> str:
        # Replit's managed PostgreSQL sets DATABASE_URL automatically. The SQLite
        # fallback keeps local tests and a fresh import bootable until it is set.
        if self.database_url:
            if self.database_url.startswith("postgres://"):
                return self.database_url.replace("postgres://", "postgresql+psycopg://", 1)
            if self.database_url.startswith("postgresql://"):
                return self.database_url.replace("postgresql://", "postgresql+psycopg://", 1)
            return self.database_url
        return "sqlite:///./data/app.db"

    def ensure_directories(self) -> None:
        Path(self.chroma_persist_directory).mkdir(parents=True, exist_ok=True)
        Path(self.upload_directory).mkdir(parents=True, exist_ok=True)
        Path("./data").mkdir(parents=True, exist_ok=True)


@lru_cache
def get_settings() -> Settings:
    return Settings()