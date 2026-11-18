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

    # With flag OFF too (F4: trust floor decoupled from follow-up flag), generated & rejected never serve.
    monkeypatch.setenv("STAGED_INLINE_FOLLOW_UPS", "0")
    _clear_caches()
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
    assert body2["final_score"] is None
    assert "scoring_breakdown" not in body2
    assert body2["rubric"] == {}
    assert body2["score_explanation"] == {}
    assert body2["follow_up_outcome"]["targets_concept"] == "io_release"
    assert body2["follow_up_outcome"]["demonstrated"] is True
    joined_fb2 = " ".join(body2["feedback"]["content"]).lower()
    assert body2["follow_up_outcome"]["concept_label"].lower() in joined_fb2
    assert "demonstrated" in joined_fb2
    assert "very brief" not in joined_fb2
    assert "lacked specific technical keywords" not in joined_fb2
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


def test_f4_incomplete_inline_live_generation_leftover_is_never_served(
    monkeypatch,
):
    """F4: even if inline live generation aborts after importing a generated bundle, it is never served."""
    from backend.routes import session as session_routes
    from modules import bundle_generator

    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setenv("INTERVIV_USE_MEMORY_DB", "true")
    monkeypatch.setenv("STAGED_INLINE_FOLLOW_UPS", "0")
    monkeypatch.setenv("REVIEWED_BUNDLES_ONLY", "false")
    _clear_caches()
    bundle_store.reset_memory_store()

    # Simulate an aborted inline generation run leaving a status="generated" bundle in DB.
    _seed_bundle(
        "custom.f4.aborted",
        status="generated",
        skill="Product Positioning",
        topic="AbortGen",
        question="Leftover generated prompt?",
    )

    def fail_step_e(*, skill: str, topic: str, difficulty: str, role: str | None = None, **kwargs):
        raise RuntimeError("simulated Step E outage after initial import")

    monkeypatch.setattr(bundle_generator, "generate_and_check_bundle", fail_step_e)
    monkeypatch.setattr(bundle_generator, "_LLM_OVERRIDE", lambda *a, **kw: "{}")
    try:
        with pytest.raises(RuntimeError, match="simulated Step E outage"):
            session_routes._maybe_prepare_opening_bundle(
                skill="Product Positioning",
                topic="AbortGen",
                difficulty="medium",
                role=None,
            )
        # Even with STAGED_INLINE_FOLLOW_UPS=0, leftover generated bundle is NEVER served.
        assert (
            bundle_selector.select_bundle_question(
                skill="Product Positioning",
                difficulty="medium",
                asked=[],
                topic="AbortGen",
            )
            is None
        )
    finally:
        bundle_generator.set_bundle_llm_override(None)
        bundle_store.reset_memory_store()
        _clear_caches()


def test_f5_seed_demo_bundles_guard_and_idempotency(monkeypatch, tmp_path: Path):
    """F5: seed_demo_bundles refuses protected DB and interviv.db, seeds demo_fixture idempotently."""
    from scripts import pregenerate_bundles, seed_demo_bundles

    # 1. Refuses unset / memory / interviv.db / protected DB (including symlink)
    for bad_url in (
        "",
        "sqlite:///:memory:",
        f"sqlite:///{tmp_path / 'interviv.db'}",
        f"sqlite:///{pregenerate_bundles._protected_local_db_path()}",
    ):
        monkeypatch.setenv("DATABASE_URL", bad_url)
        _clear_caches()
        with pytest.raises(RuntimeError, match="Refusing to run"):
            seed_demo_bundles.seed_demo_bundles()

    fake_real = tmp_path / "real-target.sqlite3"
    fake_real.write_bytes(b"")
    symlink_target = tmp_path / "link-to-protected.sqlite3"
    symlink_target.symlink_to(fake_real)
    monkeypatch.setattr(pregenerate_bundles, "_protected_local_db_path", lambda: fake_real.resolve())
    monkeypatch.setattr(seed_demo_bundles, "_protected_local_db_path", lambda: fake_real.resolve())
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{symlink_target}")
    _clear_caches()
    with pytest.raises(RuntimeError, match="Refusing to run"):
        seed_demo_bundles.seed_demo_bundles()
    assert seed_demo_bundles.main([]) == 2

    # 2. Succeeds idempotently on a clean SQLite copy path
    demo_db = tmp_path / "interviv-copy.sqlite3"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{demo_db}")
    monkeypatch.setenv("INTERVIV_USE_MEMORY_DB", "false")
    _clear_caches()
    create_all_for_smoke()
    try:
        first = seed_demo_bundles.seed_demo_bundles()
        assert len(first) == 3
        assert all(item["status"] == "auto_checked" for item in first)
        assert all(item["origin"] == "demo_fixture" for item in first)
        assert all(item["import_result"] == "created" for item in first)

        for item in first:
            stored = bundle_store.get_version(item["bundle_id"], item["version"])
            attr = stored["attribution_json"]
            assert attr.get("origin") == "demo_fixture"
            assert attr.get("demo_fixture") is True
            assert attr.get("generated_by_model") is None

        second = seed_demo_bundles.seed_demo_bundles()
        assert all(item["import_result"] == "unchanged" for item in second)
    finally:
        get_engine().dispose()
        _clear_caches()


