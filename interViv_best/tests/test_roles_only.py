"""ROLE_ONLY_TARGETS: role targets and role interviews, with the flag on and off.

Offline: isolated SQLite, no network, no model calls. With the flag off the
company target and every existing start path behave as before.
"""
from __future__ import annotations

import os
import re
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

os.environ.setdefault("INTERVIV_USE_MEMORY_DB", "true")
os.environ.setdefault("JWT_SECRET_KEY", "test-secret-key-with-at-least-32-bytes!!")
os.environ.setdefault("LLM_LIVE_FETCH", "0")
os.environ.setdefault("JOBS_LIVE_FETCH", "0")

from backend import config as app_config  # noqa: E402
from backend.auth.security import create_access_token, hash_password  # noqa: E402
from backend.db import get_database  # noqa: E402
from backend.db.sqlalchemy_store import (  # noqa: E402
    _sessionmaker,
    create_all_for_smoke,
    get_engine,
    get_sqlalchemy_database,
)
from backend.db.user_target import get_role_target, get_user_target  # noqa: E402
from backend.main import app  # noqa: E402
from modules.company_graph import get_company_graph  # noqa: E402
from modules.role_blueprints import load_blueprints  # noqa: E402
from modules.role_interview import (  # noqa: E402
    behavioural_question,
    core_practice_question,
    decode_role_target,
    encode_role_target,
    interview_slots,
    opener_question,
    scenario_question,
)

ROLE_IDS = [doc["id"] for doc in load_blueprints()]
ANSWER = "I would check the data first, explain the trade offs, and verify the result with a small test."


def _clear_caches() -> None:
    app_config.get_settings.cache_clear()
    get_engine.cache_clear()
    _sessionmaker.cache_clear()
    get_sqlalchemy_database.cache_clear()


@pytest.fixture
def sql_env(monkeypatch, tmp_path: Path):
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'roles.db'}")
    monkeypatch.setenv("INTERVIV_USE_MEMORY_DB", "false")
    monkeypatch.setenv("STAGED_INLINE_FOLLOW_UPS", "1")
    monkeypatch.setenv("REVIEWED_BUNDLES_ONLY", "false")
    monkeypatch.setenv("LLM_LIVE_FETCH", "0")
    monkeypatch.setenv("JOBS_LIVE_FETCH", "0")
    monkeypatch.delenv("ROLE_ONLY_TARGETS", raising=False)
    monkeypatch.delenv("ROLE_PRACTICE_ENABLED", raising=False)
    monkeypatch.setenv("FOLLOWUP_DECISIONS_AUDIT_PATH", str(tmp_path / "followups.jsonl"))
    monkeypatch.setenv("REJECTED_BUNDLES_AUDIT_PATH", str(tmp_path / "rejected.jsonl"))
    _clear_caches()
    create_all_for_smoke()
    from backend.db.company_seed import seed_company_graph

    seed_company_graph()
    try:
        yield get_database()
    finally:
        try:
            get_engine().dispose()
        except Exception:
            pass
        _clear_caches()


@pytest.fixture
def roles_on(sql_env, monkeypatch):
    monkeypatch.setenv("ROLE_ONLY_TARGETS", "1")
    return sql_env


def _user(db, name: str = "role") -> tuple[dict, dict[str, str]]:
    user_id = f"{name}-{uuid4().hex[:8]}"
    now = datetime.now(timezone.utc)
    doc = {
        "id": user_id, "name": "Role Candidate", "email": f"{user_id}@example.com",
        "password_hash": hash_password("TestPass123!"), "created_at": now, "last_active_at": now,
    }
    db["users"].insert_one(doc)
    return doc, {"Authorization": f"Bearer {create_access_token(user_id)}"}


def _company_target() -> tuple[str, str]:
    company = get_company_graph().list_companies()[0]
    return company.id, company.roles[0].id


def _company_names() -> list[str]:
    return [company.name for company in get_company_graph().list_companies()]


def _assert_no_company_names(text: str) -> None:
    for name in _company_names():
        assert not re.search(rf"\b{re.escape(name)}\b", text), f"{name!r} in {text!r}"


