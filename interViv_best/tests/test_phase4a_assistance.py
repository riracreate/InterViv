"""Phase 4A: assistance eligibility, exposures, follow-ups, metric gating."""

from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from concurrent.futures import ThreadPoolExecutor

import pytest

os.environ.setdefault("INTERVIV_USE_MEMORY_DB", "true")
os.environ.setdefault("JWT_SECRET_KEY", "test-secret-key-with-at-least-32-bytes!!")
os.environ["OPENAI_API_KEY"] = ""
os.environ["OPENROUTER_API_KEY"] = ""

from modules.assistance_policy import (
    ELIGIBLE,
    EXCLUDED,
    POLICY_VERSION,
    REASON_FOLLOW_UP,
    REASON_SAME_ITEM_RETRY,
    REASON_TEACHING_EXPOSURE,
    evaluate_eligibility,
    is_assessment_eligible,
    read_persisted_eligibility,
)
from modules.teaching_exposures import (
    list_exposures_for_eligibility,
    record_teaching_exposure,
)
from modules.follow_ups import (
    can_schedule_follow_up,
    build_follow_up_plan_entry,
    schedule_follow_up_in_session,
    spare_capacity,
)
from modules.attempt_snapshot import freeze_attempt_snapshot, verify_attempt_snapshot
from backend.evidence_kind import (
    assessment_eligible_scores,
    measured_scores,
)
from backend.models.blocks import MAX_TOTAL_ROUNDS
from backend.db import get_database
from backend.db.memory import _MemoryDB


