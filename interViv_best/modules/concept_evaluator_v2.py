"""Experimental concept / rubric evaluator v2 (research only).

Versioned, deterministic, no live LLM. Does **not** connect to the frozen
scoring pipeline, student-facing scores, mastery, Elo, readiness, adaptive
assessment, or production feedback.

Gate: ``EXPERIMENTAL_CONCEPT_EVALUATOR`` (default false). Callers must check
``experimental_concept_evaluator_enabled()`` before using results in any
admin/research surface.

Evidence states per concept: supported | contradicted | not_demonstrated | uncertain.
Aliases and keyword hits retrieve candidate spans; they alone never establish
support. Negated propositions and misconception-pattern hits without refutation
are treated conservatively.
"""
from __future__ import annotations

import math
import re
from typing import Any

from backend.config import get_settings

EVALUATOR_VERSION = "concept_evaluator_v2.0"
CONFIG_VERSION = "concept_evaluator_v2_config.1"

_NEGATION = re.compile(
    r"\b(?:not|no|never|isn't|isnt|aren't|arent|doesn't|doesnt|without|cannot|can't|cant)\b",
    re.I,
)
_WORD = re.compile(r"[A-Za-z0-9_]+(?:'[A-Za-z]+)?")


def experimental_concept_evaluator_enabled() -> bool:
    return bool(get_settings().experimental_concept_evaluator)


def _tokenize(text: str) -> list[tuple[int, int, str]]:
    """Return (start, end, token_lower) spans against the original answer."""
    out: list[tuple[int, int, str]] = []
    for m in _WORD.finditer(text or ""):
        out.append((m.start(), m.end(), m.group(0).casefold()))
    return out


def _normalize_concept(raw: Any) -> dict[str, Any] | None:
    if isinstance(raw, str):
        cid = raw.strip()
        if not cid:
            return None
        return {
            "id": cid,
            "descriptor": cid,
            "aliases": [],
            "expected_propositions": [],
            "positive_examples": [],
            "negative_cases": [],
        }
    if not isinstance(raw, dict):
        return None
    cid = str(raw.get("id") or raw.get("concept_id") or "").strip()
    if not cid:
        return None
    aliases = [str(a).strip() for a in (raw.get("aliases") or []) if str(a).strip()]
    props = [str(p).strip() for p in (raw.get("expected_propositions") or []) if str(p).strip()]
    return {
        "id": cid,
        "descriptor": str(raw.get("descriptor") or cid).strip(),
        "aliases": aliases,
        "expected_propositions": props,
        "positive_examples": list(raw.get("positive_examples") or []),
        "negative_cases": list(raw.get("negative_cases") or []),
    }


def _find_term_spans(answer: str, terms: list[str]) -> list[dict[str, Any]]:
    tokens = _tokenize(answer)
    if not tokens:
        return []
    spans: list[dict[str, Any]] = []
    lower_terms = []
    for term in terms:
        parts = [p for p in re.split(r"[\s_/.-]+", term.casefold()) if p]
        if parts:
            lower_terms.append((term, parts))
    tok_vals = [t[2] for t in tokens]
    for term, parts in lower_terms:
        n = len(parts)
        for i in range(len(tok_vals) - n + 1):
            if tok_vals[i : i + n] == parts:
                start, end = tokens[i][0], tokens[i + n - 1][1]
                spans.append({
                    "term": term,
                    "start": start,
                    "end": end,
                    "text": answer[start:end],
                })
    return spans


def _window_has_negation(answer: str, start: int, end: int, radius: int = 40) -> bool:
    lo = max(0, start - radius)
    hi = min(len(answer), end + radius)
    return bool(_NEGATION.search(answer[lo:hi]))


