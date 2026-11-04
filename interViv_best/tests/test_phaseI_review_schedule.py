"""Phase I: spaced-review scheduling over the mistakes notebook.

Reviews are practice — they must not move measured mastery, readiness,
or gap analysis. Coding stays due-but-unavailable. Owner-scoped.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

os.environ.setdefault("INTERVIV_USE_MEMORY_DB", "true")
os.environ.setdefault("JWT_SECRET_KEY", "test-secret-key-with-at-least-32-bytes!!")

from backend.auth.security import create_access_token, hash_password
from backend.db import get_database
from backend.db.phase2_content_bank import PHASE2_MCQ_BANK
from backend.main import app
from backend.review_schedule import (
    INTERVAL_LADDER,
    OUTCOME_CORRECT,
    OUTCOME_INCORRECT,
    advance_after_outcome,
    ladder_days_at,
)
from tests.alembic_helpers import parent_revision

PRIVATE_SUBSTRINGS = (
    "correct_option_ids",
    "reference_query",
    "reference_solution",
    "hidden_tests",
    "hidden_stdout",
    "hidden_stderr",
    "mutant",
)


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


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


@pytest.fixture
def test_user() -> dict[str, str]:
    return _make_user("phasei")


@pytest.fixture
def second_user() -> dict[str, str]:
    return _make_user("phasei-other")


def _auth(user: dict[str, str]) -> dict[str, str]:
    return {"Authorization": f"Bearer {user['token']}"}


def _options(question: dict) -> list[dict]:
    return list(question.get("options") or question.get("options_json") or [])


def _wrong_option(question: dict) -> str:
    correct = set(question.get("correct_option_ids") or [])
    for option in _options(question):
        if option["id"] not in correct:
            return option["id"]
    raise AssertionError("no wrong option available")


def _right_option(question: dict) -> str:
    return list(question["correct_option_ids"])[0]


def _start_mcq(client, user, question_ids, skill="DBMS"):
    resp = client.post("/session/start", json={
        "candidate_id": "",
        "skills": [skill],
        "rounds_per_skill": 1,
        "round_type": "mcq",
        "round_config": {
            "question_ids": question_ids,
            "count": len(question_ids),
            "duration_minutes": 20,
        },
    }, headers=_auth(user))
    assert resp.status_code == 200, resp.text
    return resp.json()


def _submit_mcq(client, user, session_id, answers, *, round_num=1):
    resp = client.post(
        "/session/answer",
        json={"session_id": session_id, "round": round_num, "answers": answers},
        headers=_auth(user),
    )
    assert resp.status_code == 200, resp.text
    return resp.json()


def _assert_no_private(blob: str) -> None:
    lowered = blob.lower()
    for needle in PRIVATE_SUBSTRINGS:
        assert needle not in lowered, f"leaked: {needle}"


def _dbms_questions(n: int = 2) -> list[dict]:
    return [q for q in PHASE2_MCQ_BANK if q.get("skill") == "DBMS"][:n]


def test_interval_ladder_progression_is_deterministic() -> None:
    assert INTERVAL_LADDER == (1, 3, 7, 16, 35)
    now = datetime(2026, 9, 7, 12, 0, tzinfo=timezone.utc)
    state = {"interval_index": 0}
    # Three correct reviews climb 1 → 3 → 7 → 16
    expected_days = [3, 7, 16, 35, 35]
    for days in expected_days:
        nxt = advance_after_outcome(
            interval_index=state["interval_index"],
            outcome=OUTCOME_CORRECT,
            now=now,
        )
        assert nxt["interval_days"] == days
        assert nxt["interval_index"] == min(
            state["interval_index"] + 1, len(INTERVAL_LADDER) - 1
        )
        assert nxt["due_at"] == now + timedelta(days=days)
        assert nxt["last_outcome"] == OUTCOME_CORRECT
        state["interval_index"] = nxt["interval_index"]
    # Incorrect resets to day-1 ladder rung
    reset = advance_after_outcome(
        interval_index=state["interval_index"],
        outcome=OUTCOME_INCORRECT,
        now=now,
    )
    assert reset["interval_index"] == 0
    assert reset["interval_days"] == ladder_days_at(0) == 1
    assert reset["due_at"] == now + timedelta(days=1)
    assert reset["last_outcome"] == OUTCOME_INCORRECT


def test_parent_revision_for_phase_i() -> None:
    assert parent_revision("20260907_0008") == "20260907_0007"


def test_fresh_account_due_list_is_absence_not_zeros(
    client: TestClient, test_user: dict[str, str]
) -> None:
    headers = _auth(test_user)
    due = client.get("/learning/reviews/due", headers=headers).json()
    assert due["items"] == []
    assert due["due_count"] == 0
    assert due["empty_reason"] == "no_scheduled_items"
    assert due.get("note") is None
    me = client.get("/learning/reviews/me", headers=headers).json()
    assert me["items"] == []
    assert me["empty_reason"] == "no_scheduled_items"


def test_only_recorded_misses_get_scheduled(
    client: TestClient, test_user: dict[str, str]
) -> None:
    headers = _auth(test_user)
    questions = _dbms_questions(2)
    # Wrong answer → notebook miss → schedule
    started = _start_mcq(client, test_user, [questions[0]["id"]])
    _submit_mcq(client, test_user, started["session_id"], [
        {"question_id": questions[0]["id"], "selected_option_ids": [_wrong_option(questions[0])]},
    ])
    # Correct answer → no miss for that item
    started_ok = _start_mcq(client, test_user, [questions[1]["id"]])
    _submit_mcq(client, test_user, started_ok["session_id"], [
        {"question_id": questions[1]["id"], "selected_option_ids": [_right_option(questions[1])]},
    ])

    sync = client.post("/learning/reviews/sync", headers=headers)
    assert sync.status_code == 200, sync.text
    due = client.get("/learning/reviews/due", headers=headers).json()
    ids = {i["item_id"] for i in due["items"]}
    assert questions[0]["id"] in ids
    assert questions[1]["id"] not in ids
    item = next(i for i in due["items"] if i["item_id"] == questions[0]["id"])
    assert item["is_due"] is True
    assert item["interval_days"] == 1
    assert item["originating_assisted"] is False
    _assert_no_private(json.dumps(due))


def test_review_outcomes_do_not_change_measured_aggregates(
    client: TestClient, test_user: dict[str, str]
) -> None:
    headers = _auth(test_user)
    question = _dbms_questions(1)[0]
    started = _start_mcq(client, test_user, [question["id"]])
    _submit_mcq(client, test_user, started["session_id"], [
        {"question_id": question["id"], "selected_option_ids": [_wrong_option(question)]},
    ])
    client.post("/learning/reviews/sync", headers=headers)

    before_mastery = client.get("/mastery/me", headers=headers).json()
    before_progress = client.get("/dashboard/progress", headers=headers).json()
    before_gap = client.get("/gap-analysis/me/tcs_swe", headers=headers)
    before_gap_body = before_gap.json() if before_gap.status_code == 200 else before_gap.text

    review = client.post("/learning/reviews/start", json={"max_items": 1}, headers=headers)
    assert review.status_code == 200, review.text
    assert review.json()["purpose"] == "spaced_review"
    sid = review.json()["session_id"]
    # Answer correctly in the review session
    _submit_mcq(client, test_user, sid, [
        {"question_id": question["id"], "selected_option_ids": [_right_option(question)]},
    ])

    after_mastery = client.get("/mastery/me", headers=headers).json()
    after_progress = client.get("/dashboard/progress", headers=headers).json()
    after_gap = client.get("/gap-analysis/me/tcs_swe", headers=headers)
    after_gap_body = after_gap.json() if after_gap.status_code == 200 else after_gap.text

    assert after_mastery["details"] == before_mastery["details"]
    assert after_mastery.get("assistance") == before_mastery.get("assistance")
    assert after_progress["readiness"] == before_progress["readiness"]
    assert after_gap_body == before_gap_body

    me = client.get("/learning/reviews/me", headers=headers).json()
    sched = next(i for i in me["items"] if i["item_id"] == question["id"])
    assert sched["last_outcome"] == "correct"
    assert sched["interval_days"] == 3
    assert sched["review_count"] == 1
    assert sched["is_due"] is False


def test_incorrect_review_resets_interval(
    client: TestClient, test_user: dict[str, str]
) -> None:
    headers = _auth(test_user)
    question = _dbms_questions(1)[0]
    started = _start_mcq(client, test_user, [question["id"]])
    _submit_mcq(client, test_user, started["session_id"], [
        {"question_id": question["id"], "selected_option_ids": [_wrong_option(question)]},
    ])
    client.post("/learning/reviews/sync", headers=headers)

    # Force interval up so an incorrect reset is observable
    db = get_database()
    row = db["review_schedules"].find_one({
        "user_id": test_user["id"], "item_id": question["id"],
    })
    db["review_schedules"].update_one(
        {"id": row["id"]},
        {"$set": {
            "interval_index": 2,
            "interval_days": 7,
            "due_at": datetime.now(timezone.utc) - timedelta(minutes=1),
        }},
    )

    review = client.post("/learning/reviews/start", json={"max_items": 1}, headers=headers)
    sid = review.json()["session_id"]
    _submit_mcq(client, test_user, sid, [
        {"question_id": question["id"], "selected_option_ids": [_wrong_option(question)]},
    ])
    me = client.get("/learning/reviews/me", headers=headers).json()
    sched = next(i for i in me["items"] if i["item_id"] == question["id"])
    assert sched["last_outcome"] == "incorrect"
    assert sched["interval_days"] == 1
    assert sched["interval_index"] == 0


def test_assisted_review_stays_out_of_unassisted_claims(
    client: TestClient, test_user: dict[str, str]
) -> None:
    headers = _auth(test_user)
    question = _dbms_questions(1)[0]
    started = _start_mcq(client, test_user, [question["id"]])
    _submit_mcq(client, test_user, started["session_id"], [
        {"question_id": question["id"], "selected_option_ids": [_wrong_option(question)]},
    ])
    client.post("/learning/reviews/sync", headers=headers)

    before = client.get("/mastery/me", headers=headers).json()["assistance"]
    review = client.post("/learning/reviews/start", json={"max_items": 1}, headers=headers)
    sid = review.json()["session_id"]
    hint = client.get(
        "/learning/hint",
        params={"item_type": "mcq", "item_id": question["id"]},
        headers=headers,
    )
    assert hint.status_code == 200, hint.text
    _submit_mcq(client, test_user, sid, [
        {"question_id": question["id"], "selected_option_ids": [_right_option(question)]},
    ])
    after = client.get("/mastery/me", headers=headers).json()["assistance"]
    assert after == before

    me = client.get("/learning/reviews/me", headers=headers).json()
    sched = next(i for i in me["items"] if i["item_id"] == question["id"])
    assert sched["last_review_assisted"] is True
    assert sched["last_outcome"] == "correct"


def test_coding_items_due_but_unavailable(
    client: TestClient, test_user: dict[str, str]
) -> None:
    headers = _auth(test_user)
    started = client.post("/session/start", json={
        "candidate_id": "",
        "skills": ["DSA"],
        "rounds_per_skill": 1,
        "round_type": "coding",
        "round_config": {"problem_id": "coding_two_sum", "duration_minutes": 30},
    }, headers=headers)
    assert started.status_code == 200, started.text
    submitted = client.post("/session/answer", json={
        "session_id": started.json()["session_id"],
        "round": 1,
        "answer_text": "def two_sum(nums, target):\n    return []\n",
    }, headers=headers)
    assert submitted.status_code == 503, submitted.text

    due = client.get("/learning/reviews/due", headers=headers).json()
    coding = [i for i in due["items"] if i["item_type"] == "coding"]
    assert coding, due
    assert coding[0]["status"] == "due_but_unavailable"
    assert coding[0]["review_available"] is False
    assert coding[0]["unavailable_reason"] == "execution_unavailable"
    assert due["unavailable_due_count"] >= 1
    assert due["note"]

    start = client.post("/learning/reviews/start", json={"max_items": 5}, headers=headers)
    assert start.status_code == 409, start.text
    assert "unavailable" in start.json()["detail"].lower()


def test_ownership_isolates_schedule_state(
    client: TestClient, test_user: dict[str, str], second_user: dict[str, str]
) -> None:
    headers = _auth(test_user)
    question = _dbms_questions(1)[0]
    started = _start_mcq(client, test_user, [question["id"]])
    _submit_mcq(client, test_user, started["session_id"], [
        {"question_id": question["id"], "selected_option_ids": [_wrong_option(question)]},
    ])
    client.post("/learning/reviews/sync", headers=headers)
    owner_due = client.get("/learning/reviews/due", headers=headers).json()
    assert any(i["item_id"] == question["id"] for i in owner_due["items"])

    other = _auth(second_user)
    other_due = client.get("/learning/reviews/due", headers=other).json()
    assert other_due["items"] == []
    assert other_due["empty_reason"] == "no_scheduled_items"
    other_me = client.get("/learning/reviews/me", headers=other).json()
    assert other_me["items"] == []
    start = client.post("/learning/reviews/start", json={"max_items": 1}, headers=other)
    assert start.status_code == 409


def test_review_surfaces_do_not_leak_private_material(
    client: TestClient, test_user: dict[str, str]
) -> None:
    headers = _auth(test_user)
    question = _dbms_questions(1)[0]
    started = _start_mcq(client, test_user, [question["id"]])
    _submit_mcq(client, test_user, started["session_id"], [
        {"question_id": question["id"], "selected_option_ids": [_wrong_option(question)]},
    ])
    for path, method in (
        ("/learning/reviews/sync", "post"),
        ("/learning/reviews/due", "get"),
        ("/learning/reviews/me", "get"),
    ):
        resp = getattr(client, method)(path, headers=headers)
        assert resp.status_code == 200, resp.text
        _assert_no_private(resp.text)
    start = client.post("/learning/reviews/start", json={"max_items": 1}, headers=headers)
    assert start.status_code == 200, start.text
    _assert_no_private(start.text)
    # Session question_context must not expose keys
    assert "correct_option_ids" not in start.text


def test_spaced_review_session_does_not_seed_new_notebook_misses(
    client: TestClient, test_user: dict[str, str]
) -> None:
    headers = _auth(test_user)
    question = _dbms_questions(1)[0]
    started = _start_mcq(client, test_user, [question["id"]])
    _submit_mcq(client, test_user, started["session_id"], [
        {"question_id": question["id"], "selected_option_ids": [_wrong_option(question)]},
    ])
    before = client.get("/learning/notebook/me", headers=headers).json()
    before_count = before["counts"]["total"]

    review = client.post("/learning/reviews/start", json={"max_items": 1}, headers=headers)
    sid = review.json()["session_id"]
    _submit_mcq(client, test_user, sid, [
        {"question_id": question["id"], "selected_option_ids": [_wrong_option(question)]},
    ])
    after = client.get("/learning/notebook/me", headers=headers).json()
    assert after["counts"]["total"] == before_count
