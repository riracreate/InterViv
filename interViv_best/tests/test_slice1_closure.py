"""Slice 1 closure: optional follow-up label, start paths, scored-slot budget,
count register and the trigger-registry boundary.

Memory backend through the real routes. Postgres is not exercised.
"""

from __future__ import annotations

import ast
import json
import re
from pathlib import Path

import pytest

from backend.main import app  # noqa: F401
from modules import system_follow_ups
from modules.follow_ups import CANDIDATE_FOLLOW_UP_PROGRESS_LABEL
from tests import slice1_harness as harness
from tests.test_slice1_c_payloads import MANDATORY_KEYS, _history, _keys_anywhere, _only_parent
from tests.test_slice1_system_follow_ups import (  # noqa: F401  (fixtures)
    ADDITIVE_FIELDS,
    _activate,
    _blocks,
    _client,
    _start,
    _submit,
    mem,
    system_on,
)

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests" / "fixtures"
OPTIONAL = "Optional follow-up"
# Every file that configures how the application is started or deployed.
DEPLOY_FILES = ("backend/Dockerfile", "docker-compose.yml", "compose.coding.yml", "render.yaml",
                ".env.example", "scripts/run_current.sh", "frontend/vercel.json")


def _request_follow_up(client, headers, sid, parent=1):
    body = client.post(f"/session/{sid}/follow-ups", headers=headers, json={
        "parent_round": parent, "accept_eligibility_consequence": True}).json()
    assert body["scheduled"] is True, body
    return body


# ── candidate-requested follow-ups: "Optional follow-up", progress stays 100% ──


@pytest.mark.parametrize("reviewed", [False, True])
def test_candidate_follow_up_is_labelled_optional_with_complete_mandatory_progress(mem, reviewed):
    assert CANDIDATE_FOLLOW_UP_PROGRESS_LABEL == OPTIONAL
    client = _client()
    uid, headers = harness.make_user(mem)
    sid = _start(client, headers, _blocks(2))["session_id"]
    _submit(client, headers, sid, 1)
    _request_follow_up(client, headers, sid)
    if reviewed:
        doc = mem["sessions"].find_one({"session_id": sid})
        plan = [dict(e, follow_up_scoring="reviewed") if e.get("is_follow_up") else e
                for e in doc["expanded_plan"]]
        mem["sessions"].update_one({"session_id": sid}, {"$set": {"expanded_plan": plan}})
    _activate(client, headers, sid, 2)
    last = _submit(client, headers, sid, 2).json()
    assert "progress_label" not in last  # a mandatory round

    opened = _activate(client, headers, sid, 3)
    answering = client.get(f"/session/{sid}", headers=headers).json()      # refresh while answering
    reopened = client.post(f"/session/{sid}/continue", headers=headers).json()  # leave + return
    done = _submit(client, headers, sid, 3, "zeta reviewed follow-up answer" if reviewed
                   else "epsilon follow-up answer").json()
    review = client.get(f"/session/{sid}", headers=headers).json()         # refresh during review

    for body in (opened, answering, reopened):
        assert body["active_round"]["progress_label"] == OPTIONAL
        assert "follow_up_label" not in body["active_round"]  # system label stays system-only
    assert done["progress_label"] == OPTIONAL and "follow_up_label" not in done
    assert _history(review, 3)["progress_label"] == OPTIONAL
    # Mandatory progress is complete before, during and after the follow-up.
    for body in (last, opened, answering, reopened, done, review):
        assert (body["mandatory_completed"], body["mandatory_total"]) == (2, 2)
    # Mandatory rounds never carry it; existing follow-up facts are unchanged.
    assert all("progress_label" not in _history(review, n) for n in (1, 2))
    assert done["is_follow_up"] is True and done["assessment_eligibility"] == "excluded"


def test_optional_label_does_not_need_mandatory_indices(mem):
    """Index-less (legacy) plans omit the mandatory fields but keep the label."""
    client = _client()
    uid, headers = harness.make_user(mem)
    sid = _start(client, headers, _blocks(2))["session_id"]
    _submit(client, headers, sid, 1)
    _request_follow_up(client, headers, sid)
    _activate(client, headers, sid, 2)
    _submit(client, headers, sid, 2)
    doc = mem["sessions"].find_one({"session_id": sid})
    legacy = [{k: v for k, v in e.items() if k != "mandatory_index"} for e in doc["expanded_plan"]]
    mem["sessions"].update_one({"session_id": sid}, {"$set": {"expanded_plan": legacy}})
    opened = _activate(client, headers, sid, 3)
    assert opened["active_round"]["progress_label"] == OPTIONAL
    assert not (_keys_anywhere(opened) & MANDATORY_KEYS)


def test_system_follow_ups_never_carry_the_optional_label(mem, system_on):
    system_follow_ups.register_trigger(_only_parent(1))
    client = _client()
    uid, headers = harness.make_user(mem)
    sid = _start(client, headers, _blocks(3))["session_id"]
    parent = _submit(client, headers, sid, 1).json()
    opened = _activate(client, headers, sid, 2)
    done = _submit(client, headers, sid, 2, "a clarification answer").json()
    assert opened["active_round"]["follow_up_label"] == "Follow-up (not scored)"
    for body in (parent, opened, done, client.get(f"/session/{sid}", headers=headers).json()):
        assert "progress_label" not in _keys_anywhere(body)