def _proposition_support(answer: str, proposition: str) -> str | None:
    """Return supported/contradicted/None for a simple keyword-proposition check.

    simplification: requires majority of content words from the proposition to
    appear as whole tokens inside a local co-occurrence window. If any such
    window lacks negation, the proposition is supported — so quoting a
    misconception earlier in the answer does not flip a later correct claim.
    If every matching window is negated, return contradicted.
    Upgrade path: dependency parses / NLI when pinned local assets exist.
    """
    words = [w for w in re.findall(r"[A-Za-z0-9_]+", proposition.casefold()) if len(w) > 2]
    if not words:
        return None
    tokens = _tokenize(answer)
    if not tokens:
        return None
    # Conservative: require every content word (len>2) from the proposition.
    needed = len(words)
    word_set = set(words)
    supported_window = False
    contradicted_window = False
    for i in range(len(tokens)):
        seen: set[str] = set()
        end = tokens[i][1]
        start = tokens[i][0]
        for j in range(i, min(len(tokens), i + 25)):
            _s, end_j, tok = tokens[j]
            if tok in word_set:
                seen.add(tok)
                end = end_j
            if len(seen) >= needed:
                if _NEGATION.search(answer[start:end]):
                    contradicted_window = True
                else:
                    supported_window = True
                break
    if supported_window:
        return "supported"
    if contradicted_window:
        return "contradicted"
    return None


def _misconception_hit(
    answer: str, misconception: Any
) -> tuple[bool, list[dict[str, Any]], bool]:
    """Return (matched, spans, refuted). Refutation = nearby negation of the pattern."""
    if isinstance(misconception, str):
        patterns = [misconception]
        mid = misconception
    elif isinstance(misconception, dict):
        mid = str(misconception.get("id") or misconception.get("description") or "misconception")
        patterns = [str(p) for p in (misconception.get("candidate_patterns") or []) if str(p).strip()]
        if misconception.get("description"):
            patterns.append(str(misconception["description"]))
    else:
        return False, [], False
    spans: list[dict[str, Any]] = []
    for pat in patterns:
        for sp in _find_term_spans(answer, [pat]):
            sp = dict(sp)
            sp["misconception_id"] = mid
            spans.append(sp)
    if not spans:
        # Soft substring for multi-word phrases not token-aligned
        answer_cf = (answer or "").casefold()
        for pat in patterns:
            p = " ".join(pat.casefold().split())
            if len(p) >= 8 and p in answer_cf:
                idx = answer_cf.find(p)
                spans.append({
                    "term": pat,
                    "start": idx,
                    "end": idx + len(p),
                    "text": answer[idx : idx + len(p)],
                    "misconception_id": mid,
                })
    if not spans:
        return False, [], False
    refuted = any(_window_has_negation(answer, s["start"], s["end"]) for s in spans)
    return True, spans, refuted


def _evaluate_one_concept(answer: str, concept: dict[str, Any]) -> dict[str, Any]:
    terms = [concept["id"], *concept["aliases"]]
    mentions = _find_term_spans(answer, terms)
    evidence: list[dict[str, Any]] = []
    for m in mentions:
        evidence.append({
            "kind": "mention",
            "method": "alias_token_match",
            "start": m["start"],
            "end": m["end"],
            "text": m["text"],
        })

    prop_states = []
    for prop in concept["expected_propositions"]:
        state = _proposition_support(answer, prop)
        if state:
            prop_states.append(state)
            evidence.append({
                "kind": "proposition",
                "method": "keyword_proposition_v1",
                "proposition": prop,
                "state": state,
            })

    # Mentions alone never establish support.
    if "contradicted" in prop_states:
        state = "contradicted"
    elif "supported" in prop_states:
        state = "supported"
    elif mentions and concept["expected_propositions"]:
        # Term present but no proposition check resolved → uncertain
        state = "uncertain"
    elif mentions and not concept["expected_propositions"]:
        # No proposition to verify; mention-only → uncertain (not supported)
        state = "uncertain"
    else:
        state = "not_demonstrated"

    return {
        "concept_id": concept["id"],
        "descriptor": concept["descriptor"],
        "state": state,
        "mentions": mentions,
        "evidence": evidence,
    }


def coverage_level(n_required: int, k_supported: int) -> int | None:
    """0–3 coverage mapping. Some levels unreachable for small n."""
    if n_required <= 0:
        return None
    k = k_supported
    n = n_required
    if k == n:
        return 3
    if k >= math.ceil(2 * n / 3):
        return 2
    if k > 0:
        return 1
    return 0


