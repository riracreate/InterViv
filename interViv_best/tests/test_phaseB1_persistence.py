"""Phase B.1: persistence repair coverage on the real SQLAlchemy adapter.

Every test binds the app to a disposable SQLite file (DATABASE_URL +
INTERVIV_USE_MEMORY_DB=false). Nothing here migrates, resets, or touches
the user's real database.
"""

from __future__ import annotations

import json
import os
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

os.environ.setdefault("JWT_SECRET_KEY", "test-secret-key-with-at-least-32-bytes!!")
os.environ["OPENAI_API_KEY"] = ""
os.environ["OPENROUTER_API_KEY"] = ""

from alembic import command as alembic_command
from alembic.config import Config as AlembicConfig
from sqlalchemy import create_engine
from sqlalchemy import inspect as sa_inspect

from backend import config as app_config
from backend.auth.security import create_access_token, hash_password
from backend.db import get_database
from backend.db.sqlalchemy_store import (
    _sessionmaker,
    create_all_for_smoke,
    get_engine,
    get_sqlalchemy_database,
)
from backend.main import app


def _clear_db_caches() -> None:
    app_config.get_settings.cache_clear()
    get_engine.cache_clear()
    _sessionmaker.cache_clear()
    get_sqlalchemy_database.cache_clear()


@pytest.fixture
def sa_url(tmp_path, monkeypatch):
    """Disposable SQLite file carrying the current models' schema."""
    db_file = tmp_path / "phaseb1.db"
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


def _make_user(prefix="b1"):
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
    return [{"question_id": q["id"],
             "selected_option_ids": [q["options"][0]["id"]]}
            for q in questions]


FORBIDDEN_RESPONSE_KEYS = (
    '"correct_option_ids"',
    '"reference_query"',
    '"checks_json"',
    '"cases"',
    '"expected"',
    "hidden_stdout",
    "hidden_stderr",
    '"explanation"',
)


def _assert_candidate_safe(payload: object) -> None:
    body = json.dumps(payload)
    for key in FORBIDDEN_RESPONSE_KEYS:
        assert key not in body, f"leaked {key}"


def _as_utc(value: str) -> datetime:
    moment = datetime.fromisoformat(value)
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    return moment


def _assert_same_deadline(first: str, second: str) -> None:
    # SQLite drops tzinfo on read; the stored deadline instant must match.
    assert _as_utc(first) == _as_utc(second)


def test_session_plans_and_round_metadata_survive_write_read(sa_url) -> None:
    db = get_database()
    now = datetime.now(timezone.utc)
    doc = {
        "session_id": "b1-plans", "candidate_id": "b1-cand", "skill": "DBMS",
        "skills": ["DBMS"], "rounds_per_skill": 1, "total_rounds": 2,
        "status": "active", "current_difficulty": "medium",
        "current_skill": "DBMS", "last_round": 1,
        "round_plan": ["mcq", "sql"],
        "round_config": {"count": 3, "duration_minutes": 10},
        "block_plan": [{"id": "b1", "position": 1, "round_type": "mcq",
                        "category": "oa", "skills": ["DBMS"], "count": 3,
                        "duration_minutes": 10, "difficulty": "easy",
                        "question_ids": [], "problem_ids": [],
                        "language": None, "negative_marking": 0.25,
                        "review_policy": "none"}],
        "expanded_plan": [{"round": 1, "block_id": "b1", "block_position": 1}],
        "allow_unknown_topic_fallback": False,
        "rounds": [{"round": 1, "question": "Multiple Choice Assessment",
                    "round_type": "mcq", "difficulty": "medium",
                    "status": "in_progress", "started_at": now,
                    "expires_at": now + timedelta(minutes=10),
                    "question_context": {"questions": []},
                    "config_json": {"count": 0},
                    "block_id": "b1", "block_position": 1,
                    "block_category": "oa", "block_index": 1,
                    "block_total": 1}],
    }
    db["sessions"].insert_one(doc)
    back = db["sessions"].find_one({"session_id": "b1-plans"})
    assert back is not None
    assert back["round_plan"] == ["mcq", "sql"]
    assert back["round_config"] == {"count": 3, "duration_minutes": 10}
    assert back["block_plan"][0]["id"] == "b1"
    assert back["block_plan"][0]["difficulty"] == "easy"
    assert back["expanded_plan"] == [{"round": 1, "block_id": "b1",
                                      "block_position": 1}]
    assert back["allow_unknown_topic_fallback"] is False
    stored_round = back["rounds"][0]
    assert (stored_round["block_id"], stored_round["block_position"],
            stored_round["block_category"], stored_round["block_index"],
            stored_round["block_total"]) == ("b1", 1, "oa", 1, 1)
    assert stored_round["question_context"] == {"questions": []}

    # Legacy session without Phase B keys still reads; the missing
    # fallback flag defaults to the old always-fill behavior.
    db["sessions"].insert_one({
        "session_id": "b1-legacy", "candidate_id": "b1-cand", "skill": "DBMS",
        "rounds": [{"round": 1, "question": "q",
                    "round_type": "technical_short_answer",
                    "difficulty": "medium"}],
    })
    legacy = db["sessions"].find_one({"session_id": "b1-legacy"})
    assert legacy["round_plan"] is None
    assert legacy["block_plan"] is None
    assert legacy["expanded_plan"] is None
    assert legacy["allow_unknown_topic_fallback"] is True
    assert legacy["rounds"][0]["block_id"] is None


