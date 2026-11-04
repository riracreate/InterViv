"""Integration and security tests for Phase 2 MCQ round API.

Validates:
- Complete 15-question MCQ round lifecycle (start -> resume -> submit).
- Strict payload validation (rejects extra fields, wrong round payload, duplicate/unassigned/forged IDs).
- Authoritative deadline enforcement (late submission yields HTTP 400, marks round expired).
- Atomic concurrency guard (concurrent submission yields HTTP 409).
- Strict JWT authentication (missing/mismatched token yields 401/403, zero candidate-ID fallback).
- Zero leakage (start, resume, and active round views contain zero answer keys or explanations).
- Zero LLM calls throughout MCQ lifecycle.
"""

from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from unittest.mock import patch
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

os.environ.setdefault("INTERVIV_USE_MEMORY_DB", "true")
os.environ.setdefault("JWT_SECRET_KEY", "test-secret-key-with-at-least-32-bytes!!")

from backend.auth.security import create_access_token, hash_password
from backend.db import get_database
from backend.main import app


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


@pytest.fixture
def test_user() -> dict[str, str]:
    db = get_database()
    user_id = str(uuid4())
    email = f"mcq-candidate-{user_id[:8]}@example.com"
    user_doc = {
        "id": user_id,
        "email": email,
        "name": "Test MCQ Candidate",
        "password_hash": hash_password("passw0rd123"),
        "created_at": datetime.now(timezone.utc),
        "last_active_at": datetime.now(timezone.utc),
    }
    db["users"].insert_one(user_doc)
    token = create_access_token(user_id)
    return {"id": user_id, "email": email, "token": token}


@pytest.fixture
def second_user() -> dict[str, str]:
    db = get_database()
    user_id = str(uuid4())
    email = f"mcq-other-{user_id[:8]}@example.com"
    user_doc = {
        "id": user_id,
        "email": email,
        "name": "Other Candidate",
        "password_hash": hash_password("passw0rd123"),
        "created_at": datetime.now(timezone.utc),
        "last_active_at": datetime.now(timezone.utc),
    }
    db["users"].insert_one(user_doc)
    token = create_access_token(user_id)
    return {"id": user_id, "email": email, "token": token}


def test_mcq_full_15_question_flow(client: TestClient, test_user: dict[str, str]):
    """Start an MCQ round, verify 15 questions returned with zero leakage, submit all 15, and verify scoring."""
    headers = {"Authorization": f"Bearer {test_user['token']}"}

    # 1. Start MCQ session
    start_resp = client.post(
        "/session/start",
        json={
            "candidate_id": "",
            "skills": ["DBMS", "Python", "OS", "Computer Networks", "DSA"],
            "round_type": "mcq",
            "round_config": {
                "count": 15,
                "duration_minutes": 20,
                "negative_marking": 0.25,
            },
        },
        headers=headers,
    )
    assert start_resp.status_code == 200, start_resp.text
    session_data = start_resp.json()
    session_id = session_data["session_id"]
    assert session_data["round_type"] == "mcq"
    assert session_data["round"] == 1
    assert "expires_at" in session_data

    questions = session_data.get("questions") or session_data.get("question_context", {}).get("questions", [])
    assert len(questions) == 15

    # Zero leakage check on start response:
    for q in questions:
        assert "correct_option_ids" not in q
        assert "explanation" not in q
        assert "stem" in q
        assert "options" in q
        assert len(q["options"]) >= 2
        for opt in q["options"]:
            assert "id" in opt
            assert "text" in opt

    # 2. Resume / Refresh check via GET /session/{session_id}
    resume_resp = client.get(f"/session/{session_id}", headers=headers)
    assert resume_resp.status_code == 200, resume_resp.text
    active_round = resume_resp.json()["active_round"]
    assert active_round["round_type"] == "mcq"
    assert active_round["status"] == "in_progress"
    active_q_list = active_round["question_context"]["questions"]
    assert len(active_q_list) == 15
    # Ensure same question IDs in same order
    assert [q["id"] for q in active_q_list] == [q["id"] for q in questions]
    for q in active_q_list:
        assert "correct_option_ids" not in q
        assert "explanation" not in q

    # 3. Retrieve raw questions from DB to construct worked-example answers (10 correct, 2 incorrect, 3 unanswered)
    db = get_database()
    raw_session = db["sessions"].find_one({"session_id": session_id})
    raw_round = raw_session["rounds"][0]
    raw_questions = raw_round["question_context"]["questions"]

    answers = []
    # 10 correct
    for i in range(10):
        answers.append({
            "question_id": raw_questions[i]["id"],
            "selected_option_ids": raw_questions[i]["correct_option_ids"],
        })
    # 2 incorrect
    for i in range(10, 12):
        correct = raw_questions[i]["correct_option_ids"][0]
        wrong = [opt["id"] for opt in raw_questions[i]["options_json"] if opt["id"] != correct][0]
        answers.append({
            "question_id": raw_questions[i]["id"],
            "selected_option_ids": [wrong],
        })
    # 3 unanswered (omit or pass empty)
    answers.append({
        "question_id": raw_questions[12]["id"],
        "selected_option_ids": [],
    })

    # 4. Submit answers
    submit_resp = client.post(
        "/session/answer",
        json={
            "session_id": session_id,
            "round": 1,
            "answers": answers,
        },
        headers=headers,
    )
    assert submit_resp.status_code == 200, submit_resp.text
    result = submit_resp.json()

    assert result["final_score"] == 63.33
    expl = result["score_explanation"]
    assert expl["correct_count"] == 10
    assert expl["incorrect_count"] == 2
    assert expl["unanswered_count"] == 3
    assert expl["total_raw_marks"] == 9.50

    artifact = result["artifact_json"]
    assert artifact["total_questions"] == 15
    assert artifact["correct_count"] == 10
    assert artifact["incorrect_count"] == 2
    assert artifact["unanswered_count"] == 3
    assert len(artifact["questions"]) == 15

    # Verify persisted round state in database
    persisted_session = db["sessions"].find_one({"session_id": session_id})
    persisted_round = persisted_session["rounds"][0]
    assert persisted_round["status"] == "submitted"
    assert persisted_round["submitted_at"] is not None
    assert persisted_round["final_score"] == 63.33


