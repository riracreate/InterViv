"""Acceptance: follow-up allocation is atomic in persistent storage.

Closes the Phase 4B follow-up scheduling gap (caps were application-level
under a process-local lock, and pending entries were invisible to caps):

* at most one follow-up per parent (materialized + pending),
* at most two per Interview block, or the lower configured ``max_follow_ups``,
* session cap respected with mandatory rounds reserved,
* concurrent workers cannot overspend shared block/session budgets,
* failed/conflicting allocations leave no partial changes or exposures,
* round identities, snapshots, feedback, narration jobs preserved.

Concurrency tests use independent SQL connections (overlapping
transactions, distinct DBAPI connections) with no shared Python lock: the
per-session submit lock is rigged to explode if touched.
"""

from __future__ import annotations

import os
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from typing import Any

import pytest

os.environ.setdefault("JWT_SECRET_KEY", "test-secret-key-with-at-least-32-bytes!!")

from backend.db.follow_up_allocate import allocate_follow_up
from backend.db.memory import _MemoryDB
from backend.models.blocks import MAX_TOTAL_ROUNDS, normalize_blocks
from modules.follow_ups import (
    block_follow_up_limit,
    build_follow_up_plan_entry,
    can_schedule_follow_up,
)


def _clear_db_caches() -> None:
    from backend import config
    from backend.db import sqlalchemy_store

    config.get_settings.cache_clear()
    sqlalchemy_store.get_engine.cache_clear()
    sqlalchemy_store._sessionmaker.cache_clear()
    sqlalchemy_store.get_sqlalchemy_database.cache_clear()


@pytest.fixture
def memory_db(monkeypatch):
    from backend import config as app_config

    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setenv("INTERVIV_USE_MEMORY_DB", "true")
    app_config.get_settings.cache_clear()
    db = _MemoryDB()
    monkeypatch.setattr("backend.db.get_database", lambda: db)
    monkeypatch.setattr("backend.db.memory.get_memory_database", lambda: db)
    # Routes from-import get_database, which reaches the store through the
    # lru_cached _get_memory_db: patch it too, or a cache populated by an
    # earlier test silently redirects route reads to the global singleton.
    monkeypatch.setattr("backend.db._get_memory_db", lambda: db)
    yield db
    app_config.get_settings.cache_clear()


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

    url = resolve_sql_url(tmp_path, "followup.db")
    monkeypatch.setenv("DATABASE_URL", url)
    monkeypatch.setenv("INTERVIV_USE_MEMORY_DB", "false")
    _clear_db_caches()
    if is_postgres(url):
        reset_postgres_schema(url)
        upgrade_head(url)
        _clear_db_caches()
    connect_args = {} if is_postgres(url) else {"check_same_thread": False}
    engine = create_engine(
        url,
        connect_args=connect_args,
        pool_pre_ping=True,
        future=True,
    )
    from backend import config as app_config
    from backend.db import sqlalchemy_store

    monkeypatch.setattr(sqlalchemy_store, "get_engine", lambda: engine)
    # Rebind dependents to the patched engine (get_engine itself is now a
    # plain lambda with no cache to clear).
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
def no_submit_lock(monkeypatch):
    """Prove the allocator never depends on the process-local submit lock."""

    def _boom(session_id: str):
        raise AssertionError("allocator must not use the process submit lock")

    monkeypatch.setattr("backend.routes.answer._get_submit_lock", _boom)


def _round(number, block_id="b1", skill="DBMS", submitted=True, **over):
    doc = {
        "round": number,
        "round_type": "technical_short_answer",
        "block_id": block_id,
        "block_category": "interview",
        "skill": skill,
        "status": "submitted" if submitted else "in_progress",
        "final_score": 60.0 if submitted else None,
        "answer_text": f"answer {number}" if submitted else None,
        "config_json": {},
        "question_context": {"followups": ["Clarify X"]},
        "question": f"Question {number}?",
    }
    doc.update(over)
    return doc


def _block(block_id="b1", allow=True, max_follow_ups=None):
    block = {
        "id": block_id,
        "category": "interview",
        "round_type": "technical_short_answer",
        "allow_optional_follow_ups": allow,
    }
    if max_follow_ups is not None:
        block["max_follow_ups"] = max_follow_ups
    return block