def test_f5_demo_bundles_end_to_end_frontend_payload_shape(monkeypatch, tmp_path: Path):
    """F5: verify exact /session/answer + /activate payloads the frontend receives on splice."""
    from scripts import seed_demo_bundles

    demo_db = tmp_path / "interviv-demo-copy.sqlite3"
    audit_path = tmp_path / "f5_audit.jsonl"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{demo_db}")
    monkeypatch.setenv("INTERVIV_USE_MEMORY_DB", "false")
    monkeypatch.setenv("STAGED_INLINE_FOLLOW_UPS", "1")
    monkeypatch.setenv("REVIEWED_BUNDLES_ONLY", "false")
    monkeypatch.setenv("LLM_LIVE_FETCH", "0")
    monkeypatch.setenv("FOLLOWUP_DECISIONS_AUDIT_PATH", str(audit_path))
    _clear_caches()
    create_all_for_smoke()
    try:
        seed_demo_bundles.seed_demo_bundles()
        client = TestClient(app)
        user = _make_user("f5-ui")

        start = client.post(
            "/session/start",
            headers=_headers(user),
            json={
                "skills": ["Python"],
                "rounds_per_skill": 2,
                "practice_mode": "coached_practice",
            },
        )
        assert start.status_code == 200, start.text
        start_body = start.json()
        sid = start_body["session_id"]
        assert start_body["total_rounds"] == 2
        assert start_body["question_context"]["bundle_id"] == "demo.python.01_gil.v1"

        ans = client.post(
            "/session/answer",
            headers=_headers(user),
            json={
                "session_id": sid,
                "round": 1,
                "answer_text": (
                    "Only one thread executes bytecode at a time because the mutex "
                    "serializes bytecode execution."
                ),
            },
        )
        assert ans.status_code == 200, ans.text
        ans_body = ans.json()
        assert ans_body["follow_up_scheduled"] is True
        assert ans_body["total_rounds"] == 3
        assert ans_body["next_round"] == 2
        assert ans_body["next_round_type"] == "technical_short_answer"
        assert ans_body["next_round_status"] == "ready"
        assert ans_body["next_skill"] == "Python"
        assert ans_body["session_status"] == "active"
        assert ans_body["session_complete"] is False

        act = client.post(f"/session/{sid}/rounds/2/activate", headers=_headers(user))
        assert act.status_code == 200, act.text
        act_body = act.json()
        active_round = act_body["active_round"]
        assert act_body["total_rounds"] == 3
        assert active_round["round"] == 2
        assert active_round["status"] == "in_progress"
        assert active_round["is_follow_up"] is True
        assert active_round["follow_up_parent_round"] == 1
        assert active_round["skill"] == "Python"
        assert (
            active_round["question"]
            == "Follow-up: Why can blocking I/O threads still overlap cleanly even while CPython enforces the GIL?"
        )
        assert active_round["question_context"]["bundle_id"] == "demo.python.01_gil.v1"
        assert "targets_concept" not in active_round
    finally:
        get_engine().dispose()
        _clear_caches()


