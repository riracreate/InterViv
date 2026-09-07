"""Phase I: review_schedules persistence on disposable SQLite.

B.1 lesson: every field must round-trip after engine dispose + reopen.
Uses parent_revision() for alembic downgrade (never relative -1).
"""

from __future__ import annotations

import os
from datetime import datetime, timezone
from uuid import uuid4

import pytest
from sqlalchemy import create_engine
from sqlalchemy import inspect as sa_inspect

os.environ.setdefault("JWT_SECRET_KEY", "test-secret-key-with-at-least-32-bytes!!")
os.environ["OPENAI_API_KEY"] = ""
os.environ["OPENROUTER_API_KEY"] = ""

from alembic import command as alembic_command
from alembic.config import Config as AlembicConfig

from backend import config as app_config
from backend.db import get_database
from backend.db.sqlalchemy_store import (
    _sessionmaker,
    create_all_for_smoke,
    get_engine,
    get_sqlalchemy_database,
)
from tests.alembic_helpers import parent_revision

PHASE_I_REVISION = "20260907_0008"


def _clear_db_caches() -> None:
    app_config.get_settings.cache_clear()
    get_engine.cache_clear()
    _sessionmaker.cache_clear()
    get_sqlalchemy_database.cache_clear()


@pytest.fixture
def sa_url(tmp_path, monkeypatch):
    db_file = tmp_path / "phasei.db"
    url = f"sqlite:///{db_file}"
    monkeypatch.setenv("DATABASE_URL", url)
    monkeypatch.setenv("INTERVIV_USE_MEMORY_DB", "false")
    _clear_db_caches()
    create_all_for_smoke()
    yield url
    try:
        get_engine().dispose()
    except Exception:
        pass
    _clear_db_caches()


def _run_alembic(engine_url: str, action: str, revision: str) -> None:
    here = os.path.dirname(__file__)
    interviv_dir = os.path.abspath(os.path.join(here, ".."))
    cfg = AlembicConfig(os.path.join(interviv_dir, "alembic.ini"))
    cfg.set_main_option("sqlalchemy.url", engine_url)
    cfg.set_main_option("script_location", os.path.join(interviv_dir, "alembic"))
    if action == "upgrade":
        alembic_command.upgrade(cfg, revision)
    else:
        alembic_command.downgrade(cfg, revision)


def test_review_schedule_survives_dispose_and_reopen(sa_url) -> None:
    db = get_database()
    now = datetime.now(timezone.utc)
    doc = {
        "id": str(uuid4()),
        "user_id": "u-phasei",
        "item_type": "mcq",
        "item_id": "q-phasei-1",
        "skill": "DBMS",
        "title": "Sample miss",
        "source_session_id": "sess-1",
        "source_round": 1,
        "originating_assisted": False,
        "miss_reason": "Missed MCQ",
        "interval_days": 3,
        "interval_index": 1,
        "due_at": now,
        "review_count": 2,
        "last_reviewed_at": now,
        "last_outcome": "correct",
        "last_review_assisted": True,
        "review_available": True,
        "unavailable_reason": None,
        "created_at": now,
        "updated_at": now,
    }
    db["review_schedules"].insert_one(doc)

    get_engine().dispose()
    get_engine.cache_clear()
    _sessionmaker.cache_clear()
    get_sqlalchemy_database.cache_clear()

    db = get_database()
    again = db["review_schedules"].find_one({"id": doc["id"]})
    assert again is not None
    for key in (
        "id", "user_id", "item_type", "item_id", "skill", "title",
        "source_session_id", "source_round", "originating_assisted",
        "miss_reason", "interval_days", "interval_index", "due_at",
        "review_count", "last_reviewed_at", "last_outcome",
        "last_review_assisted", "review_available", "unavailable_reason",
        "created_at", "updated_at",
    ):
        assert key in again, key
    assert again["user_id"] == "u-phasei"
    assert again["item_id"] == "q-phasei-1"
    assert again["interval_days"] == 3
    assert again["interval_index"] == 1
    assert again["review_count"] == 2
    assert again["last_outcome"] == "correct"
    assert again["last_review_assisted"] is True
    assert again["originating_assisted"] is False
    assert again["review_available"] is True
    assert again["skill"] == "DBMS"
    assert again["title"] == "Sample miss"
    assert again["miss_reason"] == "Missed MCQ"
    assert again["source_session_id"] == "sess-1"
    assert again["source_round"] == 1


