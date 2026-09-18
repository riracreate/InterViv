"""Phase 4A: teaching exposures + eligibility survive SQL reopen; migration."""

from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import text

os.environ.setdefault("JWT_SECRET_KEY", "test-secret-key-with-at-least-32-bytes!!")

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
    url = f"sqlite:///{tmp_path / 'phase4a.db'}"
    monkeypatch.setenv("DATABASE_URL", url)
    monkeypatch.setenv("INTERVIV_USE_MEMORY_DB", "false")
    _clear_database_caches()
    yield url
    _clear_database_caches()


def test_phase4a_migration_upgrade_downgrade(disposable_sql):
    from tests.alembic_helpers import parent_revision

    cfg = _alembic_cfg(disposable_sql)
    command.upgrade(cfg, PHASE4A_REVISION)
    from backend.db.sqlalchemy_store import get_engine

    with get_engine().connect() as conn:
        tables = {
            row[0]
            for row in conn.execute(
                text("SELECT name FROM sqlite_master WHERE type='table'")
            )
        }
        assert "teaching_exposures" in tables
        cols = {
            row[1]
            for row in conn.execute(text("PRAGMA table_info(rounds)"))
        }
        assert "assessment_eligibility" in cols
        assert "is_follow_up" in cols

    parent = parent_revision(PHASE4A_REVISION)
    command.downgrade(cfg, parent)
    _clear_database_caches()
    from backend.db.sqlalchemy_store import get_engine as get_engine2

    with get_engine2().connect() as conn:
        tables = {
            row[0]
            for row in conn.execute(
                text("SELECT name FROM sqlite_master WHERE type='table'")
            )
        }
        assert "teaching_exposures" not in tables
        cols = {
            row[1]
            for row in conn.execute(text("PRAGMA table_info(rounds)"))
        }
        assert "assessment_eligibility" not in cols


def test_teaching_exposure_and_eligibility_survive_sql_reopen(disposable_sql):
    from backend.db import get_database
    from backend.db.sqlalchemy_store import SQLAlchemyDatabase, create_all_for_smoke
    from modules.teaching_exposures import record_teaching_exposure

    create_all_for_smoke()
    db = get_database()
    assert isinstance(db, SQLAlchemyDatabase)
    session_id = "sess-phase4a"
    db["sessions"].insert_one({
        "session_id": session_id,
        "candidate_id": "cand-4a",
        "user_id": "user-4a",
        "status": "active",
        "practice_mode": "coached_practice",
        "allow_optional_follow_ups": True,
        "skill": "DBMS",
        "skills": ["DBMS"],
        "last_round": 1,
        "rounds": [{
            "round": 1,
            "round_type": "technical_short_answer",
            "status": "submitted",
            "final_score": 88.0,
            "assessment_eligibility": "eligible",
            "eligibility_policy_version": "assistance_v1",
            "eligibility_exclusion_reasons": [],
            "eligibility_exposure_ids": [],
            "is_follow_up": False,
            "question": "What is ACID?",
            "feedback": {
                "content": ["ok"], "strengths": [], "weakness": [], "next_step": "",
            },
        }],
    })
    record_teaching_exposure(
        db,
        kind="hint",
        item_type="coding",
        item_id="p-sql-1",
        session={"session_id": session_id, "user_id": "user-4a"},
        user_id="user-4a",
        round_number=1,
        now=datetime.now(timezone.utc),
    )

    _clear_database_caches()
    db2 = get_database()
    stored = db2["sessions"].find_one({"session_id": session_id})
    assert stored["practice_mode"] == "coached_practice"
    assert stored["rounds"][0]["assessment_eligibility"] == "eligible"
    exposures = list(db2["teaching_exposures"].find({"session_id": session_id}))
    assert len(exposures) == 1
    assert exposures[0]["content_kind"] == "hint"
    assert exposures[0]["delivery_id"]
