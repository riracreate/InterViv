"""Acceptance: concurrent session writers serialize without lost updates.

Every session writer (answer submit, continuation, follow-up scheduling,
expiry marks, rollbacks, dry-run slots) shares one optimistic-concurrency
protocol: narrow ``sessions.update_one`` writes gated on ``revision``. On a
lost race the attempt persisted nothing, so the caller reloads,
revalidates, and retries with a bounded budget; exhaustion is a controlled
409.

These tests simulate independent workers: threads share no process lock
(the per-session submit lock is rigged to hand out a fresh lock per call),
use independent SQL connections on one disposable SQLite file, and meet at
barriers placed so both sides hold a stale snapshot before either commits.
Every test reopens the database (disposed pool, fresh connections) and
verifies the final persisted state: both operations must remain
represented, with no duplicated scoring, Elo, exposures, snapshots, or
narration jobs.
"""

from __future__ import annotations

import os
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

os.environ.setdefault("JWT_SECRET_KEY", "test-secret-key-with-at-least-32-bytes!!")

from backend.auth.security import create_access_token, hash_password  # noqa: E402
from backend.db import get_database  # noqa: E402
from backend.main import app  # noqa: E402


def _clear_db_caches() -> None:
    from backend import config
    from backend.db import sqlalchemy_store

    config.get_settings.cache_clear()
    sqlalchemy_store.get_engine.cache_clear()
    sqlalchemy_store._sessionmaker.cache_clear()
    sqlalchemy_store.get_sqlalchemy_database.cache_clear()


@pytest.fixture
def sql_db(tmp_path, monkeypatch):
    """Disposable SQLite store whose engine is safe for threaded use.

    When ``INTERVIV_TEST_DATABASE_URL`` is set, that database is used
    instead and each test starts from ``alembic upgrade head``.
    """
    from sqlalchemy import create_engine

    from tests.sql_test_url import (
        is_postgres,
        reset_postgres_schema,
        resolve_sql_url,
        upgrade_head,
    )

    url = resolve_sql_url(tmp_path, "write-races.db")
    monkeypatch.setenv("DATABASE_URL", url)
    monkeypatch.setenv("INTERVIV_USE_MEMORY_DB", "false")
    _clear_db_caches()
    if is_postgres(url):
        reset_postgres_schema(url)
        upgrade_head(url)
        _clear_db_caches()
    connect_args = (
        {}
        if is_postgres(url)
        else {"check_same_thread": False, "timeout": 30}
    )
    engine = create_engine(
        url,
        connect_args=connect_args,
        pool_pre_ping=True,
        future=True,
    )
    from backend import config as app_config
    from backend.db import sqlalchemy_store

    monkeypatch.setattr(sqlalchemy_store, "get_engine", lambda: engine)
    sqlalchemy_store._sessionmaker.cache_clear()
    sqlalchemy_store.get_sqlalchemy_database.cache_clear()
    from backend.db.sqlalchemy_store import (
        create_all_for_smoke,
        get_sqlalchemy_database,
    )

    create_all_for_smoke()
    try:
        yield get_sqlalchemy_database(), engine
    finally:
        engine.dispose()
        # get_engine itself is a monkeypatched lambda here (no cache to
        # clear); everything else must reset so no settings leak out.
        app_config.get_settings.cache_clear()
        sqlalchemy_store._sessionmaker.cache_clear()
        sqlalchemy_store.get_sqlalchemy_database.cache_clear()
        if is_postgres(url):
            reset_postgres_schema(url)


@pytest.fixture
def independent_workers(monkeypatch):
    """Simulate separate workers: no shared process-local exclusion."""

    def _fresh_lock(session_id: str):
        return threading.Lock()

    monkeypatch.setattr("backend.routes.answer._get_submit_lock", _fresh_lock)


def _make_user(prefix: str) -> dict[str, str]:
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