def _session_doc(session_id="s1", rounds=(), blocks=(), total=None, expanded=None):
    rounds = list(rounds)
    plan = list(expanded) if expanded is not None else [
        {"round_type": "technical_short_answer", "block_id": r.get("block_id"),
         "category": "interview"}
        for r in rounds
        if not r.get("is_follow_up")
    ]
    doc = {
        "session_id": session_id,
        "user_id": "u1",
        "practice_mode": "coached_practice",
        "allow_optional_follow_ups": True,
        "total_rounds": len(plan) if total is None else total,
        "expanded_plan": plan,
        "block_plan": list(blocks),
        "rounds": rounds,
    }
    from backend.db import get_database
    from tests.user_fixtures import ensure_session_parents
    ensure_session_parents(get_database(), doc)
    return doc


def _entry_for(session_round, prompt="Clarify X"):
    return build_follow_up_plan_entry(
        parent_round_doc=session_round,
        reviewed_bundle=None,
        clarification_prompt=prompt,
    )


def _exposures_for(db, session_id, parent_round):
    return [
        doc
        for doc in (db["teaching_exposures"].find({"session_id": session_id}) or [])
        if doc.get("round") == parent_round and doc.get("content_kind") == "follow_up_prompt"
    ]


# ── pure cap rules ────────────────────────────────────────────────────


def test_pending_entry_blocks_same_parent_reschedule():
    rounds = [_round(1)]
    session = _session_doc(rounds=rounds, blocks=[_block()])
    first = _entry_for(rounds[0])
    session["expanded_plan"].append(first)
    session["total_rounds"] = 2
    ok, reason = can_schedule_follow_up(
        session=session, parent_round_doc=rounds[0]
    )
    assert (ok, reason) == (False, "parent_follow_up_exists")


def test_pending_entries_count_toward_block_cap():
    rounds = [_round(1), _round(2), _round(3)]
    session = _session_doc(rounds=rounds, blocks=[_block()])
    session["expanded_plan"].extend([_entry_for(rounds[0]), _entry_for(rounds[1])])
    session["total_rounds"] = 5
    ok, reason = can_schedule_follow_up(
        session=session, parent_round_doc=rounds[2]
    )
    assert (ok, reason) == (False, "block_follow_up_cap")


def test_materialized_follow_up_unpends_its_entry():
    parent = _round(1)
    entry = _entry_for(parent)
    session = _session_doc(
        rounds=[
            parent,
            {"round": 2, "is_follow_up": True, "block_id": "b1",
             "follow_up_parent_round": 1,
             "follow_up_identity": entry["follow_up_identity"]},
        ],
        blocks=[_block()],
        expanded=[
            {"round_type": "technical_short_answer", "block_id": "b1",
             "category": "interview"},
            entry,
        ],
        total=2,
    )
    other_parent = _round(2, block_id="b1")
    session["rounds"].append(other_parent)
    # One budget unit held (materialized), not two: a second parent may book.
    ok, reason = can_schedule_follow_up(
        session=session, parent_round_doc=other_parent
    )
    assert (ok, reason) == (True, "")


def test_configured_block_limit_is_honored_and_capped_at_two():
    assert block_follow_up_limit(None) == 2
    assert block_follow_up_limit({}) == 2
    assert block_follow_up_limit({"max_follow_ups": 1}) == 1
    assert block_follow_up_limit({"max_follow_ups": 0}) == 0
    assert block_follow_up_limit({"max_follow_ups": 9}) == 2
    assert block_follow_up_limit({"max_follow_ups": -1}) == 2
    assert block_follow_up_limit({"max_follow_ups": "many"}) == 2
    assert block_follow_up_limit({"max_follow_ups": True}) == 2


