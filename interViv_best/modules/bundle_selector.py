"""Reviewed-bundle selection for new assessment rounds.

Only the latest ``reviewed`` version of a bundle is eligible. ``draft``,
``in_review``, ``rejected`` and ``retired`` are never selectable here. The
returned payload is candidate-facing: it carries no reference answer,
keywords, concepts, misconceptions, or rubric.

Gated by ``REVIEWED_BUNDLES_ONLY`` (default off). When the gate is off, callers
must not invoke ``select_reviewed_question`` for production selection. When on,
an empty/ineligible inventory raises ``ReviewedInventoryUnavailable`` — never
silently fall back to draft or legacy scored content.
"""
from __future__ import annotations

from backend.config import get_settings
from modules import bundle_store
from modules.question_bundles import candidate_payload


class ReviewedInventoryUnavailable(LookupError):
    pass


def reviewed_bundles_only() -> bool:
    return bool(get_settings().reviewed_bundles_only)


def select_reviewed_question(
    *, skill: str, difficulty: str, asked: list[str] | None = None, topic: str | None = None,
) -> dict:
    """Deterministic pick: first eligible bundle (by bundle_id) not already asked.

    Eligibility is latest ``reviewed`` only. Asked matching uses question text
    and bundle identity strings so a client cannot force a different version.
    """
    asked_norm = {" ".join(q.split()).casefold() for q in (asked or [])}
    asked_ids = {str(q).strip() for q in (asked or []) if str(q).strip()}
    for v in bundle_store.reviewed_versions(skill, difficulty, topic):
        payload = candidate_payload(v)
        identity = f"{payload['bundle_id']}@{payload['version']}"
        if identity in asked_ids:
            continue
        if " ".join(payload["question"].split()).casefold() in asked_norm:
            continue
        return payload
    raise ReviewedInventoryUnavailable(
        f"No reviewed question bundle is available for skill={skill!r} difficulty={difficulty!r}"
        + (f" topic={topic!r}" if topic else "")
        + ". Reviewed-only selection is on; draft or unreviewed content cannot be scored."
    )
