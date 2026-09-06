"""Ticket E — guidance coach: lexicon + fallback plan, unrecognized excluded."""

from __future__ import annotations

import os
from datetime import datetime, timezone
from uuid import uuid4

from fastapi.testclient import TestClient

os.environ.setdefault("INTERVIV_USE_MEMORY_DB", "true")
os.environ.setdefault("JWT_SECRET_KEY", "test-secret-key-with-at-least-32-bytes!!")
# Force fallback (no OpenRouter) for deterministic tests
os.environ["OPENROUTER_API_KEY"] = ""
os.environ["OPENAI_API_KEY"] = ""
os.environ["QUESTION_LLM_PROVIDER"] = "openrouter"

from backend.auth.security import create_access_token, hash_password
from backend.db import get_database
from backend.main import app
from modules.guidance_coach import (
    build_coach_plan,
    cap_practice_skills,
    map_phrase_to_skills,
    set_llm_override,
)


def _make_user() -> dict[str, str]:
    db = get_database()
    user_id = str(uuid4())
    db["users"].insert_one(
        {
            "id": user_id,
            "email": f"coach-{user_id[:8]}@example.com",
            "name": "Coach User",
            "password_hash": hash_password("passw0rd123"),
            "created_at": datetime.now(timezone.utc),
            "last_active_at": datetime.now(timezone.utc),
        }
    )
    return {"id": user_id, "token": create_access_token(user_id)}


def test_fallback_maps_sql_react_and_links_practice_jobs() -> None:
    set_llm_override(None)
    user = _make_user()
    plan = build_coach_plan(
        jd_text=None,
        goal_text="backend intern SQL React Pune",
        user_id=user["id"],
        include_dashboard=True,
    )
    assert plan["mode"] == "fallback"
    assert plan["needs_clarification"] is False
    assert "SQL" in plan["recognized_skills"]
    assert "React" in plan["recognized_skills"]
    hrefs = [s["href"] for s in plan["steps"]]
    assert any(h.startswith("/practice") for h in hrefs)
    assert any(h.startswith("/jobs") for h in hrefs)
    for skill in plan["practice_preview"]["skills"]:
        assert "unrecognized" not in skill.lower()


def test_unrecognized_phrase_not_in_practice_preview() -> None:
    set_llm_override(lambda _text: ["SQL", "Quantum Telepathy Framework", "React"])
    try:
        user = _make_user()
        plan = build_coach_plan(
            jd_text="Looking for SQL React Quantum Telepathy Framework",
            goal_text=None,
            user_id=user["id"],
        )
        assert plan["mode"] == "llm"
        assert "SQL" in plan["recognized_skills"]
        assert "React" in plan["recognized_skills"]
        assert any("Quantum Telepathy" in u for u in plan["unrecognized"])
        assert "Quantum Telepathy Framework" not in plan["practice_preview"]["skills"]
        for s in plan["practice_preview"]["skills"]:
            assert s in {"SQL", "React"} or map_phrase_to_skills(s)
    finally:
        set_llm_override(None)


def test_start_practice_caps_at_five_skills() -> None:
    skills = ["Python", "SQL", "React", "Docker", "AWS", "Kubernetes", "Git"]
    capped = cap_practice_skills(skills)
    assert len(capped) == 5

    user = _make_user()
    client = TestClient(app)
    # Avoid real question generation noise — may still start if bank/fallback works
    resp = client.post(
        "/coach/start-practice",
        headers={"Authorization": f"Bearer {user['token']}"},
        json={"skills": skills},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body.get("session_id")
    assert len(body.get("skills") or []) <= 5


def test_coach_plan_api_auth_and_short_clarify() -> None:
    user = _make_user()
    client = TestClient(app)
    denied = client.post("/coach/plan", json={"goal_text": "backend intern SQL React Pune"})
    assert denied.status_code in {401, 403}

    short = client.post(
        "/coach/plan",
        headers={"Authorization": f"Bearer {user['token']}"},
        json={"goal_text": "hi"},
    )
    assert short.status_code == 200
    assert short.json()["needs_clarification"] is True

    ok = client.post(
        "/coach/plan",
        headers={"Authorization": f"Bearer {user['token']}"},
        json={"goal_text": "backend intern SQL React Pune"},
    )
    assert ok.status_code == 200
    data = ok.json()
    assert "SQL" in data["recognized_skills"]
    assert any(s["href"].startswith("/practice") for s in data["steps"])
