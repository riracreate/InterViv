"""
length_ratio_completeness.py — Exploratory completeness multiplier.

Formula from docs/human_baseline_report.md / docs/track2_heldout_protocol.md:
  length_ratio = word_count(candidate) / word_count(reference)
  multiplier   = clip(length_ratio / 0.45, 0.3, 1.0)

Tuned on the n=50 baseline form set (contaminated). Production use is gated by
LENGTH_RATIO_MULTIPLIER_ENABLED (default false).
"""

from __future__ import annotations

import os


def length_ratio_multiplier_enabled(default: bool = False) -> bool:
    raw = os.getenv("LENGTH_RATIO_MULTIPLIER_ENABLED")
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def word_count(text: str | None) -> int:
    return len(str(text or "").split())


def completeness_length_ratio(candidate: str | None, reference: str | None) -> float:
    ref_n = word_count(reference)
    if ref_n <= 0:
        return 1.0
    return word_count(candidate) / ref_n


def completeness_multiplier(candidate: str | None, reference: str | None) -> float:
    ratio = completeness_length_ratio(candidate, reference)
    return max(0.3, min(ratio / 0.45, 1.0))


def apply_completeness_multiplier(
    score: float,
    candidate: str | None,
    reference: str | None,
) -> tuple[float, float, float]:
    """Return (scaled_score, length_ratio, multiplier)."""
    ratio = completeness_length_ratio(candidate, reference)
    mult = max(0.3, min(ratio / 0.45, 1.0))
    scaled = max(0.0, min(float(score) * mult, 100.0))
    return scaled, ratio, mult