def _gate_first_writes(monkeypatch, barrier, sides):
    """Hold the first matching sessions.update_one per side at a barrier.

    ``sides`` is a list of ``(name, keys)``; the first call whose ``$set``
    covers ``keys`` waits at the barrier before executing, which forces
    both sides to commit from a stale snapshot. Later calls (retries) pass
    straight through.
    """
    from backend.db import sqlalchemy_store

    original = sqlalchemy_store._SessionCollection.update_one
    seen: set[str] = set()
    guard = threading.Lock()

    def gated(self, query, update, upsert=False, *, expected_revision=None):
        keys = set(((update or {}).get("$set") or {}).keys())
        hit = None
        with guard:
            for name, want in sides:
                if name not in seen and set(want) <= keys:
                    seen.add(name)
                    hit = name
                    break
        if hit is not None:
            barrier.wait(timeout=30)
        return original(
            self, query, update, upsert, expected_revision=expected_revision
        )

    monkeypatch.setattr(
        sqlalchemy_store._SessionCollection, "update_one", gated
    )


def _reopen(engine):
    """Drop every pooled connection so later reads come from the file."""
    engine.dispose()


def _submitted_round(number: int, **over) -> dict[str, Any]:
    doc = {
        "round": number,
        "round_type": "technical_short_answer",
        "skill": "DBMS",
        "question": f"Stored question {number}?",
        "answer_text": f"Stored answer {number}.",
        "final_score": 70.0,
        "difficulty": "medium",
        "status": "submitted",
        "feedback": {"content": [], "strengths": [], "next_step": ""},
    }
    doc.update(over)
    return doc


def _exposures_for(db, session_id, parent_round):
    return [
        doc
        for doc in (db["teaching_exposures"].find({"session_id": session_id}) or [])
        if doc.get("round") == parent_round
        and doc.get("content_kind") == "follow_up_prompt"
    ]


def _elo_deltas_for(session_id: str) -> list:
    from backend.db.sqlalchemy_models import LearningEventRow
    from backend.db.sqlalchemy_store import session_scope
    from modules.learning_signals import EVENT_ELO_DELTA

    with session_scope() as session:
        return (
            session.query(LearningEventRow)
            .filter(
                LearningEventRow.session_id == session_id,
                LearningEventRow.event_type == EVENT_ELO_DELTA,
            )
            .all()
        )


def _narrations_for(db, session_id: str, round_number: int) -> list:
    return [
        doc
        for doc in (db["narration_jobs"].find({"session_id": session_id}) or [])
        if doc.get("round_number") == round_number or doc.get("round") == round_number
    ]


