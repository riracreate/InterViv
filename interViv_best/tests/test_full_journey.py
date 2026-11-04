"""Overhaul Phase 7: the whole candidate journey through the real API.

Onboarding → Diagnosis & Plan → Practice → Interview → Progress on a
freshly migrated SQLite store, with the trusted local runner enabled (no
Docker), real resume parsing, and a refresh plus a simulated restart in the
middle. Every configured round must submit, show its review, open the next
round only on activation, survive a refresh, and complete.
"""

from __future__ import annotations

import os
from pathlib import Path
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient

os.environ.setdefault("JWT_SECRET_KEY", "test-secret-key-with-at-least-32-bytes!!")

ROOT = Path(__file__).resolve().parents[1]

TWO_SUM = (
    "def two_sum(nums, target):\n"
    "    seen = {}\n"
    "    for i, x in enumerate(nums):\n"
    "        if target - x in seen:\n"
    "            return [seen[target - x], i]\n"
    "        seen[x] = i\n"
    "    return []\n"
)
DESIGN_NOTES = (
    "Requirements: allow 100 requests per minute per API key and return 429 with a Retry-After header. "
    "Use a token bucket in Redis updated by an atomic Lua script, with a TTL on each key. "
    "Race conditions are avoided by the atomic update; keys are partitioned with consistent hashing. "
    "If Redis is down we fail open because availability matters more than accuracy. "
    "Trade-off: token bucket versus sliding window, which is more accurate but uses more memory."
)
RESUME_LINES = [
    "Asha Rao", "Education", "B.Tech Computer Science, 2025", "Experience",
    "Software Intern at Example Corp", "- Built REST APIs in Python with PostgreSQL and Redis",
    "- Wrote SQL queries and optimized indexes", "Projects",
    "- Implemented a graph search tool using DSA and OOP in Java", "Skills",
    "Python, SQL, Java, DSA, OOP, DBMS, Git",
]


