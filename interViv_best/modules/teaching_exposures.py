"""Durable teaching-exposure delivery records (Phase 4A).

A generated-but-undelivered artifact or status-only poll is not teaching
delivery. Delivery is explicit, idempotent by logical ``delivery_id``, and
serialized against submission via the session submit lock.
"""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from modules.assistance_policy import (
    POLICY_VERSION,
    TEACHING_KINDS,
    topic_scope_for_round,
)

# simplification: in-memory order counter per process for delivery_order;
# SQL rows also store created_at for durable ordering across restarts.
_ORDER_COUNTER = 0


def _next_order() -> int:
    global _ORDER_COUNTER
    _ORDER_COUNTER += 1
    return _ORDER_COUNTER


def stable_content_id(
    *,
    kind: str,
    item_type: str | None,
    item_id: str | None,
    content_fingerprint: str | None = None,
) -> str:
    raw = f"{kind}|{item_type or ''}|{item_id or ''}|{content_fingerprint or ''}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:32]


def make_delivery_id(
    *,
    owner_key: str,
    session_id: str | None,
    round_number: int | None,
    kind: str,
    content_id: str,
) -> str:
    """Logical delivery identity so transport retries cannot duplicate delivery."""
    raw = (
        f"{owner_key}|{session_id or ''}|"
        f"{round_number if round_number is not None else ''}|"
        f"{kind}|{content_id}"
    )
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:40]


def owner_key_for(session: dict[str, Any] | None, user_id: str | None) -> str:
    if user_id:
        return f"user:{user_id}"
    if session and session.get("session_id"):
        return f"guest:{session['session_id']}"
    return "guest:anonymous"


def record_teaching_exposure(
    db: Any,
    *,
    kind: str,
    item_type: str | None,
    item_id: str | None,
    session: dict[str, Any] | None = None,
    user_id: str | None = None,
    round_number: int | None = None,
    block_id: str | None = None,
    attempt_round: int | None = None,
    content_fingerprint: str | None = None,
    concept_topic_scope: dict[str, Any] | None = None,
    policy_version: str = POLICY_VERSION,
    now: datetime | None = None,
    also_legacy_assistance: bool = True,
) -> dict[str, Any] | None:
    """Idempotently record a teaching delivery. Returns the exposure doc.

    Returns None when ``kind`` is not a teaching kind (caller may still
    generate content without logging a delivery).
    """
    if kind not in TEACHING_KINDS:
        return None
    now = now or datetime.now(timezone.utc)
    session = session or {}
    uid = user_id if user_id is not None else session.get("user_id")
    sid = session.get("session_id")
    owner = owner_key_for(session, str(uid) if uid else None)
    content_id = stable_content_id(
        kind=kind,
        item_type=item_type,
        item_id=item_id,
        content_fingerprint=content_fingerprint,
    )
    delivery_id = make_delivery_id(
        owner_key=owner,
        session_id=str(sid) if sid else None,
        round_number=round_number if round_number is not None else attempt_round,
        kind=kind,
        content_id=content_id,
    )

    existing = db["teaching_exposures"].find_one({"delivery_id": delivery_id})
    if existing:
        return existing

    scope = concept_topic_scope
    if scope is None and session:
        # Best-effort scope from the active round when available.
        rounds = session.get("rounds") or []
        active = None
        target_round = round_number if round_number is not None else attempt_round
        if target_round is not None:
            active = next((r for r in rounds if r.get("round") == target_round), None)
        if active:
            scope = topic_scope_for_round(active, session)
    scope = scope or {"skill": None, "topic": None, "concept_ids": [], "scope_certainty": "unknown"}

    exposure = {
        "id": str(uuid4()),
        "delivery_id": delivery_id,
        "content_id": content_id,
        "owner_key": owner,
        "user_id": str(uid) if uid else None,
        "session_id": str(sid) if sid else None,
        "block_id": block_id,
        "round": round_number if round_number is not None else attempt_round,
        "item_type": item_type,
        "item_id": item_id,
        "content_kind": kind,
        "policy_version": policy_version,
        "concept_topic_scope": scope,
        "delivered_at": now,
        "delivery_order": _next_order(),
        "created_at": now,
    }
    db["teaching_exposures"].insert_one(exposure)

    # Keep Phase D assistance_events populated for owned accounts so legacy
    # surfaces and notebooks keep working. Guests skip that table (user_id PK).
    if also_legacy_assistance and uid and item_type and item_id:
        legacy = {
            "id": exposure["id"],
            "user_id": str(uid),
            "item_type": item_type,
            "item_id": item_id,
            "kind": kind if kind in ("hint", "explanation", "solution", "editorial") else "hint",
            "session_id": str(sid) if sid else None,
            "round": exposure["round"],
            "created_at": now,
        }
        try:
            prior = db["assistance_events"].find_one({"id": legacy["id"]})
            if not prior:
                db["assistance_events"].insert_one(legacy)
        except Exception:
            # simplification: legacy dual-write best-effort; exposure is authoritative.
            pass
    return exposure


def list_exposures_for_eligibility(
    db: Any,
    *,
    session: dict[str, Any],
    user_id: str | None,
    before: datetime,
) -> list[dict[str, Any]]:
    """Exposures visible to eligibility evaluation at submission cutoff."""
    owner = owner_key_for(session, str(user_id) if user_id else None)
    sid = str(session.get("session_id") or "")
    out: list[dict[str, Any]] = []
    seen: set[str] = set()

    queries: list[dict[str, Any]] = [{"owner_key": owner}]
    if user_id:
        queries.append({"user_id": str(user_id)})
    if sid:
        queries.append({"session_id": sid})

    for query in queries:
        try:
            rows = list(db["teaching_exposures"].find(query))
        except Exception:
            rows = []
        for row in rows:
            did = str(row.get("delivery_id") or row.get("id") or "")
            if not did or did in seen:
                continue
            delivered = row.get("delivered_at") or row.get("created_at")
            if isinstance(delivered, str):
                try:
                    delivered = datetime.fromisoformat(delivered.replace("Z", "+00:00"))
                except ValueError:
                    continue
            if isinstance(delivered, datetime):
                if delivered.tzinfo is None:
                    delivered = delivered.replace(tzinfo=timezone.utc)
                if delivered > before:
                    continue
            seen.add(did)
            out.append(row)

    # Fallback: Phase D assistance_events for pre-migration history.
    if user_id:
        try:
            for event in db["assistance_events"].find({"user_id": str(user_id)}):
                eid = f"legacy:{event.get('id')}"
                if eid in seen:
                    continue
                created = event.get("created_at")
                if isinstance(created, str):
                    try:
                        created = datetime.fromisoformat(created.replace("Z", "+00:00"))
                    except ValueError:
                        continue
                if isinstance(created, datetime):
                    if created.tzinfo is None:
                        created = created.replace(tzinfo=timezone.utc)
                    if created > before:
                        continue
                seen.add(eid)
                out.append({
                    "id": event.get("id"),
                    "delivery_id": eid,
                    "content_id": event.get("id"),
                    "owner_key": owner,
                    "user_id": str(user_id),
                    "session_id": event.get("session_id"),
                    "round": event.get("round"),
                    "item_type": event.get("item_type"),
                    "item_id": event.get("item_id"),
                    "content_kind": event.get("kind"),
                    "policy_version": None,
                    "concept_topic_scope": {
                        "skill": None,
                        "topic": None,
                        "concept_ids": [],
                        "scope_certainty": "unknown",
                    },
                    "delivered_at": created,
                    "created_at": created,
                    "legacy_assistance_event": True,
                })
        except Exception:
            pass
    return out
