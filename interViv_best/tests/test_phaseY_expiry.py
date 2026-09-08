"""Phase Y: expiry records unscored-not-zero when evaluation is unavailable.

The expiry path (POST /session/answer past the deadline) used to write a
hard 0.0 for every category except ml_primitives. Coding rounds are
permanently unevaluable behind a 503, so an expired coding zero was a
candidate zero for a round the system could never score — and it reached
the dashboard average, coverage counts, and item outcomes. The fix keys
on scoreability (backend.evidence_kind.evaluation_unavailable), not on
category: a submit that would 503 as unavailable records as unscored on
expiry. Scoreable-but-unfinished rounds keep the existing zero.
"""
from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from fastapi.testclient import TestClient

os.environ.setdefault("INTERVIV_USE_MEMORY_DB", "true")
os.environ.setdefault("JWT_SECRET_KEY", "test-secret-key-with-at-least-32-bytes!!")
os.environ["OPENAI_API_KEY"] = ""
os.environ["OPENROUTER_API_KEY"] = ""

from backend.auth.security import create_access_token, hash_password  # noqa: E402
from backend.db import get_database  # noqa: E402
from backend.evidence_kind import evaluation_unavailable  # noqa: E402
from backend.main import app  # noqa: E402

BLOCKS = {
    "verbal": {"round_type": "mcq", "category": "verbal",
               "skills": ["Verbal Ability"], "count": 3, "duration_minutes": 10},
    "oa": {"round_type": "mcq", "category": "oa", "skills": ["DBMS"],
           "count": 3, "duration_minutes": 12, "difficulty": "easy"},
    "sql": {"round_type": "sql", "category": "sql", "count": 1,
            "duration_minutes": 15, "problem_ids": ["sql_prob_026"]},
    "interview": {"round_type": "technical_short_answer", "category": "interview",
                  "skills": ["DBMS"], "count": 1, "duration_minutes": 30},
    "coding": {"round_type": "coding", "category": "coding", "count": 1,
               "duration_minutes": 30, "problem_ids": ["coding_two_sum"]},
    "system_design": {"round_type": "system_design", "category": "system_design",
                      "count": 1, "duration_minutes": 25,
                      "problem_ids": ["sd_rate_limiter"]},
    "ml_primitives": {"round_type": "ml_primitives", "category": "ml_primitives",
                      "count": 1, "duration_minutes": 30,
                      "problem_ids": ["softmax_stable.v1"]},
}

SUBMITS = {
    "verbal": {"answers": []},
    "oa": {"answers": []},
    "sql": {"answer_text": "SELECT 1"},
    "interview": {"answer_text": "A primary key uniquely identifies each row."},
    "coding": {"answer_text": "def two_sum(nums, t):\n    return [0, 1]\n"},
    "system_design": {"answer_text": "Use a token bucket per key in Redis."},
    "ml_primitives": {"answer_text": "def softmax(x):\n    return x\n"},
}


def _make_user(prefix="phasey"):
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


def _headers(user):
    return {"Authorization": f"Bearer {user['token']}"}


def _start(client, headers, category):
    started = client.post("/session/start", headers=headers,
                          json={"blocks": [BLOCKS[category]]})
    assert started.status_code == 200, started.text
    return started.json()["session_id"]


