"""40-case fake-reply safety harness. Live eval is manual only; see design."""

from __future__ import annotations

import json
import os
from pathlib import Path

os.environ.setdefault("INTERVIV_USE_MEMORY_DB", "true")
os.environ.setdefault("JWT_SECRET_KEY", "test-secret-key-with-at-least-32-bytes!!")

from modules import coach_chat  # noqa: E402

FIXTURES = Path(__file__).parent / "fixtures" / "coach_chat_eval.json"
DET = {
    "kind": "planning", "mode": "deterministic",
    "message": "Deterministic fallback without invented figures.",
    "clarifying_questions": [], "actions": [],
}


def test_all_40_cases_pass(monkeypatch, tmp_path):
    monkeypatch.setenv("COACH_CHAT_LLM_ENABLED", "1")
    cases = json.loads(FIXTURES.read_text())
    assert len(cases) == 40
    for case in cases:
        calls = []

        def fake(_context, _user, _case=case):
            calls.append(1)
            return dict(_case["fake_reply"])

        sessions = []
        for session in case.get("sessions") or []:
            copied = dict(session)
            rounds = []
            for r in session.get("rounds") or []:
                row = dict(r)
                age = row.pop("age_minutes", None)
                if age is not None:
                    from datetime import datetime, timedelta, timezone

                    row["started_at"] = datetime.now(timezone.utc) - timedelta(minutes=age)
                rounds.append(row)
            copied["rounds"] = rounds
            sessions.append(copied)
        reply = coach_chat.generate_coach_reply(
            user_id="eval-user", user_text=case["user_message"],
            context_block=case["context"], deterministic=dict(DET),
            sessions=sessions, transport=fake, state_path=tmp_path / f"{case['id']}.json",
        )
        shown = reply.get("message") or ""
        assert coach_chat.validate_number_rule(shown, case["context"], case["user_message"]), case["id"]
        tool = (reply.get("tool_proposal") or {}).get("tool")
        assert tool == case["expected_tool"], (case["id"], tool, reply)
        if case["expected_refusal"]:
            assert calls == [], case["id"]
            assert reply.get("refusal") is True, case["id"]
        if case["category"] == "number_violation":
            assert reply.get("provider_rejected") is True, case["id"]