def test_submit_racing_schedule_both_effects_survive(
    sql_db, independent_workers, monkeypatch
):
    """Answer submission racing follow-up scheduling: no lost update.

    Both workers commit from the same snapshot; the loser reloads and
    retries. Whichever order wins, the reopened session holds the scored
    round AND the pending follow-up, with each side effect applied once.
    """
    db, engine = sql_db
    user = _make_user("race-submit")
    headers = _headers(user)
    client = TestClient(app)
    started = client.post("/session/start", headers=headers, json={"blocks": [
        {"round_type": "technical_short_answer", "category": "interview",
         "skills": ["DBMS"], "count": 2, "allow_optional_follow_ups": True},
    ]})
    assert started.status_code == 200, started.text
    sid = started.json()["session_id"]
    first = client.post("/session/answer", headers=headers, json={
        "session_id": sid, "round": 1,
        "answer_text": "A primary key uniquely identifies each row.",
    })
    assert first.status_code == 200, first.text

    from backend.routes import answer as answer_module

    real_score = answer_module.score_round
    score_calls: list[str] = []

    def _counted_score(**kwargs):
        score_calls.append("scored")
        return real_score(**kwargs)

    monkeypatch.setattr(answer_module, "score_round", _counted_score)
    barrier = threading.Barrier(2)
    _gate_first_writes(monkeypatch, barrier, [
        ("submit", {"rounds"}),
        ("schedule", {"expanded_plan"}),
    ])
    client_a, client_b = TestClient(app), TestClient(app)

    def _submit():
        return client_a.post("/session/answer", headers=headers, json={
            "session_id": sid, "round": 2,
            "answer_text": "A database index speeds up lookups on a column.",
        })

    def _schedule():
        return client_b.post(f"/session/{sid}/follow-ups", headers=headers, json={
            "parent_round": 1, "accept_eligibility_consequence": True,
        })

    with ThreadPoolExecutor(max_workers=2) as pool:
        submitted, scheduled = list(pool.map(lambda fn: fn(), [_submit, _schedule]))
    assert submitted.status_code == 200, submitted.text
    assert scheduled.status_code == 200, scheduled.text
    assert scheduled.json().get("scheduled") is True
    # The retried commit reuses this request's scoring result: scored once.
    assert len(score_calls) == 1

    _reopen(engine)
    final = db["sessions"].find_one({"session_id": sid})
    assert final["total_rounds"] == 3
    rounds = final["rounds"]
    assert len(rounds) in (2, 3)
    assert rounds[1]["status"] == "submitted"
    assert rounds[1]["final_score"] is not None
    from modules.follow_ups import pending_follow_ups

    pending = pending_follow_ups(final)
    assert len(pending) == 1
    assert pending[0]["follow_up_parent_round"] == 1
    # Either serialization is valid, and each is self-consistent.
    if len(rounds) == 2:
        assert final["status"] == "completed"
    else:
        assert final["status"] == "active"
        assert rounds[2]["status"] == "in_progress"
    # Exactly three session writes happened (round-1 submit, schedule,
    # round-2 submit); the rolled-back attempt left no trace.
    assert final["revision"] == 3
    assert len(_narrations_for(db, sid, 2)) == 1
    assert len(_exposures_for(db, sid, 1)) == 1
    assert len(_elo_deltas_for(sid)) == 2
    candidate = db["candidates"].find_one(
        {"candidate_id": started.json()["candidate_id"]}
    )
    assert float(candidate["elo_ratings"]["DBMS"]) == float(
        submitted.json()["elo_after"]
    )


def _blocked_session(db, user_id: str, sid: str, submitted: list[dict]) -> None:
    db["candidates"].insert_one({
        "candidate_id": f"cand-{sid}",
        "user_id": user_id,
        "elo_ratings": {"DBMS": 1500.0},
        "session_history": [sid],
    })
    db["sessions"].insert_one({
        "session_id": sid,
        "user_id": user_id,
        "candidate_id": f"cand-{sid}",
        "status": "content_blocked",
        "progression_blocked_reason": "seeded for race test",
        "skills": ["DBMS"],
        "total_rounds": 2,
        "practice_mode": "coached_practice",
        "allow_optional_follow_ups": True,
        "rounds": submitted,
    })


def test_continue_racing_schedule_both_effects_survive(
    sql_db, independent_workers, monkeypatch
):
    """Continuation racing follow-up scheduling: single next round kept.

    The loser reloads and re-decides; the reopened session holds the one
    appended round, the active status, and the pending follow-up entry.
    """
    db, engine = sql_db
    user = _make_user("race-continue")
    headers = _headers(user)
    sid = "race-continue-1"
    _blocked_session(db, user["id"], sid, [_submitted_round(1)])
    barrier = threading.Barrier(2)
    _gate_first_writes(monkeypatch, barrier, [
        ("continue", {"rounds"}),
        ("schedule", {"expanded_plan"}),
    ])
    client_a, client_b = TestClient(app), TestClient(app)

    def _continue():
        return client_a.post(f"/session/{sid}/continue", headers=headers)

    def _schedule():
        return client_b.post(f"/session/{sid}/follow-ups", headers=headers, json={
            "parent_round": 1, "accept_eligibility_consequence": True,
        })

    with ThreadPoolExecutor(max_workers=2) as pool:
        continued, scheduled = list(
            pool.map(lambda fn: fn(), [_continue, _schedule])
        )
    assert continued.status_code == 200, continued.text
    assert continued.json()["round"] == 2
    assert scheduled.status_code == 200, scheduled.text
    assert scheduled.json().get("scheduled") is True

    _reopen(engine)
    final = db["sessions"].find_one({"session_id": sid})
    assert final["status"] == "active"
    assert final["total_rounds"] == 3
    assert len(final["rounds"]) == 2
    assert final["rounds"][1]["status"] == "in_progress"
    from modules.follow_ups import pending_follow_ups

    pending = pending_follow_ups(final)
    assert len(pending) == 1
    assert pending[0]["follow_up_parent_round"] == 1
    assert final["revision"] == 2
    assert len(_exposures_for(db, sid, 1)) == 1


