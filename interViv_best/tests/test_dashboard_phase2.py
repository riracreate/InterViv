"""Tests for the Phase 2 dashboard additions.

Covers:
- The pure ``compute_confidence_band`` helper per spec
  (stdev / 2, capped at 10, None for <2 layer scores).
- A 3-round synthetic session round-tripped through the dashboard
  route: confidence_band should appear on every round.
- The skill-graph and mastery endpoints work for the same user so
  the Phase2InsightsPanel has real data to render.
"""
from __future__ import annotations

import os
import statistics
from datetime import datetime, timezone
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

os.environ.setdefault("INTERVIV_USE_MEMORY_DB", "true")
os.environ.setdefault("JWT_SECRET_KEY", "test-secret-key-with-at-least-32-bytes!!")

from backend.db import get_database  # noqa: E402
from backend.main import app  # noqa: E402
from backend.routes.dashboard import compute_confidence_band  # noqa: E402
from modules.concept_mastery import ConceptMastery  # noqa: E402
from modules.skill_graph import StudentSkillGraph  # noqa: E402


@pytest.fixture(scope="module")
def client() -> TestClient:
    return TestClient(app)


# ---------------------------------------------------------------------------
# Pure formula tests
# ---------------------------------------------------------------------------

def test_confidence_band_matches_stdev_over_two() -> None:
    layers = [70.0, 80.0, 60.0]
    expected = round(min(statistics.stdev(layers) / 2.0, 10.0), 2)
    assert compute_confidence_band(layers) == expected


def test_confidence_band_capped_at_ten() -> None:
    # stdev of [0, 100] is ~70.7 → /2 = 35.35, must clamp to 10.0
    band = compute_confidence_band([0.0, 100.0, None])
    assert band == 10.0


def test_confidence_band_none_when_only_one_layer_scored() -> None:
    assert compute_confidence_band([None, None, 80.0]) is None
    assert compute_confidence_band([None, None, None]) is None


def test_confidence_band_handles_two_layers() -> None:
    # stdev([60, 70]) = ~7.07 → band = ~3.54
    band = compute_confidence_band([60.0, 70.0, None])
    assert band is not None
    assert 3.4 <= band <= 3.6


# ---------------------------------------------------------------------------
# Dashboard route exposes confidence_band per round
# ---------------------------------------------------------------------------

def _insert_session_with_rounds(session_id: str, user_id: str) -> None:
    """Drop a synthetic 3-round session straight into the memory store.

    We bypass the live session/answer route to keep the test cheap and
    deterministic — the route already has its own end-to-end coverage in
    tests/test_change2_serverside_metrics.py and tests/test_change5_baseline.py.
    """
    db = get_database()
    rounds = [
        {
            "round": i + 1,
            "round_number": i + 1,
            "question": f"Q{i + 1}",
            "answer_text": f"A{i + 1}",
            "difficulty": "medium",
            "final_score": 70.0 + i * 5,
            "feedback": {"next_step": "Iterate."},
            "scoring_breakdown": {
                "layer1_score": 60.0 + i * 5,
                "layer2_score": 70.0 + i * 4,
                "layer3_score": 80.0 + i * 3,
            },
            "engagement_label": "High",
            "engagement_delta": 1,
        }
        for i in range(3)
    ]
    doc = {
        "session_id": session_id,
        "id": session_id,
        "candidate_id": f"c-{session_id}",
        "user_id": user_id,
        "target_company_id": "amazon",
        "target_role_id": "amazon_sde_intern",
        "started_at": datetime.now(timezone.utc).isoformat(),
        "skill": "DSA",
        "skills": ["DSA"],
        "skills_json": ["DSA"],
        "rounds_per_skill": 3,
        "total_rounds": 3,
        "status": "completed",
        "current_skill": "DSA",
        "last_round": 3,
        "rounds": rounds,
    }
    db["sessions"].insert_one(doc)


def test_dashboard_attaches_confidence_band_to_every_round(client: TestClient) -> None:
    sid = f"phase2-task6-{uuid4().hex[:8]}"
    uid = f"u-{uuid4().hex[:8]}"
    _insert_session_with_rounds(sid, uid)

    resp = client.get(f"/dashboard/{sid}")
    assert resp.status_code == 200, resp.text
    body = resp.json()

    assert len(body["rounds"]) == 3
    bands = [r["confidence_band"] for r in body["rounds"]]
    assert all(b is not None for b in bands), bands
    assert all(0 <= b <= 10 for b in bands), bands

    # Round 1: layers [60, 70, 80] → stdev = 10 → band = 5.0
    assert bands[0] == 5.0


def test_skill_graph_and_mastery_endpoints_serve_dashboard(client: TestClient) -> None:
    """Verify the two endpoints the Phase2InsightsPanel polls return
    valid JSON for a user with seeded data — guards against accidental
    breakage of the learning router."""
    user_id = f"u-task6-{uuid4().hex[:8]}"
    sg = StudentSkillGraph(user_id)
    sg.initialize_from_resume(["DSA", "DBMS"])
    sg.update_after_round("DSA", 65.0, "medium")
    sg.update_after_round("DBMS", 80.0, "medium")

    cm = ConceptMastery()
    cm.update_from_round(
        user_id=user_id,
        skill="DSA",
        covered_concepts=["array", "pointer"],
        missing_concepts=["heap"],
    )

    sg_resp = client.get(f"/skill-graph/{user_id}")
    assert sg_resp.status_code == 200
    sg_body = sg_resp.json()
    names = {row["name"] for row in sg_body["skills"]}
    assert {"DSA", "DBMS"} <= names

    mastery_resp = client.get(f"/mastery/{user_id}")
    assert mastery_resp.status_code == 200
    mastery_body = mastery_resp.json()
    assert "DSA" in mastery_body["mastery"]
    dsa = mastery_body["mastery"]["DSA"]
    assert dsa.get("array") in {"Mastered", "Strong", "Weak", "Untested"}
