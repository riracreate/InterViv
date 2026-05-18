"""Tests for the gap analysis engine and route.

Covers:
- The spec scenario (Python 70, DSA 45, DBMS 60 vs Amazon SDE Intern):
  overall_readiness must land in [40, 70].
- Severity bucketing and the weak-area ranking.
- Untested skills don't contribute to overall_readiness but do show up
  in the gap list with severity="Untested".
- The route handler integrates the live StudentSkillGraph correctly.
- /me/{role_id} requires auth.
- Unknown role -> 404.
"""
from __future__ import annotations

import os

import pytest
from fastapi.testclient import TestClient

os.environ.setdefault("INTERVIV_USE_MEMORY_DB", "true")
os.environ.setdefault("JWT_SECRET_KEY", "test-secret")

from backend.main import app  # noqa: E402
from modules.company_graph import get_company_graph  # noqa: E402
from modules.gap_analysis import (  # noqa: E402
    GapAnalysisError,
    GapAnalyzer,
    compute_gap_for_levels,
)
from modules.skill_graph import StudentSkillGraph  # noqa: E402


@pytest.fixture(scope="module")
def client() -> TestClient:
    return TestClient(app)


def _amazon_role():
    _, role = get_company_graph().find_role("amazon_sde_intern")
    return role


def test_spec_scenario_readiness_lands_in_40_to_70_band() -> None:
    role = _amazon_role()
    levels = {
        "Python": (70.0, 3),  # not required by Amazon — must be ignored
        "DSA": (45.0, 3),
        "DBMS": (60.0, 3),
    }
    report = compute_gap_for_levels(role, levels)
    assert 40 <= report.overall_readiness_percentage <= 70, (
        f"readiness {report.overall_readiness_percentage} outside spec band"
    )
    # Specifically: DSA contributes 52.94 with weight 0.40, DBMS 100 with 0.10,
    # tested-weight total 0.50 → 62.35.
    assert abs(report.overall_readiness_percentage - 62.35) < 0.05


def test_dsa_is_high_severity_dbms_is_low() -> None:
    role = _amazon_role()
    levels = {"DSA": (45.0, 3), "DBMS": (60.0, 3)}
    report = compute_gap_for_levels(role, levels)
    by_skill = {g.skill: g for g in report.per_skill_gap}
    assert by_skill["DSA"].gap_severity == "High"
    assert by_skill["DBMS"].gap_severity == "Low"  # met exactly


def test_untested_skills_appear_as_untested() -> None:
    role = _amazon_role()
    report = compute_gap_for_levels(role, {})
    untested = [g for g in report.per_skill_gap if g.gap_severity == "Untested"]
    assert len(untested) == len(role.skill_requirements)
    assert report.overall_readiness_percentage == 0.0
    assert report.tested_skill_count == 0


def test_weak_areas_ranking_orders_by_importance_times_gap() -> None:
    role = _amazon_role()
    levels = {"DSA": (45.0, 3), "DBMS": (60.0, 3)}
    report = compute_gap_for_levels(role, levels)
    # Expected ordering by rank_score:
    #   HR untested: 0.25 * 75 = 18.75
    #   DSA tested:  0.40 * 40 = 16.0
    #   OOP untested:0.15 * 70 = 10.5
    #   System Design untested: 0.10 * 55 = 5.5
    # DBMS (tested, Low) is excluded from weak areas.
    ordered = [(w.skill, w.rank_score) for w in report.ranked_weak_areas]
    assert ordered[0][0] == "HR"
    assert ordered[1][0] == "DSA"
    assert ordered[0][1] > ordered[1][1] > ordered[2][1]
    assert "DBMS" not in [w.skill for w in report.ranked_weak_areas]


def test_unknown_role_raises() -> None:
    with pytest.raises(GapAnalysisError):
        GapAnalyzer().compute_gap(user_id="anyone", role_id="not_a_real_role")


def test_route_returns_spec_readiness_for_seeded_user(client: TestClient) -> None:
    sg = StudentSkillGraph("u-route-spec")
    sg.initialize_from_resume(["Python", "DSA", "DBMS"])
    sg.update_after_round("Python", 70.0, "medium")
    sg.update_after_round("DSA", 45.0, "medium")
    sg.update_after_round("DBMS", 60.0, "medium")

    resp = client.get("/gap-analysis/u-route-spec/amazon_sde_intern")
    assert resp.status_code == 200
    body = resp.json()
    assert body["company_id"] == "amazon"
    assert 40 <= body["overall_readiness_percentage"] <= 70
    assert any(g["skill"] == "DSA" and g["gap_severity"] == "High" for g in body["per_skill_gap"])
    assert "publicly available job descriptions" in body["disclaimer"]


def test_route_404_on_unknown_role(client: TestClient) -> None:
    resp = client.get("/gap-analysis/anyone/no_such_role")
    assert resp.status_code == 404


def test_me_route_requires_auth(client: TestClient) -> None:
    resp = client.get("/gap-analysis/me/amazon_sde_intern")
    assert resp.status_code == 401


def test_me_route_returns_my_readiness(client: TestClient) -> None:
    signup = client.post(
        "/auth/signup",
        json={"email": "gap_me@example.com", "password": "StrongPass1!", "name": "GapMe"},
    )
    assert signup.status_code == 200
    token = signup.json()["access_token"]
    uid = signup.json()["user"]["id"]

    sg = StudentSkillGraph(uid)
    sg.initialize_from_resume(["DSA", "DBMS"])
    sg.update_after_round("DSA", 45.0, "medium")
    sg.update_after_round("DBMS", 60.0, "medium")

    resp = client.get(
        "/gap-analysis/me/amazon_sde_intern",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["user_id"] == uid
    assert 40 <= body["overall_readiness_percentage"] <= 70