def test_review_schedule_update_round_trips(sa_url) -> None:
    db = get_database()
    now = datetime.now(timezone.utc)
    sid = str(uuid4())
    db["review_schedules"].insert_one({
        "id": sid,
        "user_id": "u2",
        "item_type": "coding",
        "item_id": "coding_two_sum",
        "skill": "DSA",
        "title": "Two Sum",
        "source_session_id": None,
        "source_round": None,
        "originating_assisted": None,
        "miss_reason": "Coding attempt (execution unavailable)",
        "interval_days": 1,
        "interval_index": 0,
        "due_at": now,
        "review_count": 0,
        "last_reviewed_at": None,
        "last_outcome": None,
        "last_review_assisted": None,
        "review_available": False,
        "unavailable_reason": "execution_unavailable",
        "created_at": now,
        "updated_at": now,
    })
    later = now.replace(microsecond=0)
    db["review_schedules"].update_one(
        {"id": sid},
        {"$set": {
            "interval_days": 7,
            "interval_index": 2,
            "review_count": 1,
            "last_outcome": "incorrect",
            "updated_at": later,
        }},
    )
    get_engine().dispose()
    get_engine.cache_clear()
    _sessionmaker.cache_clear()
    get_sqlalchemy_database.cache_clear()

    row = get_database()["review_schedules"].find_one({"id": sid})
    assert row["interval_days"] == 7
    assert row["interval_index"] == 2
    assert row["review_count"] == 1
    assert row["last_outcome"] == "incorrect"
    assert row["review_available"] is False
    assert row["unavailable_reason"] == "execution_unavailable"


def test_alembic_upgrade_downgrade_reupgrade_phase_i(tmp_path, monkeypatch) -> None:
    db_file = tmp_path / "phasei_mig.db"
    url = f"sqlite:///{db_file}"
    _clear_db_caches()
    _run_alembic(url, "upgrade", "head")

    engine = create_engine(url)
    inspector = sa_inspect(engine)
    tables = inspector.get_table_names()
    assert "review_schedules" in tables
    cols = {c["name"] for c in inspector.get_columns("review_schedules")}
    for required in (
        "id", "user_id", "item_type", "item_id", "interval_days",
        "interval_index", "due_at", "review_count", "last_outcome",
        "last_review_assisted", "originating_assisted", "review_available",
        "unavailable_reason", "miss_reason",
    ):
        assert required in cols, required
    engine.dispose()

    monkeypatch.setenv("DATABASE_URL", url)
    monkeypatch.setenv("INTERVIV_USE_MEMORY_DB", "false")
    _clear_db_caches()
    try:
        db = get_database()
        now = datetime.now(timezone.utc)
        db["review_schedules"].insert_one({
            "id": "rs-mig",
            "user_id": "u-mig",
            "item_type": "mcq",
            "item_id": "q-mig",
            "skill": "DBMS",
            "title": "mig",
            "source_session_id": None,
            "source_round": None,
            "originating_assisted": False,
            "miss_reason": "Missed MCQ",
            "interval_days": 1,
            "interval_index": 0,
            "due_at": now,
            "review_count": 0,
            "last_reviewed_at": None,
            "last_outcome": None,
            "last_review_assisted": None,
            "review_available": True,
            "unavailable_reason": None,
            "created_at": now,
            "updated_at": now,
        })
        assert db["review_schedules"].find_one({"id": "rs-mig"})["item_id"] == "q-mig"
    finally:
        try:
            get_engine().dispose()
        except Exception:
            pass
        _clear_db_caches()

    _run_alembic(url, "downgrade", parent_revision(PHASE_I_REVISION))
    engine = create_engine(url)
    tables = sa_inspect(engine).get_table_names()
    assert "review_schedules" not in tables
    # Prior phase tables remain
    assert "retry_sets" in tables
    assert "system_design_attempts" in tables
    engine.dispose()

    _run_alembic(url, "upgrade", "head")
    engine = create_engine(url)
    assert "review_schedules" in sa_inspect(engine).get_table_names()
    engine.dispose()
    _clear_db_caches()