def test_allocation_conflict_rolls_back_and_retries_without_duplicates(sql_db):
    """Forced write conflicts: failed attempts leave nothing behind."""
    from backend.db import sqlalchemy_store
    from backend.db.follow_up_allocate import allocate_follow_up
    from backend.db.sqlalchemy_store import SessionWriteConflict
    from modules.follow_ups import build_follow_up_plan_entry

    db, engine = sql_db
    db["sessions"].insert_one({
        "session_id": "race-alloc",
        "user_id": "u-alloc",
        "skills": ["DBMS"],
        "total_rounds": 1,
        "practice_mode": "coached_practice",
        "allow_optional_follow_ups": True,
        "rounds": [_submitted_round(1)],
    })
    parent = db["sessions"].find_one({"session_id": "race-alloc"})["rounds"][0]
    entry = build_follow_up_plan_entry(
        parent_round_doc=parent,
        reviewed_bundle=None,
        clarification_prompt="Clarify X",
    )
    original = sqlalchemy_store._SessionCollection.update_one
    calls: list[str] = []

    def flaky(self, query, update, upsert=False, *, expected_revision=None):
        calls.append("write")
        if len(calls) <= 2:
            raise SessionWriteConflict("injected race loss")
        return original(
            self, query, update, upsert, expected_revision=expected_revision
        )

    sqlalchemy_store._SessionCollection.update_one = flaky
    try:
        result = allocate_follow_up(
            db, session_id="race-alloc", parent_round=1, plan_entry=entry
        )
    finally:
        sqlalchemy_store._SessionCollection.update_one = original
    assert result["scheduled"] is True
    assert result["attempts"] == 3

    _reopen(engine)
    final = db["sessions"].find_one({"session_id": "race-alloc"})
    assert final["total_rounds"] == 2
    assert len(final["expanded_plan"]) == 1
    assert final["revision"] == 1
    # The two rolled-back attempts left no exposures and no plan entries.
    assert len(_exposures_for(db, "race-alloc", 1)) == 1


def test_concurrent_allocations_for_distinct_parents_both_win(
    sql_db, monkeypatch
):
    """Two schedulers racing on one session: both bookings persist.

    The barrier forces both attempts to validate against the same
    snapshot, so exactly one wins first and the other retries (attempts
    [1, 2]) — proving a real conflict and a clean retry, not a lucky
    serialization.
    """
    from backend.db.follow_up_allocate import allocate_follow_up
    from modules.follow_ups import build_follow_up_plan_entry

    db, engine = sql_db
    db["sessions"].insert_one({
        "session_id": "race-alloc-2",
        "user_id": "u-alloc-2",
        "skills": ["DBMS"],
        "total_rounds": 2,
        "practice_mode": "coached_practice",
        "allow_optional_follow_ups": True,
        "rounds": [_submitted_round(1), _submitted_round(2)],
    })
    live = db["sessions"].find_one({"session_id": "race-alloc-2"})
    entries = {
        n: build_follow_up_plan_entry(
            parent_round_doc=next(
                r for r in live["rounds"] if r["round"] == n
            ),
            reviewed_bundle=None,
            clarification_prompt=f"Clarify {n}",
        )
        for n in (1, 2)
    }
    barrier = threading.Barrier(2)
    _gate_first_writes(monkeypatch, barrier, [
        ("first", {"expanded_plan"}),
        ("second", {"expanded_plan"}),
    ])

    def _once(parent_round: int):
        return allocate_follow_up(
            db,
            session_id="race-alloc-2",
            parent_round=parent_round,
            plan_entry=entries[parent_round],
        )

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(_once, [1, 2]))
    assert [r["scheduled"] for r in results] == [True, True]
    assert sorted(r["attempts"] for r in results) == [1, 2]

    _reopen(engine)
    final = db["sessions"].find_one({"session_id": "race-alloc-2"})
    assert final["total_rounds"] == 4
    assert len(final["expanded_plan"]) == 2
    assert final["revision"] == 2
    assert len(_exposures_for(db, "race-alloc-2", 1)) == 1
    assert len(_exposures_for(db, "race-alloc-2", 2)) == 1


