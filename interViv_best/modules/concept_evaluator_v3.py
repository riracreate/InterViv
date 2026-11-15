"""Concept evaluator v3: 3-tier proposition + alias + MiniLM semantic evaluation.

Tier order per concept (required_concepts and optional_concepts):
1. ``"proposition"``: Expected proposition match via ``concept_evaluator_v2`` logic.
2. ``"alias"``: Whole-term match on ``[id, *aliases]``, respecting clause-bounded negation.
3. ``"semantic"``: MiniLM sentence cosine similarity against the concept's
   ``descriptor`` or ``positive_examples`` (excluding ``exclude_examples`` for
   leave-one-out evaluation), skipping sentences whose alias mentions are negated.

``modules/concept_evaluator_v2.py`` is imported read-only for shared regexes,
normalization, proposition matching, term scanning, coverage levels, and misconceptions.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
import os
import re
from typing import Any

import torch

from modules import concept_evaluator_v2 as v2
from modules.semantic_scorer import _get_model

EVALUATOR_VERSION = "concept_evaluator_v3.0"
EVALUATOR_VERSION_V3_1 = "concept_evaluator_v3.1"
DEFAULT_CONFIG_VERSION = "concept_evaluator_v3"
DEFAULT_SEMANTIC_THRESHOLD = 0.62

ALL_TIERS: tuple[str, ...] = ("proposition", "alias", "semantic")

_CLAUSE_BOUNDARY_RE = re.compile(r"[.!?\n;()]")
_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+|\n+|;\s+")


def experimental_concept_evaluator_enabled() -> bool:
    """Delegate feature flag check to concept_evaluator_v2."""
    return v2.experimental_concept_evaluator_enabled()


def coverage_level(n_required: int, k_supported: int) -> int | None:
    """Compute ordinal coverage level using concept_evaluator_v2 rubric."""
    return v2.coverage_level(n_required, k_supported)


def _normalize_example_text(text: str) -> str:
    """Normalize whitespace and case for exact leave-one-out matching."""
    return " ".join(str(text or "").split()).strip().lower()


def _normalize_exclude_examples(
    exclude_examples: Iterable[str] | Mapping[str, Iterable[str] | str] | None,
) -> tuple[set[str], dict[str, set[str]]]:
    """Return ``(global_exclusions, per_concept_exclusions)`` normalized strings."""
    if exclude_examples is None:
        return set(), {}
    if isinstance(exclude_examples, str):
        norm = _normalize_example_text(exclude_examples)
        return ({norm} if norm else set()), {}
    if isinstance(exclude_examples, Mapping):
        per_concept: dict[str, set[str]] = {}
        for cid, items in exclude_examples.items():
            key = str(cid or "").strip().lower()
            if not key:
                continue
            bucket = per_concept.setdefault(key, set())
            if isinstance(items, str):
                norm = _normalize_example_text(items)
                if norm:
                    bucket.add(norm)
            elif isinstance(items, Iterable):
                for item in items:
                    norm = _normalize_example_text(str(item))
                    if norm:
                        bucket.add(norm)
        return set(), per_concept
    global_set = {
        norm
        for item in exclude_examples
        if (norm := _normalize_example_text(str(item)))
    }
    return global_set, {}


def _split_sentences(answer_text: str) -> list[str]:
    """Split answer text into non-empty sentence/clause substrings."""
    trimmed = (answer_text or "").strip()
    if not trimmed:
        return []
    return [part.strip() for part in _SENTENCE_SPLIT_RE.split(trimmed) if part.strip()]


def _clause_window_has_negation(
    text: str,
    start: int,
    end: int,
    radius: int = 40,
) -> bool:
    """Check v2._NEGATION within radius chars clamped to the enclosing clause."""
    left_limit = 0
    for match in _CLAUSE_BOUNDARY_RE.finditer(text, 0, start):
        left_limit = match.end()
    right_limit = len(text)
    right_match = _CLAUSE_BOUNDARY_RE.search(text, end)
    if right_match is not None:
        right_limit = right_match.start()
    lo = max(left_limit, start - radius)
    hi = min(right_limit, end + radius)
    return bool(v2._NEGATION.search(text[lo:hi]))


def _sentence_has_only_negated_aliases(sentence: str, terms: list[str]) -> bool:
    """Return True if sentence mentions any alias term and every mention is negated."""
    spans = v2._find_term_spans(sentence, terms)
    if not spans:
        return False
    return all(
        _clause_window_has_negation(sentence, sp["start"], sp["end"])
        for sp in spans
    )


def _normalize_concept_v3(raw: Any) -> dict[str, Any] | None:
    """Extend v2 concept normalization with description fallback and positive_examples."""
    norm = v2._normalize_concept(raw)
    if norm is None:
        return None
    out = dict(norm)
    positive_examples: list[str] = []
    if isinstance(raw, dict):
        raw_desc = str(raw.get("descriptor") or "").strip()
        if not raw_desc:
            alt_desc = str(raw.get("description") or "").strip()
            if alt_desc:
                out["descriptor"] = alt_desc
        for ex in raw.get("positive_examples") or []:
            ex_text = str(ex or "").strip()
            if ex_text:
                positive_examples.append(ex_text)
    out["positive_examples"] = positive_examples
    return out


def _get_semantic_model() -> Any | None:
    """Return cached MiniLM model unless semantic scoring is disabled/unavailable."""
    disabled = os.environ.get("DISABLE_SEMANTIC_SCORING", "").strip().lower()
    if disabled in {"1", "true", "yes"}:
        return None
    try:
        return _get_model()
    except Exception:
        return None


def _semantic_reference_texts(
    concept: dict[str, Any],
    global_exclusions: set[str],
    per_concept_exclusions: dict[str, set[str]],
) -> list[str]:
    """Collect deduplicated semantic reference strings after leave-one-out exclusion."""
    cid_key = concept["id"].strip().lower()
    excluded = set(global_exclusions)
    if cid_key in per_concept_exclusions:
        excluded.update(per_concept_exclusions[cid_key])

    refs: list[str] = []
    seen_norm: set[str] = set()

    descriptor = str(concept.get("descriptor") or "").strip()
    if descriptor:
        desc_norm = _normalize_example_text(descriptor)
        if desc_norm not in seen_norm:
            seen_norm.add(desc_norm)
            refs.append(descriptor)

    for example in concept.get("positive_examples") or []:
        ex_norm = _normalize_example_text(example)
        if not ex_norm or ex_norm in excluded or ex_norm in seen_norm:
            continue
        seen_norm.add(ex_norm)
        refs.append(example)

    return refs


def _score_criteria(
    *,
    required_results: list[dict[str, Any]],
    optional_results: list[dict[str, Any]],
    misconceptions: list[dict[str, Any]],
    answer_text: str,
) -> dict[str, int | None]:
    """Compute rubric criteria parity fields alongside concept states."""
    n_required = len(required_results)
    k_supported = sum(1 for item in required_results if item["state"] == "supported")
    n_contradicted = sum(1 for item in required_results if item["state"] == "contradicted")
    unrefuted_hits = sum(
        1 for m in misconceptions if m.get("matched") and not m.get("refuted")
    )

    cov = coverage_level(n_required, k_supported)
    if n_contradicted > 0 or unrefuted_hits > 0:
        accuracy = 0 if (n_contradicted >= 2 or unrefuted_hits >= 2 or k_supported == 0) else 1
    elif k_supported > 0:
        accuracy = 3
    else:
        accuracy = 1

    opt_supported = sum(1 for item in optional_results if item["state"] == "supported")
    if cov == 3 and opt_supported > 0:
        depth = 3
    elif cov is not None and cov >= 2:
        depth = 2
    elif k_supported > 0:
        depth = 1
    else:
        depth = 0

    word_count = len((answer_text or "").split())
    if word_count == 0:
        clarity = 0
    elif word_count < 8 and k_supported == 0:
        clarity = 1
    elif cov is not None and cov >= 2 and word_count >= 12:
        clarity = 3
    else:
        clarity = 2

    return {
        "coverage": cov,
        "accuracy": accuracy,
        "depth": depth,
        "clarity": clarity,
    }


def evaluate_answer(
    *,
    answer_text: str,
    bundle_content: dict[str, Any],
    bundle_content_hash: str | None = None,
    exclude_examples: Iterable[str] | Mapping[str, Iterable[str] | str] | None = None,
    semantic_threshold: float | None = None,
    enabled_tiers: tuple[str, ...] = ALL_TIERS,
    strict: bool = False,
) -> dict[str, Any]:
    """Evaluate answer_text against bundle concepts using 3-tier proposition/alias/semantic matching.

    Args:
        answer_text: Candidate's answer text.
        bundle_content: Bundle document dict containing ``required_concepts``,
            optional ``optional_concepts``, ``misconceptions``, etc.
        bundle_content_hash: Optional hash passed through into the result payload.
        exclude_examples: Optional leave-one-out exclusions for ``positive_examples``.
            Accepts either an iterable of answer strings applied globally or a mapping
            from ``concept_id`` to example string(s).
        semantic_threshold: Cosine similarity threshold for Tier 3 semantic matches.
            Defaults to ``DEFAULT_SEMANTIC_THRESHOLD``.
        enabled_tiers: Active subset of ``("proposition", "alias", "semantic")``
            (default all three, useful for isolated tier ablation).

    Returns:
        Structured evaluation payload preserving ``concept_evaluator_v2`` keys plus
        per-concept ``match_type``, ``matched_text``, ``semantic_score``, and
        ``matched_reference``.
    """
    content = bundle_content if isinstance(bundle_content, dict) else {}
    config_version = str(content.get("config_version") or DEFAULT_CONFIG_VERSION)
    threshold = (
        DEFAULT_SEMANTIC_THRESHOLD
        if semantic_threshold is None
        else float(semantic_threshold)
    )
    active_tiers = set(enabled_tiers)

    raw_required = [
        c
        for item in (content.get("required_concepts") or [])
        if (c := _normalize_concept_v3(item)) is not None
    ]
    if not raw_required:
        return {
            "evaluator_version": EVALUATOR_VERSION_V3_1 if strict else EVALUATOR_VERSION,
            "config_version": config_version,
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

    raw_optional = [
        c
        for item in (content.get("optional_concepts") or [])
        if (c := _normalize_concept_v3(item)) is not None
    ]
    all_concepts = raw_required + raw_optional

    answer = answer_text or ""
    sentences = _split_sentences(answer)
    global_exclusions, per_concept_exclusions = _normalize_exclude_examples(exclude_examples)

    # First pass: run deterministic Tier 1 (proposition) and Tier 2 (alias), and collect
    # Tier 3 (semantic) candidates so MiniLM encodes sentences/references in one batch.
    preliminary: list[dict[str, Any]] = []
    semantic_pending: list[tuple[int, list[int], list[str]]] = []

    for idx, concept in enumerate(all_concepts):
        terms = [concept["id"], *concept["aliases"]]
        spans = v2._find_term_spans(answer, terms)
        unnegated_spans = [
            sp
            for sp in spans
            if not _clause_window_has_negation(answer, sp["start"], sp["end"])
        ]
        negated_spans = [
            sp
            for sp in spans
            if _clause_window_has_negation(answer, sp["start"], sp["end"])
        ]

        supported_props: list[str] = []
        contradicted_props: list[str] = []
        if "proposition" in active_tiers:
            for prop in concept["expected_propositions"]:
                verdict = v2._proposition_support(answer, prop)
                if verdict == "supported":
                    supported_props.append(prop)
                elif verdict == "contradicted":
                    contradicted_props.append(prop)

        evidence: list[dict[str, Any]] = []
        state: str | None = None
        match_type: str | None = None

        if "proposition" in active_tiers and supported_props:
            state = "supported"
            match_type = "proposition"
            for prop in supported_props:
                evidence.append({"type": "proposition", "text": prop})
        elif contradicted_props:
            # Explicit contradiction of an expected proposition blocks alias/semantic support.
            state = "contradicted"
            match_type = None
            for prop in contradicted_props:
                evidence.append({"type": "proposition_contradicted", "text": prop})
        elif "alias" in active_tiers and unnegated_spans:
            # v3.1 strict mode: naming a term is a mention, never support.
            state = "mentioned" if strict else "supported"
            match_type = "alias"
            for sp in unnegated_spans:
                evidence.append({"type": "alias", "text": sp["text"]})

        entry = {
            "concept": concept,
            "terms": terms,
            "mentions": spans,
            "unnegated_spans": unnegated_spans,
            "negated_spans": negated_spans,
            "evidence": evidence,
            "state": state,
            "match_type": match_type,
            "matched_text": None,
            "semantic_score": None,
            "matched_reference": None,
        }
        preliminary.append(entry)

        if (state is None or (strict and state == "mentioned")) and "semantic" in active_tiers and sentences:
            eligible_indices = [
                si
                for si, sent in enumerate(sentences)
                if not _sentence_has_only_negated_aliases(sent, terms)
            ]
            refs = _semantic_reference_texts(
                concept, global_exclusions, per_concept_exclusions
            )
            if eligible_indices and refs:
                semantic_pending.append((idx, eligible_indices, refs))

    # Second pass: batch MiniLM scoring for Tier 3 candidates.
    if semantic_pending:
        model = _get_semantic_model()
        if model is not None:
            unique_refs: list[str] = []
            ref_to_idx: dict[str, int] = {}
            for _, _, refs in semantic_pending:
                for ref in refs:
                    if ref not in ref_to_idx:
                        ref_to_idx[ref] = len(unique_refs)
                        unique_refs.append(ref)

            sent_embs = model.encode(
                sentences, convert_to_tensor=True, normalize_embeddings=True
            )
            ref_embs = model.encode(
                unique_refs, convert_to_tensor=True, normalize_embeddings=True
            )
            sim_matrix = torch.matmul(sent_embs, ref_embs.T)

            for entry_idx, eligible_indices, refs in semantic_pending:
                ref_indices = [ref_to_idx[r] for r in refs]
                sub_sims = sim_matrix[eligible_indices][:, ref_indices]
                flat_max = int(torch.argmax(sub_sims).item())
                best_row = flat_max // len(ref_indices)
                best_col = flat_max % len(ref_indices)
                best_score = float(sub_sims[best_row, best_col].item())
                if best_score >= threshold:
                    best_sent = sentences[eligible_indices[best_row]]
                    best_ref = refs[best_col]
                    entry = preliminary[entry_idx]
                    rounded_score = round(best_score, 4)
                    entry["state"] = "supported"
                    entry["match_type"] = "semantic"
                    entry["matched_text"] = best_sent
                    entry["semantic_score"] = rounded_score
                    entry["matched_reference"] = best_ref
                    entry["evidence"].append(
                        {
                            "type": "semantic",
                            "text": best_sent,
                            "matched_reference": best_ref,
                            "score": rounded_score,
                        }
                    )

    # Finalize unresolved states and strip internal bookkeeping keys.
    concept_outputs: list[dict[str, Any]] = []
    for entry in preliminary:
        final_state = entry["state"]
        if final_state is None:
            final_state = "uncertain" if entry["negated_spans"] else "not_demonstrated"
        concept_outputs.append(
            {
                "concept_id": entry["concept"]["id"],
                "descriptor": entry["concept"]["descriptor"],
                "state": final_state,
                "match_type": entry["match_type"],
                "matched_text": entry["matched_text"],
                "semantic_score": entry["semantic_score"],
                "matched_reference": entry["matched_reference"],
                "mentions": entry["mentions"],
                "evidence": entry["evidence"],
            }
        )

    n_req = len(raw_required)
    required_results = concept_outputs[:n_req]
    optional_results = concept_outputs[n_req:]

    misconception_results: list[dict[str, Any]] = []
    raw_misconceptions = (
        content.get("misconceptions") or content.get("common_misconceptions") or []
    )
    for raw_misconception in raw_misconceptions:
        matched, spans, refuted = v2._misconception_hit(answer, raw_misconception)
        mid = (
            raw_misconception.get("id")
            if isinstance(raw_misconception, dict)
            else str(raw_misconception)
        )
        misconception_results.append(
            {
                "id": mid,
                "matched": matched,
                "refuted": refuted,
                "mentions": spans,
            }
        )

    k_supported = sum(1 for item in required_results if item["state"] == "supported")
    criteria = _score_criteria(
        required_results=required_results,
        optional_results=optional_results,
        misconceptions=misconception_results,
        answer_text=answer,
    )

    return {
        "evaluator_version": EVALUATOR_VERSION_V3_1 if strict else EVALUATOR_VERSION,
        "config_version": config_version,
        "bundle_content_hash": bundle_content_hash,
        "assessable": True,
        "concepts": required_results,
        "optional_concepts": optional_results,
        "coverage": {
            "n_required": n_req,
            "k_supported": k_supported,
            "level": criteria["coverage"],
        },
        "criteria": criteria,
        "misconceptions": misconception_results,
        "headline_total": None,
    }


__all__ = [
    "ALL_TIERS",
    "DEFAULT_CONFIG_VERSION",
    "DEFAULT_SEMANTIC_THRESHOLD",
    "EVALUATOR_VERSION",
    "coverage_level",
    "evaluate_answer",
    "experimental_concept_evaluator_enabled",
]
