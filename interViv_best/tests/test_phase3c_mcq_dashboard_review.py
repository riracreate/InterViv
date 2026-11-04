"""Phase 3C: completed dashboard surfaces MCQ review under after_session only."""

from __future__ import annotations

import os
from datetime import datetime, timezone
from uuid import uuid4

from fastapi.testclient import TestClient

os.environ.setdefault("INTERVIV_USE_MEMORY_DB", "true")
os.environ.setdefault("JWT_SECRET_KEY", "test-secret-key-with-at-least-32-bytes!!")
os.environ["OPENAI_API_KEY"] = ""
os.environ["OPENROUTER_API_KEY"] = ""
os.environ["LLM_LIVE_FETCH"] = "0"

from backend.auth.security import create_access_token, hash_password
from backend.db import get_database
from backend.main import app


def _make_user(prefix: str = "phase3c") -> dict[str, str]:
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


def _headers(user: dict[str, str]) -> dict[str, str]:
    return {"Authorization": f"Bearer {user['token']}"}


def test_completed_after_session_dashboard_includes_mcq_review_keys() -> None:
    client = TestClient(app)
    user = _make_user("mcq-dash")
    headers = _headers(user)
    start = client.post("/session/start", headers=headers, json={
        "blocks": [{
            "round_type": "mcq",
            "category": "oa",
            "skills": ["DBMS"],
            "count": 2,
            "duration_minutes": 20,
            "review_policy": "after_session",
        }],
    })
    assert start.status_code == 200, start.text
    body = start.json()
    session_id = body["session_id"]
    questions = body.get("questions") or []
    assert questions
    answers = [
        {"question_id": q["id"], "selected_option_ids": [q["options"][0]["id"]]}
        for q in questions
    ]
    answer = client.post("/session/answer", headers=headers, json={
        "session_id": session_id, "round": 1, "answers": answers,
    })
    assert answer.status_code == 200, answer.text

    db = get_database()
    session = db["sessions"].find_one({"session_id": session_id})
    rounds = list(session.get("rounds") or [])
    cfg = dict(rounds[0].get("config_json") or {})
    cfg["review_policy"] = "after_session"
    rounds[0]["config_json"] = cfg
    q_ctx = dict(rounds[0].get("question_context") or {})
    qs = list(q_ctx.get("questions") or [])
    qs[0] = {
        **qs[0],
        "correct_option_ids": [
            (qs[0].get("options") or qs[0].get("options_json") or [{"id": "a"}])[0]["id"]
        ],
        "explanation": "PHASE3C-MCQ-EXPLANATION",
    }
    q_ctx["questions"] = qs
    rounds[0]["question_context"] = q_ctx
    db["sessions"].update_one(
        {"session_id": session_id},
        {"$set": {"rounds": rounds, "status": "completed"}},
    )

    dash = client.get(f"/dashboard/{session_id}", headers=headers)
    assert dash.status_code == 200, dash.text
    payload = dash.json()
    round0 = payload["rounds"][0]
    assert round0.get("round_type") == "mcq"
    assert round0.get("review_policy") == "after_session"
    mcq_qs = round0.get("mcq_questions") or []
    assert mcq_qs
    assert "correct_option_ids" in mcq_qs[0]
    assert mcq_qs[0].get("explanation") == "PHASE3C-MCQ-EXPLANATION"
    assert "PHASE3C-MCQ-EXPLANATION" in dash.text


def test_active_after_session_dashboard_still_hides_mcq_keys() -> None:
    client = TestClient(app)
    user = _make_user("mcq-hide")
    headers = _headers(user)
    start = client.post("/session/start", headers=headers, json={
        "blocks": [{
            "round_type": "mcq",
            "category": "oa",
            "skills": ["DBMS"],
            "count": 2,
            "duration_minutes": 20,
            "review_policy": "after_session",
        }],
    })
    assert start.status_code == 200, start.text
    session_id = start.json()["session_id"]
    db = get_database()
    session = db["sessions"].find_one({"session_id": session_id})
    rounds = list(session.get("rounds") or [])
    cfg = dict(rounds[0].get("config_json") or {})
    cfg["review_policy"] = "after_session"
    rounds[0]["config_json"] = cfg
    q_ctx = dict(rounds[0].get("question_context") or {})
    qs = list(q_ctx.get("questions") or [])
    qs[0] = {
        **qs[0],
        "correct_option_ids": ["HIDE-OPTION"],
        "explanation": "HIDE-EXPLANATION",
    }
    q_ctx["questions"] = qs
    rounds[0]["question_context"] = q_ctx
    db["sessions"].update_one(
        {"session_id": session_id},
        {"$set": {"rounds": rounds, "status": "active"}},
    )
    dash = client.get(f"/dashboard/{session_id}", headers=headers)
    assert dash.status_code == 200, dash.text
    assert "HIDE-OPTION" not in dash.text
    assert "HIDE-EXPLANATION" not in dash.text
    assert "correct_option_ids" not in dash.text