@pytest.mark.parametrize(
    ("followup_answer", "expected_demonstrated"),
    [
        ("Blocking I/O syscalls release the lock so other threads execute.", True),
        ("Okay.", False),
    ],
)
def test_s1b1_inline_followup_client_hides_score_and_breakdown_while_preserving_db_v3(
    slice1_sql_env,
    followup_answer: str,
    expected_demonstrated: bool,
):
    """S1b-1: null candidate final_score, concept-only feedback, score-free narration, raw DB breakdown."""
    _seed_bundle(
        "python.s1b1.gil",
        status="reviewed",
        topic="Interpreter Mutex",
        question="Explain GIL bytecode execution and blocking I/O release.",
    )
    client = TestClient(app)
    user = _make_user(f"s1b1-{expected_demonstrated}")

    start = client.post(
        "/session/start",
        headers=_headers(user),
        json={
            "skills": ["Python"],
            "rounds_per_skill": 1,
            "practice_mode": "coached_practice",
        },
    )
    assert start.status_code == 200, start.text
    sid = start.json()["session_id"]

    r1 = client.post(
        "/session/answer",
        headers=_headers(user),
        json={
            "session_id": sid,
            "round": 1,
            "answer_text": "Only one thread executes bytecode at a time because the mutex serializes bytecode.",
        },
    )
    assert r1.status_code == 200, r1.text
    r1_body = r1.json()
    assert r1_body["follow_up_scheduled"] is True
    assert isinstance(r1_body["final_score"], (int, float))
    assert "scoring_breakdown" in r1_body and r1_body["scoring_breakdown"]

    act2 = activate(client, _headers(user), sid, 2)
    assert act2["is_follow_up"] is True

    r2 = client.post(
        "/session/answer",
        headers=_headers(user),
        json={"session_id": sid, "round": 2, "answer_text": followup_answer},
    )
    assert r2.status_code == 200, r2.text
    r2_body = r2.json()

    # 1 & 4: /session/answer hides final_score and raw scoring_breakdown.
    assert r2_body["final_score"] is None
    assert "scoring_breakdown" not in r2_body
    assert r2_body["rubric"] == {}
    assert r2_body["score_explanation"] == {}
    assert r2_body["nlp_score"] is None
    assert r2_body["kg_score"] is None
    assert r2_body["svm_label"] is None
    assert r2_body["guard_applied"] is None

    # 2: Feedback strictly covers targeted concept label + demonstrated state, no parent boilerplate.
    outcome = r2_body["follow_up_outcome"]
    assert outcome["targets_concept"] == "io_release"
    assert "blocking i/o" in outcome["concept_label"].lower()
    assert outcome["demonstrated"] is expected_demonstrated
    fb_text = " ".join(
        r2_body["feedback"]["content"]
        + r2_body["feedback"]["strengths"]
        + r2_body["feedback"]["weakness"]
        + [r2_body["feedback"]["next_step"]]
    ).lower()
    assert outcome["concept_label"].lower() in fb_text
    if expected_demonstrated:
        assert outcome["status"] == "demonstrated"
        assert "demonstrated" in fb_text and "not clearly demonstrated" not in fb_text
    else:
        assert outcome["status"] == "not_clearly_demonstrated"
        assert "not clearly demonstrated" in fb_text
    for forbidden in ("very brief", "lacked specific technical keywords", "review the core concepts"):
        assert forbidden not in fb_text

    # 1, 2, 3: /feedback hides final_score, keeps concept-only feedback, and narration states no score.
    fb2 = client.get(f"/session/{sid}/rounds/2/feedback", headers=_headers(user))
    assert fb2.status_code == 200, fb2.text
    fb2_body = fb2.json()
    assert fb2_body["final_score"] is None
    assert "guard_applied" not in fb2_body
    assert fb2_body["follow_up_outcome"] == outcome
    fb2_text = " ".join(fb2_body["feedback"]["content"]).lower()
    assert outcome["concept_label"].lower() in fb2_text
    assert "very brief" not in fb2_text
    assert "lacked specific technical keywords" not in fb2_text
    script = str((fb2_body.get("narration") or {}).get("script") or "")
    assert script
    assert "out of 100" not in script.lower()
    assert "scored" not in script.lower()
    assert outcome["concept_label"].lower() in script.lower()

    # Core round /feedback still keeps score & narration unchanged.
    fb1 = client.get(f"/session/{sid}/rounds/1/feedback", headers=_headers(user))
    assert fb1.status_code == 200, fb1.text
    assert isinstance(fb1.json()["final_score"], (int, float))
    assert "out of 100" in str(fb1.json()["narration"]["script"]).lower()

    # 1 & 4: GET /session/{id} round_history and GET /dashboard/{id} never expose score or breakdown.
    sess_resp = client.get(f"/session/{sid}", headers=_headers(user))
    assert sess_resp.status_code == 200, sess_resp.text
    hist_r2 = next(r for r in sess_resp.json()["round_history"] if r["round"] == 2)
    assert hist_r2["final_score"] is None
    assert "scoring_breakdown" not in hist_r2
    assert hist_r2["follow_up_outcome"] == outcome

    dash = client.get(f"/dashboard/{sid}", headers=_headers(user))
    assert dash.status_code == 200, dash.text
    dash_body = dash.json()
    dash_r1 = next(r for r in dash_body["rounds"] if r["round"] == 1)
    dash_r2 = next(r for r in dash_body["rounds"] if r["round"] == 2)
    assert isinstance(dash_r1["final_score"], (int, float))
    assert "scoring_breakdown" in dash_r1 and dash_r1["scoring_breakdown"]
    assert dash_r2["final_score"] is None
    assert dash_r2["performance_band"] is None
    assert dash_r2["confidence_band"] is None
    assert "scoring_breakdown" not in dash_r2
    assert dash_r2["score_explanation"] == {}
    assert dash_r2["follow_up_outcome"] == outcome
    assert "very brief" not in " ".join(dash_r2["feedback"]["content"]).lower()
    assert dash_body["averages"]["final_score"] == pytest.approx(float(r1_body["final_score"]), abs=0.05)

    # 4: Raw v3 breakdown stays stored on RoundRow in DB for offline analysis.
    with session_scope() as s:
        db_r2 = (
            s.query(RoundRow)
            .filter(RoundRow.session_id == sid, RoundRow.round_number == 2)
            .one()
        )
        assert db_r2.final_score is None
        raw_bd = db_r2.scoring_breakdown_json
        assert raw_bd.get("inline_follow_up") is True
        assert isinstance(raw_bd.get("raw_v3_final_score"), (int, float))
        assert raw_bd.get("concepts") is not None


