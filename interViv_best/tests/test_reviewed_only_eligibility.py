"""Phase 0.C: only an explicitly reviewed bundle counts toward assessment.

The decision reads the bundle label frozen in the round's question_context
when the question was served (never a live store lookup). Auto-checked,
generated, draft or unlabelled bundle rounds still get feedback but are
excluded: no Elo change and no readiness. Decisions already persisted on
past rounds are never recomputed.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from backend import config as app_config
from backend.main import app
from backend.routes.session import _normalize_question_payload
from modules import assistance_policy, bundle_store
from modules.assistance_policy import (
    ELIGIBLE,
    EXCLUDED,
    REASON_UNREVIEWED_CONTENT,
    evaluate_eligibility,
    is_primary_metric_round,
)
from modules.question_bundles import candidate_payload
from tests.test_slice1_inline_follow_ups import (  # noqa: F401  (fixture import)
    _APPROVE_REASON,
    _CALIB,
    _CHECK_OK,
    _headers,
    _make_user,
    _seed_bundle,
    slice1_sql_env,
)

FULL_ANSWER = (
    "Only one thread executes bytecode at a time because the mutex serializes bytecode, "
    "and blocking io releases lock so other threads run while waiting on syscalls."
)


def _start_one(client: TestClient, user: dict, topic: str) -> dict:
    start = client.post(
        "/session/start",
        headers=_headers(user),
        json={
            "blocks": [
                {
                    "round_type": "technical_short_answer",
                    "category": "interview",
                    "skills": ["Python"],
                    "topic": topic,
                    "difficulty": "medium",
                    "count": 1,
                    "practice_mode": "assessment",
                }
            ],
            "practice_mode": "assessment",
        },
    )
    assert start.status_code == 200, start.text
    return start.json()


def _answer(client: TestClient, user: dict, sid: str) -> dict:
    res = client.post(
        "/session/answer",
        headers=_headers(user),
        json={"session_id": sid, "round": 1, "answer_text": FULL_ANSWER},
    )
    assert res.status_code == 200, res.text
    return res.json()


def _approve(bundle_id: str) -> None:
    bundle_store.submit_for_review(bundle_id, 1, actor_id="test", reason="Submit for review")
    ch = bundle_store.get_version(bundle_id, 1)["content_hash"]
    for reviewer in ("rev-a", "rev-b"):
        bundle_store.record_decision(
            bundle_id, 1, reviewer_id=reviewer, content_hash=ch, decision="approve",
            checklist=_CHECK_OK, reasons=_APPROVE_REASON, calibration=_CALIB,
        )


# ── candidate_payload and served-label normalization ─────────────────────────


@pytest.mark.parametrize(
    "status, label",
    [
        ("reviewed", "reviewed_bundle"),
        ("auto_checked", "auto_checked_bundle"),
        ("generated", "generated_bundle"),
        ("draft", "draft_bundle"),
        (None, "unknown_bundle"),
    ],
)
def test_candidate_payload_labels_only_reviewed_as_reviewed(status, label) -> None:
    version_doc = {
        "bundle_id": "python.label", "version": 1, "content_hash": "h", "status": status,
        "content_json": {
            "category": "technical_short_answer", "skill": "Python", "topic": "T",
            "difficulty": "easy", "question": "Q?",
        },
    }
    assert candidate_payload(version_doc)["source"] == label


@pytest.mark.parametrize(
    "source, stored",
    [
        ("reviewed_bundle", "reviewed_bundle"),
        ("auto_checked_bundle", "auto_checked_bundle"),
        ("draft_bundle", "draft_bundle"),
        (None, "unknown_bundle"),
        ("something_else", "unknown_bundle"),
    ],
)
def test_served_bundle_label_is_never_upgraded_to_reviewed(source, stored) -> None:
    payload = {"question": "Q?", "bundle_id": "python.label", "version": 1, "content_hash": "h"}
    if source is not None:
        payload["source"] = source
    normalized = _normalize_question_payload(payload, skill="Python", sub_domain=None)
    assert normalized["source"] == stored


# ── policy unit behaviour ────────────────────────────────────────────────────


def _round(source: str | None, *, pinned: bool = True, **extra) -> dict:
    ctx: dict = {"question": "Q?", "topic": "T"}
    if source is not None:
        ctx["source"] = source
    if pinned:
        ctx.update({"bundle_id": "python.unit", "version": 1})
    return {"round": 1, "round_type": "technical_short_answer", "question": "Q?",
            "question_context": ctx, **extra}


@pytest.mark.parametrize(
    "source, pinned, decision",
    [
        ("reviewed_bundle", True, ELIGIBLE),
        ("auto_checked_bundle", True, EXCLUDED),
        ("generated_bundle", True, EXCLUDED),
        ("draft_bundle", True, EXCLUDED),
        ("unknown_bundle", True, EXCLUDED),
        (None, True, EXCLUDED),
        ("dataset", False, ELIGIBLE),  # bank question, no bundle pin: unchanged
    ],
)
def test_policy_decides_from_served_label(source, pinned, decision) -> None:
    session = {"session_id": "s1", "user_id": "u1"}
    res = evaluate_eligibility(session=session, round_doc=_round(source, pinned=pinned), exposures=[])
    assert res["decision"] == decision
    assert (REASON_UNREVIEWED_CONTENT in res["exclusion_reasons"]) is (decision == EXCLUDED)


def test_follow_up_reasons_are_unchanged_by_the_reviewed_rule() -> None:
    session = {"session_id": "s1", "user_id": "u1"}
    res = evaluate_eligibility(
        session=session,
        round_doc=_round("auto_checked_bundle", is_follow_up=True),
        exposures=[],
    )
    assert res["decision"] == EXCLUDED
    assert res["exclusion_reasons"] == ["follow_up"]


def test_past_rounds_keep_their_stored_eligibility() -> None:
    legacy = _round(
        "auto_checked_bundle",
        final_score=72.0,
        assessment_eligibility=ELIGIBLE,
        eligibility_policy_version="assistance_v1",
        eligibility_exclusion_reasons=[],
    )
    assert is_primary_metric_round(legacy) is True


# ── end to end ───────────────────────────────────────────────────────────────


def test_auto_checked_bundle_round_shows_feedback_but_is_excluded(slice1_sql_env) -> None:
    _seed_bundle("python.elig.auto", status="auto_checked", topic="EligAuto")
    client = TestClient(app)
    user = _make_user("elig-auto")
    sid = _start_one(client, user, "EligAuto")["session_id"]

    body = _answer(client, user, sid)
    assert body["assessment_eligibility"] == "excluded"
    assert REASON_UNREVIEWED_CONTENT in body["eligibility_exclusion_reasons"]
    assert isinstance(body["final_score"], (int, float))
    assert body["feedback"]
    assert float(body["elo_after"]) == float(app_config.get_settings().initial_elo)
    assert body["session_complete"] is True

    dash = client.get(f"/dashboard/{sid}", headers=_headers(user))
    assert dash.status_code == 200, dash.text
    dash_body = dash.json()
    round1 = dash_body["rounds"][0]
    assert round1["assessment_eligibility"] == "excluded"
    assert round1["final_score"] is not None
    assert dash_body["block_results"][0]["assessment_eligible_rounds"] == 0
    assert dash_body["overall_readiness_score"] is None


def test_reviewed_bundle_round_is_eligible(slice1_sql_env) -> None:
    _seed_bundle("python.elig.rev", status="reviewed", topic="EligRev")
    client = TestClient(app)
    user = _make_user("elig-rev")
    sid = _start_one(client, user, "EligRev")["session_id"]
    body = _answer(client, user, sid)
    assert body["assessment_eligibility"] == "eligible"
    assert float(body["elo_after"]) != float(app_config.get_settings().initial_elo)


def test_decision_uses_the_served_snapshot_not_a_live_lookup(slice1_sql_env) -> None:
    client = TestClient(app)

    # Served while auto_checked, reviewed before the answer: still excluded.
    _seed_bundle("python.elig.late", status="auto_checked", topic="EligLate")
    user = _make_user("elig-late")
    sid = _start_one(client, user, "EligLate")["session_id"]
    _approve("python.elig.late")
    assert bundle_store.get_version("python.elig.late", 1)["status"] == "reviewed"
    assert _answer(client, user, sid)["assessment_eligibility"] == "excluded"

    # Served while reviewed, retired before the answer: still eligible.
    _seed_bundle("python.elig.retired", status="reviewed", topic="EligRetired")
    user2 = _make_user("elig-retired")
    sid2 = _start_one(client, user2, "EligRetired")["session_id"]
    bundle_store.retire("python.elig.retired", 1, actor_id="admin", reason="Retired after serving.")
    assert _answer(client, user2, sid2)["assessment_eligibility"] == "eligible"


def test_round_frozen_eligible_before_the_rule_stays_eligible(slice1_sql_env, monkeypatch) -> None:
    _seed_bundle("python.elig.past", status="auto_checked", topic="EligPast")
    client = TestClient(app)
    user = _make_user("elig-past")
    sid = _start_one(client, user, "EligPast")["session_id"]

    # Submit under the previous policy (auto_checked counted).
    with monkeypatch.context() as previous_policy:
        previous_policy.setattr(assistance_policy, "is_unreviewed_bundle_round", lambda _round: False)
        body = _answer(client, user, sid)
    assert body["assessment_eligibility"] == "eligible"
    assert assistance_policy.is_unreviewed_bundle_round(
        {"question_context": {"source": "auto_checked_bundle", "bundle_id": "x", "version": 1}}
    ) is True

    # The current rule never rewrites the stored decision.
    dash = client.get(f"/dashboard/{sid}", headers=_headers(user))
    assert dash.status_code == 200, dash.text
    dash_body = dash.json()
    assert dash_body["rounds"][0]["assessment_eligibility"] == "eligible"
    assert dash_body["block_results"][0]["assessment_eligible_rounds"] == 1
    assert dash_body["overall_readiness_score"] == pytest.approx(body["final_score"], abs=0.05)


@pytest.mark.parametrize(
    "source, expected",
    [
        ("reviewed_bundle", "reviewed_bundle"),
        ("auto_checked_bundle", "auto_checked_bundle"),
        ("generated_bundle", "generated_bundle"),
        ("draft_bundle", "draft_bundle"),
        ("unknown_bundle", "unknown_bundle"),
        (None, "unknown_bundle"),
        ("something_else", "unknown_bundle"),
    ],
)
def test_attempt_snapshot_preserves_bundle_status_label(source, expected) -> None:
    from modules.attempt_snapshot import (
        _reference_from_context,
        freeze_attempt_snapshot,
        verify_attempt_snapshot,
    )

    ctx: dict = {
        "bundle_id": "python.label",
        "version": 1,
        "content_hash": "h",
    }
    if source is not None:
        ctx["source"] = source

    ref = _reference_from_context(ctx)
    assert ref == {
        "source": expected,
        "bundle_id": "python.label",
        "version": 1,
        "content_hash": "h",
    }

    snapshot = freeze_attempt_snapshot(
        {
            "round": 1,
            "round_type": "technical_short_answer",
            "skill": "Python",
            "question": "Q?",
            "answer_text": "A.",
            "final_score": 50.0,
            "feedback": {},
            "scoring_breakdown": {},
            "question_context": ctx,
            "config_json": {},
        },
        {"scoring_schema_version": "v-test"},
    )
    assert snapshot["reference"] == ref
    assert verify_attempt_snapshot(snapshot) is True
