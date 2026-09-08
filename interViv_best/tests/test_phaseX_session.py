"""ML primitives compose, stay unavailable, and never leak pack internals."""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from uuid import uuid4

from fastapi.testclient import TestClient

os.environ.setdefault("INTERVIV_USE_MEMORY_DB", "true")
os.environ.setdefault("JWT_SECRET_KEY", "test-secret-key-with-at-least-32-bytes!!")
os.environ["OPENAI_API_KEY"] = ""
os.environ["OPENROUTER_API_KEY"] = ""

from backend.auth.security import create_access_token, hash_password
from backend.db import get_database
from backend.main import app
from backend.ml_primitives.catalog import UNAVAILABLE_MESSAGE
from modules.skill_graph import StudentSkillGraph

SENTINELS = (
    "PHASEX_REF_SENTINEL",
    "PHASEX_PROP_SENTINEL",
    "PHASEX_BUG_SENTINEL",
    "PHASEX_RULE_INTERNAL",
)


def _make_user(prefix="phasex") -> dict[str, str]:
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


def _assert_no_pack_leak(payload) -> None:
    blob = payload if isinstance(payload, str) else json.dumps(payload, default=str)
    for sentinel in SENTINELS:
        assert sentinel not in blob, sentinel


def test_ml_blocks_compose_and_repeat_with_every_category() -> None:
    client = TestClient(app)
    user = _make_user("compose")
    headers = _headers(user)
    started = client.post("/session/start", headers=headers, json={"blocks": [
        {"round_type": "mcq", "category": "verbal", "skills": ["Verbal Ability"],
         "count": 3, "duration_minutes": 10},
        {"round_type": "mcq", "category": "oa", "skills": ["DBMS"],
         "count": 3, "duration_minutes": 12, "difficulty": "easy"},
        {"round_type": "sql", "category": "sql", "count": 1, "duration_minutes": 15,
         "problem_ids": ["sql_prob_026"]},
        {"round_type": "coding", "category": "coding", "count": 1, "duration_minutes": 30,
         "problem_ids": ["coding_two_sum"]},
        {"round_type": "system_design", "category": "system_design", "count": 1,
         "duration_minutes": 25, "problem_ids": ["sd_rate_limiter"]},
        {"round_type": "technical_short_answer", "category": "interview",
         "skills": ["DBMS"], "count": 1},
        {"round_type": "ml_primitives", "category": "ml_primitives", "count": 1,
         "duration_minutes": 22, "problem_ids": ["softmax_stable.v1"]},
        {"round_type": "ml_primitives", "category": "ml_primitives", "count": 1,
         "duration_minutes": 33, "problem_ids": ["layer_norm.v1"]},
    ]})
    assert started.status_code == 200, started.text
    body = started.json()
    _assert_no_pack_leak(body)
    plan = body["block_plan"]
    assert [block["category"] for block in plan] == [
        "verbal", "oa", "sql", "coding", "system_design", "interview",
        "ml_primitives", "ml_primitives",
    ]
    assert [block["position"] for block in plan] == list(range(1, 9))
    assert plan[6]["id"] != plan[7]["id"]
    assert plan[6]["problem_ids"] == ["softmax_stable.v1"]
    assert plan[7]["problem_ids"] == ["layer_norm.v1"]
    assert plan[6]["duration_minutes"] == 22
    assert plan[7]["duration_minutes"] == 33
    assert body["total_rounds"] == 8
    stored = get_database()["sessions"].find_one({"session_id": body["session_id"]})
    assert stored["block_plan"][6]["id"] == plan[6]["id"]
    assert stored["expanded_plan"][6]["problem_ids"] == ["softmax_stable.v1"]
    assert stored["expanded_plan"][7]["problem_ids"] == ["layer_norm.v1"]
    assert stored["expanded_plan"][6]["duration_minutes"] == 22
    assert stored["expanded_plan"][7]["duration_minutes"] == 33
    assert stored["expanded_plan"][6]["block_id"] == plan[6]["id"]
    assert stored["expanded_plan"][7]["block_id"] == plan[7]["id"]