def test_close_reopen_preserves_recovery_state(sa_url) -> None:
    client = TestClient(app)
    user = _make_user("b1-reopen")
    headers = _headers(user)
    start = client.post("/session/start", headers=headers, json={"blocks": [
        {"round_type": "mcq", "category": "oa", "skills": ["DBMS"],
         "count": 4, "duration_minutes": 20},
    ]})
    assert start.status_code == 200, start.text
    body = start.json()
    session_id = body["session_id"]
    before_ids = [q["id"] for q in body["questions"]]
    before_options = [[o["id"] for o in q["options"]] for q in body["questions"]]
    before_expires = body["expires_at"]

    # Close the database: dispose pooled connections and drop every cache
    # so the next access reopens the same disposable file from scratch.
    get_engine().dispose()
    get_engine.cache_clear()
    _sessionmaker.cache_clear()
    get_sqlalchemy_database.cache_clear()

    resume = client.get(f"/session/{session_id}", headers=headers)
    assert resume.status_code == 200, resume.text
    active = resume.json()["active_round"]
    after_ids = [q["id"] for q in active["question_context"]["questions"]]
    after_options = [[o["id"] for o in q["options"]]
                     for q in active["question_context"]["questions"]]
    assert after_ids == before_ids
    assert after_options == before_options
    _assert_same_deadline(active["expires_at"], before_expires)
    assert resume.json()["block_plan"][0]["category"] == "oa"
    stored = get_database()["sessions"].find_one({"session_id": session_id})
    assert stored["total_rounds"] == 1
    assert stored["rounds"][0]["status"] == "in_progress"