def test_configured_limit_blocks_second_follow_up():
    rounds = [
        _round(1),
        {"round": 2, "is_follow_up": True, "block_id": "b1",
         "follow_up_parent_round": 1, "follow_up_identity": "f1"},
        _round(3),
    ]
    session = _session_doc(rounds=rounds, blocks=[_block(max_follow_ups=1)])
    ok, reason = can_schedule_follow_up(
        session=session, parent_round_doc=rounds[2]
    )
    assert (ok, reason) == (False, "block_follow_up_cap")


def test_normalize_blocks_threads_max_follow_ups():
    plan = normalize_blocks([
        {"round_type": "technical_short_answer", "category": "interview",
         "skills": ["DBMS"], "count": 2, "allow_optional_follow_ups": True,
         "max_follow_ups": 1},
        {"round_type": "mcq", "category": "oa", "skills": ["DBMS"], "count": 2},
    ])
    assert plan[0]["max_follow_ups"] == 1
    assert plan[0]["allow_optional_follow_ups"] is True
    assert plan[1]["max_follow_ups"] is None


# ── memory backend ────────────────────────────────────────────────────


def test_memory_allocate_then_reschedule_refused(memory_db):
    db = memory_db
    parent = _round(1)
    db["sessions"].insert_one(_session_doc(rounds=[parent], blocks=[_block()]))
    first = allocate_follow_up(
        db, session_id="s1", parent_round=1, plan_entry=_entry_for(parent)
    )
    assert first["scheduled"] is True
    assert first["total_rounds"] == 2
    second = allocate_follow_up(
        db, session_id="s1", parent_round=1, plan_entry=_entry_for(parent)
    )
    assert second == {
        "scheduled": False,
        "reason": "parent_follow_up_exists",
        "attempts": 1,
    }
    live = db["sessions"].find_one({"session_id": "s1"})
    assert live["total_rounds"] == 2
    assert len(_exposures_for(db, "s1", 1)) == 1


def test_memory_threads_single_winner_without_process_lock(memory_db, no_submit_lock):
    db = memory_db
    parent = _round(1)
    db["sessions"].insert_one(_session_doc(rounds=[parent], blocks=[_block()]))

    def _once(_):
        return allocate_follow_up(
            db, session_id="s1", parent_round=1, plan_entry=_entry_for(parent)
        )

    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(_once, range(4)))
    winners = [r for r in results if r.get("scheduled")]
    assert len(winners) == 1
    assert all(
        r.get("reason") == "parent_follow_up_exists"
        for r in results
        if not r.get("scheduled")
    )
    live = db["sessions"].find_one({"session_id": "s1"})
    assert live["total_rounds"] == 2
    assert len(_exposures_for(db, "s1", 1)) == 1


def test_memory_rollback_on_exposure_failure(memory_db, monkeypatch):
    import modules.teaching_exposures as exposures

    def _boom(*args, **kwargs):
        raise RuntimeError("injected exposure failure")

    monkeypatch.setattr(exposures, "record_teaching_exposure", _boom)
    db = memory_db
    parent = _round(1)
    db["sessions"].insert_one(_session_doc(rounds=[parent], blocks=[_block()]))
    snapshot = db["sessions"].find_one({"session_id": "s1"})
    with pytest.raises(RuntimeError):
        allocate_follow_up(
            db, session_id="s1", parent_round=1, plan_entry=_entry_for(parent)
        )
    assert db["sessions"].find_one({"session_id": "s1"}) == snapshot
    assert list(db["teaching_exposures"].find({"session_id": "s1"}) or []) == []


# ── SQL backend: independent connections, no shared lock ──────────────


def _overlap_barrier(monkeypatch, parties=2):
    """Force racing threads to overlap inside their transactions.

    Every worker must pass validation before any commits, so the test
    exercises a genuine lost race rather than lucky timing. Crossing the
    barrier from inside two open transactions proves the workers hold
    independent connections (one connection cannot host two). Returns the
    set of thread idents that crossed.
    """
    from modules.follow_ups import can_schedule_follow_up as real

    barrier = threading.Barrier(parties)
    crossed: set[int] = set()
    guard = threading.Lock()

    def _wait(*args, **kwargs):
        out = real(*args, **kwargs)
        ident = threading.get_ident()
        with guard:
            first = ident not in crossed
            crossed.add(ident)
        if first:
            # Only the first validation per worker waits: retries must
            # never deadlock on an already-broken barrier.
            barrier.wait(timeout=15)
        return out

    # The allocator imports the check lazily per call, so patch the source.
    monkeypatch.setattr("modules.follow_ups.can_schedule_follow_up", _wait)
    return crossed