def _role_start(role_id: str, preset: str = "quick", **role) -> dict:
    return {
        "flow_version": "staged_v1", "preset": preset, "practice_mode": "coached_practice",
        "role_interview": {"role_id": role_id, "level": "junior", **role},
    }


def _walk_text_rounds(client: TestClient, headers: dict, session_id: str, limit: int = 10) -> list[dict]:
    """Answer text rounds in order until the session completes or reaches a practical round."""
    seen = []
    for _ in range(limit * 2):
        state = client.get(f"/session/{session_id}", headers=headers).json()
        if state["status"] == "completed":
            break
        current = state.get("active_round") or state.get("pending_round")
        if not current:
            break
        if current["status"] == "ready":
            client.post(f"/session/{session_id}/rounds/{current['round']}/activate", headers=headers)
            continue
        if current["round_type"] != "technical_short_answer":
            break
        seen.append(current)
        res = client.post("/session/answer", headers=headers, json={
            "session_id": session_id, "round": current["round"], "answer_text": ANSWER,
        })
        assert res.status_code == 200, res.text
    return seen


# ── flag off: unchanged ──────────────────────────────────────────────────────


def test_flag_off_rejects_role_target_and_keeps_the_company_target(sql_env) -> None:
    client = TestClient(app)
    _, headers = _user(sql_env)
    company_id, role_id = _company_target()
    saved = client.put("/target-context/me", headers=headers, json={"company_id": company_id, "role_id": role_id})
    assert saved.status_code == 200, saved.text

    refused = client.put("/target-context/me", headers=headers,
                         json={"role_target": {"role_id": "backend-engineer", "level": "junior"}})
    assert refused.status_code == 422
    assert refused.json()["detail"] == "Role targets are off."

    target = client.get("/target-context/me", headers=headers).json()["target"]
    assert (target["company_id"], target["role_id"]) == (company_id, role_id)
    assert "role_target" not in target


def test_flag_off_rejects_a_role_interview_start_before_any_write(sql_env) -> None:
    client = TestClient(app)
    user, headers = _user(sql_env)
    res = client.post("/session/start", headers=headers, json=_role_start("backend-engineer"))
    assert res.status_code == 422
    assert res.json()["detail"] == "Role interviews are off."
    assert list(sql_env["sessions"].find({"user_id": user["id"]})) == []


def test_flag_off_role_practice_plan_is_the_planner_output(sql_env, monkeypatch) -> None:
    monkeypatch.setenv("ROLE_PRACTICE_ENABLED", "1")
    client = TestClient(app)
    _, headers = _user(sql_env)
    body = client.post("/role-practice/plan", headers=headers,
                       json={"role_id": "backend-engineer", "level": "junior", "length": "quick"}).json()
    assert body["slots"][0]["reason"] == "Python: easy bank warm-up"
    assert body["slots"][0]["scored"] is True
    assert "interview" not in body


def test_flag_off_role_practice_stays_404_without_either_flag(sql_env) -> None:
    client = TestClient(app)
    _, headers = _user(sql_env)
    assert client.get("/role-practice/catalog", headers=headers).status_code == 404


# ── flag on: stored role target ──────────────────────────────────────────────


def test_role_target_is_stored_without_a_company_and_hidden_from_company_consumers(roles_on) -> None:
    client = TestClient(app)
    user, headers = _user(roles_on)
    res = client.put("/target-context/me", headers=headers,
                     json={"role_target": {"role_id": "backend-engineer", "level": "mid"}})
    assert res.status_code == 200, res.text
    target = res.json()["target"]
    assert target["role_target"] == {
        "role_id": "backend-engineer", "level": "mid", "title": "Backend Engineer",
        "family": "engineering", "practical_track": "coding",
    }
    assert target["company_id"] is None and target["company_name"] is None
    assert target["role_id"] is None and target["role_title"] is None

    stored = roles_on["target_contexts"].find_one({"user_id": user["id"]})
    assert stored["role_id"] == "blueprint:backend-engineer:mid"
    assert stored["company_id"] is None
    row = roles_on["users"].find_one({"id": user["id"]})
    assert row["target_company_id"] is None and row["target_role_id"] is None

    assert get_user_target(row) == {"company_id": None, "role_id": None}
    assert get_role_target(row)["title"] == "Backend Engineer"
    me = client.get("/auth/me", headers=headers).json()
    me_user = me.get("user") or me
    assert me_user["target_company_id"] is None and me_user["target_role_id"] is None

    # A later resume-only update keeps the role target.
    client.put("/target-context/me", headers=headers, json={"jd_text": "SQL and Python"})
    assert client.get("/target-context/me", headers=headers).json()["target"]["role_target"]["level"] == "mid"


