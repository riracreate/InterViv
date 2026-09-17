"""Validate proposed narration artifacts against an attempt snapshot.

Narration may only restate production-established claims from the snapshot
(via :func:`modules.attempt_snapshot.narration_allowed_claims`). Similarity
scores are not correctness claims. Invalid or unavailable narration means
callers keep the deterministic rules artifact.
"""
from __future__ import annotations

import re
from typing import Any

from modules.attempt_snapshot import narration_allowed_claims

ALLOWED_TOP_LEVEL = frozenset({
    "version",
    "source",
    "script",
    "sections",
    "evidence_ids",
    "criterion_ids",
    "answer_spans",
    # Optional nesting retained after validation for worker metadata.
    "metadata",
    "rules_artifact",
})

ALLOWED_SECTION_KEYS = frozenset({"content", "strengths", "weakness", "next_step"})

MAX_SCRIPT_CHARS = 4000
MAX_BULLET_CHARS = 500
MAX_BULLETS_PER_SECTION = 12

# Block executable / outbound content. Notation such as 3NF, HTTP 404,
# O(n²), and O(n^2) is allowed — only scheme-bearing URLs and markup are cut.
_HTTP_URL = re.compile(r"https?://", re.IGNORECASE)
_MARKDOWN_HTTP = re.compile(r"!\[[^\]]*\]\(\s*https?://|\[[^\]]*\]\(\s*https?://", re.IGNORECASE)
_SCRIPT_TAG = re.compile(r"<\s*script\b", re.IGNORECASE)
_JS_SCHEME = re.compile(r"javascript\s*:", re.IGNORECASE)

# Numeric score claims that disagree with the snapshot final_score.
_SCORE_CLAIM = re.compile(
    r"(?i)(?:scored?|score|final(?:\s+score)?|out\s+of\s+100)\s*[:=]?\s*"
    r"(\d+(?:\.\d+)?)\b"
    r"|(?<!\w)(\d+(?:\.\d+)?)\s*/\s*100\b"
    r"|(?<!\w)(\d+(?:\.\d+)?)\s+out\s+of\s+100\b"
)

_RUBRIC_CRITERIA = frozenset({"correctness", "coverage", "depth", "clarity"})


def _as_lines(value: Any) -> list[str]:
    if isinstance(value, str):
        return [value] if value.strip() else []
    if isinstance(value, (list, tuple)):
        return [str(item) for item in value]
    return []


def _flatten_text(artifact: dict[str, Any]) -> str:
    parts = [str(artifact.get("script") or "")]
    sections = artifact.get("sections") or {}
    if isinstance(sections, dict):
        for key in ("content", "strengths", "weakness", "next_step"):
            value = sections.get(key)
            if isinstance(value, str):
                parts.append(value)
            elif isinstance(value, (list, tuple)):
                parts.extend(str(item) for item in value)
    return "\n".join(parts)


def _allowed_evidence_ids(snapshot: dict[str, Any], claims: dict[str, Any]) -> set[str]:
    allowed: set[str] = {
        "score.final",
        "feedback.content",
        "feedback.strengths",
        "feedback.weakness",
        "feedback.next_step",
    }
    if claims.get("guard_applied"):
        allowed.add(f"guard:{claims['guard_applied']}")
        allowed.add("guard.applied")
    for concept in claims.get("covered_concepts") or []:
        allowed.add(f"concept.covered:{concept}")
    for concept in claims.get("missing_concepts") or []:
        allowed.add(f"concept.missing:{concept}")
    provenance = snapshot.get("scorer_provenance") or {}
    for key, value in provenance.items():
        if value is not None:
            allowed.add(f"scorer.{key}")
    return allowed


def _allowed_criterion_ids(snapshot: dict[str, Any]) -> set[str]:
    allowed = set(_RUBRIC_CRITERIA)
    breakdown = snapshot.get("scoring_breakdown") or {}
    rubric = breakdown.get("rubric") if isinstance(breakdown.get("rubric"), dict) else {}
    for key in rubric:
        if isinstance(key, str) and key.strip():
            allowed.add(key.strip())
    return allowed


