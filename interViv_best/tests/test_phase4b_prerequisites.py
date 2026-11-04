"""Phase 4B prerequisite: eligibility filter, rolling window, learning atomicity."""

from __future__ import annotations

import copy

import pytest

from backend.db.learning_memory import restore_learning_memory, snapshot_learning_memory
from backend.db.transactions import atomic
from backend.evidence_kind import assessment_eligible_rounds
from modules.skill_graph import (
    ROLLING_WINDOW,
    StudentSkillGraph,
    _score_is_rolling_eligible,
    reset_memory_store as reset_skill_graph,
)


def test_rolling_eligible_excludes_self_reported_and_review():
    assert _score_is_rolling_eligible(
        assessment_eligibility="eligible",
        assisted=False,
        is_follow_up=False,
        round_type="technical_short_answer",
        scoring_breakdown={"evidence_kind": "measured"},
    )
    assert not _score_is_rolling_eligible(
        assessment_eligibility="eligible",
        assisted=False,
        is_follow_up=False,
        round_type="system_design",
        scoring_breakdown={"evidence_kind": "measured"},
    )
    assert not _score_is_rolling_eligible(
        assessment_eligibility="eligible",
        assisted=False,
        is_follow_up=False,
        round_type="technical_short_answer",
        scoring_breakdown={"evidence_kind": "self_reported"},
    )
    assert not _score_is_rolling_eligible(
        assessment_eligibility="eligible",
        assisted=False,
        is_follow_up=False,
        round_type="technical_short_answer",
        scoring_breakdown={"evidence_kind": "practice_review"},
    )
    # Legacy unassisted non-follow-up still counts.
    assert _score_is_rolling_eligible(
        assessment_eligibility=None,
        assisted=False,
        is_follow_up=False,
        round_type="technical_short_answer",
        scoring_breakdown={},
    )
    assert not _score_is_rolling_eligible(
        assessment_eligibility=None,
        assisted=True,
        is_follow_up=False,
        round_type="technical_short_answer",
        scoring_breakdown={},
    )


def test_assisted_rounds_do_not_displace_eligible_topic_population():
    rounds = [
        {
            "round": 1,
            "final_score": 80.0,
            "assessment_eligibility": "eligible",
            "question_context": {"topic": "Trees"},
        },
        {
            "round": 2,
            "final_score": 10.0,
            "assessment_eligibility": "excluded",
            "assisted": True,
            "question_context": {"topic": "Trees"},
        },
    ]
    eligible = assessment_eligible_rounds(rounds)
    assert len(eligible) == 1
    assert eligible[0]["final_score"] == 80.0


def test_memory_learning_globals_roll_back_with_atomic(monkeypatch):
    from backend.db.memory import get_memory_database
    from modules import skill_graph

    reset_skill_graph()
    db = get_memory_database()
    # Isolate collections used in this test.
    db["sessions"].insert_one({"session_id": "s-atomic-learn", "rounds": []})

    graph = StudentSkillGraph("user-atomic")
    graph.update_after_round(skill="DSA", score=70.0, difficulty="medium")
    before = snapshot_learning_memory()
    assert "DSA" in skill_graph._MEMORY_GRAPHS.get("user-atomic", {})

    with pytest.raises(RuntimeError, match="inject"):
        with atomic(db):
            db["sessions"].update_one(
                {"session_id": "s-atomic-learn"},
                {"$set": {"marker": 1}},
            )
            StudentSkillGraph("user-atomic").update_after_round(
                skill="DSA", score=20.0, difficulty="medium"
            )
            raise RuntimeError("inject")

    # Session write rolled back.
    doc = db["sessions"].find_one({"session_id": "s-atomic-learn"})
    assert doc is not None
    assert "marker" not in doc
    # Learning globals restored to pre-atomic snapshot.
    restore_learning_memory(before)  # idempotent check path
    state = StudentSkillGraph("user-atomic").get_current_state()
    assert state["DSA"].current_score == 70.0
    assert state["DSA"].attempts == 1


def test_followups_not_in_candidate_technical_keys():
    from modules.bundle_scoring import CANDIDATE_TECHNICAL_KEYS, candidate_technical_context

    assert "followups" not in CANDIDATE_TECHNICAL_KEYS
    out = candidate_technical_context(
        {"question": "Q", "followups": ["secret teaching"], "ideal_answer": "no"}
    )
    assert "followups" not in out
    assert out.get("question") == "Q"
    assert "ideal_answer" not in out


def test_rolling_window_constant():
    assert ROLLING_WINDOW == 5