def test_role_target_validation_and_clearing(roles_on) -> None:
    client = TestClient(app)
    _, headers = _user(roles_on)
    bad_role = client.put("/target-context/me", headers=headers, json={"role_target": {"role_id": "astronaut"}})
    assert bad_role.status_code == 422
    bad_level = client.put("/target-context/me", headers=headers,
                           json={"role_target": {"role_id": "data-analyst", "level": "senior"}})
    assert bad_level.status_code == 422
    company_id, role_id = _company_target()
    both = client.put("/target-context/me", headers=headers, json={
        "company_id": company_id, "role_id": role_id, "role_target": {"role_id": "data-analyst"},
    })
    assert both.status_code == 422

    client.put("/target-context/me", headers=headers, json={"role_target": {"role_id": "data-analyst"}})
    cleared = client.put("/target-context/me", headers=headers, json={"role_target": None})
    assert cleared.status_code == 200
    target = cleared.json()["target"]
    assert target is None or "role_target" not in target


def test_choosing_a_company_target_replaces_the_role_target(roles_on) -> None:
    client = TestClient(app)
    _, headers = _user(roles_on)
    client.put("/target-context/me", headers=headers, json={"role_target": {"role_id": "data-analyst"}})
    company_id, role_id = _company_target()
    res = client.put("/target-context/me", headers=headers, json={"company_id": company_id, "role_id": role_id})
    assert res.status_code == 200
    target = res.json()["target"]
    assert (target["company_id"], target["role_id"]) == (company_id, role_id)
    assert "role_target" not in target


def test_role_target_encoding_round_trips() -> None:
    assert decode_role_target(encode_role_target("data-scientist-ml", "intern")) == {
        "role_id": "data-scientist", "level": "intern",
    }
    assert decode_role_target("amazon_sde1") is None
    assert decode_role_target("blueprint:x:senior") is None


# ── flag on: plan ────────────────────────────────────────────────────────────


@pytest.mark.parametrize("length", ["quick", "full"])
def test_interview_plan_rules_for_every_role(roles_on, length) -> None:
    client = TestClient(app)
    _, headers = _user(roles_on)
    for role_id in ROLE_IDS:
        body = client.post("/role-practice/plan", headers=headers,
                           json={"role_id": role_id, "level": "junior", "length": length})
        assert body.status_code == 200, body.text
        plan = body.json()
        assert plan["interview"] is True
        slots = plan["slots"]
        opener = slots[0]
        assert (opener["kind"], opener["stage"], opener["scored"]) == ("opener", "warm_up", False)
        assert opener["reason"].startswith("Tell me a little about yourself")
        for slot in slots:
            if slot["kind"] in ("scenario", "behavioural"):
                assert slot["scored"] is False
            if slot["kind"] == "scenario" and plan_family(role_id) in {"business", "product", "design"}:
                assert slot["practice_only"] is True
            if slot["kind"] == "core":
                assert slot["content"] in {"bank", "none", "reviewed_bundle", "auto_checked_bundle", "generated_bundle"}
                assert slot["scored"] is (slot["content"] in {"bank", "reviewed_bundle"})
                assert (slot["stage"] == "practice") is (slot["content"] == "none")
            _assert_no_company_names(slot["reason"] + " " + slot["name"])


def plan_family(role_id: str) -> str:
    return next(doc["family"] for doc in load_blueprints() if doc["id"] == role_id)


