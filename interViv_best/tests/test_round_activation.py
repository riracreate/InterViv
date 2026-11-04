"""Overhaul Phase 2: explicit round lifecycle.

submit → next round persisted ``ready`` (no clock, prompt hidden) →
POST /session/{id}/rounds/{n}/activate starts the clock exactly once.
"""

from __future__ import annotations

import os
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from fastapi.testclient import TestClient

os.environ.setdefault("INTERVIV_USE_MEMORY_DB", "true")
os.environ.setdefault("JWT_SECRET_KEY", "test-secret-key-with-at-least-32-bytes!!")
os.environ["OPENAI_API_KEY"] = ""
os.environ["OPENROUTER_API_KEY"] = ""

from backend.auth.security import create_access_token, hash_password  # noqa: E402
from backend.db import get_database  # noqa: E402
from backend.main import app  # noqa: E402
from backend.round_lifecycle import (  # noqa: E402
    activate_round,
    prepare_round,
    round_duration_seconds,
)
from tests.round_helpers import activate  # noqa: E402


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


def _mcq_answers(questions):
    return [{"question_id": q["id"], "selected_option_ids": [q["options"][0]["id"]]}
            for q in questions]


def _iso(value):
    return datetime.fromisoformat(value) if isinstance(value, str) else value


def _start_two_technical(client, headers, **block_extra):
    start = client.post("/session/start", headers=headers, json={"blocks": [
        {"round_type": "technical_short_answer", "category": "interview",
         "skills": ["DBMS"], "count": 2, **block_extra},
    ]})
    assert start.status_code == 200, start.text
    return start.json()["session_id"]


def _answer(client, headers, session_id, number, text="An index speeds up lookups on a column."):
    return client.post("/session/answer", headers=headers, json={
        "session_id": session_id, "round": number, "answer_text": text,
    })


# ── pure lifecycle helpers ──────────────────────────────────────────────


def test_prepare_then_activate_sets_clock_once():
    built_at = datetime(2026, 11, 3, 9, 0, tzinfo=timezone.utc)
    doc = {"round": 2, "status": "in_progress", "config_json": {"duration_minutes": 20},
           "started_at": built_at, "expires_at": built_at + timedelta(minutes=20)}
    prepare_round(doc)
    assert doc["status"] == "ready"
    assert doc["started_at"] is None and doc["expires_at"] is None
    assert round_duration_seconds(doc) == 1200

    opened_at = built_at + timedelta(minutes=7)
    assert activate_round(doc, opened_at) is True
    assert doc["started_at"] == opened_at
    assert doc["expires_at"] == opened_at + timedelta(minutes=20)

    # Re-activation never restarts or extends the clock.
    assert activate_round(doc, opened_at + timedelta(minutes=5)) is False
    assert doc["expires_at"] == opened_at + timedelta(minutes=20)


def test_untimed_round_activates_without_deadline():
    doc = {"round": 3, "status": "in_progress", "config_json": {},
           "started_at": datetime.now(timezone.utc), "expires_at": None}
    prepare_round(doc)
    assert round_duration_seconds(doc) is None
    activate_round(doc)
    assert doc["status"] == "in_progress"
    assert doc["started_at"] is not None
    assert doc["expires_at"] is None


# ── API: memory store ───────────────────────────────────────────────────


def test_submit_prepares_next_round_without_revealing_it():
    client = TestClient(app)
    headers = _headers(_make_user("act-prepare"))
    session_id = _start_two_technical(client, headers)

    first = _answer(client, headers, session_id, 1)
    assert first.status_code == 200, first.text
    body = first.json()
    assert body["next_round"] == 2
    assert body["next_round_status"] == "ready"
    assert body["next_round_type"] == "technical_short_answer"
    assert body["session_complete"] is False
    for hidden in ("next_question", "next_question_context", "next_config_json", "next_expires_at"):
        assert body[hidden] is None

    stored = get_database()["sessions"].find_one({"session_id": session_id})
    prepared = stored["rounds"][1]
    assert prepared["status"] == "ready"
    assert prepared["started_at"] is None and prepared["expires_at"] is None

    # Refresh during review: prior result kept, prompt still hidden.
    view = client.get(f"/session/{session_id}", headers=headers).json()
    assert view["active_round"] is None
    assert view["review_round"] == 1
    assert [r["round"] for r in view["round_history"]] == [1]
    assert view["round_history"][0]["final_score"] == body["final_score"]
    assert view["round_history"][0]["feedback"] == body["feedback"]
    assert view["pending_round"] == {
        "round": 2, "round_type": "technical_short_answer", "status": "ready",
        "skill": prepared.get("skill"), "difficulty": prepared.get("difficulty"),
        "block_id": prepared.get("block_id"), "block_category": prepared.get("block_category"),
        "duration_seconds": None,
    }
    assert prepared["question"] not in str(view)


