"""Phase 4B SQL migration + conversation reopen on disposable SQLite."""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import text

os.environ.setdefault("JWT_SECRET_KEY", "test-secret-key-with-at-least-32-bytes!!")

PHASE4B_REVISION = "20260918_0015"
PHASE4A_REVISION = "20260917_0014"


def _clear_database_caches() -> None:
    from backend import config
    from backend.db import sqlalchemy_store

    config.get_settings.cache_clear()
    sqlalchemy_store.get_engine.cache_clear()
    sqlalchemy_store._sessionmaker.cache_clear()
    sqlalchemy_store.get_sqlalchemy_database.cache_clear()


def _alembic_cfg(url: str) -> Config:
    root = Path(__file__).resolve().parents[1]
    cfg = Config(str(root / "alembic.ini"))
    cfg.set_main_option("script_location", str(root / "alembic"))
    cfg.set_main_option("sqlalchemy.url", url)
    return cfg


@pytest.fixture()
def disposable_sql(tmp_path, monkeypatch):
    url = f"sqlite:///{tmp_path / 'phase4b.db'}"
    monkeypatch.setenv("DATABASE_URL", url)
    monkeypatch.setenv("INTERVIV_USE_MEMORY_DB", "false")
    _clear_database_caches()
    yield url
    _clear_database_caches()


def test_phase4b_migration_upgrade_downgrade(disposable_sql):
    cfg = _alembic_cfg(disposable_sql)
    command.upgrade(cfg, PHASE4B_REVISION)
    from backend.db.sqlalchemy_store import get_engine

    with get_engine().connect() as conn:
        tables = {
            row[0]
            for row in conn.execute(
                text("SELECT name FROM sqlite_master WHERE type='table'")
            )
        }
        assert "study_plans" in tables
        assert "coach_conversations" in tables

    command.downgrade(cfg, PHASE4A_REVISION)
    _clear_database_caches()
    from backend.db.sqlalchemy_store import get_engine as get_engine2

    with get_engine2().connect() as conn:
        tables = {
            row[0]
            for row in conn.execute(
                text("SELECT name FROM sqlite_master WHERE type='table'")
            )
        }
        assert "study_plans" not in tables
        assert "coach_conversations" not in tables


def test_sql_conversation_survives_reopen(disposable_sql):
    from backend.db.sqlalchemy_store import create_all_for_smoke
    from modules.coach_conversation import (
        get_conversation,
        get_or_create_conversation,
        owner_key,
        post_message,
        update_goals,
    )

    # Live store use requires the current schema (e.g. sessions.revision);
    # the pinned 4B/4A chain is asserted by the migration test above.
    command.upgrade(_alembic_cfg(disposable_sql), "head")
    _clear_database_caches()
    create_all_for_smoke()
    doc = get_or_create_conversation(user_id="sql-user", role_id="amazon_sde_intern")
    update_goals(
        doc["conversation_id"],
        owner=owner_key("sql-user"),
        confirmed_goal="SQL reopen goal",
        hours_per_week=4,
    )
    post_message(
        doc["conversation_id"],
        owner=owner_key("sql-user"),
        user_id="sql-user",
        text="Explain my plan",
        action="create_plan",
        action_payload={"days": 7},
    )
    cid = doc["conversation_id"]
    _clear_database_caches()
    again = get_conversation(cid, owner=owner_key("sql-user"))
    assert again is not None
    assert again["goals"]["confirmed_goal"] == "SQL reopen goal"
    assert again["goals"]["hours_per_week"] == 4
    assert len(again["messages"]) >= 2
