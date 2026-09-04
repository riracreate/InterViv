"""Tests ensuring backend contracts align with MCQRound and SQLRound frontend components."""

from __future__ import annotations

import uuid
import pytest
from starlette.testclient import TestClient

from backend.main import app
from backend.db import get_database


@pytest.fixture
def client():
    return TestClient(app)


def _create_test_candidate(client: TestClient) -> dict[str, str]:
    db = get_database()
    uid = uuid.uuid4().hex[:8]
    email = f"frontend-contract-{uid}@example.com"
    token_resp = client.post("/auth/signup", json={"email": email, "password": "securepassword123"})
    token = token_resp.json().get("access_token")
    user_id = token_resp.json().get("user", {}).get("id")

    candidate_id = f"cand_frontend_{uid}"
    db["candidates"].insert_one({
        "candidate_id": candidate_id,
        "name": f"Frontend Tester {uid}",
        "email": email,
        "user_id": user_id,
        "elo_ratings": {"DBMS": 1200},
    })
    return {"token": token, "candidate_id": candidate_id, "user_id": user_id}


def test_frontend_mcq_round_contract(client: TestClient) -> None:
    """Verify frontend MCQRound contracts: start payload, option shape, submit payload, and review artifact."""
    candidate = _create_test_candidate(client)
    headers = {"Authorization": f"Bearer {candidate['token']}"}

    # 1. Start session with MCQ round
    start_resp = client.post(
        "/session/start",
        json={
            "candidate_id": candidate["candidate_id"],
            "skills": ["DBMS"],
            "round_type": "mcq",
            "round_config": {"count": 5, "duration_minutes": 15},
        },
        headers=headers,
    )
    assert start_resp.status_code == 200, start_resp.text
    start_data = start_resp.json()
    session_id = start_data["session_id"]
    assert start_data["round_type"] == "mcq"

    # Frontend expectations: question_context.questions exists with safe fields
    q_ctx = start_data.get("question_context") or {}
    questions = q_ctx.get("questions") or []
    assert len(questions) == 5
    for q in questions:
        assert "id" in q
        assert "stem" in q
        assert "options" in q
        assert "difficulty" in q
        assert "skill" in q
        # Zero leakage: answers must not be sent to candidate UI
        assert "correct_option_ids" not in q
        assert "explanation" not in q

        options = q["options"]
        assert len(options) == 4
        for opt in options:
            assert "id" in opt
            assert "text" in opt

    # 2. Submit canonical answer list from MCQRound
    ans_payload = {
        "session_id": session_id,
        "round": 1,
        "answers": [
            {"question_id": q["id"], "selected_option_ids": ["b"] if idx == 0 else []}
            for idx, q in enumerate(questions)
        ],
    }
    ans_resp = client.post("/session/answer", json=ans_payload, headers=headers)
    assert ans_resp.status_code == 200, ans_resp.text
    ans_data = ans_resp.json()

    # Frontend expectations in response:
    assert "final_score" in ans_data
    assert isinstance(ans_data["final_score"], (int, float))
    assert "artifact_json" in ans_data
    art = ans_data["artifact_json"]
    assert "questions" in art
    assert "total_questions" in art
    assert art["total_questions"] == 5


def test_frontend_sql_round_contract(client: TestClient) -> None:
    """Verify frontend SQLRound contracts: sample case exposure, preview run, and final submission."""
    candidate = _create_test_candidate(client)
    headers = {"Authorization": f"Bearer {candidate['token']}"}

    # 1. Start session with SQL round
    start_resp = client.post(
        "/session/start",
        json={
            "candidate_id": candidate["candidate_id"],
            "skills": ["DBMS"],
            "round_type": "sql",
            "round_config": {"duration_minutes": 20},
        },
        headers=headers,
    )
    assert start_resp.status_code == 200, start_resp.text
    start_data = start_resp.json()
    session_id = start_data["session_id"]
    assert start_data["round_type"] == "sql"

    # Frontend expectations: schema_ddl and sample_cases exposed
    q_ctx = start_data.get("question_context") or {}
    assert "schema_ddl" in q_ctx
    assert "sample_cases" in q_ctx
    assert len(q_ctx["sample_cases"]) >= 1
    sample = q_ctx["sample_cases"][0]
    assert "description" in sample
    assert "seed_data" in sample
    # Zero leakage
    assert "reference_query" not in q_ctx
    assert "cases" not in q_ctx

    # 2. Run Query (Preview) endpoint contract
    preview_resp = client.post(
        "/session/sql/run",
        json={
            "session_id": session_id,
            "round": 1,
            "query": "SELECT 1 AS num, 'test' AS label;",
        },
        headers=headers,
    )
    assert preview_resp.status_code == 200, preview_resp.text
    preview_data = preview_resp.json()
    assert preview_data["success"] is True
    assert preview_data["columns"] == ["num", "label"]
    assert preview_data["rows"] == [[1, "test"]]
    assert preview_data["row_count"] == 1
    assert "execution_time_ms" in preview_data

    # 3. Final Submission contract
    from backend.db.phase2a_fixtures import PHASE2A_SQL_FIXTURES
    correct_query = PHASE2A_SQL_FIXTURES[0]["reference_query"]
    submit_resp = client.post(
        "/session/answer",
        json={
            "session_id": session_id,
            "round": 1,
            "answer_text": correct_query,
        },
        headers=headers,
    )
    assert submit_resp.status_code == 200, submit_resp.text
    submit_data = submit_resp.json()
    assert submit_data["final_score"] == 100.0
    art = submit_data["artifact_json"]
    assert art["evaluation_cases"] == 3
    assert art["cases_passed"] == 3
    assert art["row_count_cases_passed"] == 3
    assert art["result_equality_points"] == 60.0
    assert art["row_count_points"] == 20.0
    assert art["constraint_points"] == 20.0
    assert art["final_score"] == 100.0
    # Zero leakage: client response never contains hidden case descriptions, seed data, or internal case structures
    assert "cases" not in art
    assert "hidden_cases" not in art
