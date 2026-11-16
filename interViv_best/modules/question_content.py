"""Content rules for scored short-answer questions.

A short answer is scored against the question's reference answer and
keywords, so both have to be present and substantial before the question is
asked. This module is the one definition of that rule. The fallback-bank
audit (``scripts/question_audit.py``), the pre-start availability check and
serving all use it, for generated questions and bank questions alike.

Nothing here scores an answer or changes how one is scored.
"""
from __future__ import annotations

import re
from typing import Any

VALID_DIFFICULTIES = frozenset({"easy", "medium", "hard"})
VALID_QUESTION_TYPES = frozenset({
    "conceptual",
    "coding",
    "system_design",
    "behavioral",
    "resume_based",
})

# Below these the audit calls the keywords thin and the reference weak.
MIN_KEYWORDS = 4
MIN_REFERENCE_WORDS = 20


def split_keywords(value: Any) -> list[str]:
    """Keyword phrases from a list, or from a comma- or pipe-separated string."""
    if isinstance(value, (list, tuple)):
        parts = [str(item) for item in value if item is not None]
    else:
        parts = re.split(r"[,|]", str(value or ""))
    return [part.strip() for part in parts if part.strip()]


def word_count(value: Any) -> int:
    return len(str(value or "").split())


def reference_issues(payload: Any) -> list[str]:
    """Why ``payload`` cannot be asked as a scored question; empty when it can.

    ``payload`` is a question dict from any source: ``question``, a reference
    under ``ideal_answer`` or ``reference_answer``, keywords under
    ``ideal_keywords`` or ``keywords``.
    """
    if not isinstance(payload, dict) or not str(payload.get("question") or "").strip():
        return ["no question text"]
    issues: list[str] = []
    reference = str(payload.get("ideal_answer") or payload.get("reference_answer") or "").strip()
    if not reference:
        issues.append("no reference answer")
    elif word_count(reference) < MIN_REFERENCE_WORDS:
        issues.append(f"reference answer under {MIN_REFERENCE_WORDS} words")
    # A keyword the scorer can match has at least one letter or digit.
    keywords = {
        phrase.casefold()
        for phrase in split_keywords(payload.get("ideal_keywords") or payload.get("keywords"))
        if re.search(r"\w", phrase)
    }
    if not keywords:
        issues.append("no keywords")
    elif len(keywords) < MIN_KEYWORDS:
        issues.append(f"fewer than {MIN_KEYWORDS} keywords")
    return issues


__all__ = [
    "MIN_KEYWORDS",
    "MIN_REFERENCE_WORDS",
    "VALID_DIFFICULTIES",
    "VALID_QUESTION_TYPES",
    "reference_issues",
    "split_keywords",
    "word_count",
]
