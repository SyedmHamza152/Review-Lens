"""Pytest fixtures. Sets a test database BEFORE app modules are imported."""
from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

_TMPDIR = tempfile.mkdtemp(prefix="review_intel_test_")
os.environ["SQLALCHEMY_DATABASE_URL"] = f"sqlite:///{_TMPDIR}/test.db"

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.core.db import SessionLocal, init_db  # noqa: E402
from app.main import app  # noqa: E402


@pytest.fixture(scope="session", autouse=True)
def _setup_db():
    init_db()
    yield


@pytest.fixture(scope="session", autouse=True)
def _hermetic_adapters():
    """Keep the API/orchestrator tests offline & deterministic.

    Live connectors (Reddit archive, Hacker News, Daraz catalog) hit real
    network endpoints; unit/integration tests must not. All adapters are
    replaced by offline stubs that report needs_credentials, which restores
    the sample-corpus fallback for flow tests and the insufficient-data path.
    The live connectors themselves are tested separately with mocked HTTP
    (tests/test_live_sources.py).
    """
    import app.services.orchestrator as orch
    from app.integrations.base import AdapterResult, AdapterStatus, BaseAdapter

    class _OfflineStub(BaseAdapter):
        def __init__(self, key: str, name: str, type_: str):
            self.key, self.name, self.type = key, name, type_
            self.required_env = ["TEST_OFFLINE_STUB"]
            self.access_mode = "test stub"
            self.live_capability = "requires_credentials"

        def search(self, product_name, description, max_items):
            return AdapterResult(self.key, AdapterStatus.NEEDS_CREDENTIALS,
                                 "test stub: adapters are offline in pytest")

    original = orch.ADAPTERS
    orch.ADAPTERS = {k: _OfflineStub(k, k.title(), "social") for k in original}
    yield
    orch.ADAPTERS = original


@pytest.fixture()
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture()
def db():
    s = SessionLocal()
    try:
        yield s
    finally:
        s.close()