def test_mixed_repeated_blocks_progress_through_sqlalchemy(sa_url) -> None:
    client = TestClient(app)
    user = _make_user("b1-flow")
    headers = _headers(user)
    start = client.post("/session/start", headers=headers, json={"blocks": [
        {"round_type": "mcq", "category": "oa", "skills": ["DBMS"],
         "count": 3, "duration_minutes": 10, "difficulty": "easy"},
        {"round_type": "mcq", "category": "verbal",
         "skills": ["Verbal Ability"], "count": 2, "duration_minutes": 10},
        {"round_type": "technical_short_answer", "category": "interview",
         "skills": ["DBMS"], "count": 1},
        {"round_type": "mcq", "category": "oa", "skills": ["Python"],
         "count": 2, "duration_minutes": 20, "difficulty": "medium"},
        {"round_type": "sql", "category": "sql",
         "count": 1, "duration_minutes": 15},
    ]})
    assert start.status_code == 200, start.text
    body = start.json()
    session_id = body["session_id"]
    assert body["round_plan"] == ["mcq", "mcq", "technical_short_answer",
                                  "mcq", "sql"]
    assert [b["category"] for b in body["block_plan"]] == [
        "oa", "verbal", "interview", "oa", "sql"]
    assert [b["position"] for b in body["block_plan"]] == [1, 2, 3, 4, 5]
    assert len({b["id"] for b in body["block_plan"]}) == 5
    _assert_candidate_safe(body)

    first_ids = [q["id"] for q in body["questions"]]
    assert all(q["skill"] == "DBMS" for q in body["questions"])
    first_expires = body["expires_at"]

    # Refresh keeps identity, assignment, option order, and deadline.
    for _ in range(2):
        resume = client.get(f"/session/{session_id}", headers=headers)
        assert resume.status_code == 200, resume.text
        active = resume.json()["active_round"]
        assert [q["id"] for q in active["question_context"]["questions"]] == first_ids
        assert [[o["id"] for o in q["options"]]
                for q in active["question_context"]["questions"]] == [
                    [o["id"] for o in q["options"]] for q in body["questions"]]
        _assert_same_deadline(active["expires_at"], first_expires)
        assert active["block_position"] == 1
        assert active["block_category"] == "oa"
        _assert_candidate_safe(resume.json())

    ans1 = client.post("/session/answer", headers=headers, json={
        "session_id": session_id, "round": 1,
        "answers": _mcq_answers(body["questions"]),
    })
    assert ans1.status_code == 200, ans1.text
    assert ans1.json()["next_round_type"] == "mcq"
    assert ans1.json()["next_block_category"] == "verbal"
    verbal_questions = ans1.json()["next_question_context"]["questions"]
    assert all(q["skill"] == "Verbal Ability" for q in verbal_questions)
    _assert_candidate_safe(ans1.json())

    ans2 = client.post("/session/answer", headers=headers, json={
        "session_id": session_id, "round": 2,
        "answers": _mcq_answers(verbal_questions),
    })
    assert ans2.status_code == 200, ans2.text
    assert ans2.json()["next_round_type"] == "technical_short_answer"
    assert ans2.json()["next_block_category"] == "interview"

    ans3 = client.post("/session/answer", headers=headers, json={
        "session_id": session_id, "round": 3,
        "answer_text": "A primary key uniquely identifies each row in a table.",
    })
    assert ans3.status_code == 200, ans3.text
    assert ans3.json()["next_round_type"] == "mcq"
    assert ans3.json()["next_block_position"] == 4
    python_questions = ans3.json()["next_question_context"]["questions"]
    assert len(python_questions) == 2
    assert all(q["skill"] == "Python" for q in python_questions)
    _assert_candidate_safe(ans3.json())

    ans4 = client.post("/session/answer", headers=headers, json={
        "session_id": session_id, "round": 4,
        "answers": _mcq_answers(python_questions),
    })
    assert ans4.status_code == 200, ans4.text
    assert ans4.json()["next_round_type"] == "sql"
    assert ans4.json()["next_block_category"] == "sql"

    raw = get_database()["sessions"].find_one({"session_id": session_id})
    ref_query = raw["rounds"][4]["question_context"].get("reference_query")
    assert ref_query
    ans5 = client.post("/session/answer", headers=headers, json={
        "session_id": session_id, "round": 5, "answer_text": ref_query,
    })
    assert ans5.status_code == 200, ans5.text
    assert ans5.json()["session_complete"] is True
    _assert_candidate_safe(ans5.json())

    # Stored rounds keep block identity for every round, in order.
    stored = get_database()["sessions"].find_one({"session_id": session_id})
    assert stored["status"] == "completed"
    assert [r["block_position"] for r in stored["rounds"]] == [1, 2, 3, 4, 5]
    assert [r["block_category"] for r in stored["rounds"]] == [
        "oa", "verbal", "interview", "oa", "sql"]
    assert stored["block_plan"][3]["skills"] == ["Python"]
    assert stored["block_plan"][3]["difficulty"] == "medium"


