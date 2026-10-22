import logging
from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from .config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()
database_url = settings.effective_database_url

connect_args = {"check_same_thread": False} if database_url.startswith("sqlite") else {}
engine = create_engine(database_url, connect_args=connect_args, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    from . import models  # noqa: F401

    Base.metadata.create_all(bind=engine)
    if not settings.database_url:
        logger.warning("DATABASE_URL is not set; using the local SQLite development fallback.")