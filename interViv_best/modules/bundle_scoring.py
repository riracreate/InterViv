"""Server-side scoring context resolution for reviewed (and legacy) rounds.

Candidate-facing payloads never carry reference answers. Scoring and post-session
reports resolve authoritative grading material from the pinned bundle version or
from the legacy server-side snapshot already stored on the round.

This module does not change production scoring formulas. It only supplies the
``question_context`` dict the existing pipeline expects.
"""
from __future__ import annotations

from typing import Any

from modules import bundle_store
from modules.bundle_store import BundleStoreError


class BundleReferenceUnavailable(LookupError):
    """Pinned bundle reference missing or content hash inconsistent."""


# Fields that may appear in a candidate-safe technical question_context.
CANDIDATE_TECHNICAL_KEYS = (
    "question",
    "skill",
    "sub_domain",
    "topic",
    "difficulty",
    "question_type",
    "company",
    "role",
    "source",
    "bundle_id",
    "version",
    "content_hash",
    "adaptive_selected",
    "target_concepts",
    "adaptive_target",
    "llm_provider",
    "llm_model",
    "followups",
)

# Solution-bearing / grading-only keys that must never leave the server pre-answer.
GRADING_ONLY_KEYS = (
    "ideal_answer",
    "ideal_keywords",
    "ideal_keywords_list",
    "reference_answer",
    "keywords",
    "required_concepts",
    "optional_concepts",
    "misconceptions",
    "depth_markers",
    "rubric_descriptors",
    "acceptable_variants",
    "calibration_examples",
    "answer",
    "expected_answer",
)


def candidate_technical_context(question_context: dict[str, Any] | None) -> dict[str, Any]:
    """Newly constructed allowlist for pre-answer / active-round delivery."""
    src = dict(question_context or {})
    out: dict[str, Any] = {}
    for key in CANDIDATE_TECHNICAL_KEYS:
        if key in src and src[key] is not None:
            out[key] = src[key]
    # Never copy grading keys even if somehow present under an allowlisted alias.
    for key in GRADING_ONLY_KEYS:
        out.pop(key, None)
    return out


def _keywords_from_content(content: dict[str, Any]) -> tuple[str, list[str]]:
    raw = content.get("keywords") or []
    if isinstance(raw, list):
        items = [str(item).strip() for item in raw if str(item).strip()]
        return ", ".join(items), items
    text = str(raw)
    items = [item.strip() for item in text.split(",") if item.strip()]
    return text, items


def resolve_bundle_grading_fields(
    *,
    bundle_id: str,
    version: int,
    content_hash: str | None,
) -> dict[str, Any]:
    """Load pinned bundle content for scoring. Raises if missing or stale hash."""
    try:
        version_doc = bundle_store.get_version(bundle_id, int(version))
    except BundleStoreError as exc:
        raise BundleReferenceUnavailable(
            f"Pinned bundle {bundle_id}@{version} is unavailable for grading."
        ) from exc
    stored_hash = str(version_doc.get("content_hash") or "")
    expected = str(content_hash or "").strip()
    if expected and stored_hash and expected != stored_hash:
        raise BundleReferenceUnavailable(
            f"Pinned bundle {bundle_id}@{version} content_hash mismatch "
            f"(round={expected[:12]}… store={stored_hash[:12]}…). "
            "Grading reference is unavailable; refusing silent substitution."
        )
    content = version_doc["content_json"]
    ideal_keywords, ideal_keywords_list = _keywords_from_content(content)
    return {
        "ideal_answer": str(content.get("reference_answer") or ""),
        "ideal_keywords": ideal_keywords,
        "ideal_keywords_list": ideal_keywords_list,
        "reference_answer": str(content.get("reference_answer") or ""),
        "keywords": list(content.get("keywords") or []),
        "required_concepts": list(content.get("required_concepts") or []),
        "optional_concepts": list(content.get("optional_concepts") or []),
        "misconceptions": list(content.get("misconceptions") or []),
        "depth_markers": list(content.get("depth_markers") or []),
        "rubric_descriptors": dict(content.get("rubric_descriptors") or {}),
        "acceptable_variants": list(content.get("acceptable_variants") or []),
        "calibration_examples": list(content.get("calibration_examples") or []),
        "bundle_id": version_doc["bundle_id"],
        "version": version_doc["version"],
        "content_hash": stored_hash,
        "source": version_doc.get("source") or "reviewed_bundle",
    }


def scoring_context_from_round(question_context: dict[str, Any] | None) -> dict[str, Any]:
    """Merge authoritative grading fields for the scoring pipeline.

    Reviewed/bundle rounds: resolve from the pinned store version.
    Legacy rounds: use the server-side snapshot already on the round
    (``ideal_answer`` / ``ideal_keywords``), which was never sent to the client
    after the Phase 1B allowlist but remains available for scoring.
    """
    ctx = dict(question_context or {})
    bundle_id = ctx.get("bundle_id")
    version = ctx.get("version")
    if bundle_id is not None and version is not None:
        grading = resolve_bundle_grading_fields(
            bundle_id=str(bundle_id),
            version=int(version),
            content_hash=ctx.get("content_hash"),
        )
        merged = dict(ctx)
        merged.update(grading)
        # Public question text stays what was issued; do not rewrite from store
        # unless missing (defensive).
        if not merged.get("question"):
            # Prefer store question only as last resort for malformed rounds.
            try:
                vdoc = bundle_store.get_version(str(bundle_id), int(version))
                merged["question"] = vdoc["content_json"].get("question") or merged.get("question")
            except BundleStoreError:
                pass
        return merged
    return ctx


def report_ideal_fields(question_context: dict[str, Any] | None) -> dict[str, str]:
    """Ideal answer/keywords for completed-session reports only."""
    try:
        scored = scoring_context_from_round(question_context)
    except BundleReferenceUnavailable:
        return {"ideal_answer": "", "ideal_keywords": ""}
    return {
        "ideal_answer": str(scored.get("ideal_answer") or ""),
        "ideal_keywords": str(scored.get("ideal_keywords") or ""),
    }
