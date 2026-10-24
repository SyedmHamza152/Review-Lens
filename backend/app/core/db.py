"""SQLAlchemy database setup (PostgreSQL-ready, SQLite fallback for sandbox)."""
from __future__ import annotations

from pathlib import Path

from sqlalchemy import create_engine, text
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.core.config import settings


class Base(DeclarativeBase):
    pass


def _make_engine():
    url = settings.SQLALCHEMY_DATABASE_URL
    if url.startswith("sqlite"):
        db_path = url.split("sqlite:///")[-1]
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        return create_engine(
            url,
            connect_args={"check_same_thread": False},
            pool_pre_ping=True,
        )
    return create_engine(url, pool_pre_ping=True, pool_size=5, max_overflow=10)


engine = _make_engine()
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)


def get_db():
    """FastAPI dependency."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    """Create tables if they do not exist.

    For production PostgreSQL deployments use Alembic migrations instead
    (see backend/alembic). create_all is idempotent and keeps the sandbox MVP
    self-bootstrapping.
    """
    from app import models  # noqa: F401  (register models)

    Base.metadata.create_all(bind=engine)


def check_db() -> bool:
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception:  # pragma: no cover
        return False