def test_preset_crud_owner_only_sqlalchemy(sa_url) -> None:
    client = TestClient(app)
    user = _make_user("b1-preset")
    other = _make_user("b1-preset-other")
    headers = _headers(user)
    blocks = [{"round_type": "mcq", "category": "oa", "skills": ["DBMS"],
               "count": 5, "duration_minutes": 15}]
    created = client.post("/practice/presets", headers=headers, json={
        "name": "DBMS sprint", "version": 1, "blocks": blocks,
    })
    assert created.status_code == 200, created.text
    preset_id = created.json()["id"]
    assert created.json()["blocks"][0]["position"] == 1

    fetched = client.get(f"/practice/presets/{preset_id}", headers=headers)
    assert fetched.status_code == 200, fetched.text
    assert fetched.json()["blocks"][0]["skills"] == ["DBMS"]

    # Survives close/reopen of the disposable database.
    get_engine().dispose()
    get_engine.cache_clear()
    _sessionmaker.cache_clear()
    get_sqlalchemy_database.cache_clear()
    reopened = client.get(f"/practice/presets/{preset_id}", headers=headers)
    assert reopened.status_code == 200, reopened.text
    assert reopened.json()["name"] == "DBMS sprint"

    other_list = client.get("/practice/presets", headers=_headers(other))
    assert all(p["id"] != preset_id for p in other_list.json()["presets"])
    forbidden = client.get(f"/practice/presets/{preset_id}",
                           headers=_headers(other))
    assert forbidden.status_code == 404
    forbidden_write = client.put(
        f"/practice/presets/{preset_id}", headers=_headers(other),
        json={"name": "hijacked"})
    assert forbidden_write.status_code == 404
    still = client.get(f"/practice/presets/{preset_id}", headers=headers)
    assert still.json()["name"] == "DBMS sprint"

    bad = client.post("/practice/presets", headers=headers, json={
        "name": "bad", "version": 99, "blocks": blocks,
    })
    assert bad.status_code == 422

    updated = client.put(f"/practice/presets/{preset_id}", headers=headers,
                         json={"name": "DBMS sprint v2"})
    assert updated.status_code == 200, updated.text
    deleted = client.delete(f"/practice/presets/{preset_id}", headers=headers)
    assert deleted.status_code == 200
    gone = client.get(f"/practice/presets/{preset_id}", headers=headers)
    assert gone.status_code == 404


def test_builder_draft_recovery_sqlalchemy(sa_url) -> None:
    client = TestClient(app)
    user = _make_user("b1-builder")
    other = _make_user("b1-builder-other")
    headers = _headers(user)
    blocks = [{"round_type": "mcq", "category": "verbal",
               "skills": ["Verbal Ability"], "count": 5,
               "duration_minutes": 10}]
    saved = client.put("/practice/builder-draft", headers=headers, json={
        "version": 1, "blocks": blocks,
    })
    assert saved.status_code == 200, saved.text

    get_engine().dispose()
    get_engine.cache_clear()
    _sessionmaker.cache_clear()
    get_sqlalchemy_database.cache_clear()

    fetched = client.get("/practice/builder-draft", headers=headers)
    assert fetched.status_code == 200, fetched.text
    assert fetched.json()["blocks"][0]["skills"] == ["Verbal Ability"]

    others = client.get("/practice/builder-draft", headers=_headers(other))
    assert others.status_code == 200
    assert others.json()["blocks"] == []

    bad = client.put("/practice/builder-draft", headers=headers, json={
        "version": 99, "blocks": blocks,
    })
    assert bad.status_code == 422