def test_mixed_session_reaches_ml_and_stays_open_without_a_score() -> None:
    client = TestClient(app)
    user = _make_user("progress")
    headers = _headers(user)
    StudentSkillGraph(user["id"]).initialize_from_resume(["DBMS", "ML primitives"])
    before = {
        node["name"]: (node.get("attempts") or 0, node.get("score"))
        for node in client.get("/skill-graph/me", headers=headers).json()["skills"]
    }
    started = client.post("/session/start", headers=headers, json={"blocks": [
        {"round_type": "technical_short_answer", "category": "interview",
         "skills": ["DBMS"], "count": 1},
        {"round_type": "ml_primitives", "category": "ml_primitives",
         "problem_ids": ["minmax_normalize.v1"], "duration_minutes": 30},
        {"round_type": "coding", "category": "coding",
         "problem_ids": ["coding_two_sum"], "duration_minutes": 30},
    ]})
    assert started.status_code == 200, started.text
    session_id = started.json()["session_id"]
    interview = client.post("/session/answer", headers=headers, json={
        "session_id": session_id, "round": 1,
        "answer_text": "A primary key uniquely identifies each row.",
    })
    assert interview.status_code == 200, interview.text
    nxt = interview.json()
    assert nxt["next_round_type"] == "ml_primitives"
    assert nxt["next_block_category"] == "ml_primitives"
    context = nxt.get("next_question_context") or {}
    assert context.get("id") == "minmax_normalize.v1"
    assert context.get("scoring_available") is False
    _assert_no_pack_leak(nxt)

    source = "import numpy as np\n\ndef minmax(x):\n    return x\n"
    unavailable = client.post("/session/answer", headers=headers, json={
        "session_id": session_id, "round": 2, "answer_text": source,
    })
    assert unavailable.status_code == 503, unavailable.text
    detail = unavailable.json()["detail"]
    assert detail["submission_saved"] is True
    assert detail["retryable"] is True
    assert detail["message"] == UNAVAILABLE_MESSAGE
    assert "score" not in detail
    _assert_no_pack_leak(unavailable.json())

    stored = get_database()["sessions"].find_one({"session_id": session_id})
    ml_round = stored["rounds"][1]
    assert ml_round["status"] == "in_progress"
    assert ml_round["final_score"] is None
    assert stored.get("status") != "completed"
    assert len(stored["rounds"]) == 2
    scored_before_ml = stored["rounds"][0]["final_score"]
    assert scored_before_ml is not None

    resumed = client.get(f"/session/{session_id}", headers=headers)
    assert resumed.status_code == 200, resumed.text
    active = resumed.json()["active_round"]
    assert active["round_type"] == "ml_primitives"
    assert active["status"] == "in_progress"
    assert active["final_score"] is None
    assert active["question_context"]["id"] == "minmax_normalize.v1"
    _assert_no_pack_leak(resumed.json())

    attempts = client.get("/ml-primitives/attempts", headers=headers).json()
    assert attempts["count"] == 1
    assert attempts["attempts"][0]["source"] == source
    assert attempts["attempts"][0]["status"] == "unavailable"
    assert "score" not in attempts["attempts"][0]
    _assert_no_pack_leak(attempts)

    dashboard = client.get("/dashboard/progress", headers=headers).json()
    history = next(item for item in dashboard["history"] if item["session_id"] == session_id)
    assert history["average_score"] == round(float(scored_before_ml), 2)
    assert any(
        item["round_type"] == "ml_primitives" and item["reason"] == "execution_unavailable"
        for item in history["unscored_rounds"]
    )
    _assert_no_pack_leak(dashboard)

    review = client.get(f"/dashboard/{session_id}", headers=headers).json()
    ml_rounds = [item for item in (review.get("rounds") or []) if item.get("round_type") == "ml_primitives"]
    assert ml_rounds and all(item.get("final_score") is None for item in ml_rounds)
    _assert_no_pack_leak(review)

    after = {
        node["name"]: (node.get("attempts") or 0, node.get("score"))
        for node in client.get("/skill-graph/me", headers=headers).json()["skills"]
    }
    assert after.get("ML primitives") == before.get("ML primitives")
    notebook = client.get("/learning/notebook/me", headers=headers).json()
    assert all(entry.get("round_type") != "ml_primitives" for entry in notebook.get("entries") or [])
    _assert_no_pack_leak(notebook)


def test_injected_oracle_fields_cannot_escape_round_views() -> None:
    client = TestClient(app)
    user = _make_user("inject")
    headers = _headers(user)
    started = client.post("/session/start", headers=headers, json={"blocks": [{
        "round_type": "ml_primitives", "category": "ml_primitives",
        "problem_ids": ["attention_scores.v1"],
    }]})
    assert started.status_code == 200, started.text
    session_id = started.json()["session_id"]
    db = get_database()
    session = db["sessions"].find_one({"session_id": session_id})
    session["rounds"][0]["question_context"] = {
        **session["rounds"][0]["question_context"],
        "reference": "PHASEX_REF_SENTINEL_injected",
        "properties": {"hidden": "PHASEX_PROP_SENTINEL_injected"},
        "bugs": ["PHASEX_BUG_SENTINEL_injected"],
        "static_rules": "PHASEX_RULE_INTERNAL_injected",
    }
    db["sessions"].update_one({"session_id": session_id}, {"$set": {"rounds": session["rounds"]}})
    bank = client.get("/session/practice-bank", headers=headers).json()
    resume = client.get(f"/session/{session_id}", headers=headers).json()
    dashboard = client.get(f"/dashboard/{session_id}", headers=headers).json()
    progress = client.get("/dashboard/progress", headers=headers).json()
    for payload in (started.json(), bank, resume, dashboard, progress):
        _assert_no_pack_leak(payload)
        if isinstance(payload, dict) and payload.get("ml_primitives"):
            assert payload["counts"]["ml_primitives"] == 6
            assert all(item.get("scoring_available") is False for item in payload["ml_primitives"])