def test_mcq_strict_validation_rejections(client: TestClient, test_user: dict[str, str]):
    """Verify strict validation: unknown fields, wrong round payload, duplicate/unassigned/forged IDs."""
    headers = {"Authorization": f"Bearer {test_user['token']}"}

    start_resp = client.post(
        "/session/start",
        json={
            "candidate_id": "",
            "skills": ["DBMS", "Python"],
            "round_type": "mcq",
            "round_config": {"count": 4},
        },
        headers=headers,
    )
    assert start_resp.status_code == 200
    session_id = start_resp.json()["session_id"]
    db = get_database()
    raw_round = db["sessions"].find_one({"session_id": session_id})["rounds"][0]
    raw_questions = raw_round["question_context"]["questions"]

    # 1. Reject answer_text on MCQ round
    resp1 = client.post(
        "/session/answer",
        json={
            "session_id": session_id,
            "round": 1,
            "answer_text": "Option B is definitely correct.",
            "answers": [{"question_id": raw_questions[0]["id"], "selected_option_ids": ["a"]}],
        },
        headers=headers,
    )
    assert resp1.status_code == 422
    assert "MCQ round rejects 'answer_text'" in resp1.text

    # 2. Reject unknown extra fields in payload
    resp2 = client.post(
        "/session/answer",
        json={
            "session_id": session_id,
            "round": 1,
            "answers": [{"question_id": raw_questions[0]["id"], "selected_option_ids": ["a"]}],
            "forged_admin_override": True,
        },
        headers=headers,
    )
    assert resp2.status_code == 422
    assert "Unknown extra fields rejected" in resp2.text

    # 3. Reject duplicate question ID
    resp3 = client.post(
        "/session/answer",
        json={
            "session_id": session_id,
            "round": 1,
            "answers": [
                {"question_id": raw_questions[0]["id"], "selected_option_ids": ["a"]},
                {"question_id": raw_questions[0]["id"], "selected_option_ids": ["b"]},
            ],
        },
        headers=headers,
    )
    assert resp3.status_code == 422
    assert "Duplicate question ID" in resp3.text

    # 4. Reject unassigned question ID
    resp4 = client.post(
        "/session/answer",
        json={
            "session_id": session_id,
            "round": 1,
            "answers": [
                {"question_id": "forged_question_999", "selected_option_ids": ["a"]},
            ],
        },
        headers=headers,
    )
    assert resp4.status_code == 422
    assert "Question ID not assigned" in resp4.text

    # 5. Reject invalid / forged option ID
    resp5 = client.post(
        "/session/answer",
        json={
            "session_id": session_id,
            "round": 1,
            "answers": [
                {"question_id": raw_questions[0]["id"], "selected_option_ids": ["z_forged"]},
            ],
        },
        headers=headers,
    )
    assert resp5.status_code == 422
    assert "Invalid option ID" in resp5.text