def test_answer_draft_recovery_and_immutability_sqlalchemy(sa_url) -> None:
    client = TestClient(app)
    user = _make_user("b1-ansdraft")
    other = _make_user("b1-ansdraft-other")
    headers = _headers(user)
    start = client.post("/session/start", headers=headers, json={"blocks": [
        {"round_type": "mcq", "category": "oa", "skills": ["DBMS"],
         "count": 3, "duration_minutes": 20},
    ]})
    session_id = start.json()["session_id"]
    questions = start.json()["questions"]

    save = client.put(f"/session/{session_id}/draft", headers=headers, json={
        "round": 1, "answers": [
            {"question_id": questions[0]["id"],
             "selected_option_ids": [questions[0]["options"][0]["id"]]},
        ],
    })
    assert save.status_code == 200, save.text

    get_engine().dispose()
    get_engine.cache_clear()
    _sessionmaker.cache_clear()
    get_sqlalchemy_database.cache_clear()

    got = client.get(f"/session/{session_id}/draft?round=1", headers=headers)
    assert got.status_code == 200, got.text
    assert got.json()["draft"]["answers"][0]["question_id"] == questions[0]["id"]

    denied = client.get(f"/session/{session_id}/draft?round=1",
                        headers=_headers(other))
    assert denied.status_code in (403, 404)
    denied_write = client.put(f"/session/{session_id}/draft",
                              headers=_headers(other),
                              json={"round": 1, "answers": []})
    assert denied_write.status_code in (401, 403, 404)

    forged = client.put(f"/session/{session_id}/draft", headers=headers, json={
        "round": 1, "answers": [
            {"question_id": "forged_999", "selected_option_ids": ["a"]},
        ],
    })
    assert forged.status_code == 422

    ans = client.post("/session/answer", headers=headers, json={
        "session_id": session_id, "round": 1,
        "answers": _mcq_answers(questions),
    })
    assert ans.status_code == 200, ans.text
    after = client.get(f"/session/{session_id}/draft?round=1", headers=headers)
    assert after.status_code in (404, 409)
    resave = client.put(f"/session/{session_id}/draft", headers=headers, json={
        "round": 1, "answers": [],
    })
    assert resave.status_code == 409


def test_answer_draft_rejects_expired_round_sqlalchemy(sa_url) -> None:
    client = TestClient(app)
    user = _make_user("b1-expired")
    headers = _headers(user)
    start = client.post("/session/start", headers=headers, json={"blocks": [
        {"round_type": "mcq", "category": "oa", "skills": ["DBMS"],
         "count": 2, "duration_minutes": 20},
    ]})
    session_id = start.json()["session_id"]
    db = get_database()
    raw = db["sessions"].find_one({"session_id": session_id})
    raw["rounds"][0]["expires_at"] = datetime.now(timezone.utc) - timedelta(minutes=1)
    db["sessions"].update_one(
        {"session_id": session_id}, {"$set": {"rounds": raw["rounds"]}})
    save = client.put(f"/session/{session_id}/draft", headers=headers, json={
        "round": 1, "answers": [],
    })
    assert save.status_code == 400


def test_retry_scores_once_without_dup_progression_sqlalchemy(sa_url) -> None:
    client = TestClient(app)
    user = _make_user("b1-retry")
    headers = _headers(user)
    start = client.post("/session/start", headers=headers, json={"blocks": [
        {"round_type": "mcq", "category": "oa", "skills": ["DBMS"],
         "count": 3, "duration_minutes": 20},
        {"round_type": "sql", "category": "sql",
         "count": 1, "duration_minutes": 15},
    ]})
    session_id = start.json()["session_id"]
    questions = start.json()["questions"]
    first = client.post("/session/answer", headers=headers, json={
        "session_id": session_id, "round": 1,
        "answers": _mcq_answers(questions),
    })
    assert first.status_code == 200, first.text
    score_before = first.json()["final_score"]
    elo_after = first.json()["elo_after"]

    for _ in range(3):
        dup = client.post("/session/answer", headers=headers, json={
            "session_id": session_id, "round": 1,
            "answers": _mcq_answers(questions),
        })
        assert dup.status_code == 409

    stored = get_database()["sessions"].find_one({"session_id": session_id})
    assert len(stored["rounds"]) == 2
    assert stored["rounds"][0]["final_score"] == score_before
    assert stored["rounds"][1]["round_type"] == "sql"
    assert stored["rounds"][1]["block_position"] == 2
    candidate = get_database()["candidates"].find_one(
        {"candidate_id": stored["candidate_id"]})
    assert float(candidate["elo_ratings"]["DBMS"]) == float(elo_after)


