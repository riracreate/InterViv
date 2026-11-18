"""Slice 2 tests: ``staged_v1`` presets, stage tags, optional Practical, Warm-up,
question-text-only Behavioural, and server-side deferred feedback (A1–A8).

All tests run completely offline using an isolated temporary SQLite database,
demo bundles, and FastAPI ``TestClient`` with zero outbound network calls.
"""
from __future__ import annotations

import csv
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import inspect, select

os.environ.setdefault("INTERVIV_USE_MEMORY_DB", "true")
os.environ.setdefault("JWT_SECRET_KEY", "test-secret-key-with-at-least-32-bytes!!")
os.environ.setdefault("LLM_LIVE_FETCH", "0")
os.environ.setdefault("JOBS_LIVE_FETCH", "0")

from backend import config as app_config  # noqa: E402
from backend.auth.security import create_access_token, hash_password  # noqa: E402
from backend.db import get_database  # noqa: E402
from backend.db.sqlalchemy_models import RoundRow, SessionRow, TeachingExposureRow  # noqa: E402
from backend.db.sqlalchemy_store import (  # noqa: E402
    _sessionmaker,
    create_all_for_smoke,
    get_engine,
    get_sqlalchemy_database,
    session_scope,
)
from backend.main import app  # noqa: E402
from modules import bundle_store, staged_flow  # noqa: E402
from modules.bundle_store import REQUIRED_CHECKLIST  # noqa: E402
from scripts.seed_demo_bundles import seed_demo_bundles  # noqa: E402
from tests.round_helpers import activate  # noqa: E402

_CHECK_OK = {k: True for k in REQUIRED_CHECKLIST}
_CALIB = {"difficulty": "medium"}


def _clear_caches() -> None:
    app_config.get_settings.cache_clear()
    get_engine.cache_clear()
    _sessionmaker.cache_clear()
    get_sqlalchemy_database.cache_clear()


@pytest.fixture
def staged_sql_env(monkeypatch, tmp_path: Path):
    """Isolated SQLite DB for staged_v1 end-to-end tests."""
    db_path = tmp_path / "slice2.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_path}")
    monkeypatch.setenv("INTERVIV_USE_MEMORY_DB", "false")
    monkeypatch.setenv("STAGED_INLINE_FOLLOW_UPS", "1")
    monkeypatch.setenv("REVIEWED_BUNDLES_ONLY", "false")
    monkeypatch.setenv("LLM_LIVE_FETCH", "0")
    monkeypatch.setenv("JOBS_LIVE_FETCH", "0")
    monkeypatch.setenv(
        "FOLLOWUP_DECISIONS_AUDIT_PATH",
        str(tmp_path / "followup_decisions.jsonl"),
    )
    monkeypatch.setenv(
        "REJECTED_BUNDLES_AUDIT_PATH",
        str(tmp_path / "rejected_bundles.jsonl"),
    )
    _clear_caches()
    create_all_for_smoke()
    try:
        yield {"db": get_database(), "db_path": db_path, "tmp_path": tmp_path}
    finally:
        try:
            get_engine().dispose()
        except Exception:
            pass
        _clear_caches()


def _create_user_headers(db, *, email: str | None = None) -> tuple[str, dict[str, str]]:
    user_id = f"user-{uuid4().hex[:10]}"
    user_email = email or f"{user_id}@example.com"
    now = datetime.now(timezone.utc)
    db["users"].insert_one({
        "id": user_id,
        "name": "Staged Candidate",
        "email": user_email,
        "password_hash": hash_password("TestPass123!"),
        "created_at": now,
        "last_active_at": now,
    })
    token = create_access_token(user_id)
    return user_id, {"Authorization": f"Bearer {token}"}