def test_scripted_texts_carry_no_company_names_or_links() -> None:
    for doc in load_blueprints():
        texts = [opener_question(doc)]
        for item in doc["competencies"]:
            if item["type"] == "role_scenario":
                texts.append(scenario_question(item))
            elif item["type"] == "behavioural":
                texts.append(behavioural_question(item))
            else:
                texts.append(core_practice_question((item.get("skills") or [item["name"]])[0]))
        for text in texts:
            _assert_no_company_names(text)
            assert "http" not in text and "](" not in text


# ── flag on: role interview sessions ─────────────────────────────────────────


@pytest.mark.parametrize("role_id", ROLE_IDS)
def test_quick_role_interview_starts_from_the_blueprint_plan(roles_on, role_id) -> None:
    client = TestClient(app)
    user, headers = _user(roles_on)
    company_id, company_role = _company_target()
    client.put("/target-context/me", headers=headers, json={"company_id": company_id, "role_id": company_role})

    res = client.post("/session/start", headers=headers, json=_role_start(role_id))
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["flow_version"] == "staged_v1" and body["preset"] == "quick"
    assert body["role_interview"]["role_id"] == role_id
    assert body["stage"] == "warm_up"
    slots = interview_slots(next(d for d in load_blueprints() if d["id"] == role_id), level="junior", length="quick")
    assert [b["stage"] for b in body["block_plan"]] == [slot.stage for slot in slots]
    assert body["total_rounds"] == len(slots)
    assert body["question"] == slots[0].reason
    assert "role_interview" not in body["staged_flow"]

    session = roles_on["sessions"].find_one({"session_id": body["session_id"]})
    # A saved company target never rides along on a role interview.
    assert session["target_company_id"] is None and session["target_role_id"] is None
    _assert_no_company_names(str(session.get("round_config")))


def test_quick_role_interview_scores_only_core_content(roles_on) -> None:
    client = TestClient(app)
    user, headers = _user(roles_on)
    body = client.post("/session/start", headers=headers, json=_role_start("data-analyst")).json()
    sid = body["session_id"]
    seen = _walk_text_rounds(client, headers, sid)
    assert [r.get("stage") or (r.get("config_json") or {}).get("stage") for r in seen] == ["warm_up", "core", "practice"]
    assert seen[0]["question"].startswith("Tell me a little about yourself")
    assert seen[2]["question"].startswith("Practice question on Statistics")

    dash = client.get(f"/dashboard/{sid}", headers=headers)
    assert dash.status_code == 200, dash.text
    rounds = {r["round"]: r for r in dash.json()["rounds"]}
    assert rounds[1]["final_score"] is None
    assert rounds[2]["final_score"] is not None  # SQL from the CSV bank
    assert rounds[3]["final_score"] is None
    stored = roles_on["sessions"].find_one({"session_id": sid})
    reasons = {
        r["round"]: (r.get("scoring_breakdown") or {}).get("unscored_reason") for r in stored["rounds"]
    }
    assert reasons[1] == "warm_up_unscored"
    assert reasons[3] == "practice_unscored"
    assert [r["elo_after"] == r["elo_before"] for r in stored["rounds"]][::2] == [True, True]
    candidate = roles_on["candidates"].find_one({"candidate_id": body["candidate_id"]})
    assert "Statistics" not in (candidate.get("elo_ratings") or {})


def test_full_role_interview_keeps_scenario_behavioural_and_practical(roles_on) -> None:
    client = TestClient(app)
    _, headers = _user(roles_on)
    body = client.post("/session/start", headers=headers, json=_role_start("backend-engineer", "full"))
    assert body.status_code == 200, body.text
    plan = body.json()
    assert [b["stage"] for b in plan["block_plan"]] == [
        "warm_up", "core", "core", "practice", "practice", "behavioural", "practical",
    ]
    assert plan["block_plan"][-1]["category"] == "coding"
    assert plan["staged_flow"]["practical_track"] == "coding"

    seen = _walk_text_rounds(client, headers, plan["session_id"])
    stages = [r.get("stage") or (r.get("config_json") or {}).get("stage") for r in seen]
    assert stages == ["warm_up", "core", "core", "practice", "practice", "behavioural"]
    assert seen[4]["question"].startswith("Practice scenario on Production Debugging & Reliability")
    assert seen[5]["question"].startswith("Tell me about a time that called for cross-team technical collaboration")
    state = client.get(f"/session/{plan['session_id']}", headers=headers).json()
    assert state["role_interview"]["title"] == "Backend Engineer"


