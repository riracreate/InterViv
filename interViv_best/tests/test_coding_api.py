"""Phase C API: coding leakage, ownership, run/submit, and catalog.

Sentinel-style probes assert private coding material (hidden tests,
reference/mutant solutions, hidden execution detail) never reaches the
candidate on any surface: start, resume/fetch, run preview, submit,
dashboard, problems catalog, or post-completion review.

Ownership probes assert every coding surface requires the owning
user's JWT. Availability probes assert the C.1 unavailable outcome
surfaces as retryable 503 with the round left open and attempts
recorded as unevaluated history.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

os.environ.setdefault("INTERVIV_USE_MEMORY_DB", "true")
os.environ.setdefault("JWT_SECRET_KEY", "test-secret-key-with-at-least-32-bytes!!")

from backend.auth.security import create_access_token, hash_password
from backend.db import get_database
from backend.db.phase_c_coding_bank import get_coding_problem
from backend.main import app

PROBLEM_ID = "coding_two_sum"

PRIVATE_SUBSTRINGS = (
    "hidden_tests",
    "reference_solution",
    "mutant_solution",
    "hidden_stdout",
    "hidden_stderr",
)


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


@pytest.fixture
def test_user() -> dict[str, str]:
    return _make_user("coding-candidate")


@pytest.fixture
def second_user() -> dict[str, str]:
    return _make_user("coding-other")


def _make_user(prefix: str) -> dict[str, str]:
    db = get_database()
    user_id = str(uuid4())
    db["users"].insert_one(
        {
            "id": user_id,
            "email": f"{prefix}-{user_id[:8]}@example.com",
            "name": f"Test {prefix}",
            "password_hash": hash_password("passw0rd123"),
            "created_at": datetime.now(timezone.utc),
            "last_active_at": datetime.now(timezone.utc),
        }
    )
    return {"id": user_id, "token": create_access_token(user_id)}


def _auth(user: dict[str, str]) -> dict[str, str]:
    return {"Authorization": f"Bearer {user['token']}"}


def _start_coding_session(
    client: TestClient, user: dict[str, str], problem_id: str = PROBLEM_ID
) -> dict:
    resp = client.post(
        "/session/start",
        json={
            "candidate_id": "",
            "skills": ["DSA"],
            "rounds_per_skill": 1,
            "round_type": "coding",
            "round_config": {"problem_id": problem_id, "duration_minutes": 30},
        },
        headers=_auth(user),
    )
    assert resp.status_code == 200, resp.text
    return resp.json()


def _start_mcq_session(client: TestClient, user: dict[str, str]) -> dict:
    resp = client.post(
        "/session/start",
        json={
            "candidate_id": "",
            "skills": ["DBMS"],
            "rounds_per_skill": 1,
            "round_type": "mcq",
            "round_config": {"count": 1, "duration_minutes": 20},
        },
        headers=_auth(user),
    )
    assert resp.status_code == 200, resp.text
    return resp.json()


def _assert_no_private_material(blob: str) -> None:
    lowered = blob.lower()
    for needle in PRIVATE_SUBSTRINGS:
        assert needle not in lowered, f"leaked private material: {needle}"


def _attempts_for(session_id: str) -> list[dict]:
    db = get_database()
    return list(db["coding_submissions"].find({"session_id": session_id}))


# Start / resume surfaces --------------------------------------------------


def test_start_coding_session_exposes_public_context_only(
    client: TestClient, test_user: dict[str, str]
) -> None:
    started = _start_coding_session(client, test_user)
    assert started["round_type"] == "coding"
    q_ctx = started["question_context"]
    assert q_ctx["problem_id"] == PROBLEM_ID
    assert q_ctx["statement"]
    assert q_ctx["starter_code"]
    assert len(q_ctx["visible_tests"]) == 3
    assert started["starter_code"] == q_ctx["starter_code"]
    _assert_no_private_material(json.dumps(started))


def test_start_coding_session_requires_auth(client: TestClient) -> None:
    resp = client.post(
        "/session/start",
        json={
            "candidate_id": "",
            "skills": ["DSA"],
            "rounds_per_skill": 1,
            "round_type": "coding",
            "round_config": {"problem_id": PROBLEM_ID},
        },
    )
    assert resp.status_code == 401


def test_start_unknown_coding_problem_is_422(
    client: TestClient, test_user: dict[str, str]
) -> None:
    resp = client.post(
        "/session/start",
        json={
            "candidate_id": "",
            "skills": ["DSA"],
            "rounds_per_skill": 1,
            "round_type": "coding",
            "round_config": {"problem_id": "coding_nope"},
        },
        headers=_auth(test_user),
    )
    assert resp.status_code == 422


def test_get_session_is_leak_free_and_owned(
    client: TestClient, test_user: dict[str, str], second_user: dict[str, str]
) -> None:
    started = _start_coding_session(client, test_user)
    session_id = started["session_id"]

    resp = client.get(f"/session/{session_id}", headers=_auth(test_user))
    assert resp.status_code == 200
    _assert_no_private_material(resp.text)

    resp = client.get(f"/session/{session_id}")
    assert resp.status_code == 401

    resp = client.get(f"/session/{session_id}", headers=_auth(second_user))
    assert resp.status_code == 403


def test_sanitizer_strips_injected_coding_secrets_under_any_policy(
    client: TestClient, test_user: dict[str, str]
) -> None:
    """Assert against a real GET /session payload after secrets are injected.

    Previously called sanitize_round_for_client on a hand-built dict that
    could not regress when the route shape changed.
    """
    started = _start_coding_session(client, test_user)
    session_id = started["session_id"]
    db = get_database()
    session = db["sessions"].find_one({"session_id": session_id})
    assert session is not None
    rounds = list(session.get("rounds") or [])
    assert rounds
    q_ctx = dict(rounds[0].get("question_context") or {})
    q_ctx.update({
        "hidden_tests": [{"input": {}, "expected": "SECRET"}],
        "reference_solution": "SECRET-REF",
        "mutant_solution": "SECRET-MUTANT",
        "hidden_stdout": "SECRET-OUT",
        "hidden_stderr": "SECRET-ERR",
    })
    rounds[0] = {
        **rounds[0],
        "status": "submitted",
        "final_score": 100.0,
        "question_context": q_ctx,
        "artifact_json": {
            "evaluation": "coding",
            "problem_id": PROBLEM_ID,
            "visible": {"passed": 3, "total": 3, "cases": [
                {"passed": True, "error": None}]},
            "hidden": {"passed": 5, "total": 5, "stdout": "SECRET-OUT"},
            "capped": False,
            "final_score": 100.0,
        },
        "config_json": {
            **(rounds[0].get("config_json") or {}),
            "review_policy": "after_session",
        },
    }
    db["sessions"].update_one(
        {"session_id": session_id},
        {"$set": {"rounds": rounds, "status": "completed"}},
    )
    resp = client.get(f"/session/{session_id}", headers=_auth(test_user))
    assert resp.status_code == 200, resp.text
    blob = resp.text
    _assert_no_private_material(blob)
    assert "SECRET" not in blob
    body = resp.json()
    active = body.get("active_round") or body
    q = (active.get("question_context") or body.get("question_context") or {})
    assert "hidden_tests" not in q
    assert "reference_solution" not in q


# Run preview surface ------------------------------------------------------


def test_coding_run_guards(
    client: TestClient, test_user: dict[str, str], second_user: dict[str, str]
) -> None:
    started = _start_coding_session(client, test_user)
    session_id = started["session_id"]
    body = {"session_id": session_id, "round": 1, "source": "def f(): pass"}

    resp = client.post("/session/coding/run", json=body)
    assert resp.status_code == 401

    resp = client.post("/session/coding/run", json=body,
                       headers=_auth(second_user))
    assert resp.status_code == 403

    resp = client.post(
        "/session/coding/run",
        json={**body, "session_id": "missing"},
        headers=_auth(test_user),
    )
    assert resp.status_code == 404

    resp = client.post(
        "/session/coding/run",
        json={**body, "round": 99},
        headers=_auth(test_user),
    )
    assert resp.status_code == 404

    mcq = _start_mcq_session(client, test_user)
    resp = client.post(
        "/session/coding/run",
        json={"session_id": mcq["session_id"], "round": 1, "source": "x"},
        headers=_auth(test_user),
    )
    assert resp.status_code == 400


def test_coding_run_unavailable_is_retryable_and_leaves_round_open(
    client: TestClient, test_user: dict[str, str]
) -> None:
    started = _start_coding_session(client, test_user)
    body = {"session_id": started["session_id"], "round": 1,
            "source": "def two_sum(nums, target): pass"}

    for _ in range(2):
        resp = client.post("/session/coding/run", json=body,
                           headers=_auth(test_user))
        assert resp.status_code == 503, resp.text
        assert "not run" in resp.json()["detail"]
        assert "nothing was scored" in resp.json()["detail"]

    fetched = client.get(f"/session/{started['session_id']}",
                         headers=_auth(test_user)).json()
    active = fetched["active_round"] or fetched["current_round"]
    assert active["status"] == "in_progress"
    assert active.get("final_score") is None


def test_coding_run_returns_visible_only(
    client: TestClient, test_user: dict[str, str], monkeypatch
) -> None:
    import backend.routes.session as session_routes

    def fake_execute(**kwargs):
        assert kwargs["hidden_tests"] == []
        assert kwargs["function"] == "two_sum"
        return {
            "visible": [
                {"passed": True, "error": None, "stdout": "ok"},
                {"passed": False, "error": "mismatch", "stdout": ""},
                {"passed": False, "error": "runtime", "stdout": "boom"},
            ],
            "hidden": [],
        }

    monkeypatch.setattr(session_routes, "execute_python_tests", fake_execute)
    started = _start_coding_session(client, test_user)
    resp = client.post(
        "/session/coding/run",
        json={"session_id": started["session_id"], "round": 1,
              "source": "def two_sum(nums, target): pass"},
        headers=_auth(test_user),
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["success"] is True
    assert data["scored"] is False
    assert (data["visible_passed"], data["visible_total"]) == (1, 3)
    assert len(data["visible"]) == 3
    assert "hidden" not in data
    _assert_no_private_material(resp.text)


# Submit surface ------------------------------------------------------------


def test_submit_unavailable_records_attempt_and_stays_open(
    client: TestClient, test_user: dict[str, str]
) -> None:
    started = _start_coding_session(client, test_user)
    session_id = started["session_id"]
    source = "def two_sum(nums, target):\n    pass\n"
    body = {"session_id": session_id, "round": 1, "answer_text": source}

    for _ in range(2):
        resp = client.post("/session/answer", json=body,
                           headers=_auth(test_user))
        assert resp.status_code == 503, resp.text

    fetched = client.get(f"/session/{session_id}",
                         headers=_auth(test_user)).json()
    active = fetched["active_round"] or fetched["current_round"]
    assert active["status"] == "in_progress"
    assert active.get("final_score") is None

    attempts = _attempts_for(session_id)
    assert len(attempts) == 2
    for attempt in attempts:
        assert attempt["user_id"] == test_user["id"]
        assert attempt["round"] == 1
        assert attempt["problem_id"] == PROBLEM_ID
        assert attempt["source"] == source
        assert attempt["status"] == "unavailable"
        assert attempt["score"] is None
        _assert_no_private_material(json.dumps(attempt, default=str))


def test_submit_rejects_other_users(
    client: TestClient, test_user: dict[str, str], second_user: dict[str, str]
) -> None:
    started = _start_coding_session(client, test_user)
    resp = client.post(
        "/session/answer",
        json={"session_id": started["session_id"], "round": 1,
              "answer_text": "x"},
        headers=_auth(second_user),
    )
    assert resp.status_code == 403


def test_submit_success_with_stub_scores_and_persists(
    client: TestClient, test_user: dict[str, str], monkeypatch
) -> None:
    import backend.execution as execution

    def fake_execute(**kwargs):
        assert len(kwargs["hidden_tests"]) == 5
        return {
            "visible": [{"passed": True, "error": None} for _ in range(3)],
            "hidden": [{"passed": True, "error": None} for _ in range(5)],
        }

    monkeypatch.setattr(execution, "execute_python_tests", fake_execute)
    started = _start_coding_session(client, test_user)
    session_id = started["session_id"]
    problem = get_coding_problem(PROBLEM_ID)
    assert problem is not None

    resp = client.post(
        "/session/answer",
        json={"session_id": session_id, "round": 1,
              "answer_text": problem["reference_solution"]},
        headers=_auth(test_user),
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["final_score"] == 100.0
    _assert_no_private_material(resp.text)

    fetched = client.get(f"/session/{session_id}",
                         headers=_auth(test_user)).json()
    _assert_no_private_material(json.dumps(fetched))

    attempts = _attempts_for(session_id)
    assert len(attempts) == 1
    attempt = attempts[0]
    assert attempt["status"] == "scored"
    assert attempt["score"] == 100.0
    assert (attempt["visible_passed"], attempt["visible_total"]) == (3, 3)
    assert (attempt["hidden_passed"], attempt["hidden_total"]) == (5, 5)
    _assert_no_private_material(json.dumps(attempt, default=str))


# Catalog surfaces ----------------------------------------------------------


def test_problems_requires_auth(client: TestClient) -> None:
    assert client.get("/problems").status_code == 401
    assert client.get(f"/problems/{PROBLEM_ID}").status_code == 401


def test_problems_list_and_filters(
    client: TestClient, test_user: dict[str, str]
) -> None:
    resp = client.get("/problems", headers=_auth(test_user))
    assert resp.status_code == 200
    data = resp.json()
    assert data["count"] == 15
    assert len(data["problems"]) == 15
    first = data["problems"][0]
    assert first["statement"] and first["starter_code"]
    assert len(first["visible_tests"]) == 3
    _assert_no_private_material(resp.text)

    resp = client.get("/problems?difficulty=easy", headers=_auth(test_user))
    assert resp.status_code == 200
    data = resp.json()
    assert data["count"] == 6
    assert {p["difficulty"] for p in data["problems"]} == {"easy"}

    resp = client.get("/problems?topic=dp", headers=_auth(test_user))
    assert resp.status_code == 200
    data = resp.json()
    assert data["count"] >= 1
    assert all("dp" in p["topics"] for p in data["problems"])

    resp = client.get("/problems?difficulty=bogus", headers=_auth(test_user))
    assert resp.status_code == 422


def test_problem_detail(
    client: TestClient, test_user: dict[str, str]
) -> None:
    resp = client.get(f"/problems/{PROBLEM_ID}", headers=_auth(test_user))
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == PROBLEM_ID
    assert data["function"] == "two_sum"
    _assert_no_private_material(resp.text)

    resp = client.get("/problems/coding_nope", headers=_auth(test_user))
    assert resp.status_code == 404


def test_practice_bank_includes_leak_free_coding(
    client: TestClient, test_user: dict[str, str]
) -> None:
    assert client.get("/session/practice-bank").status_code == 401
    resp = client.get("/session/practice-bank", headers=_auth(test_user))
    assert resp.status_code == 200
    data = resp.json()
    assert data["counts"]["coding"] == 15
    assert len(data["coding"]) == 15
    for entry in data["coding"]:
        assert entry["type"] == "coding"
        assert entry["statement"] and entry["starter_code"]
    _assert_no_private_material(resp.text)
