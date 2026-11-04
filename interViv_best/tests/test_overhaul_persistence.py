"""Overhaul Phase 1: SQL persistence of ATS snapshots, round metadata and ML results.

Runs on a disposable SQLite file, or on Postgres when
``INTERVIV_TEST_DATABASE_URL`` points at a loopback ``*_test`` database.
"""

from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import inspect

os.environ.setdefault("JWT_SECRET_KEY", "test-secret-key-with-at-least-32-bytes!!")

from tests.alembic_helpers import parent_revision  # noqa: E402

OVERHAUL_REVISION = "20261103_0017"


def _clear_database_caches() -> None:
    from backend import config
    from backend.db import sqlalchemy_store

    config.get_settings.cache_clear()
    sqlalchemy_store.get_engine.cache_clear()
    sqlalchemy_store._sessionmaker.cache_clear()
    sqlalchemy_store.get_sqlalchemy_database.cache_clear()


def _alembic_cfg(url: str) -> Config:
    root = Path(__file__).resolve().parents[1]
    # Programmatic config (no ini file) so env.py skips logging.fileConfig,
    # which would disable existing loggers for every later test.
    cfg = Config()
    cfg.set_main_option("script_location", str(root / "alembic"))
    cfg.set_main_option("sqlalchemy.url", url)
    return cfg


@pytest.fixture()
def sql_db(tmp_path, monkeypatch):
    from tests.sql_test_url import is_postgres, reset_postgres_schema, resolve_sql_url

    url = resolve_sql_url(tmp_path, "overhaul.db")
    monkeypatch.setenv("DATABASE_URL", url)
    monkeypatch.setenv("INTERVIV_USE_MEMORY_DB", "false")
    _clear_database_caches()
    if is_postgres(url):
        reset_postgres_schema(url)
    command.upgrade(_alembic_cfg(url), "head")
    _clear_database_caches()
    from backend.db import get_database

    yield url, get_database()
    _clear_database_caches()
    if is_postgres(url):
        reset_postgres_schema(url)


def _columns(table: str) -> set[str]:
    from backend.db.sqlalchemy_store import get_engine

    return {c["name"] for c in inspect(get_engine()).get_columns(table)}


def test_migration_adds_and_removes_columns(sql_db):
    url, _ = sql_db
    assert "ats_snapshot" in _columns("candidates")
    assert "private_meta_json" in _columns("rounds")
    assert {"score", "result_json", "grader_version", "execution_status"} <= _columns(
        "ml_primitives_attempts"
    )

    command.downgrade(_alembic_cfg(url), parent_revision(OVERHAUL_REVISION))
    _clear_database_caches()
    assert "ats_snapshot" not in _columns("candidates")
    assert "private_meta_json" not in _columns("rounds")
    assert "grader_version" not in _columns("ml_primitives_attempts")

    command.upgrade(_alembic_cfg(url), "head")
    _clear_database_caches()
    assert "ats_snapshot" in _columns("candidates")


def test_candidate_ats_snapshot_round_trips(sql_db):
    _, db = sql_db
    snapshot = {
        "skills": ["Python", "SQL"],
        "sections": {"experience": True, "education": True},
        "section_order_ok": True,
        "layout_checked": True,
        "text_hash": "abc123",
    }
    db["candidates"].insert_one(
        {"candidate_id": "cand-ats", "resume_skills": ["Python"], "ats_snapshot": snapshot}
    )
    assert db["candidates"].find_one({"candidate_id": "cand-ats"})["ats_snapshot"] == snapshot

    # Unrelated updates must keep the snapshot.
    db["candidates"].update_one(
        {"candidate_id": "cand-ats"}, {"$set": {"resume_skills": ["Python", "Go"]}}
    )
    again = db["candidates"].find_one({"candidate_id": "cand-ats"})
    assert again["ats_snapshot"] == snapshot
    assert again["resume_skills"] == ["Python", "Go"]


def test_legacy_candidate_without_snapshot_reads_none(sql_db):
    _, db = sql_db
    db["candidates"].insert_one({"candidate_id": "cand-legacy", "resume_skills": ["SQL"]})
    assert db["candidates"].find_one({"candidate_id": "cand-legacy"})["ats_snapshot"] is None


def _session_doc(rounds):
    return {
        "session_id": "s-meta",
        "user_id": None,
        "status": "active",
        "skills": ["DSA"],
        "last_round": len(rounds),
        "total_rounds": 3,
        "rounds": rounds,
    }


