from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class User(Base):
    """Application user.

    The sandbox/demo deployment runs in single-user mode: one demo user is
    provisioned automatically. No passwords are stored — Google OAuth is the
    only external identity flow.
    """

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(200), default="")
    currency: Mapped[str] = mapped_column(String(8), default="PKR")
    market: Mapped[str] = mapped_column(String(4), default="PK")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