def test_concurrent_submit_scores_once_sqlalchemy(sa_url, monkeypatch) -> None:
    """Two simultaneous submits for one round: one 200, one 409, one scoring."""
    import backend.routes.answer as answer_module

    client_a = TestClient(app)
    client_b = TestClient(app)
    user = _make_user("b1-race")
    headers = _headers(user)
    start = client_a.post("/session/start", headers=headers, json={"blocks": [
        {"round_type": "mcq", "category": "oa", "skills": ["DBMS"],
         "count": 3, "duration_minutes": 20},
        {"round_type": "sql", "category": "sql",
         "count": 1, "duration_minutes": 15},
    ]})
    session_id = start.json()["session_id"]
    questions = start.json()["questions"]
    payload = {"session_id": session_id, "round": 1,
               "answers": _mcq_answers(questions)}

    arrivals: list[int] = []
    gate = threading.Event()
    gate_lock = threading.Lock()
    real_score = answer_module.score_round
    calls: list[int] = []

    def gated_score(*args, **kwargs):
        with gate_lock:
            calls.append(1)
            arrivals.append(1)
            first = len(arrivals) == 1
        # The first scorer pauses so a racer relying on the old
        # check-then-claim window can join; the fix serializes first.
        if first:
            gate.wait(timeout=1.5)
        else:
            gate.set()
        return real_score(*args, **kwargs)

    monkeypatch.setattr(answer_module, "score_round", gated_score)

    with ThreadPoolExecutor(max_workers=2) as pool:
        future_a = pool.submit(client_a.post, "/session/answer",
                               headers=headers, json=payload)
        future_b = pool.submit(client_b.post, "/session/answer",
                               headers=headers, json=payload)
        resp_a = future_a.result(timeout=60)
        resp_b = future_b.result(timeout=60)

    assert sorted([resp_a.status_code, resp_b.status_code]) == [200, 409]
    assert len(calls) == 1
    stored = get_database()["sessions"].find_one({"session_id": session_id})
    assert len(stored["rounds"]) == 2
    assert stored["rounds"][1]["round_type"] == "sql"


def test_alembic_migration_supports_phaseB_persistence(tmp_path, monkeypatch) -> None:
    db_file = tmp_path / "phaseb1_mig.db"
    url = f"sqlite:///{db_file}"
    _run_alembic(url, "upgrade", "head")

    engine = create_engine(url)
    inspector = sa_inspect(engine)
    tables = inspector.get_table_names()
    for table in ("practice_presets", "builder_drafts", "answer_drafts"):
        assert table in tables
    session_cols = {c["name"] for c in inspector.get_columns("sessions")}
    for col in ("round_plan_json", "round_config_json", "block_plan_json",
                "expanded_plan_json", "allow_unknown_topic_fallback"):
        assert col in session_cols
    round_cols = {c["name"] for c in inspector.get_columns("rounds")}
    for col in ("block_id", "block_position", "block_category",
                "block_index", "block_total"):
        assert col in round_cols
    engine.dispose()

    # The migrated schema (not create_all) drives the repaired store.
    monkeypatch.setenv("DATABASE_URL", url)
    monkeypatch.setenv("INTERVIV_USE_MEMORY_DB", "false")
    _clear_db_caches()
    try:
        db = get_database()
        db["sessions"].insert_one({
            "session_id": "b1-mig", "candidate_id": "b1-mig-cand",
            "skill": "DBMS", "round_plan": ["mcq"],
            "block_plan": [{"id": "b1", "position": 1}],
            "allow_unknown_topic_fallback": False,
            "rounds": [{"round": 1, "question": "q",
                        "round_type": "mcq", "difficulty": "medium",
                        "status": "in_progress", "block_id": "b1",
                        "block_position": 1, "block_category": "oa",
                        "block_index": 1, "block_total": 1}],
        })
        back = db["sessions"].find_one({"session_id": "b1-mig"})
        assert back["round_plan"] == ["mcq"]
        assert back["rounds"][0]["block_category"] == "oa"
        db["practice_presets"].insert_one({
            "id": "p1", "user_id": "u1", "name": "n", "version": 1,
            "blocks": [], "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc),
        })
        assert db["practice_presets"].find_one({"id": "p1"}) is not None
        db["builder_drafts"].update_one(
            {"user_id": "u1"},
            {"$set": {"user_id": "u1", "version": 1, "blocks": []}},
            upsert=True)
        assert db["builder_drafts"].find_one({"user_id": "u1"}) is not None
        db["answer_drafts"].update_one(
            {"session_id": "b1-mig", "round": 1},
            {"$set": {"session_id": "b1-mig", "round": 1,
                      "user_id": "u1", "draft": {"round": 1}}},
            upsert=True)
        assert db["answer_drafts"].find_one(
            {"session_id": "b1-mig", "round": 1}) is not None
    finally:
        try:
            get_engine().dispose()
        except Exception:
            pass
        _clear_db_caches()

    # Downgrade removes the new schema; re-upgrade restores it.
    _run_alembic(url, "downgrade", "20260907_0003")
    engine = create_engine(url)
    tables = sa_inspect(engine).get_table_names()
    assert "practice_presets" not in tables
    assert "builder_drafts" not in tables
    assert "answer_drafts" not in tables
    engine.dispose()
    _run_alembic(url, "upgrade", "head")
    engine = create_engine(url)
    tables = sa_inspect(engine).get_table_names()
    assert "practice_presets" in tables
    engine.dispose()


