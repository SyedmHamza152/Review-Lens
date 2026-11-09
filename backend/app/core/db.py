"""Database setup — SQLAlchemy 2.0 engine/session plus init helpers.

SQLite is the zero-config development fallback; set SQLALCHEMY_DATABASE_URL to a
PostgreSQL DSN for production (docker-compose.yml ships one) and run
`alembic upgrade head`.
"""
from __future__ import annotations

import logging
from collections.abc import Iterator
from pathlib import Path

from sqlalchemy import create_engine, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.config import settings

logger = logging.getLogger(__name__)


class Base(DeclarativeBase):
    pass


def _ensure_sqlite_dir() -> None:
    """SQLite cannot create parent directories itself — make sure the folder
    that holds the database file exists before the engine first connects."""
    url = settings.sqlalchemy_url
    if url.startswith("sqlite"):
        db_path = url.split("sqlite:///", 1)[-1]
        parent = Path(db_path).resolve().parent
        parent.mkdir(parents=True, exist_ok=True)


def _make_engine():
    _ensure_sqlite_dir()
    url = settings.sqlalchemy_url
    kwargs: dict = {"pool_pre_ping": True}
    if url.startswith("sqlite"):
        kwargs["connect_args"] = {"check_same_thread": False}
    else:
        kwargs.update(pool_size=10, max_overflow=20)
    return create_engine(url, **kwargs)


engine = _make_engine()
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def get_db() -> Iterator[Session]:
    """FastAPI dependency — one session per request."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def check_database() -> bool:
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception:  # pragma: no cover - surfaced via health endpoint
        return False


def init_db() -> None:
    """Create tables and seed baseline data (idempotent, dev-friendly).

    For production PostgreSQL use Alembic migrations instead:
        alembic upgrade head
    """
    from app import models  # noqa: F401  (register mappers)
    from app.services.demo_seeder import seed_if_empty

    Base.metadata.create_all(bind=engine)
    with SessionLocal() as db:
        seed_if_empty(db)
    logger.info("Database initialised at %s", settings.SQLALCHEMY_DATABASE_URL)