def test_sql_same_parent_single_winner(sql_db, no_submit_lock, monkeypatch):
    from sqlalchemy import event

    db, engine = sql_db
    parent = _round(1)
    db["sessions"].insert_one(_session_doc(rounds=[parent], blocks=[_block()]))
    crossed = _overlap_barrier(monkeypatch)

    # Prove independent connections: track live pool holdings and record
    # any moment two workers simultaneously hold different DBAPI conns.
    live: dict[int, Any] = {}
    overlap: list[bool] = []
    holdings_guard = threading.Lock()

    def _on_checkout(dbapi_conn, conn_record, conn_proxy):
        ident = threading.get_ident()
        with holdings_guard:
            for other, other_conn in live.items():
                if other != ident and other_conn is not dbapi_conn:
                    overlap.append(True)
            live[ident] = dbapi_conn

    def _on_checkin(dbapi_conn, conn_record):
        with holdings_guard:
            live.pop(threading.get_ident(), None)

    event.listen(engine, "checkout", _on_checkout)
    event.listen(engine, "checkin", _on_checkin)
    worker_idents: set[int] = set()
    try:

        def _once(_):
            worker_idents.add(threading.get_ident())
            return allocate_follow_up(
                db, session_id="s1", parent_round=1, plan_entry=_entry_for(parent)
            )

        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(_once, range(2)))
    finally:
        event.remove(engine, "checkout", _on_checkout)
        event.remove(engine, "checkin", _on_checkin)
    assert len(crossed) == 2  # both validated inside overlapping transactions
    assert len(worker_idents) == 2
    assert overlap  # workers simultaneously held distinct connections
    winners = [r for r in results if r.get("scheduled")]
    assert len(winners) == 1
    losers = [r for r in results if not r.get("scheduled")]
    assert len(losers) == 1
    assert losers[0]["reason"] == "parent_follow_up_exists"
    live = db["sessions"].find_one({"session_id": "s1"})
    assert live["total_rounds"] == 2
    assert sum(1 for e in live["expanded_plan"] if e.get("is_follow_up")) == 1
    assert len(_exposures_for(db, "s1", 1)) == 1
    assert len(live["rounds"]) == 1  # no round rows created or rewritten
    assert live["rounds"][0]["final_score"] == 60.0


def test_sql_different_parents_final_block_slot(sql_db, no_submit_lock, monkeypatch):
    db, engine = sql_db
    held = {"round": 2, "is_follow_up": True, "block_id": "b1",
            "follow_up_parent_round": 1, "follow_up_identity": "held-1",
            "status": "in_progress", "skill": "DBMS", "config_json": {}}
    held_entry = {
        "round_type": "technical_short_answer", "block_id": "b1",
        "category": "interview", "is_follow_up": True,
        "follow_up_parent_round": 1, "follow_up_identity": "held-1",
    }
    rounds = [_round(1), held, _round(3), _round(4)]
    mandatory = [
        {"round_type": "technical_short_answer", "block_id": "b1",
         "category": "interview"}
        for _ in range(3)
    ]
    session = _session_doc(rounds=rounds, blocks=[_block()], total=4,
                           expanded=mandatory + [held_entry])
    db["sessions"].insert_one(session)
    crossed = _overlap_barrier(monkeypatch)

    def _once(parent_round):
        live = db["sessions"].find_one({"session_id": "s1"})
        parent = next(r for r in live["rounds"] if r["round"] == parent_round)
        return allocate_follow_up(
            db, session_id="s1", parent_round=parent_round,
            plan_entry=_entry_for(parent),
        )

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(_once, [3, 4]))
    assert len(crossed) == 2
    winners = [r for r in results if r.get("scheduled")]
    assert len(winners) == 1
    losers = [r for r in results if not r.get("scheduled")]
    assert [r["reason"] for r in losers] == ["block_follow_up_cap"]
    live = db["sessions"].find_one({"session_id": "s1"})
    assert live["total_rounds"] == 5
    follow_entries = [e for e in live["expanded_plan"] if e.get("is_follow_up")]
    assert len(follow_entries) == 2  # held + exactly one new
    assert {e.get("follow_up_identity") for e in follow_entries} >= {"held-1"}
    total_exposures = len(_exposures_for(db, "s1", 3)) + len(
        _exposures_for(db, "s1", 4)
    )
    assert total_exposures == 1


