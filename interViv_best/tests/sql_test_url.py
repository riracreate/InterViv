"""Opt-in Postgres target for the SQL race and persistence tests.

``INTERVIV_TEST_DATABASE_URL``, when set, replaces the temporary SQLite
file. Unset, callers keep today's sqlite URL. A separate name so a
developer's ``DATABASE_URL`` cannot point these tests at a real database.
"""

from __future__ import annotations

import os
from pathlib import Path


_ALLOWED_HOSTS = frozenset({"127.0.0.1", "localhost"})


def require_disposable_test_database(url: str) -> None:
    """Refuse a URL these tests could wipe.

    Fixtures drop the ``public`` schema. The host must be loopback and the
    database name must end in ``_test``.
    """
    from sqlalchemy.engine import make_url

    parsed = make_url(url)
    host = (parsed.host or "").lower()
    name = parsed.database or ""
    if host not in _ALLOWED_HOSTS or not name.endswith("_test"):
        raise RuntimeError(
            "INTERVIV_TEST_DATABASE_URL must use host 127.0.0.1 or localhost "
            "and a database name ending in _test. "
            f"Refusing {host or '(no host)'}/{name or '(no database)'} "
            "because these tests drop the public schema."
        )


def resolve_sql_url(tmp_path: Path, filename: str) -> str:
    override = os.environ.get("INTERVIV_TEST_DATABASE_URL", "").strip()
    if override:
        require_disposable_test_database(override)
        return override
    return f"sqlite:///{tmp_path / filename}"


def is_postgres(url: str) -> bool:
    return url.startswith("postgresql")


def reset_postgres_schema(url: str) -> None:
    """Drop and recreate ``public`` so the next test starts empty."""
    if not is_postgres(url):
        return
    require_disposable_test_database(url)
    from sqlalchemy import create_engine, text

    engine = create_engine(url, pool_pre_ping=True, future=True)
    try:
        with engine.begin() as conn:
            conn.execute(text("DROP SCHEMA IF EXISTS public CASCADE"))
            conn.execute(text("CREATE SCHEMA public"))
            conn.execute(text("GRANT ALL ON SCHEMA public TO public"))
    finally:
        engine.dispose()


def upgrade_head(url: str) -> None:
    """Apply migrations to head. Caller must already have set DATABASE_URL."""
    from pathlib import Path as _Path

    from alembic import command
    from alembic.config import Config

    root = _Path(__file__).resolve().parents[1]
    cfg = Config()
    cfg.set_main_option("script_location", str(root / "alembic"))
    cfg.set_main_option("sqlalchemy.url", url)
    command.upgrade(cfg, "head")


def table_names(conn) -> set[str]:
    from sqlalchemy import text

    if conn.dialect.name == "sqlite":
        query = "SELECT name FROM sqlite_master WHERE type='table'"
    else:
        query = (
            "SELECT tablename FROM pg_catalog.pg_tables "
            "WHERE schemaname = 'public'"
        )
    return {row[0] for row in conn.execute(text(query))}


def table_info(conn, table: str):
    """Rows shaped like SQLite ``PRAGMA table_info`` on either dialect.

    Index 1 is the name, 3 is NOT NULL (1/0), 4 is the column default.
    """
    from sqlalchemy import text

    if conn.dialect.name == "sqlite":
        return list(conn.execute(text(f"PRAGMA table_info({table})")))
    rows = conn.execute(
        text(
            "SELECT c.ordinal_position - 1, c.column_name, c.data_type, "
            "CASE WHEN c.is_nullable = 'NO' THEN 1 ELSE 0 END, "
            "c.column_default, 0 "
            "FROM information_schema.columns c "
            "WHERE c.table_schema = 'public' AND c.table_name = :table "
            "ORDER BY c.ordinal_position"
        ),
        {"table": table},
    )
    return list(rows)