def test_ready_round_rejects_answers_drafts_until_opened():
    client = TestClient(app)
    headers = _headers(_make_user("act-reject"))
    session_id = _start_two_technical(client, headers)
    assert _answer(client, headers, session_id, 1).status_code == 200

    early = _answer(client, headers, session_id, 2)
    assert early.status_code == 409
    assert early.json()["detail"]["code"] == "round_not_active"

    draft = client.put(f"/session/{session_id}/draft", headers=headers, json={
        "round": 2, "answer_text": "draft"})
    assert draft.status_code == 409
    assert draft.json()["detail"]["code"] == "round_not_active"

    stored = get_database()["sessions"].find_one({"session_id": session_id})
    assert stored["rounds"][1]["status"] == "ready"  # rejection changed nothing

    opened = activate(client, headers, session_id, 2)
    assert opened["question"]
    final = _answer(client, headers, session_id, 2)
    assert final.status_code == 200, final.text
    assert final.json()["session_complete"] is True
    assert final.json()["next_round"] is None


def test_activation_is_idempotent_and_never_extends_deadline():
    client = TestClient(app)
    headers = _headers(_make_user("act-idem"))
    start = client.post("/session/start", headers=headers, json={"blocks": [
        {"round_type": "mcq", "category": "oa", "skills": ["DBMS"], "count": 2, "duration_minutes": 10},
        {"round_type": "mcq", "category": "oa", "skills": ["DBMS"], "count": 2, "duration_minutes": 20},
    ]})
    assert start.status_code == 200, start.text
    session_id = start.json()["session_id"]
    answer = client.post("/session/answer", headers=headers, json={
        "session_id": session_id, "round": 1, "answers": _mcq_answers(start.json()["questions"]),
    })
    assert answer.status_code == 200, answer.text

    first = activate(client, headers, session_id, 2)
    started, expires = _iso(first["started_at"]), _iso(first["expires_at"])
    assert expires - started == timedelta(minutes=20)

    for _ in range(3):
        again = activate(client, headers, session_id, 2)
        assert again["started_at"] == first["started_at"]
        assert again["expires_at"] == first["expires_at"]
    view = client.get(f"/session/{session_id}", headers=headers).json()
    assert view["active_round"]["expires_at"] == first["expires_at"]
    assert view["pending_round"] is None
    assert view["review_round"] is None


def test_activation_conflicts_and_ownership():
    client = TestClient(app)
    owner = _headers(_make_user("act-owner"))
    session_id = _start_two_technical(client, owner)

    # Round 1 is the open round; round 2 does not exist yet.
    missing = client.post(f"/session/{session_id}/rounds/2/activate", headers=owner)
    assert missing.status_code == 404

    assert _answer(client, owner, session_id, 1).status_code == 200
    closed = client.post(f"/session/{session_id}/rounds/1/activate", headers=owner)
    assert closed.status_code == 409
    assert closed.json()["detail"]["code"] == "round_closed"

    stranger = _headers(_make_user("act-stranger"))
    foreign = client.post(f"/session/{session_id}/rounds/2/activate", headers=stranger)
    assert foreign.status_code in (403, 404)
    stored = get_database()["sessions"].find_one({"session_id": session_id})
    assert stored["rounds"][1]["status"] == "ready"


def test_later_round_cannot_open_before_earlier_one_is_answered():
    db = get_database()
    user = _make_user("act-order")
    now = datetime.now(timezone.utc)
    db["sessions"].insert_one({
        "session_id": "act-order-s", "candidate_id": "act-order-c", "user_id": user["id"],
        "skill": "DBMS", "skills": ["DBMS"], "total_rounds": 3, "status": "active",
        "last_round": 1, "rounds": [
            {"round": 1, "question": "Q1", "round_type": "technical_short_answer",
             "difficulty": "medium", "status": "submitted", "final_score": 50.0,
             "started_at": now, "question_context": {}},
            {"round": 2, "question": "Q2", "round_type": "technical_short_answer",
             "difficulty": "medium", "status": "ready", "question_context": {}},
            {"round": 3, "question": "Q3", "round_type": "technical_short_answer",
             "difficulty": "medium", "status": "ready", "question_context": {}},
        ],
    })
    client = TestClient(app)
    blocked = client.post("/session/act-order-s/rounds/3/activate", headers=_headers(user))
    assert blocked.status_code == 409
    assert blocked.json()["detail"]["code"] == "previous_round_open"