def test_swapped_core_competencies_are_validated_and_kept(roles_on) -> None:
    client = TestClient(app)
    _, headers = _user(roles_on)
    swapped = client.post("/session/start", headers=headers, json=_role_start(
        "backend-engineer", core_competencies=["operating-systems-runtime-basics", "backend-programming-python-java"],
    ))
    assert swapped.status_code == 200, swapped.text
    cores = [b for b in swapped.json()["block_plan"] if b["stage"] == "core"]
    assert [b["skills"] for b in cores] == [["Operating Systems"], ["Python"]]

    bad = client.post("/session/start", headers=headers, json=_role_start(
        "backend-engineer", core_competencies=["production-debugging-reliability", "backend-programming-python-java"],
    ))
    assert bad.status_code == 422


def test_resume_plans_only_from_the_users_own_candidate(roles_on) -> None:
    client = TestClient(app)
    user, headers = _user(roles_on)
    other, other_headers = _user(roles_on, "other")
    candidate_id = f"cand-{uuid4().hex[:8]}"
    roles_on["candidates"].insert_one({
        "candidate_id": candidate_id, "user_id": user["id"], "resume_skills": ["Python", "Docker"],
        "sub_domain_profile": {}, "elo_ratings": {}, "session_history": [],
        "ats_snapshot": {"evidence_skills": ["Python"]},
    })
    plan = client.post("/role-practice/plan", headers=headers, json={
        "role_id": "backend-engineer", "level": "junior", "length": "quick", "candidate_id": candidate_id,
    }).json()
    assert plan["used_resume"] is True
    cores = [slot for slot in plan["slots"] if slot["kind"] == "core"]
    assert [(slot["skill"], slot["difficulty"]) for slot in cores] == [("Python", "hard"), ("DBMS", "easy")]

    started = client.post("/session/start", headers=headers, json={
        **_role_start("backend-engineer", use_resume=True), "candidate_id": candidate_id,
    })
    assert started.status_code == 200, started.text
    assert [b["difficulty"] for b in started.json()["block_plan"] if b["stage"] == "core"] == ["hard", "easy"]

    assert client.post("/role-practice/plan", headers=other_headers, json={
        "role_id": "backend-engineer", "candidate_id": candidate_id,
    }).status_code == 403
    assert client.post("/session/start", headers=other_headers, json={
        **_role_start("backend-engineer", use_resume=True), "candidate_id": candidate_id,
    }).status_code == 403


def test_role_interview_needs_a_preset(roles_on) -> None:
    client = TestClient(app)
    _, headers = _user(roles_on)
    res = client.post("/session/start", headers=headers, json={
        "role_interview": {"role_id": "data-analyst"}, "skills": ["SQL"],
    })
    assert res.status_code == 422


def test_skill_based_quick_interview_is_unchanged_with_the_flag_on(roles_on) -> None:
    client = TestClient(app)
    _, headers = _user(roles_on)
    res = client.post("/session/start", headers=headers, json={
        "flow_version": "staged_v1", "preset": "quick", "skills": ["Python"],
    })
    assert res.status_code == 200, res.text
    assert [b["stage"] for b in res.json()["block_plan"]] == ["warm_up", "core"]
    assert "role_interview" not in res.json()


def test_availability_probe_accepts_a_role_interview(roles_on) -> None:
    client = TestClient(app)
    user, headers = _user(roles_on)
    res = client.post("/session/availability", headers=headers, json=_role_start("ui-ux-designer", "full"))
    assert res.status_code == 200, res.text
    assert res.json()["available"] is True
    assert list(roles_on["sessions"].find({"user_id": user["id"]})) == []
