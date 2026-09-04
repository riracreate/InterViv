"""Tests for Phase 2 Alembic migration: upgrade, downgrade, schema integrity, and historical backfill."""

from __future__ import annotations

import os
from datetime import datetime, timezone
import pytest
from sqlalchemy import create_engine, text, inspect
from alembic.config import Config
from alembic import command

from backend.db.sqlalchemy_models import Base


def _run_alembic(engine_url: str, action: str, revision: str = "head"):
    here = os.path.dirname(__file__)
    interviv_dir = os.path.abspath(os.path.join(here, ".."))
    ini_path = os.path.join(interviv_dir, "alembic.ini")
    alembic_cfg = Config(ini_path)
    alembic_cfg.set_main_option("sqlalchemy.url", engine_url)
    alembic_cfg.set_main_option("script_location", os.path.join(interviv_dir, "alembic"))
    if action == "upgrade":
        command.upgrade(alembic_cfg, revision)
    elif action == "downgrade":
        command.downgrade(alembic_cfg, revision)


def test_phase2_migration_empty_db_upgrade_and_downgrade(tmp_path):
    """Verify clean upgrade and downgrade on a fresh database."""
    db_file = tmp_path / "migration_empty.db"
    db_url = f"sqlite:///{db_file}"
    engine = create_engine(db_url)

    # 1. Upgrade to head
    _run_alembic(db_url, "upgrade", "head")

    inspector = inspect(engine)
    tables = inspector.get_table_names()
    assert "mcq_questions" in tables
    assert "sql_problems" in tables
    assert "sql_problem_cases" in tables
    assert "rounds" in tables

    # Verify rounds lifecycle columns exist
    round_cols = {col["name"] for col in inspector.get_columns("rounds")}
    assert "started_at" in round_cols
    assert "expires_at" in round_cols
    assert "status" in round_cols
    assert "submitted_at" in round_cols

    # Null-check on new empty tables
    with engine.connect() as conn:
        assert conn.execute(text("SELECT COUNT(*) FROM mcq_questions")).scalar() == 0
        assert conn.execute(text("SELECT COUNT(*) FROM sql_problems")).scalar() == 0
        assert conn.execute(text("SELECT COUNT(*) FROM sql_problem_cases")).scalar() == 0

    # 2. Downgrade to Phase 1 head (20260519_0001)
    _run_alembic(db_url, "downgrade", "20260519_0001")

    inspector = inspect(engine)
    tables_after = inspector.get_table_names()
    assert "mcq_questions" not in tables_after
    assert "sql_problems" not in tables_after
    assert "sql_problem_cases" not in tables_after
    round_cols_after = {col["name"] for col in inspector.get_columns("rounds")}
    assert "status" not in round_cols_after
    assert "started_at" not in round_cols_after


def test_phase2_migration_backfills_historical_rounds(tmp_path):
    """Verify that completed rounds remain submitted and incomplete rounds are properly categorized."""
    db_file = tmp_path / "migration_backfill.db"
    db_url = f"sqlite:///{db_file}"
    engine = create_engine(db_url)

    # 1. Upgrade to Phase 1 head
    _run_alembic(db_url, "upgrade", "20260519_0001")

    now_iso = datetime.now(timezone.utc).isoformat()

    # 2. Insert Phase 1 historical data:
    #    - Session 1: completed session with 1 completed round and 1 incomplete round
    #    - Session 2: active session with 1 incomplete round
    with engine.begin() as conn:
        # insert users & skills
        conn.execute(
            text(
                "INSERT INTO users (id, email, password_hash, created_at, last_active_at) "
                "VALUES ('u1', 'contributors@example.invalid', 'hash', :now, :now)"
            ),
            {"now": now_iso},
        )
        conn.execute(
            text(
                "INSERT INTO skills (id, canonical_name, sub_domain) "
                "VALUES (1, 'DBMS', 'general')"
            )
        )
        # completed session
        conn.execute(
            text(
                "INSERT INTO sessions (id, user_id, started_at, completed_at, status, last_round, skills_json, rounds_per_skill) "
                "VALUES ('s_completed', 'u1', :now, :now, 'completed', 2, '[\"DBMS\"]', 2)"
            ),
            {"now": now_iso},
        )
        # active session
        conn.execute(
            text(
                "INSERT INTO sessions (id, user_id, started_at, status, last_round, skills_json, rounds_per_skill) "
                "VALUES ('s_active', 'u1', :now, 'active', 1, '[\"DBMS\"]', 1)"
            ),
            {"now": now_iso},
        )

        # completed round with answer in completed session
        conn.execute(
            text(
                "INSERT INTO rounds (session_id, round_number, answer_text, final_score, covered_concepts, missing_concepts, ner_entities, question_context, created_at, round_type, artifact_json, config_json) "
                "VALUES ('s_completed', 1, 'Sample answer', 85.0, '[]', '[]', '[]', '{}', :now, 'technical_short_answer', '{}', '{}')"
            ),
            {"now": now_iso},
        )
        # abandoned/incomplete round in completed session
        conn.execute(
            text(
                "INSERT INTO rounds (session_id, round_number, answer_text, final_score, covered_concepts, missing_concepts, ner_entities, question_context, created_at, round_type, artifact_json, config_json) "
                "VALUES ('s_completed', 2, NULL, NULL, '[]', '[]', '[]', '{}', :now, 'technical_short_answer', '{}', '{}')"
            ),
            {"now": now_iso},
        )
        # active incomplete round in active session
        conn.execute(
            text(
                "INSERT INTO rounds (session_id, round_number, answer_text, final_score, covered_concepts, missing_concepts, ner_entities, question_context, created_at, round_type, artifact_json, config_json) "
                "VALUES ('s_active', 1, NULL, NULL, '[]', '[]', '[]', '{}', :now, 'technical_short_answer', '{}', '{}')"
            ),
            {"now": now_iso},
        )

    # 3. Upgrade to Phase 2 head
    _run_alembic(db_url, "upgrade", "head")

    with engine.connect() as conn:
        rows = conn.execute(
            text("SELECT session_id, round_number, status, started_at, submitted_at FROM rounds ORDER BY session_id, round_number")
        ).fetchall()

        r_completed_1 = [r for r in rows if r[0] == "s_completed" and r[1] == 1][0]
        r_completed_2 = [r for r in rows if r[0] == "s_completed" and r[1] == 2][0]
        r_active_1 = [r for r in rows if r[0] == "s_active" and r[1] == 1][0]

        # Previously answered round is marked 'submitted' and has submitted_at
        assert r_completed_1[2] == "submitted"
        assert r_completed_1[3] is not None  # started_at
        assert r_completed_1[4] is not None  # submitted_at

        # Unanswered round in completed session is marked 'expired' (NOT in_progress)
        assert r_completed_2[2] == "expired"

        # Active incomplete round in active session is marked 'in_progress'
        assert r_active_1[2] == "in_progress"
        assert r_active_1[3] is not None  # started_at
        assert r_active_1[4] is None  # not yet submitted
