"""Shared helpers for the explicit round lifecycle (overhaul Phase 2).

After a submission the next round is persisted as ``ready``; the candidate
opens it with ``POST /session/{id}/rounds/{n}/activate``, which starts its
clock. Tests that walk a session call ``activate`` where the UI's
"Next Question" would.
"""

from __future__ import annotations

from typing import Any


def activate(client: Any, headers: dict[str, str] | None, session_id: str, round_number: int) -> dict[str, Any]:
    """Open a prepared round and return its sanitized ``active_round``."""
    resp = client.post(
        f"/session/{session_id}/rounds/{round_number}/activate",
        headers=headers or {},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["active_round"]["round"] == round_number
    assert body["active_round"]["status"] == "in_progress"
    return body["active_round"]


def activate_next(
    client: Any, headers: dict[str, str] | None, session_id: str, answer_body: dict[str, Any]
) -> dict[str, Any]:
    """Open the round an answer response says was prepared."""
    assert answer_body.get("next_round_status") == "ready", answer_body
    return activate(client, headers, session_id, answer_body["next_round"])