def _contains_forbidden_markup(text: str) -> str | None:
    if _HTTP_URL.search(text):
        return "http(s) links are not allowed in narration"
    if _MARKDOWN_HTTP.search(text):
        return "markdown http(s) links/images are not allowed in narration"
    if _SCRIPT_TAG.search(text):
        return "executable script markup is not allowed in narration"
    if _JS_SCHEME.search(text):
        return "javascript: URLs are not allowed in narration"
    return None


def _score_disagreement(text: str, final_score: Any) -> str | None:
    if final_score is None:
        # No established score — reject any invented numeric score claim.
        if _SCORE_CLAIM.search(text):
            return "invented score claim without an established final_score"
        return None
    try:
        expected = float(final_score)
    except (TypeError, ValueError):
        return None
    for match in _SCORE_CLAIM.finditer(text):
        raw = next((group for group in match.groups() if group is not None), None)
        if raw is None:
            continue
        claimed = float(raw)
        if abs(claimed - expected) > 1e-6:
            return f"score claim {claimed} disagrees with snapshot final_score {expected}"
    return None


def _praise_invents_concepts(artifact: dict[str, Any], claims: dict[str, Any]) -> str | None:
    """Reject praise that invents concepts absent from covered / feedback strengths."""
    covered = {str(item).strip().lower() for item in (claims.get("covered_concepts") or []) if str(item).strip()}
    feedback = claims.get("feedback") or {}
    strength_lines = [
        str(item).strip().lower()
        for item in _as_lines(feedback.get("strengths"))
        if str(item).strip()
    ]
    sections = artifact.get("sections") if isinstance(artifact.get("sections"), dict) else {}
    praise_lines = _as_lines((sections or {}).get("strengths"))
    if not praise_lines:
        return None
    # If the scorer recorded neither strengths nor covered concepts, provider
    # praise that asserts specific mastery is unsupported.
    if not strength_lines and not covered:
        for line in praise_lines:
            lowered = line.strip().lower()
            if not lowered:
                continue
            if any(token in lowered for token in ("master", "excellent", "strong grasp", "demonstrated")):
                return "unsupported praise without established strengths or covered concepts"
        return None
    for line in praise_lines:
        lowered = line.strip().lower()
        if not lowered:
            continue
        grounded_in_strength = any(
            (strength and (strength in lowered or lowered in strength))
            for strength in strength_lines
        )
        grounded_in_concept = any(
            (concept and concept in lowered) for concept in covered
        )
        if grounded_in_strength or grounded_in_concept:
            continue
        if covered or strength_lines:
            return "unsupported praise invents concepts not in covered concepts or feedback strengths"
    return None


def _clean_sections(sections: Any) -> tuple[dict[str, Any] | None, str | None]:
    if sections is None:
        return {}, None
    if not isinstance(sections, dict):
        return None, "sections must be an object"
    unexpected = set(sections) - ALLOWED_SECTION_KEYS
    if unexpected:
        return None, f"unexpected section keys: {sorted(unexpected)}"
    cleaned: dict[str, Any] = {}
    for key in ALLOWED_SECTION_KEYS:
        if key not in sections:
            continue
        value = sections[key]
        if key == "next_step":
            if value is None:
                cleaned[key] = ""
                continue
            if not isinstance(value, str):
                return None, "sections.next_step must be a string"
            if len(value) > MAX_BULLET_CHARS:
                return None, "sections.next_step exceeds size limit"
            cleaned[key] = value
            continue
        lines = _as_lines(value)
        if len(lines) > MAX_BULLETS_PER_SECTION:
            return None, f"sections.{key} exceeds {MAX_BULLETS_PER_SECTION} bullets"
        for line in lines:
            if len(line) > MAX_BULLET_CHARS:
                return None, f"sections.{key} bullet exceeds size limit"
        cleaned[key] = lines if isinstance(value, (list, tuple)) else (
            lines[0] if lines and isinstance(value, str) else (value if isinstance(value, str) else lines)
        )
        # Normalize list sections to lists of strings; string input stays string.
        if isinstance(value, (list, tuple)):
            cleaned[key] = lines
        elif isinstance(value, str):
            cleaned[key] = value
        else:
            cleaned[key] = lines
    return cleaned, None