def evaluate_answer(
    *,
    answer_text: str,
    bundle_content: dict[str, Any],
    bundle_content_hash: str | None = None,
) -> dict[str, Any]:
    """Evaluate one answer against bundle concept/rubric metadata.

    Returns evaluator/config versions, per-concept states, experimental
    criterion statuses (Accuracy/Depth/Clarity may be null/unassessed), and
    coverage counts. Does not produce a headline total.
    """
    required_raw = list(bundle_content.get("required_concepts") or [])
    optional_raw = list(bundle_content.get("optional_concepts") or [])
    required = [c for c in (_normalize_concept(x) for x in required_raw) if c]
    optional = [c for c in (_normalize_concept(x) for x in optional_raw) if c]

    if not required:
        return {
            "evaluator_version": EVALUATOR_VERSION,
            "config_version": CONFIG_VERSION,
            "bundle_content_hash": bundle_content_hash,
            "assessable": False,
            "reason": "missing_required_concepts",
            "concepts": [],
            "optional_concepts": [],
            "coverage": {"n_required": 0, "k_supported": 0, "level": None},
            "criteria": {
                "coverage": None,
                "accuracy": None,
                "depth": None,
                "clarity": None,
            },
            "misconceptions": [],
        }

    answer = answer_text or ""
    concept_results = [_evaluate_one_concept(answer, c) for c in required]
    optional_results = [_evaluate_one_concept(answer, c) for c in optional]

    k_supported = sum(1 for c in concept_results if c["state"] == "supported")
    # Uncertain must not count as supported (already excluded).
    level = coverage_level(len(required), k_supported)

    misconception_results = []
    for misc in bundle_content.get("misconceptions") or []:
        matched, spans, refuted = _misconception_hit(answer, misc)
        misconception_results.append({
            "id": (misc.get("id") if isinstance(misc, dict) else str(misc)),
            "matched": matched,
            "refuted": refuted,
            "spans": spans,
        })

    # Accuracy: only assessed when misconception checks or proposition checks exist.
    # Absence of misconception match is NOT high accuracy.
    accuracy: int | None = None
    has_prop_checks = any(c.get("expected_propositions") for c in required)
    has_misc = bool(bundle_content.get("misconceptions"))
    if has_prop_checks or has_misc:
        contradicted = any(c["state"] == "contradicted" for c in concept_results)
        active_misc = any(m["matched"] and not m["refuted"] for m in misconception_results)
        if contradicted or active_misc:
            accuracy = 0
        elif any(c["state"] == "uncertain" for c in concept_results):
            accuracy = None  # unassessed / uncertain
        elif k_supported == len(required):
            accuracy = 2  # development band only; not a production score
        elif k_supported > 0:
            accuracy = 1
        else:
            accuracy = 0

    # Depth: depth_markers must appear as phrases; verbosity alone does not count.
    depth: int | None = None
    markers = [str(m) for m in (bundle_content.get("depth_markers") or []) if str(m).strip()]
    if markers:
        hit = sum(1 for m in markers if " ".join(m.casefold().split()) in answer.casefold())
        if hit == 0:
            depth = 0
        elif hit >= math.ceil(2 * len(markers) / 3):
            depth = 2
        else:
            depth = 1

    # Clarity: no defensible automated criterion yet → unassessed.
    clarity: int | None = None

    return {
        "evaluator_version": EVALUATOR_VERSION,
        "config_version": CONFIG_VERSION,
        "bundle_content_hash": bundle_content_hash,
        "assessable": True,
        "concepts": concept_results,
        "optional_concepts": optional_results,
        "coverage": {
            "n_required": len(required),
            "k_supported": k_supported,
            "level": level,
        },
        "criteria": {
            "coverage": level,
            "accuracy": accuracy,
            "depth": depth,
            "clarity": clarity,
        },
        "misconceptions": misconception_results,
        "headline_total": None,
    }