def test_round_private_metadata_round_trips(sql_db):
    _, db = sql_db
    db["sessions"].insert_one(
        _session_doc(
            [
                {
                    "round": 1,
                    "round_type": "coding",
                    "status": "submitted",
                    "coding_exec_count": 7,
                    "wpm": 132.5,
                    "pause_count": 4,
                },
                {
                    "round": 2,
                    "round_type": "technical_short_answer",
                    "status": "in_progress",
                    "is_follow_up": True,
                    "purpose": "follow_up",
                    "follow_up_scoring": "unreviewed",
                },
            ]
        )
    )
    rounds = db["sessions"].find_one({"session_id": "s-meta"})["rounds"]
    assert rounds[0]["coding_exec_count"] == 7
    assert rounds[0]["wpm"] == 132.5
    assert rounds[0]["pause_count"] == 4
    assert rounds[1]["purpose"] == "follow_up"
    assert rounds[1]["follow_up_scoring"] == "unreviewed"
    # Absent keys stay absent, matching the memory store.
    assert "coding_exec_count" not in rounds[1]


def test_coding_exec_count_survives_store_round_trip(sql_db):
    """The per-round run cap depends on this count persisting in SQL mode."""
    from backend.execution import consume_round_exec_slot

    _, db = sql_db
    db["sessions"].insert_one(
        _session_doc([{"round": 1, "round_type": "coding", "status": "in_progress"}])
    )
    session = db["sessions"].find_one({"session_id": "s-meta"})
    consume_round_exec_slot(session["rounds"][0])
    consume_round_exec_slot(session["rounds"][0])
    db["sessions"].update_one({"session_id": "s-meta"}, {"$set": {"rounds": session["rounds"]}})
    stored = db["sessions"].find_one({"session_id": "s-meta"})["rounds"][0]
    assert stored["coding_exec_count"] == 2


def test_legacy_follow_up_scoring_in_config_is_restored(sql_db):
    _, db = sql_db
    db["sessions"].insert_one(
        _session_doc(
            [
                {
                    "round": 1,
                    "status": "in_progress",
                    "is_follow_up": True,
                    "config_json": {"follow_up_scoring": "unreviewed"},
                }
            ]
        )
    )
    # Simulate a pre-0017 row: metadata column empty.
    from sqlalchemy import update

    from backend.db.sqlalchemy_models import RoundRow
    from backend.db.sqlalchemy_store import session_scope

    with session_scope() as s:
        s.execute(update(RoundRow).values(private_meta_json=None))
    restored = db["sessions"].find_one({"session_id": "s-meta"})["rounds"][0]
    assert restored["follow_up_scoring"] == "unreviewed"


def test_sanitized_round_hides_private_metadata():
    from backend.serializers.round_serializer import sanitize_round_for_client

    cleaned = sanitize_round_for_client(
        {
            "round": 1,
            "round_type": "technical_short_answer",
            "question": "Explain indexing.",
            "coding_exec_count": 3,
            "follow_up_scoring": "unreviewed",
            "purpose": "follow_up",
            "wpm": 120.0,
            "pause_count": 2,
        }
    )
    for key in ("coding_exec_count", "follow_up_scoring", "purpose", "wpm", "pause_count"):
        assert key not in cleaned
    assert cleaned["question"] == "Explain indexing."


def test_ml_attempt_grading_result_round_trips(sql_db):
    _, db = sql_db
    db["ml_primitives_attempts"].insert_one(
        {
            "id": "att-1",
            "user_id": "u1",
            "session_id": "s1",
            "round": 1,
            "block_id": "b1",
            "problem_id": "softmax_stable",
            "problem_version": 1,
            "language": "python",
            "source": "def softmax(x):\n    return x\n",
            "status": "graded",
            "error_code": "",
            "created_at": datetime.now(timezone.utc),
            "score": 62.5,
            "result": {"cases_passed": 5, "cases_total": 8},
            "grader_version": "v1-ml-primitives",
            "execution_status": "completed",
        }
    )
    row = db["ml_primitives_attempts"].find_one({"id": "att-1"})
    assert row["score"] == 62.5
    assert row["result"] == {"cases_passed": 5, "cases_total": 8}
    assert row["grader_version"] == "v1-ml-primitives"
    assert row["execution_status"] == "completed"


def test_ats_analysis_source_labels():
    from backend.routes.ats import _analysis_from_candidate

    _, source = _analysis_from_candidate({"resume_skills": ["SQL"]}, None)
    assert source == "skills_only"
    _, source = _analysis_from_candidate(
        {"ats_snapshot": {"skills": ["SQL"], "sections": {"education": True}}}, None
    )
    assert source == "snapshot"
