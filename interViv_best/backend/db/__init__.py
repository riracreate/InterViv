"""Database selection for interViv.

Phase 2 makes PostgreSQL the real persistence path:

  DATABASE_URL set      -> SQLAlchemy/PostgreSQL adapter
  DATABASE_URL missing  -> in-memory adapter for local demos and CI

The public route-facing API remains intentionally small:
``get_database()["sessions"].find_one(...)`` and matching insert/update helpers.
"""
from __future__ import annotations

import os
from functools import lru_cache
from typing import Any

from backend.config import get_settings


class DatabaseConnectionError(RuntimeError):
    pass


def is_database_exception(exc: Exception) -> bool:
    try:
        from sqlalchemy.exc import SQLAlchemyError
    except ModuleNotFoundError:
        SQLAlchemyError = ()  # type: ignore[assignment]
    try:
        from backend.db.sqlalchemy_store import SQLAlchemyDatabaseError
    except ModuleNotFoundError:
        SQLAlchemyDatabaseError = ()  # type: ignore[assignment]
    try:
        from pymongo.errors import PyMongoError
    except ModuleNotFoundError:
        PyMongoError = ()  # type: ignore[assignment]
    return isinstance(exc, (PyMongoError, SQLAlchemyError, SQLAlchemyDatabaseError))


def _memory_db_flag() -> str:
    return (os.getenv("INTERVIV_USE_MEMORY_DB") or "").strip().lower()


@lru_cache(maxsize=1)
def _get_memory_db() -> Any:
    """Lazy import — only pulled in when actually using in-memory mode."""
    from backend.db.memory import get_memory_database
    return get_memory_database()


def get_database() -> Any:
    """Return a db-like object. DATABASE_URL enables PostgreSQL persistence."""
    settings = get_settings()
    if settings.database_url:
        try:
            from backend.db.sqlalchemy_store import get_sqlalchemy_database
        except Exception as exc:
            raise DatabaseConnectionError(str(exc)) from exc
        return get_sqlalchemy_database()

    return _get_memory_db()
