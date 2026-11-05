from __future__ import annotations

import os
import sqlite3
import pytest

from sqlalchemy import event
from sqlalchemy.engine import Engine


@event.listens_for(Engine, "connect")
def _sqlite_foreign_keys(dbapi_connection, connection_record) -> None:
    if not isinstance(dbapi_connection, sqlite3.Connection):
        return
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


from backend.config import get_settings as _get_settings
from backend.db import _get_memory_db as _get_memory_db

_CLEAR_CACHES = (_get_settings.cache_clear, _get_memory_db.cache_clear)


@pytest.fixture(autouse=True)
def _clear_settings_and_memory_db_caches():
    """Reset the two process-wide ``lru_cache`` singletons around every test.

    Intended (Step 0). ``get_settings()`` caches environment-derived flags
    (``DATABASE_URL``, ``SYSTEM_FOLLOW_UPS_ENABLED``, ...) and
    ``_get_memory_db()`` caches the in-memory store; a test that sets an env
    var or patches the store must not leak that choice into later tests,
    and must start from the environment it configures itself.

    The ``cache_clear`` callables are captured at import time so a test that
    monkeypatches ``get_settings``/``_get_memory_db`` with a plain function
    cannot break teardown for the next test.
    """
    for clear in _CLEAR_CACHES:
        clear()
    yield
    for clear in _CLEAR_CACHES:
        clear()


os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")
# 32+ bytes so PyJWT does not warn about insecure HMAC key length (RFC 7518 §3.2).
os.environ.setdefault("JWT_SECRET_KEY", "test-secret-key-with-at-least-32-bytes!!")


@pytest.fixture(autouse=True)
def isolated_auth_rate_limits(monkeypatch):
    # TestClient instances reuse the same client address across independent
    # tests; each test still exercises normal throttling within its own window.
    from backend.auth import throttling

    monkeypatch.setattr(throttling, "_windows", {})