def _write_reviewed_hr_csv(path: Path) -> Path:
    rows = [
        {
            "dataset_row": "1",
            "skill": "HR",
            "sub_domain": "hr_behavioral",
            "difficulty": "medium",
            "question": "Tell me about a time you resolved a team disagreement.",
            "ideal_answer": "SECRET_IDEAL_ANSWER_NEVER_SHOWN",
            "ideal_keywords": "secret_kw_1,secret_kw_2",
            "keep": "y",
        },
        {
            "dataset_row": "2",
            "skill": "HR",
            "sub_domain": "hr_behavioral",
            "difficulty": "medium",
            "question": "  Tell me about a time you  resolved a team disagreement. ",
            "ideal_answer": "DUPLICATE_ROW",
            "ideal_keywords": "dup_kw",
            "keep": "Y",
        },
        {
            "dataset_row": "3",
            "skill": "HR",
            "sub_domain": "hr_behavioral",
            "difficulty": "medium",
            "question": "Should be filtered out because keep is n.",
            "ideal_answer": "FILTERED",
            "ideal_keywords": "filtered",
            "keep": "n",
        },
        {
            "dataset_row": "4",
            "skill": "HR",
            "sub_domain": "hr_behavioral",
            "difficulty": "easy",
            "question": "Describe a setback you recovered from on a tight deadline.",
            "ideal_answer": "SECOND_SECRET_IDEAL",
            "ideal_keywords": "second_secret_kw",
            "keep": "yes",
        },
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
    return path


def _seed_single_reviewed_python_bundle(difficulty: str = "medium") -> dict[str, Any]:
    doc = {
        "bundle_id": f"test.py.reviewed.{uuid4().hex[:6]}",
        "version": 1,
        "skill": "Python",
        "topic": "Concurrency",
        "difficulty": difficulty,
        "question": "Explain how Python asyncio event loop schedules coroutines.",
        "reference_answer": (
            "An asyncio event loop runs single-threaded cooperative multitasking, "
            "switching tasks whenever a coroutine awaits non-blocking I/O."
        ),
        "acceptable_variants": [
            "Coroutines yield control back to the single-threaded event loop at await points."
        ],
        "keywords": ["asyncio", "event loop", "coroutine", "await", "cooperative"],
        "required_concepts": [
            {
                "id": "await_yield",
                "descriptor": "Coroutines yield control to the event loop at await points",
                "aliases": ["await", "yield control"],
                "expected_propositions": ["coroutine yields at await"],
            }
        ],
        "optional_concepts": [],
        "misconceptions": [],
        "depth_markers": ["single-threaded", "non-blocking io"],
        "rubric_descriptors": {"coverage": "Covers cooperative yielding."},
        "followups": [
            {
                "prompt": "Why does blocking CPU code stall all tasks on the same event loop?",
                "targets_concept": "await_yield",
            }
        ],
        "calibration_examples": [
            {
                "answer": "Coroutines cooperatively yield control to the event loop at await points.",
                "author_level": 3,
                "expected_band": "Good",
            }
        ],
        "source": "human_authored",
        "author": "test-reviewer",
    }
    imported = bundle_store.import_bundle(doc, actor_id="test", initial_status="draft")
    v = imported["version"]
    return _approve_bundle_version(
        v["bundle_id"],
        int(v["version"]),
        actor_id="test",
        reason1="Reference answer and concept propositions match expected rubric.",
        reason2="Second independent approval for reviewed Python medium bundle.",
    )


def _approve_bundle_version(
    bundle_id: str,
    version: int,
    *,
    actor_id: str = "test-reviewer",
    reason1: str = "Reference answer and concept propositions verified for test bundle.",
    reason2: str = "Second independent approval for test bundle.",
) -> dict[str, Any]:
    """Submit a bundle version and record two independent approvals to reach 'reviewed'."""
    v = bundle_store.submit_for_review(
        bundle_id, version, actor_id=actor_id, reason="Ready for review"
    )
    bundle_store.record_decision(
        bundle_id,
        version,
        reviewer_id="reviewer-1",
        content_hash=v["content_hash"],
        decision="approve",
        checklist=_CHECK_OK,
        reasons=reason1,
        calibration=_CALIB,
    )
    return bundle_store.record_decision(
        bundle_id,
        version,
        reviewer_id="reviewer-2",
        content_hash=v["content_hash"],
        decision="approve",
        checklist=_CHECK_OK,
        reasons=reason2,
        calibration=_CALIB,
    )


def _review_seeded_demo_bundles() -> None:
    """Transition seeded demo bundles from auto_checked to reviewed for test eligibility."""
    for bundle_id in (
        "demo.python.01_gil.v1",
        "demo.python.02_generators.v1",
        "demo.python.03_closures.v1",
    ):
        if bundle_store.get_version(bundle_id, 1)["status"] == "reviewed":
            continue
        _approve_bundle_version(bundle_id, 1)


def test_staged_v1_preset_validation_and_stage_persistence_no_migration(staged_sql_env):
    db = staged_sql_env["db"]
    _, headers = _create_user_headers(db)
    client = TestClient(app)

    # Invalid / missing preset under staged_v1 -> 422
    r_missing = client.post(
        "/session/start",
        headers=headers,
        json={"flow_version": "staged_v1", "skills": ["Python"]},
    )
    assert r_missing.status_code == 422

    r_bad_preset = client.post(
        "/session/start",
        headers=headers,
        json={"flow_version": "staged_v1", "preset": "turbo", "skills": ["Python"]},
    )
    assert r_bad_preset.status_code == 422

    r_bad_version = client.post(
        "/session/start",
        headers=headers,
        json={"flow_version": "staged_v2", "preset": "Quick", "skills": ["Python"]},
    )
    assert r_bad_version.status_code == 422

    # Valid Quick start (case-insensitive)
    r_ok = client.post(
        "/session/start",
        headers=headers,
        json={"flow_version": "staged_v1", "preset": "Quick", "skills": ["Python"]},
    )
    assert r_ok.status_code == 200, r_ok.text
    start_body = r_ok.json()
    sid = start_body["session_id"]
    assert start_body["flow_version"] == "staged_v1"
    assert start_body["preset"] == "quick"
    assert start_body["stage"] == "warm_up"
    assert start_body["difficulty"] == "easy"
    assert [b["stage"] for b in start_body["block_plan"]] == ["warm_up", "core"]
    assert start_body["total_rounds"] == 3  # 1 warm-up + 2 core (behavioural bank absent)

    # Verify persistence inside existing SQLAlchemy JSON columns (zero schema changes)
    with session_scope() as sql_session:
        row = sql_session.execute(
            select(SessionRow).where(SessionRow.id == sid)
        ).scalar_one()
        assert row.round_config_json["staged_flow"]["version"] == "staged_v1"
        assert row.round_config_json["staged_flow"]["preset"] == "quick"
        assert [b["stage"] for b in row.block_plan_json] == ["warm_up", "core"]
        assert [e["stage"] for e in row.expanded_plan_json] == ["warm_up", "core", "core"]
        r1 = sql_session.execute(
            select(RoundRow).where(RoundRow.session_id == row.id, RoundRow.round_number == 1)
        ).scalar_one()
        assert r1.config_json["stage"] == "warm_up"

    # Confirm zero unexpected columns were needed
    inspector = inspect(get_engine())
    session_cols = {c["name"] for c in inspector.get_columns("sessions")}
    assert "flow_version" not in session_cols
    assert "preset" not in session_cols


def test_warmup_unscored_easy_allowed_even_when_reviewed_bundles_only_true(
    staged_sql_env, monkeypatch
):
    db = staged_sql_env["db"]
    _, headers = _create_user_headers(db)

    # Seed ONLY a medium reviewed Python bundle — zero easy reviewed bundles!
    _seed_single_reviewed_python_bundle(difficulty="medium")
    monkeypatch.setenv("REVIEWED_BUNDLES_ONLY", "true")
    app_config.get_settings.cache_clear()

    client = TestClient(app)
    r_start = client.post(
        "/session/start",
        headers=headers,
        json={"flow_version": "staged_v1", "preset": "Quick", "skills": ["Python"]},
    )
    assert r_start.status_code == 200, r_start.text
    start_data = r_start.json()
    sid = start_data["session_id"]
    assert start_data["stage"] == "warm_up"
    assert start_data["difficulty"] == "easy"

    # Also verify a pure Warm-up block starts under REVIEWED_BUNDLES_ONLY=true even for
    # a skill with zero reviewed bundles at any difficulty.
    r_wu_only = client.post(
        "/session/start",
        headers=headers,
        json={
            "blocks": [
                {
                    "round_type": "technical_short_answer",
                    "category": "interview",
                    "stage": "warm_up",
                    "skills": ["Docker"],
                    "count": 1,
                    "difficulty": "easy",
                }
            ]
        },
    )
    assert r_wu_only.status_code == 200, r_wu_only.text
    wu_sid = r_wu_only.json()["session_id"]

    # Submit Warm-up answer in staged_v1 session -> null score & Elo unchanged
    r_ans = client.post(
        "/session/answer",
        headers=headers,
        json={
            "session_id": sid,
            "round": 1,
            "answer_text": "Python manages memory using reference counting and cyclic GC.",
        },
    )
    assert r_ans.status_code == 200, r_ans.text
    ans_data = r_ans.json()
    assert ans_data["final_score"] is None
    assert ans_data["feedback_deferred"] is True
    assert ans_data["follow_up_scheduled"] is False  # never follow-up on warm-up

    stored = db["sessions"].find_one({"session_id": sid})
    round1 = stored["rounds"][0]
    assert round1["final_score"] is None
    assert round1["scoring_breakdown"]["stage"] == "warm_up"
    assert round1["scoring_breakdown"]["unscored_reason"] == "warm_up_unscored"
    cand = db["candidates"].find_one({"candidate_id": stored["candidate_id"]})
    assert float(cand["elo_ratings"]["Python"]) == float(app_config.get_settings().initial_elo)

    # Non-staged warm-up block also returns final_score=None cleanly
    r_wu_ans = client.post(
        "/session/answer",
        headers=headers,
        json={"session_id": wu_sid, "round": 1, "answer_text": "Containers isolate processes."},
    )
    assert r_wu_ans.status_code == 200
    assert r_wu_ans.json()["final_score"] is None


def test_full_preset_practical_track_selection_and_role_optionality(
    staged_sql_env, monkeypatch
):
    db = staged_sql_env["db"]
    _, headers = _create_user_headers(db)
    client = TestClient(app)

    # 1. Google SWE -> has coding/system_design/sql track (DSA -> coding, 30m)
    r_swe = client.post(
        "/session/start",
        headers=headers,
        json={
            "flow_version": "staged_v1",
            "preset": "Full",
            "target_role_id": "google_software_engineer",
        },
    )
    assert r_swe.status_code == 200, r_swe.text
    swe = r_swe.json()
    assert swe["staged_flow"]["practical_track"] == "coding"
    assert swe["staged_flow"]["practical_skipped"] is False
    stages_swe = [b["stage"] for b in swe["block_plan"]]
    assert stages_swe == ["warm_up", "core", "practical"]  # behavioural absent in repo
    practical_blk = swe["block_plan"][2]
    assert practical_blk["round_type"] == "coding"
    assert practical_blk["duration_minutes"] == 30
    assert swe["total_rounds"] == 6  # 1 warm-up + 4 core + 1 practical

    # 2. SQL skill -> SQL practical track (25m) and walks cleanly through Practical round 6
    seed_demo_bundles()
    monkeypatch.setenv("STAGED_INLINE_FOLLOW_UPS", "0")
    app_config.get_settings.cache_clear()
    r_sql = client.post(
        "/session/start",
        headers=headers,
        json={
            "flow_version": "staged_v1",
            "preset": "Full",
            "skills": ["SQL"],
        },
    )
    assert r_sql.status_code == 200, r_sql.text
    sql_body = r_sql.json()
    sql_sid = sql_body["session_id"]
    assert sql_body["staged_flow"]["practical_track"] == "sql"
    assert sql_body["staged_flow"]["practical_skipped"] is False
    assert sql_body["block_plan"][2]["round_type"] == "sql"
    assert sql_body["block_plan"][2]["duration_minutes"] == 25
    assert sql_body["total_rounds"] == 6

    # Walk Warm-up (1) + 4 Core rounds (2..5) into Practical (6)
    assert client.post(
        "/session/answer",
        headers=headers,
        json={"session_id": sql_sid, "round": 1, "answer_text": "Warm-up SQL answer."},
    ).status_code == 200
    for rn in (2, 3, 4, 5):
        activate(client, headers, sql_sid, rn)
        assert (
            client.post(
                "/session/answer",
                headers=headers,
                json={
                    "session_id": sql_sid,
                    "round": rn,
                    "answer_text": "Normalization reduces redundancy and indexes speed lookups with B-tree traversal.",
                },
            ).status_code
            == 200
        )
    act6 = activate(client, headers, sql_sid, 6)
    assert act6["round_type"] == "sql"
    assert act6["config_json"]["stage"] == "practical"
    ans6 = client.post(
        "/session/answer",
        headers=headers,
        json={"session_id": sql_sid, "round": 6, "answer_text": "SELECT 1;"},
    )
    assert ans6.status_code == 200, ans6.text
    ans6_body = ans6.json()
    assert ans6_body["stage"] == "practical"
    assert ans6_body["session_complete"] is True
    assert ans6_body["feedback_deferred"] is True
    with session_scope() as sql_session:
        row = sql_session.execute(
            select(SessionRow).where(SessionRow.id == sql_sid)
        ).scalar_one()
        r6 = sql_session.execute(
            select(RoundRow).where(RoundRow.session_id == row.id, RoundRow.round_number == 6)
        ).scalar_one()
        assert r6.config_json["stage"] == "practical"
        assert r6.scoring_breakdown_json["stage"] == "practical"

    # 3. Product Marketing Manager (non-execution role) -> Practical skipped (A2)
    r_pmm = client.post(
        "/session/start",
        headers=headers,
        json={
            "flow_version": "staged_v1",
            "preset": "Full",
            "target_role_id": "Product Marketing Manager",
            "skills": ["Product Positioning", "Go-to-Market Strategy"],
        },
    )
    assert r_pmm.status_code == 200, r_pmm.text
    pmm = r_pmm.json()
    assert pmm["staged_flow"]["practical_track"] is None
    assert pmm["staged_flow"]["practical_skipped"] is True
    assert pmm["staged_flow"]["practical_skipped_reason"] == "no_practical_track"
    assert [b["stage"] for b in pmm["block_plan"]] == ["warm_up", "core"]
    assert pmm["total_rounds"] == 5  # 1 warm-up + 4 core (practical & behavioural skipped)


def test_behavioural_csv_builder_unscored_question_only_and_skip_when_absent(
    staged_sql_env, monkeypatch
):
    tmp_path: Path = staged_sql_env["tmp_path"]
    db = staged_sql_env["db"]
    _, headers = _create_user_headers(db)

    # Confirm default repo CSV is absent (awaiting sign-off on hr_questions_review.csv)
    assert not staged_flow.DEFAULT_BEHAVIOURAL_CSV_PATH.exists()
    assert staged_flow.load_behavioural_questions() == []

    # Build deduplicated question-text-only bank from a temp reviewed CSV
    reviewed = _write_reviewed_hr_csv(tmp_path / "hr_questions_reviewed.csv")
    out_csv = tmp_path / "behavioural_questions_v1.csv"
    written = staged_flow.build_behavioural_questions_csv(reviewed, out_csv)
    assert written == 2  # row 1 & row 2 deduplicated, row 3 (keep=n) dropped

    with out_csv.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        assert reader.fieldnames == ["question", "difficulty", "sub_domain", "source"]
        out_rows = list(reader)
        assert all("SECRET_IDEAL" not in row["question"] for row in out_rows)

    # Point loader at temp CSV and run a Quick flow through Behavioural
    monkeypatch.setattr(staged_flow, "DEFAULT_BEHAVIOURAL_CSV_PATH", out_csv)
    monkeypatch.setenv("STAGED_INLINE_FOLLOW_UPS", "0")
    app_config.get_settings.cache_clear()
    seed_demo_bundles()
    _review_seeded_demo_bundles()
    client = TestClient(app)
    r_start = client.post(
        "/session/start",
        headers=headers,
        json={
            "flow_version": "staged_v1",
            "preset": "Quick",
            "skills": ["Python"],
        },
    )
    assert r_start.status_code == 200, r_start.text
    start = r_start.json()
    sid = start["session_id"]
    assert [b["stage"] for b in start["block_plan"]] == [
        "warm_up",
        "core",
        "behavioural",
    ]
    assert start["staged_flow"]["behavioural_count"] == 1
    assert start["staged_flow"]["behavioural_skipped"] is False
    assert start["total_rounds"] == 4

    # Complete Warm-up (1) + Core 1 (2) + Core 2 (3) cleanly with complete answers
    assert client.post(
        "/session/answer",
        headers=headers,
        json={"session_id": sid, "round": 1, "answer_text": "Warm-up Python answer."},
    ).status_code == 200

    for rn in (2, 3):
        activate(client, headers, sid, rn)
        r_core = client.post(
            "/session/answer",
            headers=headers,
            json={
                "session_id": sid,
                "round": rn,
                "answer_text": (
                    "Only one thread executes bytecode at a time under the GIL mutex while "
                    "blocking I/O syscalls release the lock cleanly. Generators use yield "
                    "to suspend execution state lazily in constant memory one item at a time. "
                    "Decorators wrap callables cleanly via closures."
                ),
            },
        )
        assert r_core.status_code == 200, r_core.text

    # Activate Round 4 (Behavioural) and verify question text only & HR excluded from skills
    act4 = activate(client, headers, sid, 4)
    assert act4["stage"] == "behavioural"
    assert "SECRET_IDEAL" not in str(act4)
    assert "secret_kw_1" not in str(act4)

    stored_pre = db["sessions"].find_one({"session_id": sid})
    assert "HR" not in stored_pre["skills"]
    assert stored_pre["rounds"][3]["config_json"]["stage"] == "behavioural"
    assert stored_pre["rounds"][3]["question_context"]["ideal_answer"] == ""
    assert stored_pre["rounds"][3]["question_context"]["ideal_keywords"] == ""

    r_beh = client.post(
        "/session/answer",
        headers=headers,
        json={
            "session_id": sid,
            "round": 4,
            "answer_text": (
                "Situation: API latency spiked. Task: stabilize checkout. "
                "Action: aligned backend and QA on rollback and caching. "
                "Result: p99 dropped by 45% in one day."
            ),
        },
    )
    assert r_beh.status_code == 200, r_beh.text
    beh_resp = r_beh.json()
    assert beh_resp["session_complete"] is True
    assert beh_resp["final_score"] is None

    # After completion, Behavioural stays unscored (final_score=None) on dashboard
    dash = client.get(f"/dashboard/{sid}", headers=headers).json()
    assert dash["rounds"][0]["final_score"] is None
    assert dash["rounds"][0]["stage"] == "warm_up"
    assert dash["rounds"][3]["final_score"] is None
    assert dash["rounds"][3]["stage"] == "behavioural"
    core_scores = [dash["rounds"][1]["final_score"], dash["rounds"][2]["final_score"]]
    assert all(s is not None for s in core_scores)
    assert dash["averages"]["final_score"] == pytest.approx(sum(core_scores) / 2.0, abs=0.02)
    reasons = {u["reason"] for u in dash["coverage"]["unscored_rounds"]}
    assert "warm_up_unscored" in reasons
    assert "behavioural_unscored" in reasons

    # Ensure Warm-up and Behavioural never accept inline follow-ups
    from modules.follow_ups import can_schedule_inline_follow_up

    stored_done = db["sessions"].find_one({"session_id": sid})
    assert can_schedule_inline_follow_up(stored_done, stored_done["rounds"][0]) == (
        False,
        "non_core_stage",
    )
    assert can_schedule_inline_follow_up(stored_done, stored_done["rounds"][3]) == (
        False,
        "non_core_stage",
    )


def test_deferred_feedback_enforced_and_legacy_sessions_unchanged(
    staged_sql_env, monkeypatch
):
    db = staged_sql_env["db"]
    _, headers = _create_user_headers(db)
    monkeypatch.setenv("STAGED_INLINE_FOLLOW_UPS", "0")
    app_config.get_settings.cache_clear()
    seed_demo_bundles()
    _review_seeded_demo_bundles()
    client = TestClient(app)

    # Staged_v1 session
    sid = client.post(
        "/session/start",
        headers=headers,
        json={"flow_version": "staged_v1", "preset": "Quick", "skills": ["Python"]},
    ).json()["session_id"]

    # Round 1 Warm-up
    r1 = client.post(
        "/session/answer",
        headers=headers,
        json={"session_id": sid, "round": 1, "answer_text": "Warm-up note."},
    ).json()
    assert r1["feedback_deferred"] is True
    assert r1["final_score"] is None

    # Round 2 Core 1 -> deferred in /answer response
    activate(client, headers, sid, 2)
    r2 = client.post(
        "/session/answer",
        headers=headers,
        json={
            "session_id": sid,
            "round": 2,
            "answer_text": "One thread executes bytecode at once under the GIL mutex while blocking I/O syscalls release the lock.",
        },
    ).json()
    assert r2["feedback_deferred"] is True
    assert r2["final_score"] is None
    assert r2["feedback"] == {"content": [], "strengths": [], "weakness": [], "next_step": ""}
    assert r2["elo_after"] is None
    assert "scoring_breakdown" not in r2

    # Pre-completion /feedback returns deferred=True & records ZERO teaching_exposures
    fb2_pre = client.get(f"/session/{sid}/rounds/2/feedback", headers=headers)
    assert fb2_pre.status_code == 200
    assert fb2_pre.json()["deferred"] is True
    assert fb2_pre.json()["final_score"] is None
    assert fb2_pre.json()["narration"]["status"] == "deferred"
    with session_scope() as sql_session:
        exposures = sql_session.execute(
            select(TeachingExposureRow).where(TeachingExposureRow.session_id == sid)
        ).scalars().all()
        assert len(exposures) == 0

    # Pre-completion GET /session/{id} & /dashboard/{id} & /dashboard/progress defer scores
    sess_pre = client.get(f"/session/{sid}", headers=headers).json()
    assert all(h["final_score"] is None and h.get("feedback_deferred") is True for h in sess_pre["round_history"])
    dash_pre = client.get(f"/dashboard/{sid}", headers=headers).json()
    assert dash_pre["deferred"] is True
    assert dash_pre["averages"]["final_score"] is None
    assert dash_pre.get("overall_readiness_score") is None
    prog_pre = client.get("/dashboard/progress", headers=headers).json()
    staged_hist = next(h for h in prog_pre["history"] if h["session_id"] == sid)
    assert staged_hist["average_score"] is None

    # Complete Core 2 (round 3)
    activate(client, headers, sid, 3)
    r3 = client.post(
        "/session/answer",
        headers=headers,
        json={
            "session_id": sid,
            "round": 3,
            "answer_text": "Generators yield one item at a time lazily and suspend execution frame state in O(1) memory.",
        },
    ).json()
    assert r3["session_complete"] is True
    assert r3["feedback_deferred"] is True  # answer endpoint stays deferred

    # Post-completion /feedback & /dashboard reveal full Core feedback and scores
    fb2_post = client.get(f"/session/{sid}/rounds/2/feedback", headers=headers).json()
    assert fb2_post.get("deferred") is not True
    assert fb2_post["final_score"] is not None
    assert fb2_post["assessment_completed"] is True
    dash_post = client.get(f"/dashboard/{sid}", headers=headers).json()
    assert dash_post["deferred"] is False
    assert dash_post["averages"]["final_score"] is not None
    assert dash_post["rounds"][2]["assessment_eligibility"] == "eligible"

    # Legacy session (no flow_version / preset) remains immediate and unaffected
    leg_sid = client.post(
        "/session/start",
        headers=headers,
        json={"skills": ["Python"], "rounds_per_skill": 2},
    ).json()["session_id"]
    leg_r1 = client.post(
        "/session/answer",
        headers=headers,
        json={
            "session_id": leg_sid,
            "round": 1,
            "answer_text": "One thread executes bytecode at once under the GIL mutex while blocking I/O syscalls release the lock.",
        },
    ).json()
    assert "feedback_deferred" not in leg_r1
    assert leg_r1["final_score"] is not None
    leg_fb1 = client.get(f"/session/{leg_sid}/rounds/1/feedback", headers=headers).json()
    assert "deferred" not in leg_fb1
    assert leg_fb1["final_score"] == pytest.approx(leg_r1["final_score"])


def test_quick_staged_v1_end_to_end_demo_bundles_with_inline_followup(staged_sql_env):
    """Offline Quick session with seeded Python demo_fixture bundles & inline follow-up."""
    db = staged_sql_env["db"]
    _, headers = _create_user_headers(db)
    seed_demo_bundles()
    _review_seeded_demo_bundles()
    client = TestClient(app)

    start_resp = client.post(
        "/session/start",
        headers=headers,
        json={"flow_version": "staged_v1", "preset": "Quick", "skills": ["Python"]},
    )
    assert start_resp.status_code == 200, start_resp.text
    start_body = start_resp.json()
    sid = start_body["session_id"]
    assert start_body["total_rounds"] == 3  # 1 warm-up + 2 core

    # Round 1: Warm-up (unscored)
    ans1 = client.post(
        "/session/answer",
        headers=headers,
        json={
            "session_id": sid,
            "round": 1,
            "answer_text": "Python uses dynamic typing and automatic reference counting.",
        },
    ).json()
    assert ans1["stage"] == "warm_up"
    assert ans1["next_round"] == 2

    # Round 2: Core 1 (GIL bundle) — omit io_release to trigger inline follow-up
    act2 = activate(client, headers, sid, 2)
    assert act2["config_json"]["stage"] == "core"
    ans2 = client.post(
        "/session/answer",
        headers=headers,
        json={
            "session_id": sid,
            "round": 2,
            "answer_text": "In CPython only one thread executes bytecode at once under the GIL mutex.",
        },
    ).json()
    assert ans2["stage"] == "core"
    assert ans2["follow_up_scheduled"] is True
    assert ans2["total_rounds"] == 4
    assert ans2["next_round"] == 3

    # Round 3: Inline follow-up targeting io_release
    act3 = activate(client, headers, sid, 3)
    assert act3["is_follow_up"] is True
    assert act3["config_json"]["stage"] == "follow_up"
    ans3 = client.post(
        "/session/answer",
        headers=headers,
        json={
            "session_id": sid,
            "round": 3,
            "answer_text": (
                "During socket reads or disk waits, blocking I/O syscalls release lock "
                "so another runnable thread can acquire the interpreter."
            ),
        },
    ).json()
    assert ans3["is_follow_up"] is True
    assert ans3["stage"] == "follow_up"
    assert ans3["final_score"] is None
    assert ans3["feedback_deferred"] is True
    assert ans3["next_round"] == 4

    # Round 4: Core 2 (Generators bundle) -> session completes
    act4 = activate(client, headers, sid, 4)
    assert act4["config_json"]["stage"] == "core"
    ans4 = client.post(
        "/session/answer",
        headers=headers,
        json={
            "session_id": sid,
            "round": 4,
            "answer_text": (
                "Yield suspends state in the generator execution frame so values are computed "
                "one item at a time in constant memory instead of building a full list."
            ),
        },
    ).json()
    assert ans4["session_complete"] is True
    assert ans4["session_status"] == "completed"
    assert ans4["total_rounds"] == 4

    # Post-completion debrief checks
    dash = client.get(f"/dashboard/{sid}", headers=headers).json()
    assert dash["deferred"] is False
    rounds = dash["rounds"]
    assert [r["stage"] for r in rounds] == ["warm_up", "core", "follow_up", "core"]
    assert rounds[0]["final_score"] is None
    assert rounds[2]["final_score"] is None
    assert rounds[2]["follow_up_outcome"]["status"] == "demonstrated"

    core1_score = float(rounds[1]["final_score"])
    core2_score = float(rounds[3]["final_score"])
    expected_mean = round((core1_score + core2_score) / 2.0, 2)
    assert dash["overall_readiness_score"] == pytest.approx(expected_mean, abs=0.02)
    assert dash["averages"]["final_score"] == pytest.approx(expected_mean, abs=0.02)
    assert dash["coverage"]["scored_rounds"] == 2

    fb3 = client.get(f"/session/{sid}/rounds/3/feedback", headers=headers).json()
    assert fb3["final_score"] is None
    assert fb3["follow_up_outcome"]["targets_concept"] == "io_release"
    assert fb3["follow_up_outcome"]["status"] == "demonstrated"
