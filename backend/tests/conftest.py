"""Pytest configuration — isolated temp database for every test session.

Env vars are set at conftest import time (pytest imports conftest before any
test module), so the app reads the test configuration on first import.
"""
from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

_TMP = tempfile.mkdtemp(prefix="adpilot-test-")
os.environ["SQLALCHEMY_DATABASE_URL"] = f"sqlite:///{_TMP}/test.db"
os.environ["DATA_DIR"] = _TMP
os.environ["TASK_QUEUE"] = "inline"
os.environ["LLM_TIMEOUT_SECONDS"] = "0.2"
os.environ["SECRET_KEY"] = "test-secret-key"
os.environ["MODELS_DIR"] = str(Path(_TMP) / "models")

import pytest  # noqa: E402


@pytest.fixture(scope="session")
def app_client():
    from fastapi.testclient import TestClient

    from app.main import app as fastapi_app

    with TestClient(fastapi_app) as client:
        yield client


@pytest.fixture()
def db_session():
    from app.core.db import SessionLocal

    s = SessionLocal()
    try:
        yield s
    finally:
        s.close()
