"""Slice 1 tests: inline bundle follow-ups (staged_v1).

Verifies Q2, Q3, A4, A5, A6, opt-in gating (STAGED_INLINE_FOLLOW_UPS), and
preserved manual /follow-ups behavior strictly with fixture bundles and zero
outbound network calls.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

os.environ.setdefault("INTERVIV_USE_MEMORY_DB", "true")
os.environ.setdefault("JWT_SECRET_KEY", "test-secret-key-with-at-least-32-bytes!!")
os.environ.setdefault("LLM_LIVE_FETCH", "0")
os.environ.setdefault("JOBS_LIVE_FETCH", "0")

from backend import config as app_config  # noqa: E402
from backend.auth.security import create_access_token, hash_password  # noqa: E402
from backend.db import get_database, sqlalchemy_store  # noqa: E402
from backend.db.sqlalchemy_models import RoundRow, SessionRow  # noqa: E402
from backend.db.sqlalchemy_store import (  # noqa: E402
    SessionWriteConflict,
    _sessionmaker,
    create_all_for_smoke,
    get_engine,
    get_sqlalchemy_database,
    session_scope,
)
from backend.main import app  # noqa: E402
from modules import bundle_selector, bundle_store, follow_ups  # noqa: E402
from modules.bundle_store import REQUIRED_CHECKLIST  # noqa: E402
from tests.round_helpers import activate  # noqa: E402

_CHECK_OK = {k: True for k in REQUIRED_CHECKLIST}
_CALIB = {"difficulty": "medium"}
_APPROVE_REASON = "Reference answer and concept propositions match expected rubric."


def _clear_caches() -> None:
    app_config.get_settings.cache_clear()
    get_engine.cache_clear()
    _sessionmaker.cache_clear()
    get_sqlalchemy_database.cache_clear()


@pytest.fixture
def slice1_sql_env(monkeypatch, tmp_path: Path):
    """Isolated SQLite DB + STAGED_INLINE_FOLLOW_UPS=1 for end-to-end tests."""
    db_path = tmp_path / "slice1.db"
    audit_path = tmp_path / "followup_decisions.jsonl"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_path}")
    monkeypatch.setenv("INTERVIV_USE_MEMORY_DB", "false")
    monkeypatch.setenv("STAGED_INLINE_FOLLOW_UPS", "1")
    monkeypatch.setenv("REVIEWED_BUNDLES_ONLY", "false")
    monkeypatch.setenv("LLM_LIVE_FETCH", "0")
    monkeypatch.setenv("JOBS_LIVE_FETCH", "0")
    monkeypatch.setenv("FOLLOWUP_DECISIONS_AUDIT_PATH", str(audit_path))
    monkeypatch.setenv(
        "REJECTED_BUNDLES_AUDIT_PATH",
        str(tmp_path / "rejected_bundles.jsonl"),
    )
    _clear_caches()
    create_all_for_smoke()
    try:
        yield {
            "db": get_database(),
            "audit_path": audit_path,
            "db_path": db_path,
        }
    finally:
        try:
            get_engine().dispose()
        except Exception:
            pass
        _clear_caches()


@pytest.fixture
def slice1_memory_env(monkeypatch, tmp_path: Path):
    audit_path = tmp_path / "followup_decisions.jsonl"
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setenv("INTERVIV_USE_MEMORY_DB", "true")
    monkeypatch.setenv("STAGED_INLINE_FOLLOW_UPS", "1")
    monkeypatch.setenv("REVIEWED_BUNDLES_ONLY", "false")
    monkeypatch.setenv("FOLLOWUP_DECISIONS_AUDIT_PATH", str(audit_path))
    _clear_caches()
    bundle_store.reset_memory_store()
    yield {"audit_path": audit_path}
    bundle_store.reset_memory_store()
    _clear_caches()


def _make_user(prefix: str = "s1") -> dict[str, str]:
    db = get_database()
    user_id = str(uuid4())
    db["users"].insert_one(
        {
            "id": user_id,
            "email": f"{prefix}-{user_id[:8]}@example.com",
            "name": f"Test {prefix}",
            "password_hash": hash_password("passw0rd123"),
            "created_at": datetime.now(timezone.utc),
            "last_active_at": datetime.now(timezone.utc),
        }
    )
    return {"id": user_id, "token": create_access_token(user_id)}


def _headers(user: dict[str, str]) -> dict[str, str]:
    return {"Authorization": f"Bearer {user['token']}"}


def _fixture_bundle(
    bundle_id: str,
    *,
    skill: str = "Python",
    topic: str = "Concurrency",
    difficulty: str = "medium",
    question: str = "Explain how Python interpreter locking works across threads.",
    followups: list[dict[str, str]] | None = None,
    required_concepts: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    if required_concepts is None:
        required_concepts = [
            {
                "id": "bytecode_mutex",
                "descriptor": "Only one thread runs Python bytecode under the lock",
                "aliases": ["bytecode lock", "gil"],
                "expected_propositions": [
                    "one thread executes bytecode",
                    "mutex serializes bytecode",
                ],
            },
            {
                "id": "io_release",
                "descriptor": "Blocking I/O syscalls release the lock for other threads",
                "aliases": ["releases lock during io", "blocking io"],
                "expected_propositions": [
                    "blocking io releases lock",
                    "syscalls release lock",
                ],
            },
        ]
    if followups is None:
        followups = [
            {
                "prompt": "How does blocking I/O still overlap cleanly under the GIL?",
                "targets_concept": "io_release",
            },
            {
                "prompt": "Why does CPython serialize bytecode execution with the GIL?",
                "targets_concept": "bytecode_mutex",
            },
        ]
    return {
        "bundle_id": bundle_id,
        "version": 1,
        "skill": skill,
        "topic": topic,
        "difficulty": difficulty,
        "question": question,
        "reference_answer": (
            "CPython uses the GIL so only one thread executes Python bytecode at a "
            "time to protect reference counts. During blocking I/O syscalls, the "
            "runtime releases the lock so waiting threads make concurrent progress."
        ),
        "acceptable_variants": [
            "Only one thread executes bytecode at once while blocking I/O releases the lock."
        ],
        "keywords": ["gil", "bytecode", "mutex", "blocking io", "syscalls"],
        "required_concepts": required_concepts,
        "optional_concepts": [],
        "misconceptions": [],
        "depth_markers": ["reference counts"],
        "rubric_descriptors": {
            "coverage": "Covers bytecode mutex and I/O release.",
            "accuracy": "Accurate thread model.",
            "depth": "Explains reference counting and syscalls.",
            "clarity": "Clear structure.",
        },
        "followups": followups,
        "calibration_examples": [
            {
                "answer": (
                    "Only one thread executes bytecode at a time under the mutex lock, "
                    "and blocking I/O syscalls release the lock cleanly for concurrency."
                ),
                "author_level": 3,
                "expected_band": "Good",
            },
            {
                "answer": (
                    "Threads in Python automatically bypass every interpreter rule "
                    "regardless of locking, synchronization primitives, reference "
                    "counts, runtime boundaries, operating system schedulers, memory "
                    "models, queue synchronization, bytecode evaluation loops, socket "
                    "buffers, or execution constraints across every multi-core server "
                    "workload in modern production cloud clusters."
                ),
                "author_level": 0,
                "expected_band": "Poor",
            },
        ],
        "source": "llm_draft",
        "author": "llm:test-fixture",
        "attribution": {"note": "slice1-fixture"},
    }


def _seed_bundle(
    bundle_id: str,
    *,
    status: str = "auto_checked",
    **kwargs: Any,
) -> dict[str, Any]:
    doc = _fixture_bundle(bundle_id, **kwargs)
    initial = "draft" if status == "reviewed" else "generated"
    bundle_store.import_bundle(doc, actor_id="test-seed", initial_status=initial)
    if status == "reviewed":
        bundle_store.submit_for_review(
            bundle_id, 1, actor_id="test-seed", reason="Submit fixture for review"
        )
        ch = bundle_store.get_version(bundle_id, 1)["content_hash"]
        bundle_store.record_decision(
            bundle_id,
            1,
            reviewer_id="rev-1",
            content_hash=ch,
            decision="approve",
            checklist=_CHECK_OK,
            reasons=_APPROVE_REASON,
            calibration=_CALIB,
        )
        bundle_store.record_decision(
            bundle_id,
            1,
            reviewer_id="rev-2",
            content_hash=ch,
            decision="approve",
            checklist=_CHECK_OK,
            reasons=_APPROVE_REASON,
            calibration=_CALIB,
        )
    elif status == "auto_checked":
        bundle_store.transition_automated_check(
            bundle_id, 1, to_status="auto_checked", reason="Passed fixture check."
        )
    elif status == "rejected":
        bundle_store.transition_automated_check(
            bundle_id, 1, to_status="rejected", reason="Failed fixture check."
        )
    elif status != "generated":
        raise AssertionError(f"Unsupported test fixture status: {status}")
    return bundle_store.get_version(bundle_id, 1)


def _read_audit_rows(audit_path: Path) -> list[dict[str, Any]]:
    if not audit_path.exists():
        return []
    return [
        json.loads(line)
        for line in audit_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


# ── Setting, A4 status gating, and gap extraction unit tests ─────────────────


def test_setting_default_off_preserves_legacy_answer_flow(monkeypatch, tmp_path: Path):
    monkeypatch.delenv("STAGED_INLINE_FOLLOW_UPS", raising=False)
    _clear_caches()
    assert app_config.get_settings().staged_inline_follow_ups is False

    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'off.db'}")
    monkeypatch.setenv("INTERVIV_USE_MEMORY_DB", "false")
    monkeypatch.setenv("REVIEWED_BUNDLES_ONLY", "false")
    monkeypatch.setenv(
        "FOLLOWUP_DECISIONS_AUDIT_PATH", str(tmp_path / "audit_off.jsonl")
    )
    _clear_caches()
    create_all_for_smoke()
    try:
        _seed_bundle("python.s1.off", status="auto_checked", topic="Locks")
        client = TestClient(app)
        user = _make_user("off")
        start = client.post(
            "/session/start",
            headers=_headers(user),
            json={
                "blocks": [
                    {
                        "round_type": "technical_short_answer",
                        "category": "interview",
                        "skills": ["Python"],
                        "topic": "Locks",
                        "difficulty": "medium",
                        "count": 1,
                        "practice_mode": "coached_practice",
                    }
                ],
                "practice_mode": "coached_practice",
            },
        )
        assert start.status_code == 200, start.text
        sid = start.json()["session_id"]

        ans = client.post(
            "/session/answer",
            headers=_headers(user),
            json={
                "session_id": sid,
                "round": 1,
                "answer_text": "I think Python threads have some behavior here.",
            },
        )
        assert ans.status_code == 200, ans.text
        body = ans.json()
        assert body["follow_up_scheduled"] is False
        assert body["total_rounds"] == 1
        assert body["session_complete"] is True
        assert not (tmp_path / "audit_off.jsonl").exists()
    finally:
        get_engine().dispose()
        _clear_caches()


def test_a4_never_serves_generated_or_rejected_and_enforces_status_floor(
    slice1_memory_env, monkeypatch
):
    _seed_bundle("python.s1.gen", status="generated", topic="GenOnly", question="Gen Q?")
    _seed_bundle("python.s1.rej", status="rejected", topic="RejOnly", question="Rej Q?")

    # With flag ON (coached_practice floor = auto_checked), generated & rejected never serve.
    assert (
        bundle_selector.select_bundle_question(
            skill="Python", difficulty="medium", topic="GenOnly"
        )
        is None
    )
    assert (
        bundle_selector.select_bundle_question(
            skill="Python", difficulty="medium", topic="RejOnly"
        )
        is None
    )

    # With flag OFF, legacy select_bundle_question keeps serving generated (never rejected).
    monkeypatch.setenv("STAGED_INLINE_FOLLOW_UPS", "0")
    _clear_caches()
    gen_hit = bundle_selector.select_bundle_question(
        skill="Python", difficulty="medium", topic="GenOnly"
    )
    assert gen_hit is not None and gen_hit["bundle_id"] == "python.s1.gen"
    assert (
        bundle_selector.select_bundle_question(
            skill="Python", difficulty="medium", topic="RejOnly"
        )
        is None
    )

    # Restore flag ON: auto_checked serves cleanly; reviewed still beats auto_checked.
    monkeypatch.setenv("STAGED_INLINE_FOLLOW_UPS", "1")
    _clear_caches()
    _seed_bundle("python.s1.auto", status="auto_checked", topic="Tier", question="Auto Q?")
    hit_auto = bundle_selector.select_bundle_question(
        skill="Python", difficulty="medium", topic="Tier"
    )
    assert hit_auto is not None and hit_auto["bundle_id"] == "python.s1.auto"

    _seed_bundle("python.s1.rev", status="reviewed", topic="Tier", question="Rev Q?")
    hit_rev = bundle_selector.select_bundle_question(
        skill="Python", difficulty="medium", topic="Tier"
    )
    assert hit_rev is not None and hit_rev["bundle_id"] == "python.s1.rev"

    # decide_inline_bundle_follow_up also refuses generated/rejected bundles directly.
    base_session = {
        "session_id": "s-a4",
        "practice_mode": "coached_practice",
        "rounds": [],
        "total_rounds": 1,
    }
    for bad_id in ("python.s1.gen", "python.s1.rej"):
        parent = {
            "round": 1,
            "round_type": "technical_short_answer",
            "skill": "Python",
            "difficulty": "medium",
            "question_context": {"bundle_id": bad_id, "version": 1},
            "scoring_breakdown": {
                "concepts": {
                    "concept_match_trace": [
                        {
                            "concept": "bytecode_mutex",
                            "source": "bundle_v2",
                            "method": "not_demonstrated",
                            "status": "missed",
                            "matched": False,
                        }
                    ]
                }
            },
        }
        decision = follow_ups.decide_inline_bundle_follow_up(
            session=base_session, parent_round_doc=parent
        )
        assert decision["decision"] == "skipped"
        assert decision["reason"].startswith("disallowed_bundle_status:")

    # REVIEWED_BUNDLES_ONLY=true blocks auto_checked too, allowing reviewed only.
    monkeypatch.setenv("REVIEWED_BUNDLES_ONLY", "true")
    _clear_caches()
    auto_parent = {
        "round": 1,
        "round_type": "technical_short_answer",
        "skill": "Python",
        "difficulty": "medium",
        "question_context": {"bundle_id": "python.s1.auto", "version": 1},
        "scoring_breakdown": {
            "concepts": {
                "concept_match_trace": [
                    {
                        "concept": "bytecode_mutex",
                        "source": "bundle_v2",
                        "method": "not_demonstrated",
                        "status": "missed",
                        "matched": False,
                    }
                ]
            }
        },
    }
    d_auto = follow_ups.decide_inline_bundle_follow_up(
        session=base_session, parent_round_doc=auto_parent
    )
    assert d_auto["decision"] == "skipped"
    assert d_auto["reason"] == "disallowed_bundle_status:auto_checked"


def test_gap_priority_contradicted_beats_missing_and_uncertain_never_triggers(
    slice1_memory_env,
):
    # Bundle lists followups in order: [c_uncertain, c_missing, c_contradicted]
    _seed_bundle(
        "python.s1.prio",
        status="auto_checked",
        topic="Priority",
        followups=[
            {"prompt": "Clarify c1?", "targets_concept": "c_uncertain"},
            {"prompt": "Clarify c2 missing?", "targets_concept": "c_missing"},
            {"prompt": "Fix c3 contradiction?", "targets_concept": "c_contradicted"},
        ],
    )
    session = {
        "session_id": "s-prio",
        "practice_mode": "coached_practice",
        "rounds": [],
        "total_rounds": 2,
    }
    # Even though c_missing precedes c_contradicted in followups AND concepts["missing"]
    # contains legacy KG noise ("c_uncertain", "kg_noise"), contradicted MUST win.
    parent = {
        "round": 1,
        "round_type": "technical_short_answer",
        "skill": "Python",
        "difficulty": "medium",
        "question_context": {"bundle_id": "python.s1.prio", "version": 1},
        "scoring_breakdown": {
            "concepts": {
                "missing": ["c_uncertain", "kg_noise"],
                "concept_match_trace": [
                    {
                        "concept": "c_uncertain",
                        "source": "bundle_v2",
                        "method": "uncertain",
                        "status": "uncertain",
                        "matched": False,
                    },
                    {
                        "concept": "c_missing",
                        "source": "bundle_v2",
                        "method": "not_demonstrated",
                        "status": "missed",
                        "matched": False,
                    },
                    {
                        "concept": "c_contradicted",
                        "source": "bundle_v2",
                        "method": "contradicted",
                        "status": "missed",
                        "matched": False,
                    },
                ],
            }
        },
    }
    decision = follow_ups.decide_inline_bundle_follow_up(
        session=session, parent_round_doc=parent
    )
    assert decision["decision"] == "scheduled"
    assert decision["gap_concept"] == "c_contradicted"
    assert decision["gap_status"] == "contradicted"
    assert decision["chosen_prompt"] == "Fix c3 contradiction?"
    assert decision["targets_concept"] == "c_contradicted"

    # Uncertain ONLY (even with legacy KG noise in concepts["missing"]) -> NO follow-up.
    uncertain_only_parent = {
        "round": 1,
        "round_type": "technical_short_answer",
        "skill": "Python",
        "difficulty": "medium",
        "question_context": {"bundle_id": "python.s1.prio", "version": 1},
        "scoring_breakdown": {
            "concepts": {
                "missing": ["c_uncertain", "kg_noise"],
                "concept_match_trace": [
                    {
                        "concept": "c_uncertain",
                        "source": "bundle_v2",
                        "method": "uncertain",
                        "status": "uncertain",
                        "matched": False,
                    },
                    {
                        "concept": "c_missing",
                        "source": "bundle_v2",
                        "method": "supported",
                        "status": "matched",
                        "matched": True,
                    },
                ],
            }
        },
    }
    d_uncertain = follow_ups.decide_inline_bundle_follow_up(
        session=session, parent_round_doc=uncertain_only_parent
    )
    assert d_uncertain["decision"] == "skipped"
    assert d_uncertain["reason"] == "no_concept_gap"
    assert d_uncertain["chosen_prompt"] is None


def test_no_matching_target_never_falls_back_to_followup_zero(slice1_memory_env):
    # Followup targets ONLY io_release, NOT bytecode_mutex.
    _seed_bundle(
        "python.s1.nomatch",
        status="reviewed",
        topic="NoMatch",
        followups=[
            {"prompt": "Default zero prompt on io_release?", "targets_concept": "io_release"},
        ],
    )
    parent = {
        "round": 1,
        "round_type": "technical_short_answer",
        "skill": "Python",
        "difficulty": "medium",
        "question_context": {"bundle_id": "python.s1.nomatch", "version": 1},
        "scoring_breakdown": {
            "concepts": {
                "concept_match_trace": [
                    {
                        "concept": "bytecode_mutex",
                        "source": "bundle_v2",
                        "method": "not_demonstrated",
                        "status": "missed",
                        "matched": False,
                    },
                    {
                        "concept": "io_release",
                        "source": "bundle_v2",
                        "method": "supported",
                        "status": "matched",
                        "matched": True,
                    },
                ]
            }
        },
    }
    decision = follow_ups.decide_inline_bundle_follow_up(
        session={"session_id": "s-nm", "practice_mode": "coached_practice", "rounds": [], "total_rounds": 1},
        parent_round_doc=parent,
    )
    assert decision["decision"] == "skipped"
    assert decision["reason"] == "no_matching_followup_target"
    assert decision["chosen_prompt"] is None


# ── End-to-end Scorer v3 + SQLite splice, RoundRow identity, Elo, caps, retry ──


def test_end_to_end_real_v3_splice_preserves_round_rows_and_excludes_from_elo(
    slice1_sql_env,
):
    audit_path: Path = slice1_sql_env["audit_path"]
    # Bundle where required concept `io_release` has expected propositions that
    # a partial answer omitting I/O will miss cleanly in real Scorer v3.
    _seed_bundle(
        "python.s1.e2e.topic1",
        status="reviewed",
        topic="GIL Basics",
        question="Explain GIL bytecode execution and I/O release.",
    )

    client = TestClient(app)
    user = _make_user("e2e")
    start = client.post(
        "/session/start",
        headers=_headers(user),
        json={
            "blocks": [
                {
                    "round_type": "technical_short_answer",
                    "category": "interview",
                    "skills": ["Python"],
                    "topic": "GIL Basics",
                    "difficulty": "medium",
                    "count": 2,
                    "practice_mode": "coached_practice",
                }
            ],
            "practice_mode": "coached_practice",
        },
    )
    assert start.status_code == 200, start.text
    sid = start.json()["session_id"]

    # Seed second reviewed bundle before Round 3 is prepared so Round 1
    # deterministically asks topic1 and Round 3 asks topic2 (both reviewed).
    _seed_bundle(
        "python.s1.e2e.topic2",
        status="reviewed",
        topic="GIL Basics",
        question="How does Python garbage collection interact with locking?",
        required_concepts=[
            {
                "id": "cycle_gc",
                "descriptor": "One thread executes bytecode at once under the lock",
                "aliases": ["bytecode lock", "cycle collector"],
                "expected_propositions": ["one thread executes bytecode"],
            }
        ],
        followups=[
            {
                "prompt": "How does the cyclic collector identify reference cycles?",
                "targets_concept": "cycle_gc",
            }
        ],
    )

    with session_scope() as s:
        r1_row = (
            s.query(RoundRow)
            .filter(RoundRow.session_id == sid, RoundRow.round_number == 1)
            .one()
        )
        r1_pk = r1_row.id

    # Round 1 answer omits io_release completely -> real v3 produces not_demonstrated
    # on io_release and schedules the targeted io_release follow-up at round 2.
    r1_ans = client.post(
        "/session/answer",
        headers=_headers(user),
        json={
            "session_id": sid,
            "round": 1,
            "answer_text": "One thread executes bytecode at a time because the mutex serializes bytecode.",
        },
    )
    assert r1_ans.status_code == 200, r1_ans.text
    body1 = r1_ans.json()
    assert body1["follow_up_scheduled"] is True
    assert body1["next_round"] == 2
    assert body1["total_rounds"] == 3
    assert body1["session_status"] == "active"

    elo_after_r1 = float(body1["elo_after"])

    # Verify Round 1 Row PK unchanged, Round 2 is READY follow-up at parent+1, and
    # expanded_plan shifted unprepared mandatory round 2 -> 3 cleanly.
    with session_scope() as s:
        sess_row = s.query(SessionRow).filter(SessionRow.id == sid).one()
        rows = (
            s.query(RoundRow)
            .filter(RoundRow.session_id == sid)
            .order_by(RoundRow.round_number)
            .all()
        )
        assert [(r.round_number, r.id) for r in rows[:1]] == [(1, r1_pk)]
        assert [r.round_number for r in rows] == [1, 2]
        assert rows[1].status == "ready"
        assert rows[1].is_follow_up is True
        assert rows[1].follow_up_parent_round == 1
        assert rows[1].question == "How does blocking I/O still overlap cleanly under the GIL?"
        assert rows[1].private_meta_json["follow_up_scoring"] == "reviewed"
        assert rows[1].private_meta_json["targets_concept"] == "io_release"
        assert rows[0].private_meta_json["follow_up_decision"]["decision"] == "scheduled"
        assert rows[0].private_meta_json["follow_up_decision"]["gap_concept"] == "io_release"
        plan = sess_row.expanded_plan_json
        assert [(p["round"], bool(p.get("is_follow_up"))) for p in plan] == [
            (1, False),
            (2, True),
            (3, False),
        ]

    # Activate and submit Round 2 (the inline follow-up): scored, NO Elo change,
    # NO nested follow-up, and shifted round 3 prepares cleanly.
    act2 = activate(client, _headers(user), sid, 2)
    assert act2["question"] == "How does blocking I/O still overlap cleanly under the GIL?"
    with session_scope() as s:
        r2_qctx = (
            s.query(RoundRow)
            .filter(RoundRow.session_id == sid, RoundRow.round_number == 2)
            .one()
            .question_context
        )
        assert r2_qctx["source"] == "reviewed_bundle"
        assert r2_qctx["bundle_id"] == "python.s1.e2e.topic1"
        assert r2_qctx["followups"] == []

    r2_ans = client.post(
        "/session/answer",
        headers=_headers(user),
        json={
            "session_id": sid,
            "round": 2,
            "answer_text": "Blocking I/O syscalls release the lock so other threads execute.",
        },
    )
    assert r2_ans.status_code == 200, r2_ans.text
    body2 = r2_ans.json()
    assert body2["final_score"] is not None
    assert body2["is_follow_up"] is True
    assert body2["assessment_eligibility"] != "eligible"
    assert body2["elo_after"] == elo_after_r1
    assert body2["follow_up_scheduled"] is False
    assert body2["next_round"] == 3
    assert body2["total_rounds"] == 3

    # Activate and submit shifted mandatory Round 3 cleanly (with no gap).
    act3 = activate(client, _headers(user), sid, 3)
    assert act3["round"] == 3
    r3_ans = client.post(
        "/session/answer",
        headers=_headers(user),
        json={
            "session_id": sid,
            "round": 3,
            "answer_text": "One thread executes bytecode at once cleanly.",
        },
    )
    assert r3_ans.status_code == 200, r3_ans.text
    body3 = r3_ans.json()
    assert body3["session_complete"] is True

    # Readiness score averages eligible rounds (1 and 3) and EXCLUDES follow-up round 2.
    live_sess = slice1_sql_env["db"]["sessions"].find_one({"session_id": sid})
    expected_mean = round((float(body1["final_score"]) + float(body3["final_score"])) / 2.0, 2)
    assert live_sess["overall_readiness_score"] == pytest.approx(expected_mean, abs=0.05)

    # Feedback on round 1 must never leak follow_up_decision private meta.
    fb1 = client.get(f"/session/{sid}/rounds/1/feedback", headers=_headers(user))
    assert fb1.status_code == 200
    assert "follow_up_decision" not in fb1.json()

    # Audit log has one entry per submitted technical round (3 entries: scheduled, skipped, skipped).
    audit_rows = _read_audit_rows(audit_path)
    assert [(row["parent_round"], row["decision"]) for row in audit_rows] == [
        (1, "scheduled"),
        (2, "skipped"),
        (3, "skipped"),
    ]


def test_real_v3_contradiction_wins_and_no_match_skips_end_to_end(slice1_sql_env):
    # Bundle where concept A is contradicted by wrong statement while concept B is missing.
    _seed_bundle(
        "python.s1.contradict",
        status="auto_checked",
        topic="Threads",
        question="Explain thread bytecode execution and I/O lock release.",
        required_concepts=[
            {
                "id": "io_release",
                "descriptor": "Blocking I/O releases the lock",
                "aliases": ["blocking io"],
                "expected_propositions": ["blocking io releases lock"],
            },
            {
                "id": "bytecode_mutex",
                "descriptor": "Threads cannot run parallel bytecode without releasing lock",
                "aliases": ["bytecode lock", "python threads"],
                "expected_propositions": ["python threads run parallel bytecode simultaneously"],
            },
        ],
        followups=[
            {"prompt": "Followup missing io_release", "targets_concept": "io_release"},
            {"prompt": "Clarify contradicted bytecode_mutex", "targets_concept": "bytecode_mutex"},
        ],
    )
    client = TestClient(app)
    user = _make_user("contr")
    start = client.post(
        "/session/start",
        headers=_headers(user),
        json={
            "blocks": [
                {
                    "round_type": "technical_short_answer",
                    "category": "interview",
                    "skills": ["Python"],
                    "topic": "Threads",
                    "difficulty": "medium",
                    "count": 1,
                    "practice_mode": "coached_practice",
                }
            ],
            "practice_mode": "coached_practice",
        },
    )
    assert start.status_code == 200, start.text
    sid = start.json()["session_id"]

    # Contradict `bytecode_mutex` (negation flip in concept_evaluator_v2 -> contradicted)
    # while leaving `io_release` omitted (`not_demonstrated`).
    ans = client.post(
        "/session/answer",
        headers=_headers(user),
        json={
            "session_id": sid,
            "round": 1,
            "answer_text": "Python threads do not run parallel bytecode simultaneously in interpreters.",
        },
    )
    assert ans.status_code == 200, ans.text
    body = ans.json()
    assert body["follow_up_scheduled"] is True
    assert body["next_round"] == 2
    assert body["total_rounds"] == 2

    with session_scope() as s:
        rows = (
            s.query(RoundRow)
            .filter(RoundRow.session_id == sid)
            .order_by(RoundRow.round_number)
            .all()
        )
        decision = rows[0].private_meta_json["follow_up_decision"]
        assert decision["gap_concept"] == "bytecode_mutex"
        assert decision["gap_status"] == "contradicted"
        assert rows[1].question == "Clarify contradicted bytecode_mutex"


def test_block_cap_two_followups_enforced_end_to_end(slice1_sql_env):
    _seed_bundle("python.s1.cap.a", status="auto_checked", topic="CapTopic", question="Q1 GIL?")
    _seed_bundle("python.s1.cap.b", status="auto_checked", topic="CapTopic", question="Q2 GIL?")
    _seed_bundle("python.s1.cap.c", status="auto_checked", topic="CapTopic", question="Q3 GIL?")

    client = TestClient(app)
    user = _make_user("cap")
    start = client.post(
        "/session/start",
        headers=_headers(user),
        json={
            "blocks": [
                {
                    "round_type": "technical_short_answer",
                    "category": "interview",
                    "skills": ["Python"],
                    "topic": "CapTopic",
                    "difficulty": "medium",
                    "count": 3,
                    "practice_mode": "coached_practice",
                }
            ],
            "practice_mode": "coached_practice",
        },
    )
    assert start.status_code == 200, start.text
    sid = start.json()["session_id"]

    # Round 1 (gap -> follow-up #1 inserted at round 2)
    r1 = client.post(
        "/session/answer",
        headers=_headers(user),
        json={"session_id": sid, "round": 1, "answer_text": "Short unclear answer."},
    )
    assert r1.status_code == 200 and r1.json()["follow_up_scheduled"] is True
    assert r1.json()["total_rounds"] == 4

    # Round 2 (follow-up #1 -> no trigger)
    activate(client, _headers(user), sid, 2)
    r2 = client.post(
        "/session/answer",
        headers=_headers(user),
        json={"session_id": sid, "round": 2, "answer_text": "Short reply."},
    )
    assert r2.status_code == 200 and r2.json()["follow_up_scheduled"] is False

    # Round 3 (orig round 2; gap -> follow-up #2 inserted at round 4)
    activate(client, _headers(user), sid, 3)
    r3 = client.post(
        "/session/answer",
        headers=_headers(user),
        json={"session_id": sid, "round": 3, "answer_text": "Short unclear answer."},
    )
    assert r3.status_code == 200 and r3.json()["follow_up_scheduled"] is True
    assert r3.json()["total_rounds"] == 5

    # Round 4 (follow-up #2 -> no trigger)
    activate(client, _headers(user), sid, 4)
    r4 = client.post(
        "/session/answer",
        headers=_headers(user),
        json={"session_id": sid, "round": 4, "answer_text": "Short reply."},
    )
    assert r4.status_code == 200 and r4.json()["follow_up_scheduled"] is False

    # Round 5 (orig round 3; has gap, but block cap = 2 already reached -> skipped!)
    activate(client, _headers(user), sid, 5)
    r5 = client.post(
        "/session/answer",
        headers=_headers(user),
        json={"session_id": sid, "round": 5, "answer_text": "Short unclear answer."},
    )
    assert r5.status_code == 200
    body5 = r5.json()
    assert body5["follow_up_scheduled"] is False
    assert body5["total_rounds"] == 5
    assert body5["session_complete"] is True

    with session_scope() as s:
        row5 = (
            s.query(RoundRow)
            .filter(RoundRow.session_id == sid, RoundRow.round_number == 5)
            .one()
        )
        assert row5.private_meta_json["follow_up_decision"]["reason"] == "block_cap_reached"


def test_assessment_mode_never_triggers_inline_follow_ups(slice1_sql_env):
    _seed_bundle("python.s1.assess", status="reviewed", topic="AssessTopic", question="Assess Q?")
    client = TestClient(app)
    user = _make_user("assess")
    start = client.post(
        "/session/start",
        headers=_headers(user),
        json={
            "blocks": [
                {
                    "round_type": "technical_short_answer",
                    "category": "interview",
                    "skills": ["Python"],
                    "topic": "AssessTopic",
                    "difficulty": "medium",
                    "count": 1,
                    "allow_optional_follow_ups": True,
                    "practice_mode": "assessment",
                }
            ],
            "practice_mode": "assessment",
        },
    )
    assert start.status_code == 200, start.text
    sid = start.json()["session_id"]

    ans = client.post(
        "/session/answer",
        headers=_headers(user),
        json={"session_id": sid, "round": 1, "answer_text": "Completely missing concepts."},
    )
    assert ans.status_code == 200, ans.text
    body = ans.json()
    assert body["follow_up_scheduled"] is False
    assert body["total_rounds"] == 1
    assert body["session_complete"] is True

    audit_rows = _read_audit_rows(slice1_sql_env["audit_path"])
    assert len(audit_rows) == 1
    assert audit_rows[0]["decision"] == "skipped"
    assert audit_rows[0]["reason"] == "practice_mode_assessment"


def test_retry_idempotency_under_session_write_conflict(slice1_sql_env, monkeypatch):
    _seed_bundle("python.s1.retry", status="auto_checked", topic="RetryTopic", question="Retry Q?")
    client = TestClient(app)
    user = _make_user("retry")
    start = client.post(
        "/session/start",
        headers=_headers(user),
        json={
            "blocks": [
                {
                    "round_type": "technical_short_answer",
                    "category": "interview",
                    "skills": ["Python"],
                    "topic": "RetryTopic",
                    "difficulty": "medium",
                    "count": 2,
                    "practice_mode": "coached_practice",
                }
            ],
            "practice_mode": "coached_practice",
        },
    )
    assert start.status_code == 200, start.text
    sid = start.json()["session_id"]

    # Force a SessionWriteConflict on the first attempt's final commit (which updates total_rounds)
    # while leaving the pre-score claim commit untouched.
    original_update = sqlalchemy_store._SessionCollection.update_one
    raised = {"count": 0}

    def flaky_update(self, query, update, upsert=False, *, expected_revision=None):
        set_keys = set(((update or {}).get("$set") or {}).keys())
        if "last_round" in set_keys and raised["count"] == 0:
            raised["count"] += 1
            raise SessionWriteConflict("simulated contention on final commit")
        return original_update(
            self, query, update, upsert, expected_revision=expected_revision
        )

    monkeypatch.setattr(sqlalchemy_store._SessionCollection, "update_one", flaky_update)

    ans = client.post(
        "/session/answer",
        headers=_headers(user),
        json={"session_id": sid, "round": 1, "answer_text": "Only one concept unclear."},
    )
    assert ans.status_code == 200, ans.text
    assert raised["count"] == 1
    body = ans.json()
    assert body["follow_up_scheduled"] is True
    assert body["total_rounds"] == 3

    exposures = slice1_sql_env["db"]["teaching_exposures"].find({"session_id": sid})
    follow_exposures = [e for e in exposures if e.get("content_kind") == "follow_up_prompt"]
    assert len(follow_exposures) == 1

    # Retried commit must emit ONLY ONE audit log entry.
    audit_rows = _read_audit_rows(slice1_sql_env["audit_path"])
    assert len(audit_rows) == 1
    assert audit_rows[0]["decision"] == "scheduled"

    with session_scope() as s:
        sess_row = s.query(SessionRow).filter(SessionRow.id == sid).one()
        follow_plan_entries = [
            e for e in sess_row.expanded_plan_json if e.get("is_follow_up")
        ]
        assert len(follow_plan_entries) == 1
        assert follow_plan_entries[0]["round"] == 2

    # Second idempotency check: if a racing worker ALREADY committed the inline
    # follow-up for parent_round=1 before reload, maybe_apply_inline_bundle_follow_up
    # sees already_has_follow_up and never inserts a duplicate.
    live_session = slice1_sql_env["db"]["sessions"].find_one({"session_id": sid})
    res_dup = follow_ups.maybe_apply_inline_bundle_follow_up(
        session=dict(live_session),
        active_round=dict(live_session["rounds"][0]),
        rounds=list(live_session["rounds"]),
        total_rounds=int(live_session["total_rounds"]),
    )
    assert res_dup["scheduled"] is False
    assert res_dup["decision_record"]["reason"] == "already_has_follow_up"


def test_splice_refuses_if_next_round_row_already_prepared_never_renumbers(
    slice1_memory_env,
):
    session = {
        "session_id": "s-nopre",
        "practice_mode": "coached_practice",
        "total_rounds": 2,
        "rounds": [
            {"round": 1, "round_type": "technical_short_answer", "skill": "Python"},
            {"round": 2, "round_type": "technical_short_answer", "skill": "Python"},
        ],
        "expanded_plan": [
            {"round": 1, "round_type": "technical_short_answer", "skill": "Python"},
            {"round": 2, "round_type": "technical_short_answer", "skill": "Python"},
        ],
    }
    res = follow_ups.splice_inline_follow_up_in_session(
        session=session,
        parent_round_doc=session["rounds"][0],
        decision_result={
            "decision": "scheduled",
            "reason": "gap_missing",
            "bundle_id": "b1",
            "version": 1,
            "follow_up_scoring": "reviewed",
            "chosen_prompt": "Clarify?",
            "targets_concept": "c1",
            "gap_concept": "c1",
            "gap_status": "missing",
        },
    )
    assert res["scheduled"] is False
    assert res["reason"] == "next_round_already_prepared"
    assert [r["round"] for r in session["rounds"]] == [1, 2]


def test_manual_follow_up_endpoint_keeps_unreviewed_unscored_behavior(
    slice1_sql_env,
):
    client = TestClient(app)
    user = _make_user("manual")
    start = client.post(
        "/session/start",
        headers=_headers(user),
        json={
            "blocks": [
                {
                    "round_type": "technical_short_answer",
                    "category": "interview",
                    "skills": ["DBMS"],
                    "count": 2,
                    "allow_optional_follow_ups": True,
                    "practice_mode": "coached_practice",
                }
            ],
            "practice_mode": "coached_practice",
        },
    )
    assert start.status_code == 200, start.text
    sid = start.json()["session_id"]

    # Round 1 from offline CSV (no pinned bundle -> inline skips cleanly, prepares round 2)
    r1 = client.post(
        "/session/answer",
        headers=_headers(user),
        json={"session_id": sid, "round": 1, "answer_text": "Indexes speed up lookups."},
    )
    assert r1.status_code == 200, r1.text
    assert r1.json()["follow_up_scheduled"] is False

    # Manual /follow-ups still appends an unreviewed, unscored follow-up at round 3.
    manual = client.post(
        f"/session/{sid}/follow-ups",
        headers=_headers(user),
        json={
            "parent_round": 1,
            "reviewed": None,
            "accept_eligibility_consequence": True,
        },
    )
    assert manual.status_code == 200, manual.text
    mbody = manual.json()
    assert mbody["scheduled"] is True
    assert mbody["total_rounds"] == 3
    assert mbody["follow_up_scoring"] == "unreviewed"

    activate(client, _headers(user), sid, 2)
    r2 = client.post(
        "/session/answer",
        headers=_headers(user),
        json={"session_id": sid, "round": 2, "answer_text": "B-trees keep keys sorted."},
    )
    assert r2.status_code == 200, r2.text
    assert r2.json()["next_round"] == 3

    activate(client, _headers(user), sid, 3)
    r3 = client.post(
        "/session/answer",
        headers=_headers(user),
        json={"session_id": sid, "round": 3, "answer_text": "Manual follow-up clarification."},
    )
    assert r3.status_code == 200, r3.text
    assert r3.json()["final_score"] is None
    assert r3.json()["is_follow_up"] is True


@pytest.mark.parametrize("staged_flag", ["0", "1"])
def test_bundle_selected_with_non_empty_target_concepts_flag_off_and_on(
    monkeypatch, tmp_path: Path, staged_flag: str
):
    """F3: Bundle selection still works when target_concepts is set and topic has no CSV rows."""
    from modules.concept_mastery import ConceptMastery
    from modules import question_runtime as qr

    db_path = tmp_path / f"f3_{staged_flag}.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_path}")
    monkeypatch.setenv("INTERVIV_USE_MEMORY_DB", "false")
    monkeypatch.setenv("STAGED_INLINE_FOLLOW_UPS", staged_flag)
    monkeypatch.setenv("REVIEWED_BUNDLES_ONLY", "false")
    monkeypatch.setenv("LLM_LIVE_FETCH", "0")
    monkeypatch.setenv(
        "FOLLOWUP_DECISIONS_AUDIT_PATH", str(tmp_path / f"f3_audit_{staged_flag}.jsonl")
    )
    _clear_caches()
    create_all_for_smoke()
    try:
        _seed_bundle(
            "custom.f3.01",
            status="auto_checked",
            skill="Product Positioning",
            topic="PositioningMatrix",
            question="How do you position an enterprise workflow product?",
        )
        _seed_bundle(
            "custom.f3.02",
            status="auto_checked",
            skill="Product Positioning",
            topic="PositioningMatrix",
            question="How do you validate differentiation against incumbent tools?",
        )
        client = TestClient(app)
        user = _make_user(f"f3-{staged_flag}")

        # Pre-populate ConceptMastery so adaptive_question_selector emits non-empty target_concepts.
        ConceptMastery().update_from_round(
            user_id=user["id"],
            skill="Product Positioning",
            covered_concepts=[],
            missing_concepts=["positioning_anchor"],
        )

        # Direct generate_question with non-empty target_concepts also selects the bundle.
        qr_hit = qr.generate_question(
            "Product Positioning",
            "PositioningMatrix",
            "medium",
            asked=[],
            target_concepts=["positioning_anchor"],
        )
        assert qr_hit["bundle_id"] == "custom.f3.01"

        start = client.post(
            "/session/start",
            headers=_headers(user),
            json={
                "blocks": [
                    {
                        "round_type": "technical_short_answer",
                        "category": "interview",
                        "skills": ["Product Positioning"],
                        "topic": "PositioningMatrix",
                        "difficulty": "medium",
                        "count": 2,
                        "practice_mode": "assessment",
                    }
                ],
                "practice_mode": "assessment",
            },
        )
        assert start.status_code == 200, start.text
        sid = start.json()["session_id"]
        assert start.json()["question_context"]["bundle_id"] == "custom.f3.01"

        ans1 = client.post(
            "/session/answer",
            headers=_headers(user),
            json={
                "session_id": sid,
                "round": 1,
                "answer_text": "Weak unclear answer.",
            },
        )
        assert ans1.status_code == 200, ans1.text
        body = ans1.json()
        assert body["progression_blocked"] is False
        assert body["session_status"] == "active"
        assert body["next_round"] == 2

        act2 = activate(client, _headers(user), sid, 2)
        assert (
            act2["question"]
            == "How do you validate differentiation against incumbent tools?"
        )
    finally:
        try:
            get_engine().dispose()
        except Exception:
            pass
        _clear_caches()
