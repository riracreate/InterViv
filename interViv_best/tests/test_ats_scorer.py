"""Ticket C — ATS scorer + API contract tests."""

from __future__ import annotations

import os
from datetime import datetime, timezone
from uuid import uuid4

from fastapi.testclient import TestClient

os.environ.setdefault("INTERVIV_USE_MEMORY_DB", "true")
os.environ.setdefault("JWT_SECRET_KEY", "test-secret-key-with-at-least-32-bytes!!")

from backend.auth.security import create_access_token, hash_password
from backend.db import get_database
from backend.main import app
from modules.ats_scorer import must_have_from_role, score_ats
from modules.ats_store import reset_memory_store
from modules.resume_parser import analyze_resume_text


FIXTURE_GOOD = """
Jane Doe
jane@example.com | +1-555-0100

SKILLS
Python, DSA, OOP, DBMS, SQL, Operating Systems, Docker

EXPERIENCE
Software Engineer — Acme Corp
- Built APIs serving 2M requests/day
- Designed indexing strategy that reduced query latency 40%
- Implemented OOP services with measurable SLOs

EDUCATION
B.S. Computer Science
"""

FIXTURE_NO_KEYWORDS = """
Alex Applicant
alex@example.com

SKILLS
Microsoft Word, Excel, PowerPoint

EXPERIENCE
Office Assistant
- Helped with filing and scheduling
- Wrote emails for the team

EDUCATION
B.A. History
"""


def _make_user() -> dict[str, str]:
    db = get_database()
    user_id = str(uuid4())
    db["users"].insert_one(
        {
            "id": user_id,
            "email": f"ats-{user_id[:8]}@example.com",
            "name": "ATS User",
            "password_hash": hash_password("passw0rd123"),
            "created_at": datetime.now(timezone.utc),
            "last_active_at": datetime.now(timezone.utc),
        }
    )
    return {"id": user_id, "token": create_access_token(user_id)}


def _insert_candidate(user_id: str, text: str) -> str:
    analysis = analyze_resume_text(text)
    candidate_id = str(uuid4())
    get_database()["candidates"].insert_one(
        {
            "candidate_id": candidate_id,
            "user_id": user_id,
            "resume_skills": analysis["skills"],
            "ats_snapshot": analysis,
            "elo_ratings": {},
            "session_history": [],
        }
    )
    return candidate_id


def test_fixture_resume_vs_role_score_in_documented_band() -> None:
    """Single-column fixture with sections + known skills vs tcs_swe → total in [55, 95]."""
    analysis = analyze_resume_text(FIXTURE_GOOD)
    assert analysis["extract_ok"] is True
    assert analysis["layout_checked"] is False
    assert analysis["sections"]["skills"] is True
    assert analysis["sections"]["experience"] is True
    must = must_have_from_role("tcs_swe")
    assert must  # DSA OOP DBMS OS HR
    result = score_ats(analysis=analysis, must_have=must, role_id="tcs_swe")
    assert "extract_layout_unchecked" in result["flags"]
    # Documented band for this fixture
    assert 55 <= result["total"] <= 95, result
    assert result["components"]["keyword_coverage"] >= 40
    assert result["components"]["parse_health"] == 100.0


def test_missing_all_must_have_skills_near_zero_keyword() -> None:
    analysis = analyze_resume_text(FIXTURE_NO_KEYWORDS)
    must = must_have_from_role("tcs_swe")
    result = score_ats(analysis=analysis, must_have=must, role_id="tcs_swe")
    assert result["components"]["keyword_coverage"] <= 5
    assert result["missing_skills"]
    assert "no_must_have_overlap" in result["flags"] or result["components"]["keyword_coverage"] == 0


def test_layout_not_detected_uses_unchecked_flag_not_fake_penalty() -> None:
    analysis = analyze_resume_text(FIXTURE_GOOD)
    # Parser cannot detect two-column layout — we refuse to invent ParseHealth penalties.
    assert analysis["layout_checked"] is False
    result = score_ats(analysis=analysis, must_have=["DSA"], role_id=None)
    assert result["components"]["parse_health"] == 100.0
    assert "extract_layout_unchecked" in result["flags"]


def test_post_ats_score_contract() -> None:
    reset_memory_store()
    client = TestClient(app)
    user = _make_user()
    headers = {"Authorization": f"Bearer {user['token']}"}
    candidate_id = _insert_candidate(user["id"], FIXTURE_GOOD)

    resp = client.post(
        "/ats/score",
        headers=headers,
        json={"candidate_id": candidate_id, "role_id": "tcs_swe"},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert "total" in body
    assert set(body["components"]) == {
        "parse_health",
        "section_complete",
        "keyword_coverage",
        "content_heuristics",
    }
    assert isinstance(body["flags"], list)
    assert isinstance(body["missing_skills"], list)
    assert body["run_id"] is not None

    runs = client.get("/ats/runs", headers=headers)
    assert runs.status_code == 200
    assert runs.json()["count"] >= 1


def test_ats_requires_xor_role_or_jd() -> None:
    reset_memory_store()
    client = TestClient(app)
    user = _make_user()
    headers = {"Authorization": f"Bearer {user['token']}"}
    candidate_id = _insert_candidate(user["id"], FIXTURE_GOOD)
    both = client.post(
        "/ats/score",
        headers=headers,
        json={
            "candidate_id": candidate_id,
            "role_id": "tcs_swe",
            "jd_text": "Need DSA and DBMS",
        },
    )
    assert both.status_code == 422
    neither = client.post(
        "/ats/score",
        headers=headers,
        json={"candidate_id": candidate_id},
    )
    assert neither.status_code == 422


def test_jd_path_uses_lexicon_intersection() -> None:
    reset_memory_store()
    client = TestClient(app)
    user = _make_user()
    headers = {"Authorization": f"Bearer {user['token']}"}
    candidate_id = _insert_candidate(user["id"], FIXTURE_GOOD)
    resp = client.post(
        "/ats/score",
        headers=headers,
        json={
            "candidate_id": candidate_id,
            "jd_text": "We need strong DSA, Python, and DBMS experience. No LLM.",
        },
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["jd_hash"]
    assert "DSA" in body["present_skills"] or "Python" in body["present_skills"]
