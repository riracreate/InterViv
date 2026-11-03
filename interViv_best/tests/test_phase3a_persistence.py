"""Phase 3A: atomic start / atomic attempt commits on both backends.

- /session/start commits candidate + session + Elo seeds as one unit, and
  content failures (422) happen before any write: no orphan candidates,
  no sessions missing from their candidate.
- /session/answer commits scored round + Elo as one unit. A 503 inside the
  commit leaves the claimed-but-unscored round behind, and the retry is a
  clean resubmit (stale-claim takeover) — never a 409 lockout, never a
  double-applied Elo or a duplicated next round.
- atomic() fails closed on unknown backends.

Memory-backed tests run on the default backend; the sqlalchemy section
binds the app to a disposable SQLite file per test (same pattern as
test_phaseB1_persistence.py).
"""

from __future__ import annotations

import os
from datetime import datetime, timezone
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

os.environ.setdefault("INTERVIV_USE_MEMORY_DB", "true")
os.environ.setdefault("JWT_SECRET_KEY", "test-secret-key-with-at-least-32-bytes!!")
os.environ["OPENAI_API_KEY"] = ""
os.environ["OPENROUTER_API_KEY"] = ""

from backend import config as app_config
from backend.auth.security import create_access_token, hash_password
from backend.config import get_settings
from backend.db import DatabaseConnectionError, get_database
from backend.db.memory import _MemoryDB
from backend.db.sqlalchemy_store import (
    _sessionmaker,
    create_all_for_smoke,
    get_engine,
    get_sqlalchemy_database,
)
from backend.db.transactions import atomic
from backend.main import app


def _make_user(prefix: str = "phase3aatomic") -> dict[str, str]:
    db = get_database()
    user_id = str(uuid4())
    db["users"].insert_one({
        "id": user_id,
        "email": f"{prefix}-{user_id[:8]}@example.com",
        "name": f"Test {prefix}",
        "password_hash": hash_password("passw0rd123"),
        "created_at": datetime.now(timezone.utc),
        "last_active_at": datetime.now(timezone.utc),
    })
    return {"id": user_id, "token": create_access_token(user_id)}


def _headers(user) -> dict[str, str]:
    return {"Authorization": f"Bearer {user['token']}"}


def _interview_block(skills, topic=None, **over):
    block = {"round_type": "technical_short_answer", "category": "interview",
             "skills": list(skills), "count": 1}
    if topic is not None:
        block["topic"] = topic
    block.update(over)
    return block


def _fail_once(monkeypatch, collection, method="update_one"):
    """Make the next collection write raise DatabaseConnectionError (503)."""
    original = getattr(collection, method)
    calls: list[int] = []

    def flaky(*args, **kwargs):
        calls.append(1)
        if len(calls) == 1:
            raise DatabaseConnectionError("injected commit failure")
        return original(*args, **kwargs)

    monkeypatch.setattr(collection, method, flaky)
    return calls


# ── memory backend ──────────────────────────────────────────────────────


def test_start_422_creates_no_candidate_and_no_session() -> None:
    client = TestClient(app)
    user = _make_user("t3a-noorphan")
    headers = _headers(user)
    db = get_database()
    sessions_before = db["sessions"].count_documents({})
    candidates_before = db["candidates"].count_documents({})

    # Unsatisfiable scope fails upfront: the opening-round build raises
    # before any write, so neither document may exist afterwards.
    start = client.post("/session/start", headers=headers, json={
        "blocks": [_interview_block(["DBMS"], topic="zzzz-nope")],
    })
    assert start.status_code == 422, start.text
    assert get_database()["sessions"].find_one({"user_id": user["id"]}) is None
    assert get_database()["candidates"].find_one({"user_id": user["id"]}) is None
    assert db["sessions"].count_documents({}) == sessions_before
    assert db["candidates"].count_documents({}) == candidates_before


