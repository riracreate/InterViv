"""Unit, scoring rubric, and API tests for sandboxed SQL round evaluation."""

from __future__ import annotations

import os
from unittest.mock import patch
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

os.environ.setdefault("INTERVIV_USE_MEMORY_DB", "true")
os.environ.setdefault("JWT_SECRET_KEY", "test-secret-key-with-at-least-32-bytes!!")

from backend.auth.security import create_access_token, hash_password
from backend.db import get_database
from backend.db.phase2a_fixtures import PHASE2A_SQL_FIXTURES
from backend.main import app
from modules.scoring import score_round
from modules.scoring.sql_round import score_sql_round


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


@pytest.fixture
def test_user() -> dict[str, str]:
    db = get_database()
    user_id = str(uuid4())
    email = f"sql-candidate-{user_id[:8]}@example.com"
    user_doc = {
        "id": user_id,
        "email": email,
        "name": "Test SQL Candidate",
        "password_hash": hash_password("passw0rd123"),
        "created_at": None,
        "last_active_at": None,
    }
    db["users"].insert_one(user_doc)
    token = create_access_token(user_id)
    return {"id": user_id, "email": email, "token": token}


@pytest.fixture
def other_user() -> dict[str, str]:
    db = get_database()
    user_id = str(uuid4())
    email = f"sql-other-{user_id[:8]}@example.com"
    user_doc = {
        "id": user_id,
        "email": email,
        "name": "Other Candidate",
        "password_hash": hash_password("passw0rd123"),
        "created_at": None,
        "last_active_at": None,
    }
    db["users"].insert_one(user_doc)
    token = create_access_token(user_id)
    return {"id": user_id, "email": email, "token": token}


# ── 1. Unit scoring rubric tests ─────────────────────────────────────────────

def test_sql_scoring_reference_query_gets_100_percent():
    """Executing the reference query across all 3 cases yields 100.0%."""
    problem = PHASE2A_SQL_FIXTURES[0]
    result = score_sql_round(
        candidate_query=problem["reference_query"],
        question_context=problem,
    )
    assert result["final_score"] == 100.0
    assert result["score_explanation"]["passed_cases"] == 3
    assert result["score_explanation"]["total_cases"] == 3
    assert not result["score_explanation"]["has_forbidden_constructs"]

    # Verify artifact_json structure & zero leakage
    artifact = result["artifact_json"]
    assert artifact["total_cases"] == 3
    assert artifact["passed_cases"] == 3
    for case_item in artifact["cases"]:
        assert case_item["passed"] is True
        assert case_item["result_match"] is True
        assert case_item["row_count_match"] is True
        assert "seed_data" not in case_item
        assert "reference_query" not in case_item


def test_sql_scoring_order_insensitive_matching():
    """Order-insensitive problem passes when rows are returned in reversed order."""
    problem = dict(PHASE2A_SQL_FIXTURES[1])
    problem["checks_json"] = {"order_matters": False}

    # Reference query is:
    # SELECT c.name, SUM(o.amount) AS total_spent ...
    # Candidate changes order:
    reversed_order_query = """
    SELECT c.name, SUM(o.amount) AS total_spent
    FROM customers c
    JOIN orders o ON c.id = o.customer_id
    GROUP BY c.id, c.name
    HAVING SUM(o.amount) > 100.0
    ORDER BY c.name DESC;
    """
    result = score_sql_round(
        candidate_query=reversed_order_query,
        question_context=problem,
    )
    assert result["final_score"] == 100.0
    assert result["score_explanation"]["passed_cases"] == 3


def test_sql_scoring_mutant_query_partial_score():
    """Mutant query (> 150 instead of > 100) misses boundary rows in cases, yielding partial score."""
    problem = PHASE2A_SQL_FIXTURES[1]
    mutant_query = """
    SELECT c.name, SUM(o.amount) AS total_spent
    FROM customers c
    JOIN orders o ON c.id = o.customer_id
    GROUP BY c.id, c.name
    HAVING SUM(o.amount) > 150.0;
    """
    result = score_sql_round(
        candidate_query=mutant_query,
        question_context=problem,
    )
    assert result["final_score"] < 100.0
    # The candidate is clean of forbidden constructs (20 pts per case = 20)
    # But row count and result equality fail on cases where amounts are between 100 and 150
    assert result["score_explanation"]["construct_score"] == 20.0
    assert result["score_explanation"]["passed_cases"] < 3


