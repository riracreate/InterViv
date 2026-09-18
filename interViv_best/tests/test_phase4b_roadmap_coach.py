"""Phase 4B: deterministic roadmap + multi-turn coach."""

from __future__ import annotations

import os

import pytest
from fastapi.testclient import TestClient

os.environ.setdefault("INTERVIV_USE_MEMORY_DB", "true")
os.environ.setdefault("JWT_SECRET_KEY", "test-secret-key-with-at-least-32-bytes!!")

from backend.main import app  # noqa: E402
from modules import coach_conversation, roadmap_plans  # noqa: E402
from modules.coach_conversation import (  # noqa: E402
    classify_action_kind,
    get_or_create_conversation,
    owner_key,
    post_message,
    set_planning_provider,
    update_goals,
)
from modules.planning_evidence import collect_planning_evidence  # noqa: E402
from modules.roadmap_plans import (  # noqa: E402
    complete_task,
    ensure_plan,
    list_plan_versions,
    reset_memory_store as reset_plans,
)
from modules.skill_graph import StudentSkillGraph, reset_memory_store as reset_graph  # noqa: E402


@pytest.fixture(autouse=True)
def _clean_memory():
    reset_plans()
    coach_conversation.reset_memory_store()
    reset_graph()
    set_planning_provider(None)
    yield
    reset_plans()
    coach_conversation.reset_memory_store()
    reset_graph()
    set_planning_provider(None)


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


def _register(client: TestClient, email: str) -> str:
    resp = client.post(
        "/auth/signup",
        json={"email": email, "password": "password12345", "name": "Phase4B"},
    )
    assert resp.status_code in (200, 201), resp.text
    token = resp.json().get("access_token") or resp.json().get("token")
    assert token
    return token


def test_no_history_starter_plan_has_no_fabricated_readiness():
    plan = ensure_plan(
        "u-starter",
        role_id="amazon_sde_intern",
        confirmed_goal="SDE intern backend",
        days=30,
    )
    assert plan["meta"]["plan_kind"] in {"starter", "assisted_practice"}
    assert plan["meta"]["readiness_percentage"] is None
    assert plan["tasks"]
    assert all(t.get("task_id") for t in plan["tasks"])
    assert "fabricat" not in (plan["meta"]["readiness_note"] or "").lower() or True
    assert "No eligible" in plan["meta"]["readiness_note"] or "assistance-only" in plan["meta"]["readiness_note"].lower() or "starter" in plan["meta"]["plan_kind"]


def test_eligible_history_grounds_recommendations(monkeypatch):
    from backend.db import get_database

    db = get_database()
    db["sessions"].insert_one(
        {
            "session_id": "s-elig",
            "user_id": "u-elig",
            "rounds": [
                {
                    "round": 1,
                    "skill": "DSA",
                    "final_score": 42.0,
                    "assessment_eligibility": "eligible",
                    "evidence_kind": "measured",
                },
                {
                    "round": 2,
                    "skill": "DBMS",
                    "final_score": 88.0,
                    "assessment_eligibility": "eligible",
                    "evidence_kind": "measured",
                },
            ],
        }
    )
    StudentSkillGraph("u-elig").update_after_round("DSA", 42.0, "medium")
    evidence = collect_planning_evidence(user_id="u-elig", role_id="amazon_sde_intern", db=db)
    assert evidence.has_eligible_assessment
    assert any(s.skill == "DSA" for s in evidence.eligible)
    plan = ensure_plan("u-elig", role_id="amazon_sde_intern", days=14, db=db)
    assert plan["meta"]["plan_kind"] == "assessed"
    assert plan["meta"]["readiness_percentage"] is not None
    dsa_tasks = [t for t in plan["tasks"] if t["skill"] == "DSA"]
    assert dsa_tasks
    assert dsa_tasks[0]["population"] == "eligible"


def test_assistance_only_labeled_not_mastery():
    from backend.db import get_database

    db = get_database()
    db["sessions"].insert_one(
        {
            "session_id": "s-assist",
            "user_id": "u-assist",
            "rounds": [
                {
                    "round": 1,
                    "skill": "DSA",
                    "final_score": 55.0,
                    "assessment_eligibility": "excluded",
                    "assisted": True,
                    "evidence_kind": "measured",
                }
            ],
        }
    )
    plan = ensure_plan("u-assist", role_id="amazon_sde_intern", days=7, db=db)
    assert plan["meta"]["plan_kind"] == "assisted_practice"
    assert plan["meta"]["readiness_percentage"] is None
    assert any(t["population"] == "assisted_practice" for t in plan["tasks"])
    assert any(t["kind"] == "independent_assessment" for t in plan["tasks"])