def test_start_commit_failure_rolls_back_everything(monkeypatch) -> None:
    client = TestClient(app)
    headers = _headers(_make_user("t3a-startroll"))
    db = get_database()
    sessions_before = db["sessions"].count_documents({})
    candidates_before = db["candidates"].count_documents({})
    _fail_once(monkeypatch, db["candidates"])

    failed = client.post("/session/start", headers=headers, json={
        "blocks": [_interview_block(["DBMS"], count=2)],
    })
    assert failed.status_code == 503, failed.text
    # Candidate insert + session insert + candidate update committed as
    # one unit: the mid-commit failure left nothing behind.
    assert db["sessions"].count_documents({}) == sessions_before
    assert db["candidates"].count_documents({}) == candidates_before

    retry = client.post("/session/start", headers=headers, json={
        "blocks": [_interview_block(["DBMS"], count=2)],
    })
    assert retry.status_code == 200, retry.text
    assert db["sessions"].count_documents({}) == sessions_before + 1


def test_submit_commit_failure_rolls_back_and_retry_scores_once(monkeypatch) -> None:
    client = TestClient(app)
    headers = _headers(_make_user("t3a-submitroll"))
    db = get_database()
    start = client.post("/session/start", headers=headers, json={
        "blocks": [_interview_block(["DBMS"], count=2)],
    })
    assert start.status_code == 200, start.text
    session_id = start.json()["session_id"]
    candidate_id = start.json()["candidate_id"]
    initial_elo = float(get_settings().initial_elo)
    payload = {"session_id": session_id, "round": 1,
               "answer_text": "ACID transactions keep related writes atomic."}

    _fail_once(monkeypatch, db["candidates"])
    failed = client.post("/session/answer", headers=headers, json=payload)
    assert failed.status_code == 503, failed.text

    stored = db["sessions"].find_one({"session_id": session_id})
    assert len(stored["rounds"]) == 1
    assert stored["rounds"][0]["final_score"] is None
    assert stored["rounds"][0].get("answer_text") is None
    # The claim (separate commit, crash marker) survived; the score did not.
    assert stored["rounds"][0]["status"] == "finalizing"
    candidate = db["candidates"].find_one({"candidate_id": candidate_id})
    assert float(candidate["elo_ratings"]["DBMS"]) == initial_elo

    retry = client.post("/session/answer", headers=headers, json=payload)
    assert retry.status_code == 200, retry.text
    body = retry.json()
    # Elo applied exactly once; next round appended exactly once.
    candidate = db["candidates"].find_one({"candidate_id": candidate_id})
    assert float(candidate["elo_ratings"]["DBMS"]) == float(body["elo_after"])
    stored = db["sessions"].find_one({"session_id": session_id})
    assert len(stored["rounds"]) == 2
    assert stored["rounds"][0]["status"] == "submitted"
    # The next round is prepared, not started, until the candidate opens it.
    assert stored["rounds"][1]["status"] == "ready"


def test_stale_finalizing_claim_is_taken_over() -> None:
    client = TestClient(app)
    headers = _headers(_make_user("t3a-takeover"))
    db = get_database()
    start = client.post("/session/start", headers=headers, json={
        "blocks": [_interview_block(["DBMS"], count=1)],
    })
    assert start.status_code == 200, start.text
    session_id = start.json()["session_id"]

    # A previous submit died between claim and commit: finalizing marker
    # with no scored data. The retry takes over instead of 409ing forever.
    raw = db["sessions"].find_one({"session_id": session_id})
    assert raw["rounds"][0]["final_score"] is None
    raw["rounds"][0]["status"] = "finalizing"
    db["sessions"].update_one(
        {"session_id": session_id}, {"$set": {"rounds": raw["rounds"]}}
    )

    answer = client.post("/session/answer", headers=headers, json={
        "session_id": session_id, "round": 1,
        "answer_text": "A database index speeds up lookups on a column.",
    })
    assert answer.status_code == 200, answer.text
    stored = db["sessions"].find_one({"session_id": session_id})
    assert stored["rounds"][0]["status"] == "submitted"
    assert stored["rounds"][0]["final_score"] is not None