def test_sql_scoring_forbidden_constructs_penalty():
    """Using a forbidden construct applies -20% penalty across all cases."""
    problem = dict(PHASE2A_SQL_FIXTURES[1])
    problem["checks_json"] = {
        "order_matters": False,
        "forbidden_constructs": ["having"],
    }
    # Candidate query uses HAVING (forbidden)
    query_with_having = problem["reference_query"]
    result = score_sql_round(
        candidate_query=query_with_having,
        question_context=problem,
    )
    # Result equality (60) + Row count (20) = 80, construct (0) -> 80.0%
    assert result["final_score"] == 80.0
    assert result["score_explanation"]["has_forbidden_constructs"] is True
    assert "having" in result["score_explanation"]["forbidden_constructs_found"]


def test_sql_scoring_runtime_error_handled_cleanly():
    """Syntax or runtime error does not crash the server and scores 20 (or 0) points."""
    problem = PHASE2A_SQL_FIXTURES[0]
    result = score_sql_round(
        candidate_query="SELECT non_existent_column FROM non_existent_table;",
        question_context=problem,
    )
    # Construct check passes (20 pts), execution fails (0 result, 0 row count) -> 20.0%
    assert result["final_score"] == 20.0
    assert result["score_explanation"]["passed_cases"] == 0
    assert result["artifact_json"]["cases"][0]["error"] is not None


def test_sql_scoring_dispatcher_contract():
    """Verify score_round(round_type='sql', ...) returns standard breakdown keys."""
    problem = PHASE2A_SQL_FIXTURES[0]
    result = score_round(
        round_type="sql",
        answer_text=problem["reference_query"],
        question_context=problem,
    )
    assert result["final_score"] == 100.0
    assert "layer1_score" in result["scoring_breakdown"]
    assert "layer2_score" in result["scoring_breakdown"]
    assert "layer3_score" in result["scoring_breakdown"]
    assert result["nlp_score"] is None
    assert result["svm_label"] is None
    assert result["kg_score"] is None
    assert result["ner_entities"] == []


# ── 2. API Integration Tests ────────────────────────────────────────────────

def test_sql_preview_endpoint_runs_sample_case(client: TestClient, test_user: dict[str, str]):
    """POST /session/sql/run executes candidate query against visible sample case."""
    headers = {"Authorization": f"Bearer {test_user['token']}"}

    # Start session with SQL round
    start_resp = client.post(
        "/session/start",
        json={"candidate_id": "", "skills": ["DBMS"], "round_type": "sql"},
        headers=headers,
    )
    assert start_resp.status_code == 200, start_resp.text
    session_id = start_resp.json()["session_id"]
    assert start_resp.json()["round_type"] == "sql"

    # Preview query against visible sample (departments table in problem 1)
    preview_resp = client.post(
        "/session/sql/run",
        json={
            "session_id": session_id,
            "round": 1,
            "query": "SELECT id, name FROM departments ORDER BY id ASC;",
        },
        headers=headers,
    )
    assert preview_resp.status_code == 200
    data = preview_resp.json()
    assert data["columns"] == ["id", "name"]
    assert len(data["rows"]) == 2
    assert data["rows"][0] == [1, "Engineering"]
    assert data["truncated"] is False
    assert data["error"] is None
    assert data["execution_time_ms"] >= 0


def test_sql_preview_endpoint_handles_syntax_errors(client: TestClient, test_user: dict[str, str]):
    """POST /session/sql/run returns 200 with error string on syntax error."""
    headers = {"Authorization": f"Bearer {test_user['token']}"}

    start_resp = client.post(
        "/session/start",
        json={"candidate_id": "", "skills": ["DBMS"], "round_type": "sql"},
        headers=headers,
    )
    session_id = start_resp.json()["session_id"]

    preview_resp = client.post(
        "/session/sql/run",
        json={
            "session_id": session_id,
            "round": 1,
            "query": "SELECT FROM invalid syntax;",
        },
        headers=headers,
    )
    assert preview_resp.status_code == 200
    data = preview_resp.json()
    assert data["error"] is not None
    assert "syntax error" in data["error"].lower()