def test_legacy_session_without_plans_still_progresses(sa_url) -> None:
    client = TestClient(app)
    user = _make_user("b1-legprog")
    headers = _headers(user)
    db = get_database()
    now = datetime.now(timezone.utc)

    # Legacy mixed session mid-flight: MCQ round stored without any
    # Phase B keys must still submit and progress to SQL.
    from backend.db.phase2_content_bank import PHASE2_MCQ_BANK
    assigned = [{**q, "options": q["options_json"]} for q in PHASE2_MCQ_BANK[:2]]
    db["sessions"].insert_one({
        "session_id": "b1-leg-mixed", "candidate_id": "b1-leg-cand",
        "user_id": user["id"], "skill": "DBMS", "skills": ["DBMS"],
        "rounds_per_skill": 1, "total_rounds": 2, "status": "active",
        "current_difficulty": "medium", "current_skill": "DBMS",
        "last_round": 1, "round_plan": ["mcq", "sql"],
        "rounds": [{"round": 1, "question": "Multiple Choice Assessment",
                    "round_type": "mcq", "difficulty": "medium",
                    "status": "in_progress", "started_at": now,
                    "expires_at": now + timedelta(minutes=20),
                    "question_context": {"questions": assigned},
                    "config_json": {"count": 2, "duration_minutes": 20,
                                    "negative_marking": 0.25,
                                    "attempt_policy": "single_submission_final",
                                    "review_policy": "none"}}],
    })
    ans = client.post("/session/answer", headers=headers, json={
        "session_id": "b1-leg-mixed", "round": 1,
        "answers": _mcq_answers(assigned),
    })
    assert ans.status_code == 200, ans.text
    assert ans.json()["next_round_type"] == "sql"

    # Legacy technical opener with unknown MCQ topics progresses through
    # the preserved unknown-topic fallback (missing flag means allowed).
    db["sessions"].insert_one({
        "session_id": "b1-leg-fallback", "candidate_id": "b1-leg-cand",
        "user_id": user["id"], "skill": "SQL", "skills": ["SQL", "React"],
        "rounds_per_skill": 1, "total_rounds": 2, "status": "active",
        "current_difficulty": "medium", "current_skill": "SQL",
        "last_round": 1, "round_plan": ["technical_short_answer", "mcq"],
        "rounds": [{"round": 1, "question": "Explain indexing.",
                    "round_type": "technical_short_answer",
                    "difficulty": "medium", "status": "in_progress",
                    "started_at": now, "question_context": {}}],
    })
    ans2 = client.post("/session/answer", headers=headers, json={
        "session_id": "b1-leg-fallback", "round": 1,
        "answer_text": "Indexes speed up lookups by ordering keys.",
    })
    assert ans2.status_code == 200, ans2.text
    assert ans2.json()["next_round_type"] == "mcq"
    assert len(ans2.json()["next_question_context"]["questions"]) == 15
