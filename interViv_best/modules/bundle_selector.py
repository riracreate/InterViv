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


def reviewed_available_count(
    *, skill: str, difficulty: str | None = None, topic: str | None = None,
) -> int:
    """Eligible reviewed bundles for a skill without selecting content.

    Counts latest ``reviewed`` versions only (never drafts or unreviewed
    work). ``difficulty``/``topic`` narrow the count when the caller pins
    them; ``None`` counts across all values. Returns a count, never
    content, so availability probes disclose no reference material.
    """
    if difficulty is not None:
        return len(bundle_store.reviewed_versions(skill, difficulty, topic))
    total = 0
    for level in ("easy", "medium", "hard"):
        total += len(bundle_store.reviewed_versions(skill, level, topic))
    return total


def _pick_unasked_payload(
    versions: list[dict],
    asked: list[str] | None,
) -> dict | None:
    asked_norm = {" ".join(q.split()).casefold() for q in (asked or [])}
    asked_ids = {str(q).strip() for q in (asked or []) if str(q).strip()}
    for v in versions:
        payload = candidate_payload(v)
        identity = f"{payload['bundle_id']}@{payload['version']}"
        if identity in asked_ids:
            continue
        if " ".join(payload["question"].split()).casefold() in asked_norm:
            continue
        return payload
    return None


def select_reviewed_question(
    *, skill: str, difficulty: str, asked: list[str] | None = None, topic: str | None = None,
) -> dict:
    """Deterministic pick: first eligible bundle (by bundle_id) not already asked.

    Eligibility is latest ``reviewed`` only. Asked matching uses question text
    and bundle identity strings so a client cannot force a different version.
    """
    picked = _pick_unasked_payload(
        bundle_store.reviewed_versions(skill, difficulty, topic),
        asked,
    )
    if picked is not None:
        return picked
    raise ReviewedInventoryUnavailable(
        f"No reviewed question bundle is available for skill={skill!r} difficulty={difficulty!r}"
        + (f" topic={topic!r}" if topic else "")
        + ". Reviewed-only selection is on; draft or unreviewed content cannot be scored."
    )


def select_bundle_question(
    *,
    skill: str,
    difficulty: str,
    asked: list[str] | None = None,
    topic: str | None = None,
) -> dict | None:
    """Select an eligible bundle question ordered by trust tier.

    When ``REVIEWED_BUNDLES_ONLY`` is enabled, delegates strictly to
    ``select_reviewed_question`` (raising ``ReviewedInventoryUnavailable`` if
    no reviewed bundle is available). Otherwise floors at ``auto_checked``
    (``reviewed`` > ``auto_checked``) in every configuration and never serves
    ``generated``, ``rejected``, ``draft``, or ``retired`` bundles.
    """
    if reviewed_bundles_only():
        return select_reviewed_question(
            skill=skill,
            difficulty=difficulty,
            asked=asked,
            topic=topic,
        )
    versions = bundle_store.selectable_versions(
        skill,
        difficulty,
        topic,
        include_auto_checked=True,
        include_unchecked_generated=False,
    )
    return _pick_unasked_payload(versions, asked)
