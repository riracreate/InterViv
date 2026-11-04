"""Phase G honesty coverage: scoring-mode persistence and F-phase regressions.

These tests must fail if F.0/F.1 behavior is reverted. Protected scorers are
not modified; mode recording is disclosure-only.
"""

from __future__ import annotations

import os
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

os.environ.setdefault("JWT_SECRET_KEY", "test-secret-key-with-at-least-32-bytes!!")
os.environ["OPENAI_API_KEY"] = ""
os.environ["OPENROUTER_API_KEY"] = ""

from backend.auth.security import create_access_token, hash_password
from backend.db import get_database
from backend.evidence_kind import (
    SCORING_MODE_DEGRADED,
    SCORING_MODE_FULL,
    SCORING_MODE_SELF_REPORTED,
    SCORING_MODE_UNKNOWN,
    scoring_mode_at_write,
    scoring_mode_for_round,
)
from backend.main import app
from backend.db.phase_e_system_design_bank import SYSTEM_DESIGN_RUBRIC
from modules.skill_graph import StudentSkillGraph
from tests.alembic_helpers import parent_revision


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


def _user(email_prefix: str = "g") -> dict[str, str]:
    user_id = str(uuid4())
    get_database()["users"].insert_one({
        "id": user_id,
        "email": f"{email_prefix}-{user_id[:8]}@example.local",
        "name": "Phase G",
        "password_hash": hash_password("PhaseG123"),
        "role": "candidate",
    })
    return {"id": user_id, "token": create_access_token(user_id)}


def _headers(user: dict[str, str]) -> dict[str, str]:
    return {"Authorization": f"Bearer {user['token']}"}


def _full_ratings() -> dict[str, int]:
    return {c["id"]: 4 for c in SYSTEM_DESIGN_RUBRIC}


def test_parent_revision_convention_is_absolute() -> None:
    assert parent_revision("20260907_0006") == "20260907_0005"
    assert parent_revision("20260907_0007") == "20260907_0006"


def test_health_exposes_scoring_mode(client: TestClient) -> None:
    body = client.get("/health").json()
    scoring = body["scoring"]
    assert scoring["mode"] in {SCORING_MODE_FULL, SCORING_MODE_DEGRADED}
    assert "semantic_scoring_available" in scoring
    source = body["question_source"]
    assert source["configured_mode"] in {"llm", "csv", "llm_csv_fallback"}
    assert source["effective_mode"] in {
        "llm",
        "csv",
        "llm_csv_fallback",
        "csv_fallback",
        "llm_gated_off",
    }
    assert "llm_live_fetch" in source
    assert "outbound_allowed" in source


def test_scoring_mode_unknown_for_legacy_rows() -> None:
    assert scoring_mode_for_round({"final_score": 50}) == SCORING_MODE_UNKNOWN
    assert scoring_mode_for_round({
        "scoring_mode": SCORING_MODE_DEGRADED,
    }) == SCORING_MODE_DEGRADED


def test_scoring_mode_persisted_on_measured_attempt(client: TestClient) -> None:
    user = _user("mode")
    headers = _headers(user)
    started = client.post(
        "/session/start",
        headers=headers,
        json={
            "skills": ["DBMS"],
            "rounds_per_skill": 1,
            "round_type": "technical_short_answer",
        },
    )
    assert started.status_code == 200, started.text
    sid = started.json()["session_id"]
    submit = client.post(
        "/session/answer",
        headers=headers,
        json={
            "session_id": sid,
            "round": 1,
            "answer_text": (
                "ACID means atomicity, consistency, isolation, and durability. "
                "Transactions either commit fully or roll back."
            ),
        },
    )
    assert submit.status_code == 200, submit.text
    mode = submit.json()["scoring_mode"]
    assert mode in {SCORING_MODE_FULL, SCORING_MODE_DEGRADED}
    assert submit.json()["scoring_mode_label"] == mode
    stored = get_database()["sessions"].find_one({"session_id": sid})
    round_doc = stored["rounds"][0]
    assert round_doc.get("scoring_mode") == mode or (
        (round_doc.get("scoring_breakdown") or {}).get("scoring_mode") == mode
    )
    dash = client.get(f"/dashboard/{sid}", headers=headers).json()
    assert dash["rounds"][0]["scoring_mode"] == mode
    assert dash["rounds"][0]["scoring_mode_label"]
    progress = client.get("/dashboard/progress", headers=headers).json()
    matched = [
        row for row in progress.get("history") or []
        if row.get("session_id") == sid
    ]
    assert matched
    assert mode in (matched[0].get("scoring_modes") or [])


