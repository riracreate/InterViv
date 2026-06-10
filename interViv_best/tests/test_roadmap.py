"""Tests for the Roadmap generator and route.

Spec scenario:
    A user weak in DSA and System Design (targeting Amazon SDE Intern)
    should see those two skills emphasized in the EARLY weeks (Week 1
    and Week 2). HR / OOP / etc. can show up in later weeks even if
    they have higher importance × required-level scores because the
    roadmap intentionally prioritizes tested-with-a-gap signal over
    untested-but-important guesses.
"""
from __future__ import annotations

import os

import pytest
from fastapi.testclient import TestClient

os.environ.setdefault("INTERVIV_USE_MEMORY_DB", "true")
os.environ.setdefault("JWT_SECRET_KEY", "test-secret-key-with-at-least-32-bytes!!")

from backend.main import app  # noqa: E402
from modules.roadmap_generator import (  # noqa: E402
    RoadmapGenerationError,
    RoadmapGenerator,
    SUPPORTED_DAYS,
)
from modules.skill_graph import StudentSkillGraph  # noqa: E402


@pytest.fixture(scope="module")
def client() -> TestClient:
    return TestClient(app)


def _seed_weak_dsa_sd(user_id: str) -> None:
    sg = StudentSkillGraph(user_id)
    sg.initialize_from_resume(["DSA", "System Design", "DBMS"])
    sg.update_after_round("DSA", 40.0, "medium")
    sg.update_after_round("System Design", 35.0, "medium")
    sg.update_after_round("DBMS", 75.0, "medium")


def test_30_day_plan_puts_dsa_in_week1_and_sd_by_week2() -> None:
    _seed_weak_dsa_sd("u-spec-30")
    rd = RoadmapGenerator().generate("u-spec-30", "amazon_sde_intern", days=30)
    blocks = rd.weekly_blocks
    assert len(blocks) == 4
    assert blocks[0].label == "Foundations"
    assert "DSA" in blocks[0].focus_skills, blocks[0].focus_skills
    assert "System Design" in blocks[1].focus_skills, blocks[1].focus_skills
    # By the application/mock weeks, all top weak skills are present
    assert "DSA" in blocks[2].focus_skills
    assert "System Design" in blocks[2].focus_skills


def test_days_param_snaps_to_supported_values() -> None:
    _seed_weak_dsa_sd("u-spec-snap")
    rd = RoadmapGenerator().generate("u-spec-snap", "amazon_sde_intern", days=10)
    assert rd.days in SUPPORTED_DAYS
    # 10 → snaps to 7 (nearest)
    assert rd.days == 7


def test_7_day_plan_compresses_to_4_phases() -> None:
    _seed_weak_dsa_sd("u-spec-7")
    rd = RoadmapGenerator().generate("u-spec-7", "amazon_sde_intern", days=7)
    assert rd.days == 7
    assert len(rd.weekly_blocks) == 4
    assert rd.weekly_blocks[0].day_range == "Days 1-2"
    assert rd.weekly_blocks[-1].day_range == "Day 7"


def test_14_day_plan_uses_14_day_ranges() -> None:
    _seed_weak_dsa_sd("u-spec-14")
    rd = RoadmapGenerator().generate("u-spec-14", "amazon_sde_intern", days=14)
    assert rd.days == 14
    assert rd.weekly_blocks[0].day_range == "Days 1-4"
    assert rd.weekly_blocks[-1].day_range == "Days 13-14"


def test_focus_concepts_include_skill_specific_concepts() -> None:
    _seed_weak_dsa_sd("u-spec-concepts")
    rd = RoadmapGenerator().generate("u-spec-concepts", "amazon_sde_intern", days=30)
    # First focus skill is DSA — its KG concept list includes "array"
    assert rd.focus_skills[0] == "DSA"
    lowered = [c.lower() for c in rd.focus_concepts]
    assert any("array" in c for c in lowered)


def test_unknown_role_raises() -> None:
    with pytest.raises(RoadmapGenerationError):
        RoadmapGenerator().generate("u-anyone", "not_a_role", days=30)


def test_user_with_no_skill_graph_returns_untested_plan() -> None:
    rd = RoadmapGenerator().generate("u-blank", "amazon_sde_intern", days=30)
    assert rd.overall_readiness_percentage == 0.0
    # Even with no signal, the plan still surfaces required skills
    assert len(rd.focus_skills) >= 1
    assert len(rd.weekly_blocks) == 4


def test_route_returns_200_for_seeded_user(client: TestClient) -> None:
    _seed_weak_dsa_sd("u-route-30")
    resp = client.get("/roadmap/u-route-30/amazon_sde_intern?days=30")
    assert resp.status_code == 200
    body = resp.json()
    assert body["role_id"] == "amazon_sde_intern"
    assert body["days"] == 30
    # Disclaimer flows through from gap analysis
    assert "publicly available job descriptions" in body["disclaimer"]
    # First-week skills mention DSA
    assert "DSA" in body["weekly_blocks"][0]["focus_skills"]


def test_route_404_on_unknown_role(client: TestClient) -> None:
    resp = client.get("/roadmap/u-route-30/unknown_role")
    assert resp.status_code == 404


def test_me_route_requires_auth(client: TestClient) -> None:
    resp = client.get("/roadmap/me/amazon_sde_intern")
    assert resp.status_code == 401


def test_route_supports_7_and_14_day_query(client: TestClient) -> None:
    _seed_weak_dsa_sd("u-route-multi")
    for days, first_range, last_range in [
        (7, "Days 1-2", "Day 7"),
        (14, "Days 1-4", "Days 13-14"),
    ]:
        resp = client.get(f"/roadmap/u-route-multi/amazon_sde_intern?days={days}")
        assert resp.status_code == 200
        body = resp.json()
        assert body["days"] == days
        assert body["weekly_blocks"][0]["day_range"] == first_range
        assert body["weekly_blocks"][-1]["day_range"] == last_range