def test_atomic_rejects_unknown_backend() -> None:
    with pytest.raises(TypeError):
        with atomic(object()):
            pass


def test_memory_atomic_rolls_back_restores_and_nests() -> None:
    db = _MemoryDB()
    db["a"].insert_one({"_id": "x", "v": 1})

    with pytest.raises(RuntimeError):
        with atomic(db):
            db["a"].insert_one({"_id": "y", "v": 2})
            db["brand_new"].insert_one({"_id": "z"})
            with atomic(db):
                db["a"].update_one({"_id": "x"}, {"$set": {"v": 99}})
            raise RuntimeError("boom")
    assert db["a"].count_documents({}) == 1
    assert db["a"].find_one({"_id": "x"})["v"] == 1
    assert "brand_new" not in db._cols

    with atomic(db):
        db["a"].insert_one({"_id": "y", "v": 2})
    assert db["a"].count_documents({}) == 2


# ── sqlalchemy backend (disposable SQLite) ──────────────────────────────


def _clear_db_caches() -> None:
    app_config.get_settings.cache_clear()
    get_engine.cache_clear()
    _sessionmaker.cache_clear()
    get_sqlalchemy_database.cache_clear()


@pytest.fixture
def sa_url(tmp_path, monkeypatch):
    db_file = tmp_path / "phase3a.db"
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


def test_start_atomic_sqlalchemy_rolls_back(sa_url, monkeypatch) -> None:
    client = TestClient(app)
    headers = _headers(_make_user("t3a-sastart"))
    db = get_database()
    _fail_once(monkeypatch, db["candidates"])

    failed = client.post("/session/start", headers=headers, json={
        "blocks": [_interview_block(["DBMS"], count=2)],
    })
    assert failed.status_code == 503, failed.text
    assert db["sessions"].count_documents({}) == 0
    assert db["candidates"].count_documents({}) == 0

    retry = client.post("/session/start", headers=headers, json={
        "blocks": [_interview_block(["DBMS"], count=2)],
    })
    assert retry.status_code == 200, retry.text
    stored = db["sessions"].find_one({"session_id": retry.json()["session_id"]})
    assert len(stored["rounds"]) == 1
    candidate = db["candidates"].find_one(
        {"candidate_id": retry.json()["candidate_id"]})
    assert retry.json()["session_id"] in (candidate["session_history"] or [])


def test_submit_atomic_sqlalchemy_retry_scores_once(sa_url, monkeypatch) -> None:
    client = TestClient(app)
    headers = _headers(_make_user("t3a-sasubmit"))
    db = get_database()
    start = client.post("/session/start", headers=headers, json={
        "blocks": [_interview_block(["DBMS"], count=2)],
    })
    assert start.status_code == 200, start.text
    session_id = start.json()["session_id"]
    candidate_id = start.json()["candidate_id"]
    initial_elo = float(get_settings().initial_elo)
    payload = {"session_id": session_id, "round": 1,
               "answer_text": "ACID transactions keep related writes atomic."}

    _fail_once(monkeypatch, db["candidates"])
    failed = client.post("/session/answer", headers=headers, json=payload)
    assert failed.status_code == 503, failed.text
    stored = db["sessions"].find_one({"session_id": session_id})
    assert len(stored["rounds"]) == 1
    assert stored["rounds"][0]["final_score"] is None
    assert stored["rounds"][0]["status"] == "finalizing"
    candidate = db["candidates"].find_one({"candidate_id": candidate_id})
    assert float(candidate["elo_ratings"]["DBMS"]) == initial_elo

    retry = client.post("/session/answer", headers=headers, json=payload)
    assert retry.status_code == 200, retry.text
    candidate = db["candidates"].find_one({"candidate_id": candidate_id})
    assert float(candidate["elo_ratings"]["DBMS"]) == float(retry.json()["elo_after"])
    stored = db["sessions"].find_one({"session_id": session_id})
    assert len(stored["rounds"]) == 2
    assert stored["rounds"][1]["round_type"] == "technical_short_answer"
