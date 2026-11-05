"""Client view of a session's ``expanded_plan``.

``expanded_plan`` is server state. The only route that serializes it is
``GET /dashboard/{session_id}`` (whole-document report payload); every key
added for Slice 1 scheduling is stripped there so the client body stays
exactly what it was before those keys existed.
"""

from __future__ import annotations

import copy
from typing import Any

# Server-only plan-entry keys (Slice 1). Pre-existing keys are untouched.
SERVER_ONLY_PLAN_KEYS: tuple[str, ...] = (
    "mandatory_index",
    "follow_up_initiator",
    "follow_up_kind",
    "resolved_next_target",
)


def sanitize_plan_for_client(plan: Any) -> Any:
    """Copy of ``plan`` without :data:`SERVER_ONLY_PLAN_KEYS`."""
    if not isinstance(plan, list):
        return plan
    cleaned = []
    for entry in plan:
        if isinstance(entry, dict):
            entry = {k: copy.deepcopy(v) for k, v in entry.items() if k not in SERVER_ONLY_PLAN_KEYS}
        cleaned.append(entry)
    return cleaned