def validate_narration_artifact(
    artifact: dict[str, Any] | None,
    snapshot: dict[str, Any] | None,
) -> tuple[bool, dict[str, Any] | str]:
    """Validate a proposed narration artifact against a snapshot.

    Returns ``(True, cleaned_artifact)`` or ``(False, reason)``.
    """
    if not isinstance(artifact, dict):
        return False, "narration artifact must be an object"
    if not isinstance(snapshot, dict):
        return False, "snapshot required for narration validation"

    unexpected = set(artifact) - ALLOWED_TOP_LEVEL
    if unexpected:
        return False, f"unexpected fields: {sorted(unexpected)}"

    # Reject invented top-level score fields.
    for key in artifact:
        if "score" in key.lower() and key not in ALLOWED_TOP_LEVEL:
            return False, f"invented score field: {key}"

    script = artifact.get("script")
    if script is not None and not isinstance(script, str):
        return False, "script must be a string"
    script = script or ""
    if len(script) > MAX_SCRIPT_CHARS:
        return False, "script exceeds size limit"

    sections, section_error = _clean_sections(artifact.get("sections"))
    if section_error:
        return False, section_error
    assert sections is not None

    claims = narration_allowed_claims(snapshot)
    text = _flatten_text({"script": script, "sections": sections})

    markup_error = _contains_forbidden_markup(text)
    if markup_error:
        return False, markup_error

    score_error = _score_disagreement(text, claims.get("final_score"))
    if score_error:
        return False, score_error

    praise_error = _praise_invents_concepts(
        {"sections": sections},
        claims,
    )
    if praise_error:
        return False, praise_error

    evidence_ids = artifact.get("evidence_ids")
    if evidence_ids is not None:
        if not isinstance(evidence_ids, list) or not all(isinstance(item, str) for item in evidence_ids):
            return False, "evidence_ids must be a list of strings"
        allowed_evidence = _allowed_evidence_ids(snapshot, claims)
        unknown = [item for item in evidence_ids if item not in allowed_evidence]
        if unknown:
            return False, f"evidence_ids not in allowed set: {unknown}"

    criterion_ids = artifact.get("criterion_ids")
    if criterion_ids is not None:
        if not isinstance(criterion_ids, list) or not all(isinstance(item, str) for item in criterion_ids):
            return False, "criterion_ids must be a list of strings"
        allowed_criteria = _allowed_criterion_ids(snapshot)
        unknown = [item for item in criterion_ids if item not in allowed_criteria]
        if unknown:
            return False, f"criterion_ids not in allowed set: {unknown}"

    answer_spans = artifact.get("answer_spans")
    if answer_spans is not None:
        if not isinstance(answer_spans, list):
            return False, "answer_spans must be a list"
        answer = snapshot.get("answer") or ""
        answer_len = len(answer) if isinstance(answer, str) else 0
        cleaned_spans: list[dict[str, int]] = []
        for span in answer_spans:
            if not isinstance(span, dict):
                return False, "answer_spans entries must be objects"
            if set(span) - {"start", "end"}:
                return False, "answer_spans entries may only include start and end"
            start, end = span.get("start"), span.get("end")
            if not isinstance(start, int) or not isinstance(end, int):
                return False, "answer_spans start/end must be ints"
            if start < 0 or end < start or end > answer_len:
                return False, "answer_spans out of answer bounds"
            cleaned_spans.append({"start": start, "end": end})
        answer_spans = cleaned_spans

    cleaned: dict[str, Any] = {
        "version": artifact.get("version"),
        "source": artifact.get("source"),
        "script": script,
        "sections": sections,
    }
    if evidence_ids is not None:
        cleaned["evidence_ids"] = list(evidence_ids)
    if criterion_ids is not None:
        cleaned["criterion_ids"] = list(criterion_ids)
    if answer_spans is not None:
        cleaned["answer_spans"] = answer_spans
    if "metadata" in artifact and isinstance(artifact.get("metadata"), dict):
        cleaned["metadata"] = dict(artifact["metadata"])
    if "rules_artifact" in artifact and isinstance(artifact.get("rules_artifact"), dict):
        cleaned["rules_artifact"] = dict(artifact["rules_artifact"])
    return True, cleaned