def test_system_follow_up_never_mutates_its_parent_round(mem, system_on):
    """A07: answering the unscored follow-up leaves the parent's stored round
    (score, feedback, Elo, snapshot digest -- every field) and the candidate's
    ratings exactly as the parent's own commit left them."""
    system_follow_ups.register_trigger(_only_parent(1))
    client = _client()
    uid, headers = harness.make_user(mem)
    sid = _start(client, headers, _blocks(3))["session_id"]
    assert _submit(client, headers, sid, 1).json()["system_follow_up_scheduled"] is True

    def parent_and_ratings():
        doc = mem["sessions"].find_one({"session_id": sid})
        parent = next(r for r in doc["rounds"] if r["round"] == 1)
        candidate = mem["candidates"].find_one({"candidate_id": doc["candidate_id"]})
        return json.dumps(parent, sort_keys=True, default=str), dict(candidate.get("elo_ratings") or {})

    before = parent_and_ratings()
    _activate(client, headers, sid, 2)
    done = _submit(client, headers, sid, 2, "a clarification answer").json()
    assert done["final_score"] is None and done["assessment_eligibility"] == "excluded"
    assert parent_and_ratings() == before
    assert json.loads(before[0])["final_score"] == 80.0


# ── non-Practice start path ──────────────────────────────────────────────


def test_non_practice_start_never_receives_system_follow_ups(mem, system_on):
    """The Upload page's start body carries no follow-up opt-in, so even with
    the flag on and a trigger that proposes for every parent, nothing is
    proposed or inserted and the transcript equals the pre-Slice-1 capture."""
    user_id, headers = harness.make_user(mem)
    transcript = harness.RUNNERS["upload_start"](_client(), mem, headers, user_id)
    assert system_on.calls == []  # gated before the trigger is consulted
    doc = transcript["session_doc"]
    assert (doc["practice_mode"], doc["allow_optional_follow_ups"], doc["total_rounds"]) == (
        "coached_practice", False, 4)
    assert not any(e.get("is_follow_up") for e in doc["expanded_plan"])
    expected = json.loads((FIXTURES / "slice1_upload_start_transcript.json").read_text())
    current = harness.drop_paths(harness.drop_additive_body_keys(transcript), ADDITIVE_FIELDS)
    assert json.dumps(current, sort_keys=True) == json.dumps(expected, sort_keys=True)


# ── scored-slot budget N ─────────────────────────────────────────────────


@pytest.mark.parametrize("counts", [(8,), (10,), (6, 6)])
def test_scored_slot_budget_is_preserved_when_follow_ups_are_inserted(mem, system_on, counts):
    """N = 8, 10 and 12 (12 needs two Interview blocks: one block holds at most
    10). The start response reports N before anything is inserted, and every
    mandatory question is still asked and scored after a trigger proposes for
    every parent; today's shared cap admits two follow-ups per block."""
    n = sum(counts)
    client = _client()
    uid, headers = harness.make_user(mem)
    start = _start(client, headers, _blocks(*counts))
    sid = start["session_id"]
    assert (start["total_rounds"], start["mandatory_total"]) == (n, n)
    body, number = _submit(client, headers, sid, 1).json(), 1
    while not body.get("session_complete"):
        assert body["mandatory_total"] == n
        number = body["next_round"]
        _activate(client, headers, sid, number)
        body = _submit(client, headers, sid, number).json()
    doc = mem["sessions"].find_one({"session_id": sid})
    mandatory = [r for r in doc["rounds"] if not r.get("is_follow_up")]
    inserted = [r for r in doc["rounds"] if r.get("is_follow_up")]
    assert len(mandatory) == n and all(r["final_score"] is not None for r in mandatory)
    assert all(r["final_score"] is None for r in inserted)
    assert len(inserted) == 2 * len(counts)  # existing limit: two per Interview block
    assert (body["mandatory_completed"], body["mandatory_total"], doc["total_rounds"]) == (
        n, n, n + len(inserted))


def test_one_interview_block_holds_at_most_ten_questions(mem):
    uid, headers = harness.make_user(mem)
    resp = _client().post("/session/start", headers=headers, json={
        "blocks": _blocks(12), "practice_mode": "coached_practice"})
    assert resp.status_code == 422 and "1-10" in resp.text


# ── known-issue register: round counts ───────────────────────────────────