def test_s1b1_manual_followup_with_reviewed_bundle_keeps_legacy_behavior(slice1_sql_env):
    """S1b-1: manual follow-up with a reviewed bundle keeps its existing numeric/feedback behavior."""
    from backend.db import get_database
    from backend.db.follow_up_allocate import allocate_follow_up
    from modules.follow_ups import build_follow_up_plan_entry

    _seed_bundle(
        "python.s1b1.manual",
        status="reviewed",
        topic="ManualTopic",
        question="Manual parent Q?",
    )
    _seed_bundle(
        "python.s1b1.manual2",
        status="reviewed",
        topic="ManualTopic",
        question="Manual Q2?",
    )
    client = TestClient(app)
    user = _make_user("s1b1-manual")
    start = client.post(
        "/session/start",
        headers=_headers(user),
        json={
            "blocks": [
                {
                    "round_type": "technical_short_answer",
                    "category": "interview",
                    "skills": ["Python"],
                    "topic": "ManualTopic",
                    "difficulty": "medium",
                    "count": 2,
                    "allow_optional_follow_ups": True,
                    "practice_mode": "coached_practice",
                }
            ],
            "practice_mode": "coached_practice",
        },
    )
    assert start.status_code == 200
    sid = start.json()["session_id"]

    full_answer = (
        "Only one thread executes bytecode at once under the GIL mutex while "
        "blocking I/O syscalls release the lock so other threads run cleanly."
    )
    r1 = client.post(
        "/session/answer",
        headers=_headers(user),
        json={"session_id": sid, "round": 1, "answer_text": full_answer},
    )
    assert r1.status_code == 200
    assert r1.json()["follow_up_scheduled"] is False

    # Manually allocate a reviewed follow-up (followup:... identity, no stage="follow_up").
    db = get_database()
    sess_doc = db["sessions"].find_one({"session_id": sid})
    entry = build_follow_up_plan_entry(
        parent_round_doc=sess_doc["rounds"][0],
        reviewed_bundle={"bundle_id": "python.s1b1.manual", "version": 1},
    )
    alloc = allocate_follow_up(db, session_id=sid, parent_round=1, plan_entry=entry)
    assert alloc["scheduled"] is True

    activate(client, _headers(user), sid, 2)
    r2 = client.post(
        "/session/answer",
        headers=_headers(user),
        json={"session_id": sid, "round": 2, "answer_text": full_answer},
    )
    assert r2.status_code == 200, r2.text
    assert r2.json()["next_round"] == 3

    act3 = activate(client, _headers(user), sid, 3)
    assert act3["is_follow_up"] is True
    r3 = client.post(
        "/session/answer",
        headers=_headers(user),
        json={"session_id": sid, "round": 3, "answer_text": "Manual follow-up explanation."},
    )
    assert r3.status_code == 200, r3.text
    r3_body = r3.json()
    assert isinstance(r3_body["final_score"], (int, float))
    assert "scoring_breakdown" in r3_body and r3_body["scoring_breakdown"]
    assert "follow_up_outcome" not in r3_body