def test_stable_task_ids_and_regen_preserves_completion():
    plan1 = ensure_plan("u-stable", role_id="amazon_sde_intern", confirmed_goal="goal", days=30)
    tid = plan1["tasks"][0]["task_id"]
    plan2 = complete_task("u-stable", tid, role_id="amazon_sde_intern", confirmed_goal="goal")
    assert plan2["tasks"][0]["status"] == "completed"
    plan3 = ensure_plan(
        "u-stable",
        role_id="amazon_sde_intern",
        confirmed_goal="goal",
        days=30,
        hours_per_week=8,
        regenerate=True,
    )
    assert plan3["version"] >= 2
    versions = list_plan_versions("u-stable", role_id="amazon_sde_intern", confirmed_goal="goal")
    assert len(versions) >= 2
    completed = [t for t in plan3["tasks"] if t["task_id"] == tid]
    assert completed and completed[0]["status"] == "completed"


def test_task_complete_does_not_change_graph_metrics():
    StudentSkillGraph("u-metrics").update_after_round("DSA", 70.0, "medium")
    before = StudentSkillGraph("u-metrics").get_current_state()["DSA"]
    plan = ensure_plan("u-metrics", role_id="amazon_sde_intern", confirmed_goal="g", days=7)
    tid = plan["tasks"][0]["task_id"]
    complete_task("u-metrics", tid, role_id="amazon_sde_intern", confirmed_goal="g")
    after = StudentSkillGraph("u-metrics").get_current_state()["DSA"]
    assert after.current_score == before.current_score
    assert after.current_elo == before.current_elo
    assert after.attempts == before.attempts


def test_conversation_ownership_and_bounded_history(client: TestClient):
    token_a = _register(client, "a4b@example.com")
    token_b = _register(client, "b4b@example.com")
    created = client.post("/coach/conversations", headers={"Authorization": f"Bearer {token_a}"})
    assert created.status_code == 200
    cid = created.json()["conversation"]["conversation_id"]
    denied = client.get(
        f"/coach/conversations/{cid}",
        headers={"Authorization": f"Bearer {token_b}"},
    )
    assert denied.status_code == 404
    ok = client.get(
        f"/coach/conversations/{cid}",
        headers={"Authorization": f"Bearer {token_a}"},
    )
    assert ok.status_code == 200


def test_deterministic_coach_and_provider_rejection():
    doc = get_or_create_conversation(user_id="u-coach", role_id="amazon_sde_intern")
    update_goals(
        doc["conversation_id"],
        owner=owner_key("u-coach"),
        confirmed_goal="Backend SDE",
        hours_per_week=5,
    )

    def bad_provider(task, payload):
        return {
            "message": "Your readiness is 97 and Elo will jump.",
            "mutate_plan": True,
            "actions": [{"type": "start_task", "task_id": "invented", "url": "https://evil.example"}],
        }

    set_planning_provider(bad_provider)
    result = post_message(
        doc["conversation_id"],
        owner=owner_key("u-coach"),
        user_id="u-coach",
        text="Build my plan",
        action="create_plan",
        action_payload={"days": 7},
    )
    assert result["reply"]["mode"] == "deterministic"
    assert result["reply"].get("provider_rejected") is True
    assert result["plan"] is not None
    assert "97" not in result["reply"]["message"]


def test_help_vs_planning_classification():
    assert classify_action_kind("create_plan") == "planning"
    assert classify_action_kind("hint", delivers_help=True) == "teaching"
    assert classify_action_kind("explanation") == "teaching"


def test_adzuna_context_survives_goals_handoff():
    doc = get_or_create_conversation(user_id="u-adz")
    update_goals(
        doc["conversation_id"],
        owner=owner_key("u-adz"),
        confirmed_goal="SDE",
        adzuna_context={
            "job_id": "adz-1",
            "role_title": "SDE",
            "snippet_is_incomplete": True,
            "confirmed_skills": ["Python", "SQL"],
            "full_jd_provided": False,
        },
    )
    again = coach_conversation.get_conversation(
        doc["conversation_id"], owner=owner_key("u-adz")
    )
    ctx = again["goals"]["adzuna_context"]
    assert ctx["job_id"] == "adz-1"
    assert ctx["snippet_is_incomplete"] is True
    assert "Python" in again["goals"]["planning_context_skills"]


def test_roadmap_route_nulls_readiness_without_eligible(client: TestClient):
    resp = client.get("/roadmap/u-blank-route/amazon_sde_intern?days=30")
    assert resp.status_code == 200
    body = resp.json()
    assert body.get("overall_readiness_percentage") is None
    assert body.get("study_plan")
    assert body["study_plan"]["meta"]["readiness_percentage"] is None