def test_sql_preview_endpoint_authentication_guard(
    client: TestClient, test_user: dict[str, str], other_user: dict[str, str]
):
    """POST /session/sql/run rejects unauthenticated (401) and unauthorized (403) requests."""
    headers = {"Authorization": f"Bearer {test_user['token']}"}
    other_headers = {"Authorization": f"Bearer {other_user['token']}"}

    start_resp = client.post(
        "/session/start",
        json={"candidate_id": "", "skills": ["DBMS"], "round_type": "sql"},
        headers=headers,
    )
    session_id = start_resp.json()["session_id"]

    # 1. Without auth header -> 401
    resp_no_auth = client.post(
        "/session/sql/run",
        json={"session_id": session_id, "round": 1, "query": "SELECT 1;"},
    )
    assert resp_no_auth.status_code == 401

    # 2. With wrong user token -> 403
    resp_wrong_user = client.post(
        "/session/sql/run",
        json={"session_id": session_id, "round": 1, "query": "SELECT 1;"},
        headers=other_headers,
    )
    assert resp_wrong_user.status_code == 403


def test_sql_full_answer_submission_flow(client: TestClient, test_user: dict[str, str]):
    """Start SQL session, preview query, submit final answer, verify scoring and persistence."""
    headers = {"Authorization": f"Bearer {test_user['token']}"}

    start_resp = client.post(
        "/session/start",
        json={"candidate_id": "", "skills": ["DBMS"], "round_type": "sql"},
        headers=headers,
    )
    assert start_resp.status_code == 200
    session_data = start_resp.json()
    session_id = session_data["session_id"]

    # Verify zero leakage in start_session response
    q_ctx = session_data.get("question_context") or {}
    assert "reference_query" not in q_ctx
    assert "cases" not in q_ctx
    assert "sample_cases" in q_ctx
    assert len(q_ctx["sample_cases"]) >= 1

    # Submit correct query via /session/answer
    correct_query = PHASE2A_SQL_FIXTURES[0]["reference_query"]
    ans_resp = client.post(
        "/session/answer",
        json={
            "session_id": session_id,
            "round": 1,
            "answer_text": correct_query,
        },
        headers=headers,
    )
    assert ans_resp.status_code == 200, ans_resp.text
    result = ans_resp.json()

    assert result["final_score"] == 100.0
    artifact = result["artifact_json"]
    assert artifact["total_cases"] == 3
    assert artifact["passed_cases"] == 3

    # Check database persistence
    db = get_database()
    saved = db["sessions"].find_one({"session_id": session_id})
    round_doc = saved["rounds"][0]
    assert round_doc["status"] == "submitted"
    assert round_doc["final_score"] == 100.0
    assert round_doc["answer_text"] == correct_query


def test_sql_zero_llm_calls_enforced(client: TestClient, test_user: dict[str, str]):
    """Verify strictly zero LLM invocations occur during start, preview, and scoring of SQL rounds."""
    headers = {"Authorization": f"Bearer {test_user['token']}"}

    with patch("backend.scoring.pipeline.run_scoring_pipeline") as mock_pipeline_score, \
         patch("modules.nlp_scorer.NLPScorer.compute_overall_score") as mock_nlp, \
         patch("modules.question_bank._generate_via_llm") as mock_llm_gen, \
         patch("modules.question_bank.get_next_question") as mock_qb:

        start_resp = client.post(
            "/session/start",
            json={"candidate_id": "", "skills": ["DBMS"], "round_type": "sql"},
            headers=headers,
        )
        assert start_resp.status_code == 200
        session_id = start_resp.json()["session_id"]

        preview_resp = client.post(
            "/session/sql/run",
            json={"session_id": session_id, "round": 1, "query": "SELECT 1;"},
            headers=headers,
        )
        assert preview_resp.status_code == 200

        ans_resp = client.post(
            "/session/answer",
            json={"session_id": session_id, "round": 1, "answer_text": "SELECT 1;"},
            headers=headers,
        )
        assert ans_resp.status_code == 200

        # Assert zero calls to any LLM functions
        assert mock_pipeline_score.call_count == 0
        assert mock_nlp.call_count == 0
        assert mock_llm_gen.call_count == 0
        assert mock_qb.call_count == 0