def test_sql_session_capacity_race_never_exceeds_cap(sql_db, no_submit_lock, monkeypatch):
    # Near the 50-round cap with per-parent mandatory reservation, the two
    # eligible parents (47, 48) race for the last slots in separate blocks
    # (block caps cannot bind). Commit order decides how many fit, so the
    # test asserts invariants: the cap holds, every loser is definitive,
    # and jobs/exposures match scheduled entries exactly.
    db, engine = sql_db
    rounds = [
        _round(n, block_id="b1" if n % 2 else "b2") for n in range(1, 49)
    ]
    session = _session_doc(
        rounds=rounds, blocks=[_block("b1"), _block("b2")], total=48,
        expanded=[
            {"round_type": "technical_short_answer",
             "block_id": "b1" if n % 2 else "b2", "category": "interview"}
            for n in range(1, 49)
        ],
    )
    db["sessions"].insert_one(session)
    crossed = _overlap_barrier(monkeypatch)

    def _once(parent_round):
        live = db["sessions"].find_one({"session_id": "s1"})
        parent = next(r for r in live["rounds"] if r["round"] == parent_round)
        return allocate_follow_up(
            db, session_id="s1", parent_round=parent_round,
            plan_entry=_entry_for(parent),
        )

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(_once, [47, 48]))
    assert len(crossed) == 2
    scheduled = [r for r in results if r.get("scheduled")]
    refused = [r for r in results if not r.get("scheduled")]
    assert scheduled, "at least the last parent must fit"
    assert all(r["reason"] == "no_capacity" for r in refused)
    live = db["sessions"].find_one({"session_id": "s1"})
    assert live["total_rounds"] == 48 + len(scheduled)
    assert live["total_rounds"] <= MAX_TOTAL_ROUNDS
    new_entries = [e for e in live["expanded_plan"] if e.get("is_follow_up")]
    assert len(new_entries) == len(scheduled)
    assert len({e["follow_up_parent_round"] for e in new_entries}) == len(scheduled)
    total_exposures = len(_exposures_for(db, "s1", 47)) + len(
        _exposures_for(db, "s1", 48)
    )
    assert total_exposures == len(scheduled)
    assert len(live["rounds"]) == 48  # allocation adds no round rows


def test_sql_rollback_on_exposure_failure(sql_db, monkeypatch):
    import modules.teaching_exposures as exposures

    def _boom(*args, **kwargs):
        raise RuntimeError("injected exposure failure")

    monkeypatch.setattr(exposures, "record_teaching_exposure", _boom)
    db, engine = sql_db
    parent = _round(1)
    db["sessions"].insert_one(_session_doc(rounds=[parent], blocks=[_block()]))
    snapshot = db["sessions"].find_one({"session_id": "s1"})
    with pytest.raises(RuntimeError):
        allocate_follow_up(
            db, session_id="s1", parent_round=1, plan_entry=_entry_for(parent)
        )
    assert db["sessions"].find_one({"session_id": "s1"}) == snapshot
    assert list(db["teaching_exposures"].find({"session_id": "s1"}) or []) == []
    from sqlalchemy import select
    from backend.db.sqlalchemy_models import SessionRow
    from backend.db.sqlalchemy_store import session_scope

    with session_scope() as session:
        revision = session.execute(
            select(SessionRow.revision).where(SessionRow.id == "s1")
        ).scalar()
    assert revision == 0