def test_s1b3_deferred_feedback_three_core_shared_topic_one_followup_all_core_eligible(
    slice1_sql_env,
):
    """S1b-3 (Q1 acceptance): 3 bundle core rounds (>=2 sharing topic) + 1 inline follow-up, no mid-session /feedback."""
    _seed_bundle(
        "python.s1b3.core1",
        status="reviewed",
        topic="Concurrency",
        question="Core 1: Explain how the GIL affects bytecode threads vs blocking I/O.",
    )
    _seed_bundle(
        "python.s1b3.core2",
        status="reviewed",
        topic="Concurrency",
        question="Core 2: How does releasing the lock on socket waits help multi-threaded servers?",
        required_concepts=[
            {
                "id": "socket_release",
                "descriptor": "Socket I/O waits release the GIL lock so worker threads run",
                "aliases": ["socket waits", "release lock"],
                "expected_propositions": ["socket waits release lock"],
            },
        ],
        followups=[
            {
                "prompt": "Follow-up Core 2: Why can threads still progress during socket waits?",
                "targets_concept": "socket_release",
            }
        ],
    )
    _seed_bundle(
        "python.s1b3.core3",
        status="reviewed",
        topic="Generators",
        question="Core 3: How does yield suspend generator execution in memory?",
        required_concepts=[
            {
                "id": "yield_frame",
                "descriptor": "Yield suspends the execution frame between next steps",
                "aliases": ["yield suspends", "execution frame"],
                "expected_propositions": ["yield suspends execution frame"],
            },
        ],
        followups=[
            {
                "prompt": "Follow-up Core 3: What does yield preserve across next calls?",
                "targets_concept": "yield_frame",
            }
        ],
    )

    client = TestClient(app)
    user = _make_user("s1b3-q1")
    start = client.post(
        "/session/start",
        headers=_headers(user),
        json={
            "blocks": [
                {
                    "round_type": "technical_short_answer",
                    "category": "interview",
                    "skills": ["Python"],
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

    # Round 1 (Core 1, topic="Concurrency"): omit io_release -> schedules inline follow-up at Round 2.
    # No /feedback calls during active session (Q1 deferred feedback).
    r1 = client.post(
        "/session/answer",
        headers=_headers(user),
        json={
            "session_id": sid,
            "round": 1,
            "answer_text": "Only one thread executes bytecode at once under the mutex lock.",
        },
    )
    assert r1.status_code == 200, r1.text
    b1 = r1.json()
    assert b1["assessment_eligibility"] == "eligible"
    assert b1["follow_up_scheduled"] is True
    assert b1["next_round"] == 2
    assert b1["total_rounds"] == 4
    core1_score = float(b1["final_score"])

    # Round 2 (Inline follow-up for Core 1): excluded, candidate final_score is null.
    act2 = activate(client, _headers(user), sid, 2)
    assert act2["is_follow_up"] is True
    r2 = client.post(
        "/session/answer",
        headers=_headers(user),
        json={
            "session_id": sid,
            "round": 2,
            "answer_text": "Blocking I/O syscalls release the lock so other threads run.",
        },
    )
    assert r2.status_code == 200, r2.text
    b2 = r2.json()
    assert b2["is_follow_up"] is True
    assert b2["final_score"] is None
    assert b2["assessment_eligibility"] == "excluded"
    assert b2["follow_up_scheduled"] is False
    assert b2["follow_up_outcome"]["demonstrated"] is True
    assert b2["next_round"] == 3

    # Round 3 (Core 2, shares topic="Concurrency" with Core 1): full answer -> eligible, no follow-up.
    act3 = activate(client, _headers(user), sid, 3)
    assert not act3.get("is_follow_up")
    r3 = client.post(
        "/session/answer",
        headers=_headers(user),
        json={
            "session_id": sid,
            "round": 3,
            "answer_text": (
                "Blocking socket waits release the lock cleanly so other Python worker threads "
                "can execute I/O concurrently under the interpreter mutex."
            ),
        },
    )
    assert r3.status_code == 200, r3.text
    b3 = r3.json()
    assert b3["assessment_eligibility"] == "eligible"
    assert b3["follow_up_scheduled"] is False
    assert b3["next_round"] == 4
    core2_score = float(b3["final_score"])

    # Round 4 (Core 3, topic="Generators"): full answer -> eligible, completes session.
    act4 = activate(client, _headers(user), sid, 4)
    assert not act4.get("is_follow_up")
    r4 = client.post(
        "/session/answer",
        headers=_headers(user),
        json={
            "session_id": sid,
            "round": 4,
            "answer_text": (
                "The yield statement suspends execution frame state cleanly between next calls "
                "and resumes lazily without materializing full lists in memory."
            ),
        },
    )
    assert r4.status_code == 200, r4.text
    b4 = r4.json()
    assert b4["assessment_eligibility"] == "eligible"
    assert b4["follow_up_scheduled"] is False
    assert b4["session_complete"] is True
    core3_score = float(b4["final_score"])

    expected_mean = round((core1_score + core2_score + core3_score) / 3.0, 2)

    # Debrief: fetch dashboard and per-round feedback strictly after completion.
    dash = client.get(f"/dashboard/{sid}", headers=_headers(user))
    assert dash.status_code == 200, dash.text
    dash_body = dash.json()
    by_round = {int(r["round"]): r for r in dash_body["rounds"]}

    for rn in (1, 3, 4):
        assert by_round[rn]["assessment_eligibility"] == "eligible"
    assert by_round[2]["assessment_eligibility"] == "excluded"
    assert "follow_up" in by_round[2]["eligibility_exclusion_reasons"]
    assert by_round[2]["final_score"] is None
    assert "scoring_breakdown" not in by_round[2]

    assert dash_body["averages"]["final_score"] == pytest.approx(expected_mean, abs=0.05)
    assert dash_body["block_results"][0]["assessment_eligible_rounds"] == 3
    assert dash_body["block_results"][0]["average_score"] == pytest.approx(expected_mean, abs=0.05)
    assert dash_body["overall_readiness_score"] == pytest.approx(expected_mean, abs=0.05)

    for rn in (1, 2, 3, 4):
        fb = client.get(f"/session/{sid}/rounds/{rn}/feedback", headers=_headers(user))
        assert fb.status_code == 200, fb.text
        if rn == 2:
            assert fb.json()["final_score"] is None
        else:
            assert fb.json()["assessment_eligibility"] == "eligible"


def test_p1_followup_outcome_robustness_prompt_echo_without_alias_wrong_alias_and_three_states():
    """P1: prompt-echo rejection (a), explanation without alias (b), wrong with alias (c), and 3 states."""
    from modules.follow_ups import evaluate_inline_follow_up_outcome

    bundle_ctx = {
        "question": "Explain how CPython GIL affects blocking I/O.",
        "required_concepts": [
            {
                "id": "io_release",
                "descriptor": "Blocking I/O syscalls release the lock so other threads run",
                "aliases": ["blocking io", "blocking i/o", "io syscalls"],
                "expected_propositions": ["blocking io releases lock", "syscalls release lock"],
            }
        ],
        "misconceptions": [
            {
                "id": "never_release",
                "description": "blocking io keeps holding lock across cores",
                "candidate_patterns": ["threads run python bytecode simultaneously across cores"],
            }
        ],
    }

    # Case (a): prompt names concept/proposition terms and candidate ONLY repeats prompt wording.
    prompt_echo_round = {
        "round": 2,
        "question": "Follow-up: How do blocking I/O syscalls release the lock?",
        "targets_concept": "io_release",
        "config_json": {"targets_concept": "io_release", "stage": "follow_up"},
    }
    res_a = evaluate_inline_follow_up_outcome(
        active_round=prompt_echo_round,
        scoring_question_context=bundle_ctx,
        answer_text="Blocking I/O syscalls release the lock.",
    )
    assert res_a["demonstrated"] is False
    assert res_a["status"] == "not_clearly_demonstrated"

    # Also Case (a) when prompt only names the alias and candidate merely echoes prompt phrasing.
    prompt_alias_round = {
        "round": 2,
        "question": "Follow-up: Why can blocking I/O threads overlap cleanly?",
        "targets_concept": "io_release",
        "config_json": {"targets_concept": "io_release", "stage": "follow_up"},
    }
    res_a2 = evaluate_inline_follow_up_outcome(
        active_round=prompt_alias_round,
        scoring_question_context=bundle_ctx,
        answer_text="Blocking I/O threads overlap cleanly.",
    )
    assert res_a2["demonstrated"] is False
    assert res_a2["status"] == "not_clearly_demonstrated"

    # Case (b): correct explanation WITHOUT using the concept aliases ("blocking io" / "io syscalls").
    res_b = evaluate_inline_follow_up_outcome(
        active_round=prompt_alias_round,
        scoring_question_context=bundle_ctx,
        answer_text="Wait syscalls temporarily release the interpreter lock so another thread executes.",
    )
    assert res_b["demonstrated"] is True
    assert res_b["status"] == "demonstrated"

    # Case (c1): wrong statement containing alias that contradicts proposition -> not clearly demonstrated.
    res_c_wrong = evaluate_inline_follow_up_outcome(
        active_round=prompt_alias_round,
        scoring_question_context=bundle_ctx,
        answer_text="Blocking I/O never releases lock state cleanly for other waiting threads.",
    )
    assert res_c_wrong["demonstrated"] is False
    assert res_c_wrong["status"] == "not_clearly_demonstrated"

    # Case (c2): off-base claim containing alias without proposition resolution -> evaluator "uncertain" -> "unclear" (never "demonstrated").
    res_unclear = evaluate_inline_follow_up_outcome(
        active_round=prompt_alias_round,
        scoring_question_context=bundle_ctx,
        answer_text="Blocking I/O optimizes hash bucket caching across tuples cleanly.",
    )
    assert res_unclear["demonstrated"] is False
    assert res_unclear["status"] == "unclear"
    assert "unclear" in " ".join(res_unclear["feedback"]["content"]).lower()

    # Case (c3): active misconception + alias -> not_clearly_demonstrated.
    res_misc = evaluate_inline_follow_up_outcome(
        active_round=prompt_alias_round,
        scoring_question_context=bundle_ctx,
        answer_text="Blocking I/O means threads run python bytecode simultaneously across cores.",
    )
    assert res_misc["demonstrated"] is False
    assert res_misc["status"] == "not_clearly_demonstrated"


def test_p1_end_to_end_unclear_alias_only_followup_status_propagates(slice1_sql_env):
    """P1: evaluator 'uncertain' (alias-only mention) surfaces status='unclear' via API."""
    _seed_bundle(
        "python.p1.unclear",
        status="auto_checked",
        topic="Interpreter Mutex",
        question="Explain GIL bytecode mutex and blocking I/O release.",
    )
    client = TestClient(app)
    user = _make_user("p1-unclear")
    start = client.post(
        "/session/start",
        headers=_headers(user),
        json={"skills": ["Python"], "rounds_per_skill": 1, "practice_mode": "coached_practice"},
    )
    assert start.status_code == 200
    sid = start.json()["session_id"]

    r1 = client.post(
        "/session/answer",
        headers=_headers(user),
        json={
            "session_id": sid,
            "round": 1,
            "answer_text": "Only one thread runs bytecode at once under the GIL mutex.",
        },
    )
    assert r1.status_code == 200 and r1.json()["follow_up_scheduled"] is True

    activate(client, _headers(user), sid, 2)
    r2 = client.post(
        "/session/answer",
        headers=_headers(user),
        json={
            "session_id": sid,
            "round": 2,
            "answer_text": "Blocking IO scheduling involves queues inside kernel drivers.",
        },
    )
    assert r2.status_code == 200, r2.text
    b2 = r2.json()
    assert b2["final_score"] is None
    assert b2["follow_up_outcome"]["status"] == "unclear"
    assert b2["follow_up_outcome"]["demonstrated"] is False
    assert "unclear" in b2["feedback"]["content"][0].lower()