def test_legacy_in_progress_round_keeps_its_deadline():
    db = get_database()
    user = _make_user("act-legacy")
    started = datetime.now(timezone.utc) - timedelta(minutes=3)
    deadline = started + timedelta(minutes=20)
    db["sessions"].insert_one({
        "session_id": "act-legacy-s", "candidate_id": "act-legacy-c", "user_id": user["id"],
        "skill": "DBMS", "skills": ["DBMS"], "total_rounds": 2, "status": "active",
        "last_round": 1, "rounds": [
            {"round": 1, "question": "Q1", "round_type": "technical_short_answer",
             "difficulty": "medium", "status": "submitted", "final_score": 40.0,
             "question_context": {}},
            {"round": 2, "question": "Legacy open question", "round_type": "technical_short_answer",
             "difficulty": "medium", "status": "in_progress", "started_at": started,
             "expires_at": deadline, "question_context": {}},
        ],
    })
    client = TestClient(app)
    view = client.get("/session/act-legacy-s", headers=_headers(user)).json()
    assert view["active_round"]["round"] == 2
    assert _iso(view["active_round"]["expires_at"]) == deadline
    assert view["pending_round"] is None
    opened = activate(client, _headers(user), "act-legacy-s", 2)
    assert _iso(opened["expires_at"]) == deadline
    assert _iso(opened["started_at"]) == started


def test_concurrent_activation_sets_one_deadline():
    client = TestClient(app)
    headers = _headers(_make_user("act-race"))
    start = client.post("/session/start", headers=headers, json={"blocks": [
        {"round_type": "mcq", "category": "oa", "skills": ["DBMS"], "count": 2, "duration_minutes": 10},
        {"round_type": "mcq", "category": "oa", "skills": ["DBMS"], "count": 2, "duration_minutes": 15},
    ]})
    session_id = start.json()["session_id"]
    assert client.post("/session/answer", headers=headers, json={
        "session_id": session_id, "round": 1, "answers": _mcq_answers(start.json()["questions"]),
    }).status_code == 200

    def _open(_):
        return TestClient(app).post(f"/session/{session_id}/rounds/2/activate", headers=headers)

    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(_open, range(4)))
    assert all(r.status_code == 200 for r in results), [r.text for r in results]
    deadlines = {r.json()["active_round"]["expires_at"] for r in results}
    assert len(deadlines) == 1


def test_progress_lists_session_waiting_on_next_question_as_resumable():
    client = TestClient(app)
    headers = _headers(_make_user("act-resume"))
    session_id = _start_two_technical(client, headers)
    assert _answer(client, headers, session_id, 1).status_code == 200
    progress = client.get("/dashboard/progress", headers=headers).json()
    resumable = progress["resumable_session"]
    assert resumable is not None
    assert resumable["session_id"] == session_id
    assert resumable["pending_activation"] is True
    assert resumable["expires_at"] is None


def test_follow_up_is_materialized_as_a_follow_up_round():
    client = TestClient(app)
    headers = _headers(_make_user("act-follow"))
    session_id = _start_two_technical(client, headers, allow_optional_follow_ups=True)
    assert _answer(client, headers, session_id, 1).status_code == 200
    scheduled = client.post(f"/session/{session_id}/follow-ups", headers=headers, json={
        "parent_round": 1, "accept_eligibility_consequence": True,
    })
    assert scheduled.status_code == 200, scheduled.text
    assert scheduled.json()["scheduled"] is True
    assert scheduled.json()["total_rounds"] == 3

    activate(client, headers, session_id, 2)
    second = _answer(client, headers, session_id, 2)
    assert second.status_code == 200, second.text
    assert second.json()["next_round"] == 3
    assert second.json()["total_rounds"] == 3

    stored = get_database()["sessions"].find_one({"session_id": session_id})
    follow_up = stored["rounds"][2]
    assert follow_up["status"] == "ready"
    assert follow_up["is_follow_up"] is True
    assert follow_up["follow_up_parent_round"] == 1
    assert follow_up["follow_up_identity"] == scheduled.json()["follow_up_identity"]


def test_activation_on_sql_store_survives_reload(tmp_path, monkeypatch):
    from backend import config as app_config
    from backend.db import sqlalchemy_store
    from backend.db.sqlalchemy_store import create_all_for_smoke

    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'activation.db'}")
    monkeypatch.setenv("INTERVIV_USE_MEMORY_DB", "false")
    for cached in (app_config.get_settings, sqlalchemy_store.get_engine,
                   sqlalchemy_store._sessionmaker, sqlalchemy_store.get_sqlalchemy_database):
        cached.cache_clear()
    create_all_for_smoke()
    try:
        client = TestClient(app)
        headers = _headers(_make_user("act-sql"))
        session_id = _start_two_technical(client, headers)
        assert _answer(client, headers, session_id, 1).status_code == 200
        stored = get_database()["sessions"].find_one({"session_id": session_id})
        assert stored["rounds"][1]["status"] == "ready"
        opened = activate(client, headers, session_id, 2)
        again = activate(client, headers, session_id, 2)
        assert again["started_at"] == opened["started_at"]
        reloaded = get_database()["sessions"].find_one({"session_id": session_id})
        assert reloaded["rounds"][1]["status"] == "in_progress"
        assert reloaded["rounds"][1]["started_at"] is not None
    finally:
        for cached in (app_config.get_settings, sqlalchemy_store.get_engine,
                       sqlalchemy_store._sessionmaker, sqlalchemy_store.get_sqlalchemy_database):
            cached.cache_clear()