def test_concurrent_continues_append_next_round_once(
    sql_db, independent_workers, monkeypatch
):
    """Two continuations racing: the next round is appended exactly once.

    The loser reloads, finds the winner's open round, and returns it
    instead of appending a duplicate.
    """
    db, engine = sql_db
    user = _make_user("race-dblcontinue")
    headers = _headers(user)
    sid = "race-continue-2"
    _blocked_session(db, user["id"], sid, [_submitted_round(1)])
    barrier = threading.Barrier(2)
    _gate_first_writes(monkeypatch, barrier, [
        ("first", {"rounds"}),
        ("second", {"rounds"}),
    ])
    client_a, client_b = TestClient(app), TestClient(app)

    def _continue(client):
        return client.post(f"/session/{sid}/continue", headers=headers)

    with ThreadPoolExecutor(max_workers=2) as pool:
        first, second = list(
            pool.map(_continue, [client_a, client_b])
        )
    assert first.status_code == 200, first.text
    assert second.status_code == 200, second.text
    assert first.json()["round"] == 2
    assert second.json()["round"] == 2

    _reopen(engine)
    final = db["sessions"].find_one({"session_id": sid})
    assert final["status"] == "active"
    assert len(final["rounds"]) == 2
    assert final["rounds"][1]["status"] == "in_progress"
    # One append happened; the loser's retry wrote nothing.
    assert final["revision"] == 1


def test_stale_write_fails_instead_of_clobbering(sql_db):
    """The store protocol, directly: stale fails, narrow never crosses.

    A write conditioned on an outdated revision raises with nothing
    persisted — not even partially. A write without that expectation
    still only touches its own fields, so a ``rounds`` commit physically
    cannot drop a concurrently committed plan entry.
    """
    from backend.db.sqlalchemy_store import SessionWriteConflict

    db, engine = sql_db
    db["sessions"].insert_one({
        "session_id": "race-store",
        "user_id": "u-store",
        "skills": ["DBMS"],
        "total_rounds": 1,
        "rounds": [_submitted_round(1)],
    })
    stale = db["sessions"].find_one({"session_id": "race-store"})
    assert stale["revision"] == 0

    # A concurrent scheduler commits a plan entry first.
    db["sessions"].update_one(
        {"session_id": "race-store"},
        {"$set": {
            "expanded_plan": [{"is_follow_up": True, "follow_up_identity": "f1"}],
            "total_rounds": 2,
        }},
        expected_revision=0,
    )
    assert db["sessions"].find_one({"session_id": "race-store"})["revision"] == 1

    # The stale rounds commit fails instead of clobbering the plan.
    clobber = [dict(r, answer_text="stale overwrite") for r in stale["rounds"]]
    with pytest.raises(SessionWriteConflict):
        db["sessions"].update_one(
            {"session_id": "race-store"},
            {"$set": {"rounds": clobber}},
            expected_revision=stale["revision"],
        )
    after_conflict = db["sessions"].find_one({"session_id": "race-store"})
    assert after_conflict["rounds"][0]["answer_text"] == "Stored answer 1."
    assert after_conflict["expanded_plan"][0]["follow_up_identity"] == "f1"
    assert after_conflict["total_rounds"] == 2
    assert after_conflict["revision"] == 1

    # Even an unconditioned write is field-scoped: rounds land, plan stays.
    db["sessions"].update_one(
        {"session_id": "race-store"},
        {"$set": {"rounds": clobber}},
    )
    narrowed = db["sessions"].find_one({"session_id": "race-store"})
    assert narrowed["rounds"][0]["answer_text"] == "stale overwrite"
    assert narrowed["expanded_plan"][0]["follow_up_identity"] == "f1"
    assert narrowed["total_rounds"] == 2
    assert narrowed["revision"] == 2

    # Parity with the old write path: unknown keys are still dropped, and
    # a no-op $set performs no write and no revision bump.
    db["sessions"].update_one(
        {"session_id": "race-store"},
        {"$set": {"overall_readiness_population": "assessment_eligible"}},
    )
    assert "overall_readiness_population" not in db["sessions"].find_one(
        {"session_id": "race-store"}
    )
    result = db["sessions"].update_one(
        {"session_id": "race-store"},
        {"$set": {"status": narrowed["status"]}},
        expected_revision=2,
    )
    assert result.modified_count == 0
    assert db["sessions"].find_one({"session_id": "race-store"})["revision"] == 2
    _reopen(engine)
    assert db["sessions"].find_one({"session_id": "race-store"})["revision"] == 2


