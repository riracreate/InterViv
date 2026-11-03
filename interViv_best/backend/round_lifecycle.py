"""Round activation: a prepared round's clock starts only when it is opened.

Lifecycle of a round document's ``status``:

* ``ready`` — built and persisted after the previous round was submitted,
  but not shown to the candidate. No ``started_at`` / ``expires_at``; the
  time budget is kept in ``config_json["duration_seconds"]``.
* ``in_progress`` — activated. ``started_at`` and (for timed rounds)
  ``expires_at`` are set exactly once and never extended.
* ``finalizing`` / ``submitted`` / ``expired`` — unchanged from before.

The first round of a session is still activated at session start. Rounds
that were already ``in_progress`` before this module existed keep their
deadlines.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

ROUND_STATUS_READY = "ready"
ROUND_STATUS_ACTIVE = "in_progress"
DURATION_SECONDS_KEY = "duration_seconds"

# Statuses that still accept candidate work (open) or are waiting to open.
OPEN_STATUSES = frozenset({ROUND_STATUS_ACTIVE, ROUND_STATUS_READY})


def _as_datetime(value: Any) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, str):
        try:
            value = datetime.fromisoformat(value)
        except ValueError:
            return None
    if not isinstance(value, datetime):
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value


def round_duration_seconds(round_doc: dict[str, Any]) -> int | None:
    """Time budget of a round in seconds, or ``None`` for untimed rounds."""
    config = round_doc.get("config_json") or {}
    stored = config.get(DURATION_SECONDS_KEY)
    if stored is not None:
        try:
            seconds = int(stored)
        except (TypeError, ValueError):
            seconds = 0
        return seconds if seconds > 0 else None
    started = _as_datetime(round_doc.get("started_at"))
    expires = _as_datetime(round_doc.get("expires_at"))
    if started is not None and expires is not None:
        seconds = int(round((expires - started).total_seconds()))
        return seconds if seconds > 0 else None
    return None


def prepare_round(round_doc: dict[str, Any]) -> dict[str, Any]:
    """Turn a freshly built (clock-running) round into a ``ready`` round.

    Mutates and returns ``round_doc``. The duration is captured from the
    build-time ``started_at``/``expires_at`` pair before both are cleared.
    """
    seconds = round_duration_seconds(round_doc)
    config = dict(round_doc.get("config_json") or {})
    if seconds is not None:
        config[DURATION_SECONDS_KEY] = seconds
    round_doc["config_json"] = config
    round_doc["status"] = ROUND_STATUS_READY
    round_doc["started_at"] = None
    round_doc["expires_at"] = None
    return round_doc


def activate_round(round_doc: dict[str, Any], now: datetime | None = None) -> bool:
    """Start a ``ready`` round's clock. Returns True when the round changed.

    Idempotent: an ``in_progress`` (or closed) round is left untouched, so a
    repeated activation can never extend a deadline.
    """
    if round_doc.get("status") != ROUND_STATUS_READY:
        return False
    started = now or datetime.now(timezone.utc)
    seconds = round_duration_seconds(round_doc)
    round_doc["status"] = ROUND_STATUS_ACTIVE
    round_doc["started_at"] = started
    round_doc["expires_at"] = (
        started + timedelta(seconds=seconds) if seconds is not None else None
    )
    return True


def is_ready(round_doc: dict[str, Any] | None) -> bool:
    return bool(round_doc) and round_doc.get("status") == ROUND_STATUS_READY


def open_round(rounds: list[dict[str, Any]]) -> dict[str, Any] | None:
    """The latest round that is in progress or waiting to be activated."""
    return next(
        (r for r in reversed(rounds or []) if r.get("status") in OPEN_STATUSES),
        None,
    )


def round_not_active_detail(round_doc: dict[str, Any]) -> dict[str, Any]:
    """409 body for work sent to a round that has not been activated."""
    return {
        "code": "round_not_active",
        "round": round_doc.get("round"),
        "message": "Open this question with Next before answering it.",
    }