def test_scoring_mode_degraded_when_semantic_disabled(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("DISABLE_SEMANTIC_SCORING", "1")
    # Force sticky unavailable path for this process.
    import modules.semantic_scorer as ss

    monkeypatch.setattr(ss, "_model", None)
    monkeypatch.setattr(ss, "_model_load_error", False)
    monkeypatch.setattr(ss, "_model_load_error_reason", None)
    monkeypatch.setattr(ss, "_warning_logged", False)

    user = _user("deg")
    headers = _headers(user)
    started = client.post(
        "/session/start",
        headers=headers,
        json={
            "skills": ["DBMS"],
            "rounds_per_skill": 1,
            "round_type": "technical_short_answer",
        },
    )
    assert started.status_code == 200, started.text
    submit = client.post(
        "/session/answer",
        headers=headers,
        json={
            "session_id": started.json()["session_id"],
            "round": 1,
            "answer_text": "Transactions use ACID properties for reliability.",
        },
    )
    assert submit.status_code == 200, submit.text
    assert submit.json()["scoring_mode"] == SCORING_MODE_DEGRADED
    assert submit.json()["semantic_scoring_available"] is False


def test_self_assessment_excluded_from_gap_readiness_retry_notebook(
    client: TestClient,
) -> None:
    user = _user("self")
    headers = _headers(user)
    StudentSkillGraph(user["id"]).initialize_from_resume(["System Design", "DBMS"])
    # Set a target so readiness/gap endpoints have a role.
    get_database()["users"].update_one(
        {"id": user["id"]},
        {"$set": {"target_company_id": "tcs", "target_role_id": "tcs_swe"}},
    )
    get_database()["target_contexts"].update_one(
        {"user_id": user["id"]},
        {"$set": {
            "user_id": user["id"],
            "company_id": "tcs",
            "role_id": "tcs_swe",
            "jd_source": "role",
        }},
        upsert=True,
    )
    started = client.post(
        "/session/start",
        headers=headers,
        json={
            "blocks": [{
                "round_type": "system_design",
                "category": "system_design",
                "count": 1,
                "problem_ids": ["sd_url_shortener"],
            }]
        },
    )
    assert started.status_code == 200, started.text
    submit = client.post(
        "/session/answer",
        headers=headers,
        json={
            "session_id": started.json()["session_id"],
            "round": 1,
            "answer_text": 'Requirements: the service is read-heavy with about 100 reads per write and links expire after a TTL. API: POST /links creates a short code and GET /{code} returns a 302 redirect. Store codes in a key-value store, use base62 encoding of a unique counter, and cache hot links in Redis because redirects must be fast. Shard by code and keep replicas for availability.',
            "rubric_ratings": _full_ratings(),
        },
    )
    assert submit.status_code == 200, submit.text
    # New system-design rounds are practice estimates; same exclusions apply.
    assert submit.json()["scoring_mode"] == "practice_estimate"
    assert submit.json()["evidence_kind"] == "practice_review"

    sid = started.json()["session_id"]
    progress = client.get("/dashboard/progress", headers=headers).json()
    # Self-reported-only history must not produce a measured average.
    for row in progress.get("history") or []:
        if row.get("session_id") == sid:
            assert row.get("average_score") is None
            assert "practice_estimate" in (row.get("scoring_modes") or [])

    # Session report must load even when feedback is a plain string (SD path).
    dash = client.get(f"/dashboard/{sid}", headers=headers)
    assert dash.status_code == 200, dash.text
    body = dash.json()
    assert body["rounds"][0]["scoring_mode"] == "practice_estimate"
    assert body["rounds"][0]["scoring_mode_label"] == "Practice estimate (not measured)"
    assert (body.get("averages") or {}).get("final_score") is None

    notebook = client.get("/learning/notebook/me", headers=headers).json()
    assert all(
        e.get("round_type") != "system_design"
        for e in notebook.get("entries") or []
    )
    # No measured misses → retry-set generation refuses rather than inventing
    # system_design self-assessment items.
    retry = client.post(
        "/learning/retry-sets",
        headers=headers,
        json={"name": "from-self", "source": "missed-topics"},
    )
    assert retry.status_code == 409, retry.text
    assert "missed" in retry.json()["detail"].lower()


def test_coding_dsa_skills_resolves_without_problem_id_all_entry_paths(
    client: TestClient,
) -> None:
    """Regression for F.1: skills=['DSA'] must not filter the coding bank empty.

    Exercises the same expansion path the browser Standalone / Builder use
    (blocks with skills DSA, no problem_ids).
    """
    user = _user("dsa")
    headers = _headers(user)

    # 1) Standalone / builder-shaped blocks payload
    standalone = client.post(
        "/session/start",
        headers=headers,
        json={
            "blocks": [{
                "id": "b-coding",
                "category": "coding",
                "round_type": "coding",
                "skills": ["DSA"],
                "count": 1,
                "duration_minutes": 30,
            }]
        },
    )
    assert standalone.status_code == 200, standalone.text
    assert standalone.json()["round_type"] == "coding"
    assert standalone.json()["question_context"]["problem_id"]

    # 2) Builder with repeated coding block (still no problem_ids)
    builder = client.post(
        "/session/start",
        headers=headers,
        json={
            "blocks": [
                {
                    "id": "c1",
                    "category": "coding",
                    "round_type": "coding",
                    "skills": ["DSA"],
                    "count": 1,
                    "duration_minutes": 30,
                },
                {
                    "id": "c2",
                    "category": "coding",
                    "round_type": "coding",
                    "skills": ["DSA"],
                    "count": 1,
                    "duration_minutes": 30,
                },
            ]
        },
    )
    assert builder.status_code == 200, builder.text
    plan = builder.json().get("block_plan") or builder.json().get("rounds") or []
    assert plan

    # 3) /problems multi-select practice set (explicit problem_ids)
    problems = client.get("/problems", headers=headers).json()["problems"]
    assert len(problems) >= 2
    ids = [problems[0]["id"], problems[1]["id"]]
    multi = client.post(
        "/session/start",
        headers=headers,
        json={
            "blocks": [{
                "category": "coding",
                "round_type": "coding",
                "skills": ["DSA"],
                "problem_ids": ids,
                "count": len(ids),
                "duration_minutes": 45,
            }]
        },
    )
    assert multi.status_code == 200, multi.text
    assert multi.json()["question_context"]["problem_id"] in ids


def test_scoring_mode_at_write_helpers() -> None:
    assert scoring_mode_at_write(self_reported=True) == SCORING_MODE_SELF_REPORTED
    assert scoring_mode_at_write(
        self_reported=False,
        scoring_breakdown={"semantic_scoring_available": False},
    ) == SCORING_MODE_DEGRADED
    assert scoring_mode_at_write(
        self_reported=False,
        scoring_breakdown={"semantic_scoring_available": True},
    ) == SCORING_MODE_FULL