def test_memory_update_accepts_expected_revision_for_parity():
    """The memory adapter takes the protocol kwarg (single-process)."""
    from backend.db.memory import _MemoryDB

    db = _MemoryDB()
    db["sessions"].insert_one({"session_id": "m1", "status": "active"})
    result = db["sessions"].update_one(
        {"session_id": "m1"},
        {"$set": {"status": "completed"}},
        expected_revision=999,
    )
    assert result.matched_count == 1
    assert db["sessions"].find_one({"session_id": "m1"})["status"] == "completed"


def test_submit_reclaims_claim_overwritten_by_racing_writer(sql_db, monkeypatch):
    """A submit whose claim was wiped reclaims instead of 409ing.

    The racing writer's effect (its rounds state) survives, and the
    submit commits exactly once on top: scored exactly once, one narration
    job, one Elo delta.
    """
    db, engine = sql_db
    user = _make_user("race-reclaim")
    headers = _headers(user)
    client = TestClient(app)
    started = client.post("/session/start", headers=headers, json={"blocks": [
        {"round_type": "technical_short_answer", "category": "interview",
         "skills": ["DBMS"], "count": 1},
    ]})
    assert started.status_code == 200, started.text
    sid = started.json()["session_id"]

    from backend.routes import answer as answer_module

    real_score = answer_module.score_round
    scoring_started = threading.Event()
    release_scoring = threading.Event()
    score_calls: list[str] = []

    def _gated_score(**kwargs):
        score_calls.append("scored")
        scoring_started.set()
        assert release_scoring.wait(timeout=30)
        return real_score(**kwargs)

    monkeypatch.setattr(answer_module, "score_round", _gated_score)
    client_a = TestClient(app)

    def _submit():
        return client_a.post("/session/answer", headers=headers, json={
            "session_id": sid, "round": 1,
            "answer_text": "A database index speeds up lookups on a column.",
        })

    with ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(_submit)
        assert scoring_started.wait(timeout=30)
        # The claim ("finalizing") is committed but bumps no revision; a
        # racing writer overwrites the rounds state from its own snapshot.
        mid = db["sessions"].find_one({"session_id": sid})
        assert mid["rounds"][0]["status"] == "finalizing"
        wiped = [dict(r, status="in_progress") for r in mid["rounds"]]
        db["sessions"].update_one(
            {"session_id": sid}, {"$set": {"rounds": wiped}}
        )
        wiped_rev = db["sessions"].find_one({"session_id": sid})["revision"]
        release_scoring.set()
        response = future.result(timeout=60)

    assert response.status_code == 200, response.text
    assert len(score_calls) == 1
    _reopen(engine)
    final = db["sessions"].find_one({"session_id": sid})
    assert final["rounds"][0]["status"] == "submitted"
    assert final["rounds"][0]["final_score"] is not None
    assert final["revision"] == wiped_rev + 1
    assert len(_narrations_for(db, sid, 1)) == 1
    assert len(_elo_deltas_for(sid)) == 1