def test_sql_allocation_preserves_round_row_identities(sql_db):
    from sqlalchemy import select
    from backend.db.sqlalchemy_models import RoundRow
    from backend.db.sqlalchemy_store import session_scope

    db, engine = sql_db
    parent = _round(1)
    db["sessions"].insert_one(_session_doc(rounds=[parent], blocks=[_block()]))

    def _ids():
        with session_scope() as session:
            return session.execute(
                select(RoundRow.id, RoundRow.round_number).where(
                    RoundRow.session_id == "s1"
                )
            ).all()

    before_ids = _ids()
    before_rounds = db["sessions"].find_one({"session_id": "s1"})["rounds"]
    result = allocate_follow_up(
        db, session_id="s1", parent_round=1, plan_entry=_entry_for(parent)
    )
    assert result["scheduled"] is True
    assert _ids() == before_ids  # surgical write: round rows untouched
    assert db["sessions"].find_one({"session_id": "s1"})["rounds"] == before_rounds


def test_sql_revision_increments_per_allocation(sql_db):
    from sqlalchemy import select
    from backend.db.sqlalchemy_models import SessionRow
    from backend.db.sqlalchemy_store import session_scope

    db, engine = sql_db
    rounds = [_round(1), _round(2)]
    db["sessions"].insert_one(_session_doc(rounds=rounds, blocks=[_block()]))

    def _revision():
        with session_scope() as session:
            return session.execute(
                select(SessionRow.revision).where(SessionRow.id == "s1")
            ).scalar()

    assert _revision() == 0
    live = db["sessions"].find_one({"session_id": "s1"})
    allocate_follow_up(
        db, session_id="s1", parent_round=1,
        plan_entry=_entry_for(live["rounds"][0]),
    )
    assert _revision() == 1
    live = db["sessions"].find_one({"session_id": "s1"})
    allocate_follow_up(
        db, session_id="s1", parent_round=2,
        plan_entry=_entry_for(live["rounds"][1]),
    )
    assert _revision() == 2


# ── route behavior ────────────────────────────────────────────────────


def test_route_sequential_second_refused_and_conflict_is_409(memory_db, monkeypatch):
    from fastapi import HTTPException

    from backend.routes.follow_ups import FollowUpRequest, request_follow_up

    db = memory_db
    parent = _round(1)
    session = _session_doc(rounds=[parent], blocks=[_block()])
    from backend.auth.security import create_access_token, hash_password

    user_id = "follow-owner"
    db["users"].insert_one({
        "id": user_id,
        "email": "follow-owner@example.com",
        "name": "Owner",
        "password_hash": hash_password("passw0rd123"),
        "created_at": datetime.now(timezone.utc),
        "last_active_at": datetime.now(timezone.utc),
    })
    session["user_id"] = user_id
    db["sessions"].insert_one(session)
    token = f"Bearer {create_access_token(user_id)}"

    body = FollowUpRequest(parent_round=1, accept_eligibility_consequence=True)
    missing = None
    try:
        request_follow_up("s1", body, None)
    except HTTPException as exc:
        missing = exc.status_code
    assert missing == 401
    first = request_follow_up("s1", body, token)
    assert first["scheduled"] is True
    assert first["label"] == "Follow-up"
    second = request_follow_up("s1", body, token)
    assert second == {
        "scheduled": False,
        "reason": "parent_follow_up_exists",
        "session_id": "s1",
        "parent_round": 1,
    }

    def _conflict(*args, **kwargs):
        return {"scheduled": False, "reason": "allocation_conflict",
                "retryable": True}

    monkeypatch.setattr(
        "backend.routes.follow_ups.allocate_follow_up", _conflict
    )
    with pytest.raises(HTTPException) as excinfo:
        request_follow_up("s1", body, token)
    assert excinfo.value.status_code == 409
    assert "retry" in excinfo.value.detail.lower()


def _alembic_cfg(url: str, monkeypatch):
    from pathlib import Path

    from alembic.config import Config

    from backend import config as app_config

    # Pin the database deterministically: env.py prefers get_settings().
    monkeypatch.setenv("DATABASE_URL", url)
    monkeypatch.setenv("INTERVIV_USE_MEMORY_DB", "false")
    app_config.get_settings.cache_clear()
    root = Path(__file__).resolve().parents[1]
    # Programmatic config (no ini file): env.py then skips
    # logging.fileConfig, which would otherwise disable existing loggers
    # process-wide and pollute unrelated tests.
    cfg = Config()
    cfg.set_main_option("script_location", str(root / "alembic"))
    cfg.set_main_option("sqlalchemy.url", url)
    return cfg


