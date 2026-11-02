"""Dependency readiness, separate from the process liveness endpoint."""
from __future__ import annotations

import os

from backend.config import get_settings


def readiness_status() -> tuple[bool, dict]:
    settings = get_settings()
    checks: dict[str, dict] = {}
    if not settings.database_url:
        checks["database"] = {"ready": True, "mode": "memory", "persistent": False}
    else:
        try:
            from alembic.config import Config
            from alembic.migration import MigrationContext
            from alembic.script import ScriptDirectory
            from sqlalchemy import text
            from backend.db.sqlalchemy_store import get_engine

            config = Config()
            config.set_main_option("script_location", str(settings.project_root / "alembic"))
            expected = set(ScriptDirectory.from_config(config).get_heads())
            with get_engine().connect() as connection:
                connection.execute(text("SELECT 1"))
                current = set(MigrationContext.configure(connection).get_current_heads())
            checks["database"] = {
                "ready": current == expected,
                "mode": "sql",
                "persistent": True,
                "migrations_current": current == expected,
            }
        except Exception:
            # Never expose database URLs, credentials or driver errors publicly.
            checks["database"] = {"ready": False, "mode": "sql", "reason": "database_unavailable"}

    try:
        from backend.ml_primitives.catalog import list_problems

        count = len(list_problems())
        checks["practice_content"] = {"ready": count > 0, "ml_packs": count}
    except Exception:
        checks["practice_content"] = {"ready": False, "reason": "practice_content_unavailable"}

    redis_url = (os.getenv("REDIS_URL") or "").strip()
    if redis_url:
        try:
            from backend.auth.throttling import redis_client

            checks["auth_limiter"] = {"ready": bool(redis_client(redis_url).ping()), "mode": "redis"}
        except Exception:
            checks["auth_limiter"] = {"ready": False, "mode": "redis"}
    else:
        checks["auth_limiter"] = {"ready": True, "mode": "process_memory"}
    ready = all(check["ready"] for check in checks.values())
    return ready, {"status": "ready" if ready else "not_ready", "checks": checks}
