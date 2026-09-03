"""Phase 1 round engine checks: persistence round-trip and scoring dispatch."""
from __future__ import annotations

import os

os.environ.setdefault("JWT_SECRET_KEY", "test-secret-key-with-at-least-32-bytes!!")


import pytest


def _clear_caches() -> None:
    from backend import config
    from backend.db import sqlalchemy_store

    config.get_settings.cache_clear()
    sqlalchemy_store.get_engine.cache_clear()
    sqlalchemy_store._sessionmaker.cache_clear()
    sqlalchemy_store.get_sqlalchemy_database.cache_clear()


@pytest.fixture()
def phase1_db(tmp_path, monkeypatch):
    from backend.db import sqlalchemy_store

    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'phase1_round.db'}")
    monkeypatch.setenv("INTERVIV_USE_MEMORY_DB", "false")
    _clear_caches()
    sqlalchemy_store.create_all_for_smoke()
    try:
        yield sqlalchemy_store.get_sqlalchemy_database()
    finally:
        sqlalchemy_store.get_engine().dispose()
        _clear_caches()


def test_round_type_columns_survive_full_replace_save(phase1_db) -> None:
    """New columns must be mapped on write AND read: saves replace all rows."""
    sessions = phase1_db["sessions"]
    sessions.insert_one(
        {
            "session_id": "phase1-r1",
            "skill": "DSA",
            "skills": ["DSA"],
            "rounds_per_skill": 3,
            "template_id": None,
            "rounds": [
                {
                    "round": 1,
                    "skill": "DSA",
                    "question": "What is a stack?",
                    "round_type": "technical_short_answer",
                    "artifact_json": {},
                    "config_json": {"time_limit_s": 300},
                }
            ],
        }
    )
    stored = sessions.find_one({"session_id": "phase1-r1"})
    assert stored is not None
    assert stored["template_id"] is None
    assert stored["rounds"][0]["round_type"] == "technical_short_answer"
    assert stored["rounds"][0]["artifact_json"] == {}
    assert stored["rounds"][0]["config_json"] == {"time_limit_s": 300}


def test_legacy_round_document_without_type_keys_defaults(phase1_db) -> None:
    """Pre-Phase-1 documents carry no type keys; they must read back typed."""
    sessions = phase1_db["sessions"]
    sessions.insert_one(
        {
            "session_id": "phase1-legacy",
            "skill": "DSA",
            "skills": ["DSA"],
            "rounds_per_skill": 3,
            "rounds": [{"round": 1, "skill": "DSA", "question": "What is a queue?"}],
        }
    )
    stored = sessions.find_one({"session_id": "phase1-legacy"})
    assert stored is not None
    assert stored["rounds"][0]["round_type"] == "technical_short_answer"
    assert stored["rounds"][0]["artifact_json"] == {}
    assert stored["rounds"][0]["config_json"] == {}
