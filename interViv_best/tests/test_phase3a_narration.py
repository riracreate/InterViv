"""Phase 3A: narration-job infrastructure without live generation.

- Every attempt commit enqueues exactly one job for the scored round (same
  atomic commit: failed submits enqueue nothing).
- Enqueue is idempotent by deterministic id; processing is re-entrant.
- The worker renders a deterministic artifact from stored feedback only —
  byte-identical across runs, with no network and no live models.
- The worker refuses rounds whose snapshot changed after enqueue, retries
  failures up to MAX_ATTEMPTS, then parks them for inspection.
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

from alembic import command as alembic_command
from alembic.config import Config as AlembicConfig
from sqlalchemy import create_engine
from sqlalchemy import inspect as sa_inspect

from backend import config as app_config
from backend.auth.security import create_access_token, hash_password
from backend.db import DatabaseConnectionError, get_database
from backend.db.sqlalchemy_store import (
    _sessionmaker,
    create_all_for_smoke,
    get_engine,
    get_sqlalchemy_database,
)
from backend.main import app
from modules.llm_outbound_gate import llm_live_fetch_enabled
from modules.narration_jobs import (
    MAX_ATTEMPTS,
    enqueue_narration_job,
    narration_job_id,
    process_narration_job,
    render_narration_artifact,
    run_narration_worker_once,
)
from tests.alembic_helpers import parent_revision

NARRATION_REVISION = "20260914_0012"


def _make_user(prefix: str = "phase3anarr") -> dict[str, str]:
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


def _start_interview(client, headers, count=1):
    return client.post("/session/start", headers=headers, json={
        "blocks": [{"round_type": "technical_short_answer",
                    "category": "interview", "skills": ["DBMS"],
                    "count": count}],
    })


# ── memory backend ──────────────────────────────────────────────────────


def test_submit_enqueues_exactly_one_job() -> None:
    client = TestClient(app)
    headers = _headers(_make_user("t3a-enqueue"))
    db = get_database()
    jobs_before = db["narration_jobs"].count_documents({})
    start = _start_interview(client, headers)
    assert start.status_code == 200, start.text
    session_id = start.json()["session_id"]

    answer = client.post("/session/answer", headers=headers, json={
        "session_id": session_id, "round": 1,
        "answer_text": "A B-tree index keeps sorted keys so lookups stay fast.",
    })
    assert answer.status_code == 200, answer.text

    assert db["narration_jobs"].count_documents({}) == jobs_before + 1
    job = db["narration_jobs"].find_one({"id": narration_job_id(session_id, 1)})
    assert job["status"] == "queued"
    assert job["attempts"] == 0
    assert job["feedback"] == answer.json()["feedback"]
    assert job["final_score"] == answer.json()["final_score"]
    assert job["skill"] == "DBMS"
    stored = db["sessions"].find_one({"session_id": session_id})
    assert job["snapshot_digest"] == stored["rounds"][0]["attempt_snapshot"]["digest"]


def test_enqueue_is_idempotent() -> None:
    db = get_database()
    first = enqueue_narration_job(
        db, session_id="idem-s", round_number=1, user_id=None,
        skill="DBMS", final_score=80.0,
        feedback={"content": ["Good."], "strengths": [], "weakness": [],
                  "next_step": ""},
        snapshot_digest=None,
    )
    second = enqueue_narration_job(
        db, session_id="idem-s", round_number=1, user_id=None,
        skill="DBMS", final_score=80.0,
        feedback={"content": ["Good."], "strengths": [], "weakness": [],
                  "next_step": ""},
        snapshot_digest=None,
    )
    assert first["id"] == second["id"] == "idem-s:1:narration"
    assert db["narration_jobs"].count_documents({"id": first["id"]}) == 1


def test_failed_submit_enqueues_nothing(monkeypatch) -> None:
    client = TestClient(app)
    headers = _headers(_make_user("t3a-nojob"))
    db = get_database()
    start = _start_interview(client, headers)
    session_id = start.json()["session_id"]
    jobs_before = db["narration_jobs"].count_documents({})

    original = db["candidates"].update_one
    calls: list[int] = []

    def flaky(*args, **kwargs):
        calls.append(1)
        if len(calls) == 1:
            raise DatabaseConnectionError("injected commit failure")
        return original(*args, **kwargs)

    monkeypatch.setattr(db["candidates"], "update_one", flaky)
    failed = client.post("/session/answer", headers=headers, json={
        "session_id": session_id, "round": 1,
        "answer_text": "ACID transactions keep related writes atomic.",
    })
    assert failed.status_code == 503, failed.text
    assert db["narration_jobs"].count_documents({}) == jobs_before


def test_worker_renders_deterministically_without_network(monkeypatch) -> None:
    def _no_network(*args, **kwargs):
        raise AssertionError("narration worker must not touch the network")

    monkeypatch.setattr("urllib.request.urlopen", _no_network)
    monkeypatch.setattr("socket.create_connection", _no_network)
    # Phase 3A pins live generation off; force it here so the test never
    # depends on ambient env leaked by other suites.
    monkeypatch.setenv("LLM_LIVE_FETCH", "0")
    assert llm_live_fetch_enabled() is False

    db = get_database()
    feedback = {"content": ["Good length and pacing."],
                "strengths": ["Concise"],
                "weakness": [],
                "next_step": "Maintain this level of detail."}
    first = render_narration_artifact(round_number=2, skill="DBMS",
                                      final_score=82.5, feedback=feedback)
    second = render_narration_artifact(round_number=2, skill="DBMS",
                                       final_score=82.5, feedback=feedback)
    assert first == second
    assert first["source"] == "rules_feedback"
    assert "Round 2 (DBMS): scored 82.5 out of 100." in first["script"]
    assert "Good length and pacing." in first["script"]
    assert "Strengths: Concise." in first["script"]
    assert "Next step: Maintain this level of detail." in first["script"]


def test_worker_claims_renders_and_reprocesses_idempotently(monkeypatch) -> None:
    monkeypatch.setenv("LLM_LIVE_FETCH", "0")
    client = TestClient(app)
    headers = _headers(_make_user("t3a-work"))
    db = get_database()
    start = _start_interview(client, headers)
    session_id = start.json()["session_id"]
    answer = client.post("/session/answer", headers=headers, json={
        "session_id": session_id, "round": 1,
        "answer_text": "Normalization removes redundancy by splitting tables.",
    })
    assert answer.status_code == 200, answer.text
    job_id = narration_job_id(session_id, 1)

    # Process this job directly: the shared suite database may hold other
    # tests' queued jobs, so a bounded worker sweep is not job-specific.
    done = process_narration_job(db, job_id)
    assert done["status"] == "skipped"
    assert done["attempts"] == 1
    assert done["artifact"]["source"] == "rules_feedback"
    assert "Round 1 (DBMS)" in done["artifact"]["script"]
    assert "disabled" in (done["last_error"] or "").lower()

    # Reprocessing a terminal job is a no-op returning the same artifact.
    again = process_narration_job(db, job_id)
    assert again["status"] == "skipped"
    assert again["attempts"] == 1
    assert again["artifact"] == done["artifact"]


def test_worker_sweep_processes_due_jobs_oldest_first(monkeypatch) -> None:
    monkeypatch.setenv("LLM_LIVE_FETCH", "0")
    from backend.db.memory import _MemoryDB

    # Isolated store: hand-built scored round plus two queued jobs.
    db = _MemoryDB()
    db["sessions"].insert_one({
        "session_id": "sweep-s", "candidate_id": "sweep-c",
        "rounds": [
            {"round": 1, "status": "submitted", "final_score": 80.0,
             "attempt_snapshot": {"digest": "aaa"}},
            {"round": 2, "status": "submitted", "final_score": 70.0,
             "attempt_snapshot": {"digest": "bbb"}},
        ],
    })
    enqueue_narration_job(
        db, session_id="sweep-s", round_number=1, user_id=None,
        skill="DBMS", final_score=80.0,
        feedback={"content": ["One."], "strengths": [], "weakness": [],
                  "next_step": ""},
        snapshot_digest="aaa",
    )
    enqueue_narration_job(
        db, session_id="sweep-s", round_number=2, user_id=None,
        skill="DBMS", final_score=70.0,
        feedback={"content": ["Two."], "strengths": [], "weakness": [],
                  "next_step": ""},
        snapshot_digest="bbb",
    )
    counts = run_narration_worker_once(db, limit=25)
    assert counts == {"processed": 2, "done": 0, "failed": 0, "skipped": 2}
    assert db["narration_jobs"].find_one(
        {"id": "sweep-s:1:narration"})["status"] == "skipped"
    assert db["narration_jobs"].find_one(
        {"id": "sweep-s:2:narration"})["status"] == "skipped"
    # Nothing due afterwards: the sweep is a no-op.
    assert run_narration_worker_once(db) == {
        "processed": 0, "done": 0, "failed": 0, "skipped": 0,
    }


def test_worker_refuses_tampered_snapshot() -> None:
    client = TestClient(app)
    headers = _headers(_make_user("t3a-tamper"))
    db = get_database()
    start = _start_interview(client, headers)
    session_id = start.json()["session_id"]
    answer = client.post("/session/answer", headers=headers, json={
        "session_id": session_id, "round": 1,
        "answer_text": "An index trades write cost and space for faster reads.",
    })
    assert answer.status_code == 200, answer.text
    job_id = narration_job_id(session_id, 1)

    # The round's snapshot no longer matches the digest pinned at enqueue.
    db["narration_jobs"].update_one(
        {"id": job_id}, {"$set": {"snapshot_digest": "0" * 64}})
    finished = process_narration_job(db, job_id)
    assert finished["status"] == "failed"
    assert finished["attempts"] == 1
    assert "verification failed" in (finished["last_error"] or "")


def test_worker_retries_failures_up_to_max_attempts() -> None:
    db = get_database()
    enqueue_narration_job(
        db, session_id="ghost-session", round_number=1, user_id=None,
        skill="DBMS", final_score=10.0, feedback={"content": ["x"]},
        snapshot_digest=None,
    )
    job_id = "ghost-session:1:narration"
    for _ in range(MAX_ATTEMPTS + 2):
        finished = process_narration_job(db, job_id)
    assert finished["status"] == "failed"
    assert finished["attempts"] == MAX_ATTEMPTS
    assert "not found" in (finished["last_error"] or "")

    # Exhausted failures are no longer due (isolated store: the shared
    # suite database may hold other tests' queued jobs).
    from backend.db.memory import _MemoryDB

    alone = _MemoryDB()
    enqueue_narration_job(
        alone, session_id="ghost-alone", round_number=1, user_id=None,
        skill="DBMS", final_score=10.0, feedback={"content": ["x"]},
        snapshot_digest=None,
    )
    for _ in range(MAX_ATTEMPTS):
        process_narration_job(alone, "ghost-alone:1:narration")
    assert run_narration_worker_once(alone) == {
        "processed": 0, "done": 0, "failed": 0, "skipped": 0,
    }


def test_expired_lease_is_reclaimed_and_stale_worker_cannot_overwrite(
    monkeypatch,
) -> None:
    """Expired leases reclaim; a stale claim_token cannot overwrite results."""
    monkeypatch.setenv("LLM_LIVE_FETCH", "0")
    from datetime import timedelta

    from backend.db.memory import _MemoryDB
    from modules import narration_jobs as nj

    db = _MemoryDB()
    db["sessions"].insert_one({
        "session_id": "lease-s", "candidate_id": "lease-c",
        "rounds": [{
            "round": 1, "status": "submitted", "final_score": 75.0,
            "attempt_snapshot": {"digest": "digest-1"},
        }],
    })
    enqueue_narration_job(
        db, session_id="lease-s", round_number=1, user_id=None,
        skill="DBMS", final_score=75.0,
        feedback={"content": ["Solid."], "strengths": [], "weakness": [],
                  "next_step": ""},
        snapshot_digest="digest-1",
    )
    job_id = "lease-s:1:narration"

    # Crashed worker still holds a live lease — process is a no-op.
    live_until = datetime.now(timezone.utc) + timedelta(seconds=30)
    db["narration_jobs"].update_one(
        {"id": job_id},
        {"$set": {
            "status": "processing",
            "attempts": 1,
            "claim_token": "stale-token",
            "lease_until": live_until,
        }},
    )
    held = process_narration_job(db, job_id)
    assert held["status"] == "processing"
    assert held["claim_token"] == "stale-token"
    assert held["attempts"] == 1

    # Expire the lease; a new worker reclaims and finishes as skipped.
    expired = datetime.now(timezone.utc) - timedelta(seconds=1)
    db["narration_jobs"].update_one(
        {"id": job_id},
        {"$set": {"lease_until": expired}},
    )
    reclaimed = process_narration_job(db, job_id)
    assert reclaimed["status"] == "skipped"
    assert reclaimed["attempts"] == 2
    assert reclaimed["claim_token"] != "stale-token"
    assert reclaimed["artifact"]["source"] == "rules_feedback"

    # Mid-flight steal: after worker B claims, a newer worker C takes the
    # token. B must not overwrite C's row when finishing.
    db["narration_jobs"].update_one(
        {"id": job_id},
        {"$set": {
            "status": "processing",
            "claim_token": "worker-a",
            "lease_until": expired,
            "artifact": None,
            "attempts": 2,
        }},
    )
    monkeypatch.setattr(nj, "uuid4", lambda: "worker-b-token")
    real_update = db["narration_jobs"].update_one
    swap_armed = {"ok": False}

    def update_then_steal(query, update, *args, **kwargs):
        result = real_update(query, update, *args, **kwargs)
        set_fields = (update or {}).get("$set") or {}
        if (
            set_fields.get("status") == "processing"
            and set_fields.get("claim_token") == "worker-b-token"
        ):
            real_update({"id": job_id}, {"$set": {
                "claim_token": "worker-c-token",
                "status": "processing",
                "artifact": {"version": 1, "source": "newer"},
            }})
            swap_armed["ok"] = True
        return result

    monkeypatch.setattr(db["narration_jobs"], "update_one", update_then_steal)
    finished = process_narration_job(db, job_id)
    assert swap_armed["ok"] is True
    assert finished["claim_token"] == "worker-c-token"
    assert finished["status"] == "processing"
    assert finished["artifact"] == {"version": 1, "source": "newer"}
    stored = db["narration_jobs"].find_one({"id": job_id})
    assert stored["claim_token"] == "worker-c-token"
    assert stored["artifact"] == {"version": 1, "source": "newer"}
    assert stored["status"] != "skipped"


def test_process_unknown_job_raises_key_error() -> None:
    with pytest.raises(KeyError):
        process_narration_job(get_database(), "nope:9:narration")


# ── sqlalchemy backend (disposable SQLite) ──────────────────────────────


def _clear_db_caches() -> None:
    app_config.get_settings.cache_clear()
    get_engine.cache_clear()
    _sessionmaker.cache_clear()
    get_sqlalchemy_database.cache_clear()


@pytest.fixture
def sa_url(tmp_path, monkeypatch):
    db_file = tmp_path / "phase3a_narr.db"
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


def test_narration_job_round_trips_sqlalchemy(sa_url, monkeypatch) -> None:
    monkeypatch.setenv("LLM_LIVE_FETCH", "0")
    client = TestClient(app)
    headers = _headers(_make_user("t3a-sanarr"))
    db = get_database()
    start = _start_interview(client, headers)
    assert start.status_code == 200, start.text
    session_id = start.json()["session_id"]
    answer = client.post("/session/answer", headers=headers, json={
        "session_id": session_id, "round": 1,
        "answer_text": "ACID transactions keep related writes atomic.",
    })
    assert answer.status_code == 200, answer.text

    job_id = narration_job_id(session_id, 1)
    job = db["narration_jobs"].find_one({"id": job_id})
    assert job is not None and job["status"] == "queued"
    assert job["feedback"] == answer.json()["feedback"]

    finished = process_narration_job(db, job_id)
    assert finished["status"] == "skipped"
    assert finished["artifact"]["source"] == "rules_feedback"
    reloaded = db["narration_jobs"].find_one({"id": job_id})
    assert reloaded["artifact"] == finished["artifact"]


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


def test_alembic_narration_table_upgrades_and_downgrades(tmp_path) -> None:
    db_file = tmp_path / "phase3a_narr_mig.db"
    url = f"sqlite:///{db_file}"

    _run_alembic(url, "upgrade", "head")
    engine = create_engine(url)
    assert "narration_jobs" in sa_inspect(engine).get_table_names()
    engine.dispose()

    _run_alembic(url, "downgrade", parent_revision(NARRATION_REVISION))
    engine = create_engine(url)
    assert "narration_jobs" not in sa_inspect(engine).get_table_names()
    engine.dispose()

    _run_alembic(url, "upgrade", "head")
    engine = create_engine(url)
    assert "narration_jobs" in sa_inspect(engine).get_table_names()
    engine.dispose()