def test_migration_0016_revision_upgrade_downgrade(tmp_path, monkeypatch):
    from alembic import command
    from sqlalchemy import create_engine, text

    from tests.alembic_helpers import parent_revision

    from tests.sql_test_url import (
        is_postgres,
        reset_postgres_schema,
        table_info,
        resolve_sql_url,
    )

    url = resolve_sql_url(tmp_path, "followup-mig.db")
    if is_postgres(url):
        reset_postgres_schema(url)
    cfg = _alembic_cfg(url, monkeypatch)
    command.upgrade(cfg, "head")
    engine = create_engine(url)
    with engine.connect() as conn:
        info = {row[1]: row for row in table_info(conn, "sessions")}
        assert "revision" in info
        assert info["revision"][3] == 1  # NOT NULL
        assert str(info["revision"][4]).strip("'\"") == "0"  # backfill default
    engine.dispose()

    command.downgrade(cfg, parent_revision("20260918_0016"))
    engine = create_engine(url)
    with engine.connect() as conn:
        cols = {row[1] for row in table_info(conn, "sessions")}
        assert "revision" not in cols
    engine.dispose()

    command.upgrade(cfg, "head")
    engine = create_engine(url)
    with engine.connect() as conn:
        cols = {row[1] for row in table_info(conn, "sessions")}
        assert "revision" in cols
    engine.dispose()
    if is_postgres(url):
        reset_postgres_schema(url)


def test_migrated_schema_backfills_revision_zero(tmp_path, monkeypatch):
    from alembic import command
    from sqlalchemy import create_engine, text

    from tests.alembic_helpers import parent_revision

    from tests.sql_test_url import (
        is_postgres,
        reset_postgres_schema,
        table_info,
        resolve_sql_url,
    )

    url = resolve_sql_url(tmp_path, "followup-backfill.db")
    if is_postgres(url):
        reset_postgres_schema(url)
    cfg = _alembic_cfg(url, monkeypatch)
    command.upgrade(cfg, parent_revision("20260918_0016"))
    engine = create_engine(url)
    with engine.begin() as conn:
        # Insert a legacy row satisfying every NOT NULL column without a
        # database default, whatever the pre-0016 schema requires.
        info = list(table_info(conn, "sessions"))
        names, values = ["id"], ["'legacy-s'"]
        for _, name, ctype, notnull, dflt, _pk in info:
            if name == "id" or not notnull or dflt is not None:
                continue
            names.append(f'"{name}"')
            ctype = str(ctype or "").upper()
            if "INT" in ctype:
                values.append("0")
            elif "DATE" in ctype or "TIME" in ctype:
                values.append("'2026-01-01T00:00:00+00:00'")
            elif "REAL" in ctype or "FLOA" in ctype or "DOUB" in ctype:
                values.append("0.0")
            elif "JSON" in ctype:
                values.append("'[]'")
            else:
                values.append("''")
        conn.execute(text(f"INSERT INTO sessions ({', '.join(names)}) "
                          f"VALUES ({', '.join(values)})"))
    command.upgrade(cfg, "head")
    with engine.connect() as conn:
        value = conn.execute(
            text("SELECT revision FROM sessions WHERE id='legacy-s'")
        ).scalar()
        assert value == 0
    engine.dispose()
    if is_postgres(url):
        reset_postgres_schema(url)


def test_route_requires_eligibility_consent(memory_db):
    from fastapi import HTTPException

    from backend.routes.follow_ups import FollowUpRequest, request_follow_up

    db = memory_db
    db["sessions"].insert_one(_session_doc(rounds=[_round(1)], blocks=[_block()]))
    with pytest.raises(HTTPException) as excinfo:
        request_follow_up(
            "s1", FollowUpRequest(parent_round=1), None
        )
    assert excinfo.value.status_code == 422