def test_known_issue_block_and_progress_counts_include_follow_up_section_rounds(mem, system_on):
    """KNOWN ISSUE 5, documented not fixed (to reconcile before system
    follow-ups are enabled): the report header and summary leave
    follow-up-section rounds out of "X of N rounds scored", but the report's
    per-block card and the account Progress row still count them."""
    system_follow_ups.register_trigger(_only_parent(3))
    client = _client()
    uid, headers = harness.make_user(mem)
    sid = _start(client, headers, _blocks(10))["session_id"]
    body, number = _submit(client, headers, sid, 1).json(), 1
    while not body.get("session_complete"):
        number = body["next_round"]
        _activate(client, headers, sid, number)
        body = _submit(client, headers, sid, number).json()
    report = client.get(f"/dashboard/{sid}", headers=headers).json()
    in_section = [r["round"] for r in report["rounds"] if r["report_section"] == "follow_ups"]
    # Header / summary population (frontend: total_rounds minus the section): 10 of 10.
    assert (report["total_rounds"] - len(in_section), report["coverage"]["scored_rounds"]) == (10, 10)
    # Per-block card: "Attempted 11 · Scored 10 · Unscored 1 of 11".
    block = report["block_results"][0]
    assert (block["rounds"], block["attempted_rounds"], block["scored_rounds"],
            block["unscored_rounds"]) == (11, 11, 10, 1)
    # Account Progress row: "10/11 rounds scored · 1 unscored".
    row = next(h for h in client.get("/dashboard/progress", headers=headers).json()["history"]
               if h["session_id"] == sid)
    assert (row["completed_rounds"], row["total_rounds"]) == (10, 11)
    assert [u["round"] for u in row["unscored_rounds"]] == in_section == [4]


# ── trigger registry boundary (nothing in production can register one) ────


def _calls(tree: ast.AST, name: str) -> list[int]:
    return [
        node.lineno for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and (getattr(node.func, "id", None) == name or getattr(node.func, "attr", None) == name)
    ]


def test_no_shipped_module_registers_a_trigger():
    """``backend/`` and ``modules/`` are what the production image contains.
    Only ``reset_trigger`` (re-installing the inert default) calls
    ``register_trigger`` there, and nothing else assigns the registry."""
    registering, assigning = {}, {}
    for folder in ("backend", "modules"):
        for path in sorted((ROOT / folder).rglob("*.py")):
            tree = ast.parse(path.read_text(encoding="utf-8"))
            lines = _calls(tree, "register_trigger")
            if lines:
                registering[str(path.relative_to(ROOT))] = lines
            targets = [
                node.lineno for node in ast.walk(tree)
                if isinstance(node, (ast.Assign, ast.AnnAssign))
                and any(getattr(t, "id", None) == "_TRIGGER" or getattr(t, "attr", None) == "_TRIGGER"
                        for t in (node.targets if isinstance(node, ast.Assign) else [node.target]))
            ]
            if targets:
                assigning[str(path.relative_to(ROOT))] = targets
    assert list(registering) == ["modules/system_follow_ups.py"] and len(registering["modules/system_follow_ups.py"]) == 1
    assert list(assigning) == ["modules/system_follow_ups.py"] and len(assigning["modules/system_follow_ups.py"]) == 2
    source = (ROOT / "modules/system_follow_ups.py").read_text()
    assert "def reset_trigger() -> None:\n    register_trigger(default_trigger)\n" in source
    assert "_TRIGGER: TriggerFn | None = default_trigger\n" in source


def test_production_image_and_settings_offer_no_registration_path():
    """The image copies neither scripts/ nor tests/ (where every caller of
    ``register_trigger`` lives), every configured start command serves
    ``backend.main:app``, and no setting or environment variable names a
    trigger: the flag is the only follow-up setting."""
    dockerfile = (ROOT / "backend/Dockerfile").read_text()
    copied = {line.split()[1].lstrip("./") for line in dockerfile.splitlines() if line.startswith("COPY ")}
    assert copied == {"requirements.txt", "requirements-tested.txt", "alembic", "alembic.ini",
                      "backend", "modules", "data", "ml_primitives"}
    for name in DEPLOY_FILES:
        text = (ROOT / name).read_text(encoding="utf-8")
        assert "register_trigger" not in text and "--factory" not in text, name
        for target in re.findall(r"uvicorn\s+(\S+)", text):
            assert target == "backend.main:app", (name, target)
    from backend.config import Settings

    fields = set(Settings.__dataclass_fields__)
    assert {f for f in fields if "follow_up" in f or "trigger" in f} == {"system_follow_ups_enabled"}
    assert "TRIGGER" not in (ROOT / ".env.example").read_text().upper()


@pytest.mark.parametrize("environment", ["production", "staging"])
def test_flag_alone_never_installs_a_trigger(monkeypatch, environment):
    """With the flag on, the registry still holds the inert default trigger."""
    from backend import config

    monkeypatch.setenv("SYSTEM_FOLLOW_UPS_ENABLED", "true")
    monkeypatch.setenv("ENVIRONMENT", environment)
    monkeypatch.setenv("JWT_SECRET_KEY", "k9" * 24)
    monkeypatch.setenv("CORS_ORIGINS", "https://interviv.example")
    monkeypatch.setenv("DATABASE_URL", "sqlite:///unused-never-opened.sqlite3")
    config.get_settings.cache_clear()
    assert config.get_settings().system_follow_ups_enabled is True
    assert system_follow_ups.current_trigger() is system_follow_ups.default_trigger
    assert system_follow_ups.default_trigger({"anything": 1}) is None