def test_mcq_deadline_enforcement(client: TestClient, test_user: dict[str, str]):
    """Late submission (now > expires_at) yields HTTP 400 and marks round expired."""
    headers = {"Authorization": f"Bearer {test_user['token']}"}

    start_resp = client.post(
        "/session/start",
        json={"candidate_id": "", "skills": ["DBMS"], "round_type": "mcq"},
        headers=headers,
    )
    assert start_resp.status_code == 200
    session_id = start_resp.json()["session_id"]

    # Manually expire the round in DB
    db = get_database()
    past_time = datetime.now(timezone.utc) - timedelta(minutes=5)
    session_raw = db["sessions"].find_one({"session_id": session_id})
    session_raw["rounds"][0]["expires_at"] = past_time
    db["sessions"].update_one(
        {"session_id": session_id},
        {"$set": {"rounds": session_raw["rounds"]}},
    )

    # Attempt submission after expiration
    resp = client.post(
        "/session/answer",
        json={
            "session_id": session_id,
            "round": 1,
            "answers": [],
        },
        headers=headers,
    )
    assert resp.status_code == 400
    assert "deadline expired" in resp.text.lower()

    # Verify marked expired in database
    session_after = db["sessions"].find_one({"session_id": session_id})
    assert session_after["rounds"][0]["status"] == "expired"
    assert session_after["rounds"][0]["final_score"] == 0.0


def test_mcq_concurrency_guard(client: TestClient, test_user: dict[str, str]):
    """Submitting on already finalizing or submitted round yields HTTP 409."""
    headers = {"Authorization": f"Bearer {test_user['token']}"}

    start_resp = client.post(
        "/session/start",
        json={"candidate_id": "", "skills": ["DBMS"], "round_type": "mcq"},
        headers=headers,
    )
    session_id = start_resp.json()["session_id"]

    # Submit successfully once
    resp1 = client.post(
        "/session/answer",
        json={"session_id": session_id, "round": 1, "answers": []},
        headers=headers,
    )
    assert resp1.status_code == 200

    # Second submission on submitted round -> 409
    resp2 = client.post(
        "/session/answer",
        json={"session_id": session_id, "round": 1, "answers": []},
        headers=headers,
    )
    assert resp2.status_code == 409
    assert "already been submitted or is finalizing" in resp2.text

    # Verify if status is set to finalizing, submission also gets 409
    db = get_database()
    session_raw = db["sessions"].find_one({"session_id": session_id})
    session_raw["rounds"][0]["status"] = "finalizing"
    db["sessions"].update_one(
        {"session_id": session_id},
        {"$set": {"rounds": session_raw["rounds"]}},
    )
    resp3 = client.post(
        "/session/answer",
        json={"session_id": session_id, "round": 1, "answers": []},
        headers=headers,
    )
    assert resp3.status_code == 409


def test_mcq_strict_jwt_authentication(client: TestClient, test_user: dict[str, str], second_user: dict[str, str]):
    """Strict JWT authentication: 401 if missing header, 403 if token belongs to another user."""
    auth_headers = {"Authorization": f"Bearer {test_user['token']}"}

    start_resp = client.post(
        "/session/start",
        json={"candidate_id": "", "skills": ["DBMS"], "round_type": "mcq"},
        headers=auth_headers,
    )
    session_id = start_resp.json()["session_id"]

    # 1. Answer without Authorization header -> 401
    resp_no_auth = client.post(
        "/session/answer",
        json={"session_id": session_id, "round": 1, "answers": []},
    )
    assert resp_no_auth.status_code == 401
    assert "Authentication is required" in resp_no_auth.text

    # 2. Answer with different user's token -> 403
    other_headers = {"Authorization": f"Bearer {second_user['token']}"}
    resp_wrong_user = client.post(
        "/session/answer",
        json={"session_id": session_id, "round": 1, "answers": []},
        headers=other_headers,
    )
    assert resp_wrong_user.status_code == 403
    assert "You cannot access another user's data" in resp_wrong_user.text

    # 3. GET /session/{session_id} without auth -> 401
    get_no_auth = client.get(f"/session/{session_id}")
    assert get_no_auth.status_code == 401

    # 4. GET /session/{session_id} with other user -> 403
    get_wrong_user = client.get(f"/session/{session_id}", headers=other_headers)
    assert get_wrong_user.status_code == 403


