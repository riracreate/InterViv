"""Sentinel-based SQL leakage probes across every client-facing surface.

Seeds unmistakable private values into the stored SQL round and asserts they
never reach the candidate on any surface:

- start, resume/fetch, submit, SQL preview, dashboard, post-completion
  review, next-round response.

Also asserts private field names (``reference_query``, hidden ``seed_data``,
``expected_rows``/``expected_row_count``, hidden-case descriptions, internal
hidden-case IDs) never appear. SQL reference queries and hidden cases remain
permanently private; only aggregate scores and the visible sample may ship.
"""

from __future__ import annotations

from copy import deepcopy
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
from backend.db.phase2_content_bank import PHASE2_SQL_BANK
from backend.main import app

REF_SENTINEL = "SECRET_REFERENCE_QUERY_SENTINEL"
HIDDEN_SENTINEL = "SECRET_HIDDEN_CASE_SENTINEL"
ROWS_SENTINEL = "SECRET_EXPECTED_ROWS_SENTINEL"

PRIVATE_FIELD_NAMES = (
    "reference_query",
    "expected_rows",
    "expected_row_count",
    "hidden_cases",
)


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


def _start_sql_session(client: TestClient, headers: dict[str, str]) -> dict:
    resp = client.post(
        "/session/start",
        json={
            "candidate_id": "",
            "skills": ["DBMS"],
            "rounds_per_skill": 1,
            "round_type": "sql",
            "round_config": {"problem_id": "sql_prob_026", "duration_minutes": 25},
        },
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    return resp.json()


def _inject_sentinels(q_ctx: dict) -> None:
    """Seed every private SQL field before production creates the response."""
    q_ctx["reference_query"] = f"SELECT '{REF_SENTINEL}' AS sentinel_col"
    for case in q_ctx["cases"]:
        if case.get("case_type") != "visible_sample":
            case["description"] = HIDDEN_SENTINEL
            case["seed_data"] = (
                (case.get("seed_data") or "")
                + f"\n-- {HIDDEN_SENTINEL}\n"
            )
            case["expected_rows"] = [[ROWS_SENTINEL]]
            case["expected_row_count"] = ROWS_SENTINEL
            case["internal_case_id"] = "hidden-internal-999"


def _seed_sentinels_before_start(monkeypatch: pytest.MonkeyPatch) -> None:
    """Patch the production bank so Start persists and sanitizes seeded data."""
    from backend.db import phase2_content_bank

    seeded_bank = deepcopy(PHASE2_SQL_BANK)
    problem = next(p for p in seeded_bank if p["id"] == "sql_prob_026")
    _inject_sentinels(problem)
    monkeypatch.setattr(phase2_content_bank, "PHASE2_SQL_BANK", seeded_bank)


def _assert_no_leak(payload: object, surface: str) -> None:
    blob = json.dumps(payload, default=str)
    for sentinel in (REF_SENTINEL, HIDDEN_SENTINEL, ROWS_SENTINEL):
        assert sentinel not in blob, f"{surface} leaked {sentinel}"
    for field in PRIVATE_FIELD_NAMES:
        assert f'"{field}"' not in blob, f"{surface} exposed private field {field}"
    assert "internal_case_id" not in blob, f"{surface} exposed internal case IDs"


def _assert_stored_sentinels(session_id: str) -> None:
    """Prove the stored round was seeded before a response is leakage-checked."""
    db = get_database()
    round_doc = db["sessions"].find_one({"session_id": session_id})["rounds"][0]
    blob = json.dumps(round_doc["question_context"], default=str)
    for sentinel in (REF_SENTINEL, HIDDEN_SENTINEL, ROWS_SENTINEL):
        assert sentinel in blob, f"stored round missing {sentinel}"


def test_sql_start_response_has_zero_private_data(monkeypatch: pytest.MonkeyPatch) -> None:
    client = TestClient(app)
    user = _make_user("leak-start")
    headers = {"Authorization": f"Bearer {user['token']}"}

    _seed_sentinels_before_start(monkeypatch)
    started = _start_sql_session(client, headers)
    _assert_stored_sentinels(started["session_id"])
    _assert_no_leak(started, "start")

    # The raw hidden seeds in the DB must not be echoable from the start payload.
    db = get_database()
    raw = db["sessions"].find_one({"session_id": started["session_id"]})["rounds"][0]
    hidden_seeds = [
        c["seed_data"]
        for c in raw["question_context"]["cases"]
        if c.get("case_type") != "visible_sample"
    ]
    assert hidden_seeds
    blob = json.dumps(started, default=str)
    for seed in hidden_seeds:
        first_insert = [ln.strip() for ln in seed.splitlines() if "INSERT" in ln][0]
        assert first_insert not in blob


def test_sql_start_probe_fails_closed_on_sentinel() -> None:
    leaked_start = {"question_context": {"reference_query": REF_SENTINEL}}
    with pytest.raises(AssertionError, match=f"start leaked {REF_SENTINEL}"):
        _assert_no_leak(leaked_start, "start")


def test_sql_resume_submit_preview_surfaces_have_zero_leakage(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = TestClient(app)
    user = _make_user("leak-surfaces")
    headers = {"Authorization": f"Bearer {user['token']}"}

    _seed_sentinels_before_start(monkeypatch)
    started = _start_sql_session(client, headers)
    session_id = started["session_id"]
    _assert_stored_sentinels(session_id)

    # 2. Resume / fetch
    resume = client.get(f"/session/{session_id}", headers=headers)
    assert resume.status_code == 200, resume.text
    _assert_no_leak(resume.json(), "resume")

    # 4. SQL preview (runs against the visible sample only)
    preview = client.post(
        "/session/sql/run",
        json={"session_id": session_id, "round": 1, "query": "SELECT 1 AS one;"},
        headers=headers,
    )
    assert preview.status_code == 200, preview.text
    _assert_no_leak(preview.json(), "preview")

    # 3. Submit (ground truth is the sentinel constant; only leakage is asserted)
    bank_ref = next(p for p in PHASE2_SQL_BANK if p["id"] == "sql_prob_026")["reference_query"]
    submit = client.post(
        "/session/answer",
        json={"session_id": session_id, "round": 1, "answer_text": bank_ref},
        headers=headers,
    )
    assert submit.status_code == 200, submit.text
    submit_body = submit.json()
    _assert_no_leak(submit_body, "submit")

    # 7. Next-round response fields carry no private data
    next_fields = {
        k: submit_body.get(k)
        for k in ("next_question", "next_round_type", "next_difficulty", "next_skill")
    }
    _assert_no_leak(next_fields, "next-round")

    # 5. Dashboard after submit
    dash = client.get(f"/dashboard/{session_id}", headers=headers)
    assert dash.status_code == 200, dash.text
    _assert_no_leak(dash.json(), "dashboard")

    # 6. Post-completion review (single-round session is completed after submit)
    review = client.get(f"/session/{session_id}", headers=headers)
    assert review.status_code == 200, review.text
    assert review.json()["status"] == "completed"
    _assert_no_leak(review.json(), "post-completion-review")
