"""Ticket F — demo-path contract smoke (coach + ATS + jobs + round_plan)."""

from __future__ import annotations

import os
from datetime import datetime, timezone
from uuid import uuid4

from fastapi.testclient import TestClient

os.environ.setdefault("INTERVIV_USE_MEMORY_DB", "true")
os.environ.setdefault("JWT_SECRET_KEY", "test-secret-key-with-at-least-32-bytes!!")
os.environ["OPENROUTER_API_KEY"] = ""
os.environ["OPENAI_API_KEY"] = ""
os.environ["ADZUNA_APP_ID"] = ""
os.environ["ADZUNA_APP_KEY"] = ""

from backend.auth.security import create_access_token, hash_password
from backend.db import get_database
from backend.main import app
from modules.jobs_explorer import reset_memory_store
from modules.resume_parser import analyze_resume_text


FIXTURE_RESUME = """
Demo Student
demo@example.com

SKILLS
Python, SQL, React, DSA

EXPERIENCE
Intern — Backend APIs
- Shipped SQL migrations and React dashboards

EDUCATION
B.Tech Computer Science
"""


def _make_user() -> dict[str, str]:
    db = get_database()
    user_id = str(uuid4())
    db["users"].insert_one(
        {
            "id": user_id,
            "email": f"demo-{user_id[:8]}@example.com",
            "name": "Demo User",
            "password_hash": hash_password("passw0rd123"),
            "created_at": datetime.now(timezone.utc),
            "last_active_at": datetime.now(timezone.utc),
        }
    )
    analysis = analyze_resume_text(FIXTURE_RESUME)
    candidate_id = str(uuid4())
    db["candidates"].insert_one(
        {
            "candidate_id": candidate_id,
            "user_id": user_id,
            "resume_skills": analysis["skills"],
            "ats_snapshot": analysis,
            "resume_text": FIXTURE_RESUME,
        }
    )
    return {"id": user_id, "token": create_access_token(user_id), "candidate_id": candidate_id}


def test_demo_path_coach_ats_jobs_session_contracts() -> None:
    reset_memory_store()
    client = TestClient(app)
    user = _make_user()
    headers = {"Authorization": f"Bearer {user['token']}"}

    coach = client.post(
        "/coach/plan",
        headers=headers,
        json={"goal_text": "backend intern SQL React Pune"},
    )
    assert coach.status_code == 200, coach.text
    plan = coach.json()
    assert plan.get("mode") in {"fallback", "llm"}
    assert "SQL" in plan["recognized_skills"] or "React" in plan["recognized_skills"]
    hrefs = [s["href"] for s in plan.get("steps") or []]
    assert any(h.startswith("/practice") for h in hrefs)
    assert any(h.startswith("/jobs") for h in hrefs)

    ats = client.post(
        "/ats/score",
        headers=headers,
        json={"candidate_id": user["candidate_id"], "role_id": "tcs_swe"},
    )
    assert ats.status_code == 200, ats.text
    assert "total" in ats.json()

    jobs = client.get("/jobs?q=backend&where=Pune&page=1", headers=headers)
    assert jobs.status_code == 200, jobs.text
    body = jobs.json()
    assert "jobs" in body
    assert isinstance(body["jobs"], list)

    start = client.post(
        "/session/start",
        headers=headers,
        json={
            "skills": ["SQL", "React"],
            "round_plan": ["technical_short_answer", "mcq"],
            "round_type": "technical_short_answer",
            "rounds_per_skill": 1,
        },
    )
    assert start.status_code == 200, start.text
    session = start.json()
    assert session.get("session_id")
    assert session.get("round_plan") == ["technical_short_answer", "mcq"]
    assert session.get("total_rounds") == 2