def _text_pdf(lines: list[str]) -> bytes:
    """A minimal, real text PDF (Helvetica) the resume parser can read."""
    content = "BT /F1 11 Tf 14 TL 72 760 Td " + " ".join(
        f"({line}) Tj T*" for line in lines) + " ET"
    objects = [
        "<< /Type /Catalog /Pages 2 0 R >>",
        "<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        "<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R "
        "/Resources << /Font << /F1 5 0 R >> >> >>",
        f"<< /Length {len(content)} >>\nstream\n{content}\nendstream",
        "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    out, offsets = b"%PDF-1.4\n", []
    for number, body in enumerate(objects, 1):
        offsets.append(len(out))
        out += f"{number} 0 obj\n{body}\nendobj\n".encode()
    xref = len(out)
    out += f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n".encode()
    out += b"".join(f"{o:010d} 00000 n \n".encode() for o in offsets)
    out += f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode()
    return out


def _clear_caches() -> None:
    from backend import config
    from backend.db import sqlalchemy_store

    config.get_settings.cache_clear()
    sqlalchemy_store.get_engine.cache_clear()
    sqlalchemy_store._sessionmaker.cache_clear()
    sqlalchemy_store.get_sqlalchemy_database.cache_clear()


@pytest.fixture
def journey_env(tmp_path, monkeypatch):
    url = f"sqlite:///{tmp_path / 'journey.sqlite3'}"
    for key, value in {
        "DATABASE_URL": url, "INTERVIV_USE_MEMORY_DB": "false", "ENVIRONMENT": "development",
        "LLM_LIVE_FETCH": "0", "JOBS_LIVE_FETCH": "0", "QUESTION_GENERATION_MODE": "csv",
        "INTERVIV_TRUSTED_LOCAL_EXECUTION": "1", "INTERVIV_BIND_HOST": "127.0.0.1",
    }.items():
        monkeypatch.setenv(key, value)
    monkeypatch.delenv("CODING_EXECUTOR_URL", raising=False)
    _clear_caches()
    cfg = Config()  # programmatic: no logging.fileConfig side effects
    cfg.set_main_option("script_location", str(ROOT / "alembic"))
    cfg.set_main_option("sqlalchemy.url", url)
    command.upgrade(cfg, "head")
    _clear_caches()
    from backend.main import app

    # Context manager runs startup (company graph seeding), like the real app.
    with TestClient(app) as client:
        yield client
    _clear_caches()


def _answer_for(round_doc: dict, db) -> dict:
    kind = round_doc["round_type"]
    number = round_doc["round"]
    if kind == "mcq":
        questions = round_doc["question_context"]["questions"]
        return {"answers": [{"question_id": q["id"], "selected_option_ids": [q["options"][0]["id"]]}
                            for q in questions]}
    if kind == "sql":
        stored = next(r for r in db["sessions"].find_one({"session_id": round_doc["session_id"]})["rounds"]
                      if r["round"] == number)
        return {"answer_text": stored["question_context"]["reference_query"]}
    if kind == "coding":
        return {"answer_text": TWO_SUM, "language": "python"}
    if kind == "ml_primitives":
        return {"answer_text": (ROOT / "ml_primitives/minmax_normalize/v1/reference.py").read_text()}
    if kind == "system_design":
        return {"answer_text": DESIGN_NOTES,
                "rubric_ratings": {"requirements": 4, "api_data": 4, "scale": 4, "tradeoffs": 3}}
    return {"answer_text": "An index keeps keys sorted so lookups avoid a full table scan, "
                           "at the cost of slower writes and extra storage."}


def test_complete_candidate_journey(journey_env):
    client = journey_env
    from backend.db import get_database

    # ── Onboarding ───────────────────────────────────────────────────────
    signup = client.post("/auth/signup", json={
        "email": f"journey-{uuid4().hex[:8]}@example.test", "password": "journey-pass-123", "name": "Asha"})
    assert signup.status_code in (200, 201), signup.text
    headers = {"Authorization": f"Bearer {signup.json()['access_token']}"}
    assert client.get("/auth/me", headers=headers).status_code == 200

    resume = client.post("/resume", headers=headers,
                         files={"file": ("resume.pdf", _text_pdf(RESUME_LINES), "application/pdf")})
    assert resume.status_code == 200, resume.text
    candidate_id = resume.json()["candidate_id"]
    assert {"Python", "SQL", "DSA"} <= set(resume.json()["skills"])

    companies = client.get("/companies", headers=headers).json()["companies"]
    company = next(c for c in companies if any(r["id"] == "amazon_sde_intern" for r in c["roles"]))
    target = client.patch("/auth/me/target", headers=headers,
                          json={"target_company_id": company["id"], "target_role_id": "amazon_sde_intern"})
    assert target.status_code == 200, target.text

    # ATS scoring reads the resume snapshot persisted in SQL (Phase 1).
    ats = client.post("/ats/score", headers=headers,
                      json={"candidate_id": candidate_id, "role_id": "amazon_sde_intern"})
    assert ats.status_code == 200, ats.text
    assert ats.json()["analysis_source"] == "snapshot"
    assert ats.json()["reupload_recommended"] is False

    # ── Diagnosis & plan ─────────────────────────────────────────────────
    gap = client.get("/gap-analysis/me/amazon_sde_intern", headers=headers)
    assert gap.status_code == 200, gap.text
    roadmap = client.get("/roadmap/me/amazon_sde_intern", headers=headers)
    assert roadmap.status_code == 200, roadmap.text
    conversation = client.post("/coach/conversations", headers=headers).json()["conversation"]
    coach = client.post(f"/coach/conversations/{conversation['conversation_id']}/messages", headers=headers,
                        json={"text": "Build my plan", "action": "create_plan", "action_payload": {"days": 14}})
    assert coach.status_code == 200, coach.text
    plan_skills = {t["skill"] for t in coach.json()["plan"]["tasks"]}
    assert plan_skills <= {"DSA", "OOP", "DBMS", "System Design", "HR"}  # role requirements reach the coach

    # ── Practice: one session with every round type ─────────────────────
    start = client.post("/session/start", headers=headers, json={"candidate_id": candidate_id, "blocks": [
        {"round_type": "technical_short_answer", "category": "interview", "skills": ["DBMS"], "count": 1},
        {"round_type": "mcq", "category": "oa", "skills": ["DBMS"], "count": 2, "duration_minutes": 10},
        {"round_type": "sql", "category": "sql", "count": 1, "duration_minutes": 15},
        {"round_type": "coding", "category": "coding", "problem_ids": ["coding_two_sum"], "duration_minutes": 30},
        {"round_type": "ml_primitives", "category": "ml_primitives",
         "problem_ids": ["minmax_normalize.v1"], "duration_minutes": 30},
        {"round_type": "system_design", "category": "system_design", "count": 1,
         "problem_ids": ["sd_rate_limiter"]},
    ]})
    assert start.status_code == 200, start.text
    session_id = start.json()["session_id"]
    total = start.json()["total_rounds"]
    assert total == 6

    # ── Interview: submit → review → activate, with refreshes ────────────
    seen_types = []
    for number in range(1, total + 1):
        view = client.get(f"/session/{session_id}", headers=headers).json()
        if number > 1:
            # Refresh during review: previous result kept, next prompt hidden.
            assert view["active_round"] is None
            assert view["review_round"] == number - 1
            assert len(view["round_history"]) == number - 1
            assert view["pending_round"]["round"] == number
            opened = client.post(f"/session/{session_id}/rounds/{number}/activate", headers=headers)
            assert opened.status_code == 200, opened.text
            again = client.post(f"/session/{session_id}/rounds/{number}/activate", headers=headers)
            assert again.json()["active_round"]["expires_at"] == opened.json()["active_round"]["expires_at"]
            view = client.get(f"/session/{session_id}", headers=headers).json()
        active = view["active_round"]
        assert active["round"] == number and active["status"] == "in_progress"
        seen_types.append(active["round_type"])

        payload = {"session_id": session_id, "round": number, **_answer_for({**active, "session_id": session_id},
                                                                           get_database())}
        result = client.post("/session/answer", headers=headers, json=payload)
        assert result.status_code == 200, (active["round_type"], result.text)
        body = result.json()
        assert body["next_question"] is None  # never revealed before activation
        if number < total:
            assert body["session_complete"] is False
            assert body["next_round"] == number + 1 and body["next_round_status"] == "ready"
        else:
            assert body["session_complete"] is True

        if number == 3:
            # Simulated restart: drop every cached engine/session and reload.
            _clear_caches()
            restored = client.get(f"/session/{session_id}", headers=headers).json()
            assert [r["round"] for r in restored["round_history"]] == [1, 2, 3]

    assert seen_types == ["technical_short_answer", "mcq", "sql", "coding", "ml_primitives", "system_design"]

    # ── Progress ─────────────────────────────────────────────────────────
    stored = get_database()["sessions"].find_one({"session_id": session_id})
    by_type = {r["round_type"]: r for r in stored["rounds"]}
    assert by_type["coding"]["final_score"] == 100.0
    assert by_type["ml_primitives"]["final_score"] == 100.0
    assert by_type["ml_primitives"]["evidence_kind"] == "measured"
    assert by_type["system_design"]["evidence_kind"] == "practice_review"
    assert by_type["coding"]["coding_exec_count"] >= 1  # persisted in SQL (Phase 1)
    assert all(r["final_score"] is not None for r in stored["rounds"])

    report = client.get(f"/dashboard/{session_id}", headers=headers)
    assert report.status_code == 200, report.text
    assert report.json()["coverage"]["scored_rounds"] == 6
    progress = client.get("/dashboard/progress", headers=headers).json()
    assert any(row["session_id"] == session_id for row in progress["history"])
    assert progress["resumable_session"] is None  # finished sessions are not resumable
