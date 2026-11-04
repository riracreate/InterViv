from __future__ import annotations

from datetime import datetime, timezone

from fastapi.testclient import TestClient

from backend.auth.security import create_access_token, hash_password
from backend.db import get_database
from backend.main import app
from modules.concept_mastery import ConceptMastery
from modules.skill_graph import StudentSkillGraph


def test_skill_graph_initializes_from_resume():
    graph = StudentSkillGraph("skill-graph-user-init")
    graph.initialize_from_resume(["Python", "DSA"])

    state = graph.get_current_state()

    assert {"Python", "DSA"} <= set(state)
    assert state["Python"].current_elo == 1200
    assert "decorator" in state["Python"].sub_concepts


def test_skill_graph_updates_score_elo_and_weak_skills():
    graph = StudentSkillGraph("skill-graph-user-update")
    graph.initialize_from_resume(["DSA"])
    graph.update_after_round("DSA", 42, "medium")
    graph.update_after_round("DSA", 58, "medium")

    node = graph.get_current_state()["DSA"]

    assert node.attempts == 2
    assert node.current_score == 50
    assert node.current_elo != 1200
    assert graph.get_weak_skills(threshold=51)[0].name == "DSA"


def test_concept_mastery_levels_and_endpoint_payload():
    user_id = "skill-graph-user-mastery"
    mastery = ConceptMastery()
    mastery.update_from_round(user_id, "DSA", ["tree"], ["dynamic programming"])
    mastery.update_from_round(user_id, "DSA", ["tree"], [])
    mastery.update_from_round(user_id, "DSA", ["tree"], [])

    mastery_map = mastery.get_mastery_map(user_id)
    get_database()["users"].insert_one({
        "id": user_id,
        "email": f"{user_id}@example.com",
        "name": user_id,
        "password_hash": hash_password("passw0rd123"),
        "created_at": datetime.now(timezone.utc),
        "last_active_at": datetime.now(timezone.utc),
    })
    client = TestClient(app)
    response = client.get(
        f"/mastery/{user_id}",
        headers={"Authorization": f"Bearer {create_access_token(user_id)}"},
    )

    assert mastery_map["DSA"]["tree"] == "Mastered"
    assert mastery_map["DSA"]["dynamic programming"] == "Weak"
    assert response.status_code == 200
    assert response.json()["details"]["DSA"]["tree"]["demonstrated"] == 3
