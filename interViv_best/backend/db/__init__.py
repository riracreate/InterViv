"""
db_v2.py — Drop-in replacement for backend/db.py

Adds an env-gated in-memory fallback so the demo runs without MongoDB:

  INTERVIV_USE_MEMORY_DB=true   → always use the memory DB (dev / mid-eval demo)
  INTERVIV_USE_MEMORY_DB=false  → use MongoDB (production / real deployment)
  (unset) + MongoDB unreachable → auto-fallback to memory DB + warning

Public API unchanged:
  get_database() -> db-like object supporting __getitem__
  is_database_exception(exc) -> bool
  DatabaseConnectionError — same exception class the routes import
"""
from __future__ import annotations

import os
import warnings
from functools import lru_cache
from typing import Any

from backend.config import get_settings


class DatabaseConnectionError(RuntimeError):
    pass


def is_database_exception(exc: Exception) -> bool:
    try:
        from pymongo.errors import PyMongoError
    except ModuleNotFoundError:
        return False
    return isinstance(exc, PyMongoError)


def _memory_db_flag() -> str:
    return (os.getenv("INTERVIV_USE_MEMORY_DB") or "").strip().lower()


@lru_cache(maxsize=1)
def _get_memory_db() -> Any:
    """Lazy import — only pulled in when actually using in-memory mode."""
    from backend.db.memory import get_memory_database
    return get_memory_database()


@lru_cache(maxsize=1)
def get_client() -> Any:
    settings = get_settings()
    try:
        from pymongo import MongoClient
    except ModuleNotFoundError as exc:
        raise DatabaseConnectionError(
            "pymongo is not installed. Install backend dependencies before starting the API."
        ) from exc

    return MongoClient(
        settings.mongodb_uri,
        serverSelectionTimeoutMS=settings.mongodb_timeout_ms,
        connectTimeoutMS=settings.mongodb_timeout_ms,
    )


def get_database() -> Any:
    """Return a db-like object. Honors INTERVIV_USE_MEMORY_DB env override."""
    flag = _memory_db_flag()
    if flag == "true":
        return _get_memory_db()

    settings = get_settings()
    try:
        client = get_client()
        db = client[settings.mongodb_db]
        # Trigger a ping if we want strict-mode (skip in default to keep cold start fast)
        if flag == "false":
            client.admin.command("ping")
        return db
    except Exception as exc:
        if flag == "false":
            # Strict mode — rethrow as DatabaseConnectionError
            raise DatabaseConnectionError(str(exc)) from exc
        # Soft fallback: MongoDB unreachable → switch to memory DB with a warning
        warnings.warn(
            f"[interViv] MongoDB unreachable ({exc}); falling back to in-memory DB. "
            f"Set INTERVIV_USE_MEMORY_DB=false to disable fallback.",
            RuntimeWarning,
            stacklevel=2,
        )
        return _get_memory_db()
