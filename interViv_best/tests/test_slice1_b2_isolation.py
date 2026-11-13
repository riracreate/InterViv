"""Slice 1 / Checkpoint B2: selector isolation, eligibility, snapshots, report.

Backends: memory and SQLite. Postgres is NOT exercised here.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from backend.main import app  # noqa: F401  (route registration)
from modules import adaptive_question_selector, system_follow_ups
from modules.concept_mastery import ConceptMastery
from modules.attempt_snapshot import (
    freeze_attempt_snapshot,
    regenerate_rules_feedback,
    replayable_snapshots,
    snapshot_digest,
    snapshot_has_follow_up_markers,
    verify_attempt_snapshot,
)
from modules.skill_graph import StudentSkillGraph
from modules.system_follow_ups import SystemFollowUpProposal
from tests import slice1_harness as harness
from tests.test_slice1_system_follow_ups import (  # noqa: F401  (fixtures)
    STUB_PROMPT,
    _activate,
    _client,
    _exposures,
    _follow_up_entries,
    _server_only_paths,
    _start,
    _submit,
    independent_workers,
    mem,
    sql_db,
    system_on,
)

FIXTURES = Path(__file__).resolve().parent / "fixtures"
ISO_BLOCKS = [{"round_type": "technical_short_answer", "category": "interview",
               "skills": ["DBMS", "OS"], "count": 3, "allow_optional_follow_ups": True}]
SERVED_KEYS = ("skill", "difficulty", "question", "elo_before", "adaptive_target", "sub_domain")


def _only_for(session_ids, prompt=STUB_PROMPT):
    def trigger(context):
        if context["session"]["session_id"] in session_ids:
            return SystemFollowUpProposal(prompt=prompt)
        return None
    return trigger


def _round(db, sid, number):
    return next(r for r in db["sessions"].find_one({"session_id": sid})["rounds"] if r["round"] == number)


def _served(round_doc):
    ctx = round_doc.get("question_context") or {}
    return {"skill": round_doc["skill"], "difficulty": round_doc["difficulty"],
            "question": round_doc["question"], "elo_before": float(round_doc["elo_before"]),
            "adaptive_target": ctx.get("adaptive_target"), "sub_domain": ctx.get("sub_domain")}


def _bank(monkeypatch, fn):
    for module in ("backend.routes.answer", "backend.routes.session", "backend.routes.session_continue"):
        monkeypatch.setattr(f"{module}._get_next_question", fn)


# ── test 1: selector isolation (reported first) ──────────────────────


@pytest.mark.parametrize("backend", ["memory", "sqlite"])
@pytest.mark.parametrize("resume", ["submit", "continue"])
def test_selector_isolation_serves_the_normal_paths_target(backend, resume, request, system_on,
                                                           monkeypatch):
    """The next mandatory question served AFTER the follow-up equals the one the
    normal path serves with no insertion, although the skill graph changed in
    between (parent learning update plus an extra update); covers leaving
    during the follow-up and returning via GET and /continue."""
    from backend.integrations import IntegrationError

    if backend == "memory":
        db, engine = request.getfixturevalue("mem"), None
    else:
        db, engine = request.getfixturevalue("sql_db")
    client = _client()
    plain_uid, plain_h = harness.make_user(db, prefix="iso-plain")
    ins_uid, ins_h = harness.make_user(db, prefix="iso-insert")
    plain = _start(client, plain_h, ISO_BLOCKS)["session_id"]
    ins = _start(client, ins_h, ISO_BLOCKS)["session_id"]
    system_follow_ups.register_trigger(_only_for({ins}))
    answer = harness.TRANSCRIPT_ANSWERS[0]

    # No insertion: the normal path serves the next mandatory round now.
    body = _submit(client, plain_h, plain, 1, answer).json()
    assert body["next_round"] == 2 and not _round(db, plain, 2).get("is_follow_up")
    expected = _served(_round(db, plain, 2))

    # Insertion: the follow-up is next; the mandatory target is preserved
    # on its spec, resolved before the parent's learning updates.
    body = _submit(client, ins_h, ins, 1, answer).json()
    assert body["next_round"] == 2 and _round(db, ins, 2)["is_follow_up"] is True
    stored = db["sessions"].find_one({"session_id": ins})
    spec = next(s for s in stored["expanded_plan"] if s.get("mandatory_index") == 2)
    assert spec["round"] == 3 and spec["resolved_next_target"]["next_skill"] == expected["skill"]

    # A skill-graph update between parent and follow-up submission that WOULD
    # change the target if it were recomputed now.
    StudentSkillGraph(ins_uid).update_after_round(skill="DBMS", score=99.0, difficulty="medium")
    live = adaptive_question_selector.choose_adaptive_target(
        user_id=ins_uid, fallback_skill="DBMS", fallback_difficulty="medium",
        session_skills=["DBMS", "OS"], candidate_elo_by_skill={})
    assert live.skill != expected["skill"], "test must exercise a diverging recomputation"

    # Leave during the follow-up and return.
    _activate(client, ins_h, ins, 2)
    if engine is not None:
        engine.dispose()  # restore from storage on fresh connections
    restored = client.get(f"/session/{ins}", headers=ins_h).json()
    assert restored["active_round"]["round"] == 2 and restored["active_round"]["question"] == STUB_PROMPT
    reopened = client.post(f"/session/{ins}/continue", headers=ins_h)
    assert reopened.status_code == 200 and reopened.json()["round"] == 2
    progress = client.get("/dashboard/progress", headers=ins_h).json()
    assert progress["resumable_session"]["session_id"] == ins
    for payload in (restored, reopened.json(), progress):
        assert _server_only_paths(payload) == []

    if resume == "submit":
        body = _submit(client, ins_h, ins, 2, "a clarification answer").json()
        assert body["next_round"] == 3 and body["next_round_status"] == "ready"
    else:
        def bank_miss(**kwargs):
            raise IntegrationError("stub bank exhausted")

        _bank(monkeypatch, bank_miss)
        body = _submit(client, ins_h, ins, 2, "a clarification answer").json()
        assert body["session_status"] == "content_blocked"
        if engine is not None:
            engine.dispose()
        assert client.get(f"/session/{ins}", headers=ins_h).json()["status"] == "content_blocked"
        _bank(monkeypatch, harness.stub_next_question)
        resumed = client.post(f"/session/{ins}/continue", headers=ins_h)
        assert resumed.status_code == 200 and resumed.json()["round"] == 3
        assert _server_only_paths(resumed.json()) == []
    served = _served(_round(db, ins, 3))
    assert {k: served[k] for k in SERVED_KEYS} == {k: expected[k] for k in SERVED_KEYS}
    assert served["skill"] != live.skill


# ── test 2: eligibility, and no learning effects from the follow-up ──


def _eligibility(round_doc):
    return (round_doc.get("assessment_eligibility"), list(round_doc.get("eligibility_exclusion_reasons") or []))


def _account_signals(client, headers):
    body = client.get("/dashboard/progress", headers=headers).json()
    return {k: body[k] for k in ("readiness", "readiness_observed", "skills", "target",
                                 "learning_signals", "readiness_assistance", "scored_session_count")}


@pytest.mark.parametrize("mode", ["coached_practice", "assessment_api_opt_in"])
def test_eligibility_unchanged_by_intervening_follow_up(mem, system_on, mode):
    client = _client()
    extra = ({"practice_mode": "assessment", "allow_optional_follow_ups": True}
             if mode == "assessment_api_opt_in" else {})
    blocks = [dict(ISO_BLOCKS[0], skills=["DBMS"], allow_optional_follow_ups=(mode == "coached_practice"))]
    sessions = {}
    for name in ("plain", "ins"):
        uid, headers = harness.make_user(mem, prefix=f"elig-{name}")
        mem["target_contexts"].insert_one({"user_id": uid, "company_id": "tcs", "role_id": "tcs_swe"})
        resp = client.post("/session/start", headers=headers, json={"blocks": blocks, **extra})
        assert resp.status_code == 200, resp.text
        sessions[name] = (resp.json()["session_id"], uid, headers)
    plain, _, plain_h = sessions["plain"]
    ins, ins_uid, ins_h = sessions["ins"]
    if mode == "assessment_api_opt_in":
        assert mem["sessions"].find_one({"session_id": ins})["practice_mode"] == "assessment"
    # The prompt deliberately equals the next mandatory question's text: a
    # same-item check that saw the follow-up would mark that round a retry.
    trap = "[DBMS] Stub question 2: explain the core idea?"
    system_follow_ups.register_trigger(_only_for({ins}, prompt=trap))
    answer = harness.TRANSCRIPT_ANSWERS[0]

    _submit(client, plain_h, plain, 1, answer)
    _submit(client, ins_h, ins, 1, answer)
    assert _eligibility(_round(mem, plain, 1)) == _eligibility(_round(mem, ins, 1)) == ("eligible", [])

    candidate_id = mem["sessions"].find_one({"session_id": ins})["candidate_id"]
    elo_before = mem["candidates"].find_one({"candidate_id": candidate_id})["elo_ratings"]
    signals_before = _account_signals(client, ins_h)
    mastery_before = copy.deepcopy(ConceptMastery().get_mastery_details(ins_uid))
    _activate(client, ins_h, ins, 2)
    fu = _submit(client, ins_h, ins, 2, "a clarification answer").json()
    assert fu["final_score"] is None
    follow_up = _round(mem, ins, 2)
    assert _eligibility(follow_up) == ("excluded", ["follow_up", "unreviewed_follow_up"])
    # Unscored, ineligible, exposure-free; no Elo, mastery, readiness or gap effects.
    assert mem["candidates"].find_one({"candidate_id": candidate_id})["elo_ratings"] == elo_before
    assert _account_signals(client, ins_h) == signals_before
    assert ConceptMastery().get_mastery_details(ins_uid) == mastery_before
    assert _exposures(mem, ins) == []

    assert _round(mem, ins, 3)["question"] == trap == _round(mem, plain, 2)["question"]
    _activate(client, plain_h, plain, 2)
    _submit(client, plain_h, plain, 2, harness.TRANSCRIPT_ANSWERS[1])
    _activate(client, ins_h, ins, 3)
    _submit(client, ins_h, ins, 3, harness.TRANSCRIPT_ANSWERS[1])
    assert _eligibility(_round(mem, plain, 2)) == _eligibility(_round(mem, ins, 3)) == ("eligible", [])


# ── test 3: report exposure recording ────────────────────────────────


def _walk(client, headers, sid, answers):
    number, body = 1, None
    for text in answers:
        if number > 1:
            _activate(client, headers, sid, number)
        body = _submit(client, headers, sid, number, text).json()
        if body["session_complete"]:
            return body
        number = body["next_round"]
    return body


def _reveals(db, sid):
    return sorted(d["round"] for d in (db["teaching_exposures"].find({"session_id": sid}) or [])
                  if d.get("content_kind") == "feedback_reveal")


def test_report_exposure_skips_only_system_and_unreviewed_follow_ups(mem, system_on):
    client = _client()
    uid, headers = harness.make_user(mem, prefix="reveal")
    # Session X: system follow-up (round 2) and an unreviewed candidate
    # follow-up (round 5); both get a FORCED numeric score in storage.
    sx = _start(client, headers, _blocks_one(3))["session_id"]
    system_follow_ups.register_trigger(_only_for({sx}))
    _submit(client, headers, sx, 1, harness.TRANSCRIPT_ANSWERS[0])
    _activate(client, headers, sx, 2)
    _submit(client, headers, sx, 2, "a clarification answer")
    system_follow_ups.register_trigger(None)
    _activate(client, headers, sx, 3)
    _submit(client, headers, sx, 3, harness.TRANSCRIPT_ANSWERS[1])
    assert client.post(f"/session/{sx}/follow-ups", headers=headers, json={
        "parent_round": 3, "accept_eligibility_consequence": True}).json()["scheduled"] is True
    _activate(client, headers, sx, 4)
    _submit(client, headers, sx, 4, harness.TRANSCRIPT_ANSWERS[2])
    _activate(client, headers, sx, 5)
    assert _submit(client, headers, sx, 5, "epsilon follow-up answer").json()["session_complete"]
    doc = mem["sessions"].find_one({"session_id": sx})
    rounds = [dict(r, final_score=77.0) if r.get("is_follow_up") else r for r in doc["rounds"]]
    mem["sessions"].update_one({"session_id": sx}, {"$set": {"rounds": rounds}})
    assert client.get(f"/dashboard/{sx}", headers=headers).status_code == 200
    assert _reveals(mem, sx) == [1, 3, 4]  # never 2 (system) or 5 (unreviewed)

    # Session Y: a REVIEWED, scored candidate follow-up keeps today's exposure.
    uid2, headers2 = harness.make_user(mem, prefix="reveal-reviewed")
    sy = _start(client, headers2, _blocks_one(2))["session_id"]
    _submit(client, headers2, sy, 1, harness.TRANSCRIPT_ANSWERS[0])
    client.post(f"/session/{sy}/follow-ups", headers=headers2, json={
        "parent_round": 1, "accept_eligibility_consequence": True})
    doc = mem["sessions"].find_one({"session_id": sy})
    plan = [dict(e, follow_up_scoring="reviewed") if e.get("is_follow_up") else e for e in doc["expanded_plan"]]
    mem["sessions"].update_one({"session_id": sy}, {"$set": {"expanded_plan": plan}})
    _activate(client, headers2, sy, 2)
    _submit(client, headers2, sy, 2, harness.TRANSCRIPT_ANSWERS[1])
    _activate(client, headers2, sy, 3)
    assert _submit(client, headers2, sy, 3, "zeta reviewed follow-up answer").json()["final_score"] == 100.0
    client.get(f"/dashboard/{sy}", headers=headers2)
    assert _reveals(mem, sy) == [1, 2, 3]


def _blocks_one(count):
    return [{"round_type": "technical_short_answer", "category": "interview",
             "skills": ["DBMS"], "count": count, "allow_optional_follow_ups": True}]


# ── private metadata: persisted, stripped from client payloads ───────


@pytest.mark.parametrize("backend", ["memory", "sqlite"])
def test_initiator_and_kind_are_private_round_metadata(backend, request, system_on):
    db = request.getfixturevalue("mem") if backend == "memory" else request.getfixturevalue("sql_db")[0]
    client = _client()
    uid, headers = harness.make_user(db)
    sid = _start(client, headers, _blocks_one(3))["session_id"]
    _submit(client, headers, sid, 1)
    stored = _round(db, sid, 2)
    assert (stored["follow_up_initiator"], stored["follow_up_kind"]) == ("system", "clarification")
    assert "follow_up_initiator" not in (stored.get("config_json") or {})
    if backend == "sqlite":
        from sqlalchemy import select

        from backend.db.sqlalchemy_models import RoundRow
        from backend.db.sqlalchemy_store import session_scope

        with session_scope() as session:
            meta = session.execute(select(RoundRow.private_meta_json).where(
                RoundRow.session_id == sid, RoundRow.round_number == 2)).scalar()
        assert meta["follow_up_initiator"] == "system" and meta["follow_up_kind"] == "clarification"
    bodies = [_activate(client, headers, sid, 2), client.get(f"/session/{sid}", headers=headers).json()]
    _submit(client, headers, sid, 2, "a clarification answer")
    bodies.append(client.get(f"/dashboard/{sid}", headers=headers).json())
    for body in bodies:
        assert _server_only_paths(body) == []
    assert _round(db, sid, 2)["follow_up_initiator"] == "system"  # survives submit


# ── test 4: snapshots ────────────────────────────────────────────────


LEGACY = json.loads((FIXTURES / "slice1_legacy_snapshots.json").read_text())


def test_new_follow_up_snapshots_freeze_not_replayable(mem, system_on):
    client = _client()
    uid, headers = harness.make_user(mem)
    sid = _start(client, headers, _blocks_one(2))["session_id"]
    _submit(client, headers, sid, 1)                       # system follow-up -> round 2
    system_follow_ups.register_trigger(None)
    _activate(client, headers, sid, 2)
    _submit(client, headers, sid, 2, "a clarification answer")
    _activate(client, headers, sid, 3)
    _submit(client, headers, sid, 3, harness.TRANSCRIPT_ANSWERS[1])
    rounds = mem["sessions"].find_one({"session_id": sid})["rounds"]
    by_round = {r["round"]: r["attempt_snapshot"] for r in rounds}
    assert by_round[2]["rules_replayable"] is False and verify_attempt_snapshot(by_round[2])
    assert regenerate_rules_feedback(by_round[2]) is None
    assert by_round[1]["rules_replayable"] is True and by_round[3]["rules_replayable"] is True
    assert [s["round"] for s in replayable_snapshots(rounds)] == [1, 3]


def test_non_follow_up_freeze_is_byte_identical_to_pre_slice1():
    inputs = LEGACY["inputs"]
    for name in ("mandatory", "reviewed_follow_up"):
        # Mandatory rounds AND reviewed scored candidate follow-ups freeze
        # byte-identically to the pre-change code (same digest).
        assert freeze_attempt_snapshot(inputs[name], inputs["scoring_result"]) == LEGACY["frozen"][name]
    assert LEGACY["frozen"]["reviewed_follow_up"]["rules_replayable"] is True
    new_follow_up = freeze_attempt_snapshot(inputs["follow_up"], inputs["scoring_result"])
    assert new_follow_up["rules_replayable"] is False  # unreviewed only
    assert new_follow_up["digest"] != LEGACY["frozen"]["follow_up"]["digest"]


def test_legacy_follow_up_snapshot_read_guard_keeps_digest():
    legacy = copy.deepcopy(LEGACY["frozen"]["follow_up"])
    pristine = copy.deepcopy(legacy)
    assert legacy["rules_replayable"] is True  # frozen before Slice 1
    assert verify_attempt_snapshot(legacy)
    assert snapshot_has_follow_up_markers(legacy)  # nested legacy markers only
    assert "is_follow_up" not in legacy
    assert regenerate_rules_feedback(legacy) is None
    assert legacy == pristine and verify_attempt_snapshot(legacy)  # nothing rewritten
    # A legacy row whose round document lost its follow-up flag is still excluded.
    row = {"round": 2, "question": legacy["question"], "attempt_snapshot": legacy}
    assert replayable_snapshots([row]) == []
    # A legacy REVIEWED candidate follow-up carries no unreviewed marker and
    # stays replayable.
    reviewed = copy.deepcopy(LEGACY["frozen"]["reviewed_follow_up"])
    assert not snapshot_has_follow_up_markers(reviewed)
    assert isinstance(regenerate_rules_feedback(reviewed), dict)
    assert verify_attempt_snapshot(reviewed)


def _rescore_without(snapshot, key):
    core = {k: v for k, v in snapshot.items() if k not in ("digest", key)}
    return {**core, "digest": snapshot_digest(core)}


@pytest.fixture
def mem_real_scorer(monkeypatch):
    """Memory store + stubbed bank, but the REAL scoring pipeline."""
    db = harness.install(monkeypatch)
    import backend.routes.answer as answer_module
    from modules.scoring import score_round

    monkeypatch.setattr(answer_module, "score_round", score_round)
    return db


def test_replay_equality_and_replayable_snapshot_rejections(mem_real_scorer):
    db = mem_real_scorer
    client = _client()
    uid, headers = harness.make_user(db)
    sid = _start(client, headers, _blocks_one(2))["session_id"]
    resp = _submit(client, headers, sid, 1,
                   "Normalization splits tables so each fact is stored once, removing update anomalies.")
    assert resp.status_code == 200, resp.text
    rounds = db["sessions"].find_one({"session_id": sid})["rounds"]
    snapshot = rounds[0]["attempt_snapshot"]
    assert regenerate_rules_feedback(snapshot) == rounds[0]["feedback"]  # replay equality
    assert replayable_snapshots(rounds) == [snapshot]

    missing = copy.deepcopy(rounds)
    missing[0]["attempt_snapshot"] = _rescore_without(snapshot, "answer")
    assert verify_attempt_snapshot(missing[0]["attempt_snapshot"])  # intact, just incomplete
    assert replayable_snapshots(missing) == []
    mismatched = copy.deepcopy(rounds)
    mismatched[0]["question"] = "A different question?"
    assert replayable_snapshots(mismatched) == []
    tampered = copy.deepcopy(rounds)
    tampered[0]["attempt_snapshot"]["scores"]["final_score"] = 100.0
    assert replayable_snapshots(tampered) == []
    for marking, kept in (({"follow_up_scoring": "unreviewed"}, False),
                          ({"follow_up_initiator": "system", "follow_up_scoring": "unreviewed"}, False),
                          ({"follow_up_scoring": "reviewed"}, True)):
        variant = copy.deepcopy(rounds)
        variant[0].update({"is_follow_up": True, **marking})
        assert (replayable_snapshots(variant) == [snapshot]) is kept, marking


def test_reviewed_candidate_follow_up_stays_replayable(mem_real_scorer):
    """Reviewed, scored candidate follow-ups keep rules replay (real pipeline)."""
    db = mem_real_scorer
    client = _client()
    uid, headers = harness.make_user(db)
    sid = _start(client, headers, _blocks_one(2))["session_id"]
    text = "Normalization splits tables so each fact is stored once, removing update anomalies."
    _submit(client, headers, sid, 1, text)
    assert client.post(f"/session/{sid}/follow-ups", headers=headers, json={
        "parent_round": 1, "accept_eligibility_consequence": True}).json()["scheduled"]
    doc = db["sessions"].find_one({"session_id": sid})
    plan = [dict(e, follow_up_scoring="reviewed") if e.get("is_follow_up") else e for e in doc["expanded_plan"]]
    db["sessions"].update_one({"session_id": sid}, {"$set": {"expanded_plan": plan}})
    _activate(client, headers, sid, 2)
    _submit(client, headers, sid, 2, "An index is a sorted structure that speeds up lookups on a column.")
    _activate(client, headers, sid, 3)
    resp = _submit(client, headers, sid, 3, "A B-tree index keeps keys ordered so range scans stay fast.")
    assert resp.json()["final_score"] is not None
    rounds = db["sessions"].find_one({"session_id": sid})["rounds"]
    follow_up = rounds[2]
    assert follow_up["is_follow_up"] is True
    snap = follow_up["attempt_snapshot"]
    assert snap["rules_replayable"] is True and not snapshot_has_follow_up_markers(snap)
    assert regenerate_rules_feedback(snap) == follow_up["feedback"]
    assert [s["round"] for s in replayable_snapshots(rounds)] == [1, 2, 3]


# ── test 5: candidate-follow-up compatibility (account level) ────────


def test_account_level_candidate_follow_ups_unchanged(mem):
    """Readiness (conservative + observed), skill-graph attempts, scored-session
    count, Progress history and reports equal the pre-Slice-1 capture."""
    user_id, headers = harness.make_user(mem)
    transcript = harness.drop_additive_body_keys(
        harness.RUNNERS["account_candidate_follow_ups"](_client(), mem, headers, user_id))
    expected = json.loads((FIXTURES / "slice1_account_transcript.json").read_text())
    assert json.dumps(transcript, sort_keys=True) == json.dumps(expected, sort_keys=True)


def test_two_reviewed_candidate_follow_ups_unchanged(mem):
    """Asked list keeps candidate follow-ups: a reviewed follow-up's bank
    question is never re-served to the next follow-up (pre-change capture)."""
    user_id, headers = harness.make_user(mem)
    transcript = harness.drop_additive_body_keys(
        harness.RUNNERS["two_candidate_follow_ups"](_client(), mem, headers, user_id))
    expected = json.loads((FIXTURES / "slice1_two_candidate_transcript.json").read_text())
    assert json.dumps(transcript, sort_keys=True) == json.dumps(expected, sort_keys=True)
    questions = [q for _, _, q in transcript["served_questions"]]
    assert len(questions) == len(set(questions)) == 5


def test_known_issue_reviewed_candidate_follow_up_in_report_series():
    """KNOWN ISSUE, documented not fixed: with 80 / 60 plus a reviewed candidate
    follow-up of 100, the assessed mean and session readiness are 70, yet the
    scored series the report and charts use includes the 100 (best 100,
    range 40, 3 of 3 scored). Frontend: dashboardMapping.js:154-168 (scores,
    range), :249 (chart), :362 (best), :376 (count)."""
    expected = json.loads((FIXTURES / "slice1_account_transcript.json").read_text())
    steps = {s["step"]: s["body"] for s in expected["steps"]}
    report = steps["s1_report"]
    assert report["averages"]["final_score"] == 70.0
    assert report["overall_readiness_score"] == 70.0
    scored = [r["final_score"] for r in report["rounds"] if r.get("final_score") is not None]
    assert scored == [80.0, 60.0, 100.0]
    assert (max(scored), max(scored) - min(scored)) == (100.0, 40.0)
    assert len(report["elo_progression"]) == 3
    history = {h["session_id"]: h for h in steps["progress_after_reports"]["history"]}
    s1 = history["<s1>"]
    assert (s1["completed_rounds"], s1["total_rounds"], s1["average_score"]) == (3, 3, 70.0)