def _force_expiry(session_id, round_type=None):
    db = get_database()
    session = db["sessions"].find_one({"session_id": session_id})
    assert session["rounds"][0].get("expires_at") is not None
    rounds = session["rounds"]
    rounds[0]["expires_at"] = (
        datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
    if round_type is not None:
        rounds[0]["round_type"] = round_type
    db["sessions"].update_one({"session_id": session_id},
                              {"$set": {"rounds": rounds}})


def _expire_and_submit(client, headers, category):
    session_id = _start(client, headers, category)
    _force_expiry(session_id)
    resp = client.post("/session/answer", headers=headers, json={
        "session_id": session_id, "round": 1, **SUBMITS[category]})
    assert resp.status_code == 400, resp.text
    stored = get_database()["sessions"].find_one({"session_id": session_id})
    return session_id, stored["rounds"][0]


def test_expired_verbal_records_zero():
    client = TestClient(app)
    _, rnd = _expire_and_submit(client, _headers(_make_user("verbal")), "verbal")
    assert rnd["status"] == "expired"
    assert rnd["final_score"] == 0.0


def test_expired_oa_records_zero():
    client = TestClient(app)
    _, rnd = _expire_and_submit(client, _headers(_make_user("oa")), "oa")
    assert rnd["status"] == "expired"
    assert rnd["final_score"] == 0.0


def test_expired_sql_records_zero():
    client = TestClient(app)
    _, rnd = _expire_and_submit(client, _headers(_make_user("sql")), "sql")
    assert rnd["status"] == "expired"
    assert rnd["final_score"] == 0.0


def test_expired_interview_with_deadline_records_zero():
    client = TestClient(app)
    headers = _headers(_make_user("interview"))
    _, rnd = _expire_and_submit(client, headers, "interview")
    assert rnd["status"] == "expired"
    assert rnd["final_score"] == 0.0


def test_expired_coding_records_unscored_not_zero():
    client = TestClient(app)
    _, rnd = _expire_and_submit(client, _headers(_make_user("coding")), "coding")
    assert rnd["status"] == "expired"
    assert rnd["final_score"] is None


def test_expired_system_design_records_zero():
    """Self-assessment runs in-process, so expiry keeps the existing zero;
    the category rule still segregates it out of measured evidence."""
    client = TestClient(app)
    headers = _headers(_make_user("sd"))
    session_id, rnd = _expire_and_submit(client, headers, "system_design")
    assert rnd["status"] == "expired"
    assert rnd["final_score"] == 0.0
    progress = client.get("/dashboard/progress", headers=headers).json()
    history = next(item for item in progress["history"]
                   if item["session_id"] == session_id)
    assert history["average_score"] is None
    assert history["self_reported_rounds"] == 1


def test_expired_ml_primitives_records_unscored():
    client = TestClient(app)
    _, rnd = _expire_and_submit(client, _headers(_make_user("ml")), "ml_primitives")
    assert rnd["status"] == "expired"
    assert rnd["final_score"] is None


def test_expired_unavailable_excluded_from_aggregates():
    client = TestClient(app)
    headers = _headers(_make_user("agg"))
    session_id, _ = _expire_and_submit(client, headers, "coding")

    progress = client.get("/dashboard/progress", headers=headers).json()
    history = next(item for item in progress["history"]
                   if item["session_id"] == session_id)
    assert history["average_score"] is None
    assert history["completed_rounds"] == 0
    assert any(item["round_type"] == "coding"
               and item["reason"] == "execution_unavailable"
               for item in history["unscored_rounds"])
    coverage = progress["coding_coverage"]
    assert coverage["scored_coding_rounds"] == 0
    assert coverage["unscored_coding_rounds"] == 1
    assert progress["readiness"] is None

    graph = client.get("/skill-graph/me", headers=headers).json()
    assert all((node.get("attempts") or 0) == 0
               for node in graph.get("skills") or [])

    notebook = client.get("/learning/notebook/me", headers=headers).json()
    assert notebook.get("entries") == []
    assert notebook["coverage"]["excluded_coding_rounds"] == 1

    items = client.get("/learning/item-status/me", headers=headers,
                       params={"item_type": "coding"}).json()
    assert items["states"]["coding_two_sum"]["attempts"] == 0

    retry = client.post("/learning/retry-sets", headers=headers, json={})
    assert retry.status_code == 409

    session = get_database()["sessions"].find_one({"session_id": session_id})
    assert session.get("status") != "completed"
    assert session.get("overall_readiness_score") is None


def test_expired_scoreable_retains_zero_in_average():
    """Pins the unchanged case so the fix cannot silently widen later."""
    client = TestClient(app)
    headers = _headers(_make_user("widen"))
    session_id, _ = _expire_and_submit(client, headers, "sql")
    progress = client.get("/dashboard/progress", headers=headers).json()
    history = next(item for item in progress["history"]
                   if item["session_id"] == session_id)
    assert history["average_score"] == 0.0
    assert history["completed_rounds"] == 1


def test_predicate_unknown_future_category_defaults_scoreable():
    assert evaluation_unavailable("holodeck") is False
    assert evaluation_unavailable(None) is False
    assert evaluation_unavailable("") is False
    assert evaluation_unavailable("mcq") is False
    assert evaluation_unavailable("sql") is False
    assert evaluation_unavailable("technical_short_answer") is False
    assert evaluation_unavailable("system_design") is False


def test_expired_unknown_round_type_records_zero():
    client = TestClient(app)
    headers = _headers(_make_user("future"))
    session_id = _start(client, headers, "sql")
    _force_expiry(session_id, round_type="holodeck")
    resp = client.post("/session/answer", headers=headers, json={
        "session_id": session_id, "round": 1, "answer_text": "x"})
    assert resp.status_code == 400, resp.text
    stored = get_database()["sessions"].find_one({"session_id": session_id})
    assert stored["rounds"][0]["status"] == "expired"
    assert stored["rounds"][0]["final_score"] == 0.0


def test_predicate_coding_tracks_execution_availability(monkeypatch):
    import backend.evidence_kind as evidence_kind

    assert evaluation_unavailable("coding") is True
    assert evaluation_unavailable("ml_primitives") is True
    monkeypatch.setattr(evidence_kind, "get_execution_status",
                        lambda: {"available": True})
    assert evaluation_unavailable("coding") is False
    assert evaluation_unavailable("ml_primitives") is True
    monkeypatch.setattr(evidence_kind, "get_execution_status",
                        lambda: {"available": False})
    assert evaluation_unavailable("coding") is True


def test_503_seams_intact_after_expiry_change():
    client = TestClient(app)
    headers = _headers(_make_user("seam"))
    coding_id = _start(client, headers, "coding")
    coding = client.post("/session/answer", headers=headers, json={
        "session_id": coding_id, "round": 1, **SUBMITS["coding"]})
    assert coding.status_code == 503, coding.text
    coding_body = coding.json()
    assert isinstance(coding_body.get("detail"), str) and coding_body["detail"]
    assert "score" not in coding_body
    ml_id = _start(client, headers, "ml_primitives")
    ml_resp = client.post("/session/answer", headers=headers, json={
        "session_id": ml_id, "round": 1, **SUBMITS["ml_primitives"]})
    assert ml_resp.status_code == 503, ml_resp.text
    assert ml_resp.json()["detail"]["submission_saved"] is True
    db = get_database()
    assert db["sessions"].find_one(
        {"session_id": coding_id})["rounds"][0]["status"] == "in_progress"
    assert db["sessions"].find_one(
        {"session_id": ml_id})["rounds"][0]["status"] == "in_progress"