@pytest.fixture
def memory_db(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setenv("INTERVIV_USE_MEMORY_DB", "true")
    # Fresh isolated memory store for each test.
    db = _MemoryDB()
    monkeypatch.setattr("backend.db.get_database", lambda: db)
    monkeypatch.setattr("backend.db.memory.get_memory_database", lambda: db)
    return db

def test_policy_version_constant():
    assert POLICY_VERSION == "assistance_v1"


def test_hint_before_submit_excludes_attempt(memory_db):
    session = {
        "session_id": "s1",
        "user_id": "u1",
        "rounds": [],
    }
    now = datetime.now(timezone.utc)
    record_teaching_exposure(
        memory_db,
        kind="hint",
        item_type="mcq",
        item_id="q1",
        session=session,
        user_id="u1",
        round_number=1,
        now=now - timedelta(seconds=5),
    )
    exposures = list_exposures_for_eligibility(
        memory_db, session=session, user_id="u1", before=now
    )
    round_doc = {
        "round": 1,
        "round_type": "mcq",
        "question_context": {"questions": [{"id": "q1"}]},
        "final_score": 90,
    }
    decision = evaluate_eligibility(
        session=session,
        round_doc=round_doc,
        exposures=exposures,
        prior_rounds=[],
        now=now,
    )
    assert decision["decision"] == EXCLUDED
    assert REASON_TEACHING_EXPOSURE in decision["exclusion_reasons"]
    assert decision["exposure_ids"]


def test_feedback_after_submit_does_not_change_committed_eligibility(memory_db):
    session = {"session_id": "s2", "user_id": "u1", "rounds": []}
    submit_at = datetime.now(timezone.utc)
    round_doc = {
        "round": 1,
        "round_type": "technical_short_answer",
        "question": "What is an index?",
        "question_id": "tech-1",
        "final_score": 80,
    }
    pre = evaluate_eligibility(
        session=session,
        round_doc=round_doc,
        exposures=[],
        prior_rounds=[],
        now=submit_at,
    )
    assert pre["decision"] == ELIGIBLE
    # Feedback delivered after cutoff.
    record_teaching_exposure(
        memory_db,
        kind="feedback_reveal",
        item_type="technical",
        item_id="tech-1",
        session=session,
        user_id="u1",
        round_number=1,
        now=submit_at + timedelta(seconds=30),
    )
    later = list_exposures_for_eligibility(
        memory_db, session=session, user_id="u1", before=submit_at
    )
    post = evaluate_eligibility(
        session=session,
        round_doc=round_doc,
        exposures=later,
        prior_rounds=[],
        now=submit_at,
    )
    assert post["decision"] == ELIGIBLE
    # Later attempt can see the exposure.
    later_attempt_cut = submit_at + timedelta(minutes=1)
    exposures2 = list_exposures_for_eligibility(
        memory_db, session=session, user_id="u1", before=later_attempt_cut
    )
    later_round = {
        "round": 2,
        "round_type": "technical_short_answer",
        "question_id": "tech-1",
        "question": "What is an index?",
    }
    d2 = evaluate_eligibility(
        session=session,
        round_doc=later_round,
        exposures=exposures2,
        prior_rounds=[{**round_doc, "assessment_eligibility": ELIGIBLE}],
        now=later_attempt_cut,
    )
    assert d2["decision"] == EXCLUDED
    assert REASON_SAME_ITEM_RETRY in d2["exclusion_reasons"] or REASON_TEACHING_EXPOSURE in d2["exclusion_reasons"]


def test_duplicate_delivery_idempotent(memory_db):
    session = {"session_id": "s3", "user_id": "u1"}
    a = record_teaching_exposure(
        memory_db,
        kind="hint",
        item_type="coding",
        item_id="p1",
        session=session,
        user_id="u1",
        round_number=1,
        content_fingerprint="level:1",
    )
    b = record_teaching_exposure(
        memory_db,
        kind="hint",
        item_type="coding",
        item_id="p1",
        session=session,
        user_id="u1",
        round_number=1,
        content_fingerprint="level:1",
    )
    assert a["delivery_id"] == b["delivery_id"]
    assert a["id"] == b["id"]
    assert memory_db["teaching_exposures"].count_documents({}) == 1


def test_same_item_retry_and_follow_up_excluded():
    session = {"session_id": "s4", "user_id": "u1"}
    prior = {
        "round": 1,
        "round_type": "sql",
        "config_json": {"problem_id": "sql-1"},
        "final_score": 70,
        "status": "submitted",
    }
    retry = {
        "round": 2,
        "round_type": "sql",
        "config_json": {"problem_id": "sql-1"},
    }
    d = evaluate_eligibility(
        session=session,
        round_doc=retry,
        exposures=[],
        prior_rounds=[prior],
        now=datetime.now(timezone.utc),
    )
    assert d["decision"] == EXCLUDED
    assert REASON_SAME_ITEM_RETRY in d["exclusion_reasons"]

    follow = {"round": 3, "is_follow_up": True, "round_type": "technical_short_answer"}
    d2 = evaluate_eligibility(
        session=session,
        round_doc=follow,
        exposures=[],
        prior_rounds=[prior],
        now=datetime.now(timezone.utc),
    )
    assert d2["decision"] == EXCLUDED
    assert REASON_FOLLOW_UP in d2["exclusion_reasons"]


def test_cross_session_window_boundary(memory_db):
    session_a = {"session_id": "sa", "user_id": "u1"}
    session_b = {"session_id": "sb", "user_id": "u1"}
    now = datetime.now(timezone.utc)
    record_teaching_exposure(
        memory_db,
        kind="hint",
        item_type="mcq",
        item_id="q9",
        session=session_a,
        user_id="u1",
        round_number=1,
        now=now - timedelta(hours=25),
    )
    exposures = list_exposures_for_eligibility(
        memory_db, session=session_b, user_id="u1", before=now
    )
    round_doc = {
        "round": 1,
        "round_type": "mcq",
        "question_context": {"questions": [{"id": "q9"}]},
    }
    d = evaluate_eligibility(
        session=session_b,
        round_doc=round_doc,
        exposures=exposures,
        prior_rounds=[],
        now=now,
    )
    # Outside 24h window → eligible (fresh related item).
    assert d["decision"] == ELIGIBLE

    record_teaching_exposure(
        memory_db,
        kind="hint",
        item_type="mcq",
        item_id="q9",
        session=session_a,
        user_id="u1",
        round_number=2,
        now=now - timedelta(hours=2),
        content_fingerprint="second",
    )
    exposures2 = list_exposures_for_eligibility(
        memory_db, session=session_b, user_id="u1", before=now
    )
    d2 = evaluate_eligibility(
        session=session_b,
        round_doc=round_doc,
        exposures=exposures2,
        prior_rounds=[],
        now=now,
    )
    assert d2["decision"] == EXCLUDED


def test_incomplete_history_is_unknown_not_clean():
    session = {"session_id": "s5", "user_id": "u1"}
    d = evaluate_eligibility(
        session=session,
        round_doc={"round": 1, "round_type": "technical_short_answer"},
        exposures=[],
        prior_rounds=[],
        now=datetime.now(timezone.utc),
        history_complete=False,
    )
    assert d["decision"] == "unknown"
    assert not is_assessment_eligible(
        {
            "assessment_eligibility": d["decision"],
            "eligibility_exclusion_reasons": d["exclusion_reasons"],
            "final_score": 50,
        }
    )


def test_legacy_rounds_read_as_legacy_unknown():
    info = read_persisted_eligibility({"final_score": 40, "assisted": False})
    assert info["decision"] == "legacy_unknown"
    assert info["legacy"] is True


def test_primary_metrics_exclude_assisted_and_keep_numerator_denominator():
    rounds = [
        {
            "final_score": 100,
            "assessment_eligibility": ELIGIBLE,
            "eligibility_policy_version": POLICY_VERSION,
        },
        {
            "final_score": 0,
            "assessment_eligibility": EXCLUDED,
            "eligibility_exclusion_reasons": [REASON_TEACHING_EXPOSURE],
            "assisted": True,
            "eligibility_policy_version": POLICY_VERSION,
        },
        {
            "final_score": 50,
            "is_follow_up": True,
            "assessment_eligibility": EXCLUDED,
            "eligibility_exclusion_reasons": [REASON_FOLLOW_UP],
            "eligibility_policy_version": POLICY_VERSION,
        },
    ]
    measured = measured_scores(rounds)
    eligible = assessment_eligible_scores(rounds)
    assert measured == [100.0, 0.0, 50.0]
    assert eligible == [100.0]
    assert sum(eligible) / len(eligible) == 100.0


def test_snapshot_v2_still_verifies_with_eligibility_fields():
    scored = {
        "round": 1,
        "round_type": "technical_short_answer",
        "skill": "DBMS",
        "question": "Q?",
        "answer_text": "A",
        "nlp_score": 50,
        "svm_label": "ok",
        "kg_score": 50,
        "ner_entities": [],
        "final_score": 55,
        "scoring_breakdown": {},
        "feedback": {"content": [], "strengths": [], "weakness": [], "next_step": ""},
        "elo_before": 1200,
        "elo_after": 1200,
        "difficulty": "medium",
        "difficulty_change": "same",
        "evidence_kind": "measured",
        "scoring_mode": "full",
        "evaluation_mode": None,
        "assessment_eligibility": ELIGIBLE,
        "eligibility_policy_version": POLICY_VERSION,
        "eligibility_exclusion_reasons": [],
        "config_json": {"attempt_policy": "single_submission_final", "review_policy": "none"},
        "submitted_at": datetime.now(timezone.utc),
        "question_context": {"source": "legacy"},
    }
    snap = freeze_attempt_snapshot(scored, {"scoring_schema_version": "1"})
    assert verify_attempt_snapshot(snap)
    assert snap["assessment_eligibility"] == ELIGIBLE


def test_follow_up_caps_and_capacity():
    session = {
        "session_id": "s6",
        "practice_mode": "coached_practice",
        "allow_optional_follow_ups": True,
        "total_rounds": 2,
        "expanded_plan": [
            {"round_type": "technical_short_answer", "block_id": "b1", "category": "interview"},
            {"round_type": "technical_short_answer", "block_id": "b1", "category": "interview"},
        ],
        "block_plan": [
            {
                "id": "b1",
                "category": "interview",
                "round_type": "technical_short_answer",
                "allow_optional_follow_ups": True,
            }
        ],
        "rounds": [
            {
                "round": 1,
                "block_id": "b1",
                "final_score": 40,
                "status": "submitted",
                "skill": "DBMS",
                "config_json": {},
            },
            {"round": 2, "block_id": "b1", "status": "in_progress"},
        ],
    }
    parent = session["rounds"][0]
    ok, reason = can_schedule_follow_up(session=session, parent_round_doc=parent)
    assert ok, reason
    entry = build_follow_up_plan_entry(
        parent_round_doc=parent,
        reviewed_bundle=None,
        clarification_prompt="Clarify indexes.",
    )
    assert entry["follow_up_scoring"] == "unreviewed"
    result = schedule_follow_up_in_session(session, parent_round_doc=parent, plan_entry=entry)
    assert result["scheduled"] is True
    assert result["total_rounds"] == 3

    # Second request for same parent fails.
    session2 = {
        **session,
        "expanded_plan": result["expanded_plan"],
        "total_rounds": result["total_rounds"],
        "rounds": session["rounds"]
        + [
            {
                "round": 3,
                "is_follow_up": True,
                "follow_up_parent_round": 1,
                "block_id": "b1",
            }
        ],
    }
    ok2, reason2 = can_schedule_follow_up(session=session2, parent_round_doc=parent)
    assert not ok2
    assert reason2 == "parent_follow_up_exists"


def test_no_capacity_skips_optional_without_dropping_mandatory():
    session = {
        "session_id": "s7",
        "practice_mode": "coached_practice",
        "allow_optional_follow_ups": True,
        "total_rounds": MAX_TOTAL_ROUNDS,
        "expanded_plan": [{"round_type": "technical_short_answer"}] * MAX_TOTAL_ROUNDS,
        "block_plan": [
            {
                "id": "b1",
                "category": "interview",
                "allow_optional_follow_ups": True,
            }
        ],
        "rounds": [
            {
                "round": 1,
                "block_id": "b1",
                "final_score": 10,
                "status": "submitted",
                "config_json": {},
            }
        ],
    }
    assert spare_capacity(session, 1) == 0
    ok, reason = can_schedule_follow_up(
        session=session, parent_round_doc=session["rounds"][0]
    )
    assert not ok
    assert reason == "no_capacity"


def test_concurrent_follow_up_requests_at_most_one(memory_db):
    session = {
        "session_id": "s8",
        "user_id": "u1",
        "practice_mode": "coached_practice",
        "allow_optional_follow_ups": True,
        "total_rounds": 1,
        "expanded_plan": [
            {"round_type": "technical_short_answer", "block_id": "b1", "category": "interview"}
        ],
        "block_plan": [
            {
                "id": "b1",
                "category": "interview",
                "allow_optional_follow_ups": True,
            }
        ],
        "rounds": [
            {
                "round": 1,
                "block_id": "b1",
                "final_score": 20,
                "status": "submitted",
                "skill": "DBMS",
                "config_json": {},
                "question_context": {"followups": ["Clarify X"]},
            }
        ],
    }
    memory_db["sessions"].insert_one(session)

    def _once():
        from backend.routes.follow_ups import request_follow_up
        from backend.routes.answer import _submit_locked

        # Direct schedule under lock mimics the route.
        with _submit_locked("s8"):
            live = memory_db["sessions"].find_one({"session_id": "s8"})
            parent = live["rounds"][0]
            entry = build_follow_up_plan_entry(
                parent_round_doc=parent,
                reviewed_bundle=None,
                clarification_prompt="Clarify X",
            )
            result = schedule_follow_up_in_session(
                live, parent_round_doc=parent, plan_entry=entry
            )
            if result.get("scheduled"):
                memory_db["sessions"].update_one(
                    {"session_id": "s8"},
                    {
                        "$set": {
                            "expanded_plan": result["expanded_plan"],
                            "total_rounds": result["total_rounds"],
                            "rounds": live["rounds"]
                            + [
                                {
                                    "round": result["total_rounds"],
                                    "is_follow_up": True,
                                    "follow_up_parent_round": 1,
                                    "block_id": "b1",
                                }
                            ],
                        }
                    },
                )
            return result

    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(lambda _: _once(), range(4)))
    scheduled = [r for r in results if r.get("scheduled")]
    assert len(scheduled) == 1
    final = memory_db["sessions"].find_one({"session_id": "s8"})
    assert final["total_rounds"] == 2
    assert sum(1 for r in final["rounds"] if r.get("is_follow_up")) == 1


def test_help_unavailable_does_not_fabricate_delivery(memory_db):
    # Generation-only path: no record_teaching_exposure call → zero rows.
    assert memory_db["teaching_exposures"].count_documents({}) == 0
    from modules.teaching_exposures import record_teaching_exposure as rec

    assert rec(memory_db, kind="not_a_real_kind", item_type="x", item_id="y") is None
    assert memory_db["teaching_exposures"].count_documents({}) == 0