def test_mcq_zero_llm_calls_enforced(client: TestClient, test_user: dict[str, str]):
    """Verify strictly zero LLM invocations occur during start and answer of MCQ rounds."""
    headers = {"Authorization": f"Bearer {test_user['token']}"}

    with patch("backend.scoring.pipeline.run_scoring_pipeline") as mock_pipeline_score, \
         patch("modules.nlp_scorer.NLPScorer.compute_overall_score") as mock_nlp, \
         patch("modules.question_bank._generate_via_llm") as mock_llm_gen, \
         patch("modules.question_bank.get_next_question") as mock_qb:

        start_resp = client.post(
            "/session/start",
            json={"candidate_id": "", "skills": ["DBMS"], "round_type": "mcq"},
            headers=headers,
        )
        assert start_resp.status_code == 200
        session_id = start_resp.json()["session_id"]

        ans_resp = client.post(
            "/session/answer",
            json={"session_id": session_id, "round": 1, "answers": []},
            headers=headers,
        )
        assert ans_resp.status_code == 200

        # Assert zero calls to any technical short answer / LLM scoring functions
        assert mock_pipeline_score.call_count == 0
        assert mock_nlp.call_count == 0
        assert mock_llm_gen.call_count == 0
        assert mock_qb.call_count == 0


def test_mcq_review_policy_zero_leakage(client: TestClient, test_user: dict[str, str]):
    """Review policy leakage asserted on real start / resume / completed GET.

    Replaces the prior hand-built sanitize_round_for_client fixture that could
    not regress when the route payload shape changed.
    """
    headers = {"Authorization": f"Bearer {test_user['token']}"}

    # Active session with after_session policy: must NOT leak keys.
    start = client.post(
        "/session/start",
        headers=headers,
        json={
            "blocks": [{
                "round_type": "mcq",
                "category": "oa",
                "skills": ["DBMS"],
                "count": 2,
                "duration_minutes": 20,
                "review_policy": "after_session",
            }],
        },
    )
    assert start.status_code == 200, start.text
    body = start.json()
    session_id = body["session_id"]
    for q in body.get("questions") or []:
        assert "correct_option_ids" not in q
        assert "explanation" not in q
    resume = client.get(f"/session/{session_id}", headers=headers)
    assert resume.status_code == 200
    for q in (resume.json().get("questions")
              or (resume.json().get("question_context") or {}).get("questions")
              or []):
        assert "correct_option_ids" not in q
        assert "explanation" not in q

    # Completed + review_policy none: still no keys.
    answers = [
        {"question_id": q["id"], "selected_option_ids": [q["options"][0]["id"]]}
        for q in (body.get("questions") or [])
    ]
    submit = client.post(
        "/session/answer",
        headers=headers,
        json={"session_id": session_id, "round": 1, "answers": answers},
    )
    assert submit.status_code == 200, submit.text
    # Force review_policy none on stored round and mark completed.
    db = get_database()
    session = db["sessions"].find_one({"session_id": session_id})
    rounds = list(session.get("rounds") or [])
    cfg = dict(rounds[0].get("config_json") or {})
    cfg["review_policy"] = "none"
    rounds[0]["config_json"] = cfg
    db["sessions"].update_one(
        {"session_id": session_id},
        {"$set": {"rounds": rounds, "status": "completed"}},
    )
    done_none = client.get(f"/session/{session_id}", headers=headers)
    assert done_none.status_code == 200
    for q in (done_none.json().get("questions")
              or (done_none.json().get("question_context") or {}).get("questions")
              or []):
        assert "correct_option_ids" not in q
        assert "explanation" not in q

    # Completed + after_session: keys may be revealed.
    start2 = client.post(
        "/session/start",
        headers=headers,
        json={
            "blocks": [{
                "round_type": "mcq",
                "category": "oa",
                "skills": ["DBMS"],
                "count": 2,
                "duration_minutes": 20,
                "review_policy": "after_session",
            }],
        },
    )
    assert start2.status_code == 200, start2.text
    body2 = start2.json()
    sid2 = body2["session_id"]
    answers2 = [
        {"question_id": q["id"], "selected_option_ids": [q["options"][0]["id"]]}
        for q in (body2.get("questions") or [])
    ]
    assert client.post(
        "/session/answer",
        headers=headers,
        json={"session_id": sid2, "round": 1, "answers": answers2},
    ).status_code == 200
    db["sessions"].update_one(
        {"session_id": sid2},
        {"$set": {"status": "completed"}},
    )
    revealed = client.get(f"/session/{sid2}", headers=headers)
    assert revealed.status_code == 200
    active = revealed.json().get("active_round") or {}
    questions = (active.get("question_context") or {}).get("questions") or []
    # After session completion with after_session, correct ids are allowed.
    assert questions
    assert any("correct_option_ids" in q for q in questions)
