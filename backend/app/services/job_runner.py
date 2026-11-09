"""In-process background job runner.

Default mode (TASK_QUEUE=inline): a bounded thread pool inside the FastAPI
process — zero extra services needed for development/sandbox. For production
set TASK_QUEUE=celery; the dispatch functions here are the single place to
swap the transport (Celery+Redis ship in docker-compose.yml).
"""
from __future__ import annotations

import logging
import traceback
from concurrent.futures import Future, ThreadPoolExecutor
from typing import Callable

from app.core.config import settings

logger = logging.getLogger(__name__)

_executor = ThreadPoolExecutor(max_workers=3, thread_name_prefix="adpilot-job")


def submit(fn: Callable[[], None], *, name: str = "job") -> None:
    """Run a background task. Inline mode by default; Celery documented."""
    if settings.TASK_QUEUE == "celery":  # pragma: no cover - optional path
        try:
            from app.tasks.celery_app import run_sync_task  # type: ignore

            run_sync_task.delay(fn.__module__ + "." + fn.__name__)
            return
        except Exception as e:
            logger.error("Celery dispatch failed (%s) — falling back to inline", e)
    _executor.submit(_safe, fn, name)


def _safe(fn: Callable[[], None], name: str) -> None:
    try:
        fn()
    except Exception:
        logger.error("Background job '%s' crashed:\n%s", name, traceback.format_exc())


def wait_all(timeout: float | None = None) -> None:
    """Block until queued jobs finish (used by tests)."""
    _executor.shutdown(wait=True)
    if timeout is None:
        return
