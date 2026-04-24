"""
pipeline_v11.py — Updated scoring pipeline for interViv v11.
=============================================================
Key changes from v10:
  • Passes difficulty + candidate_baseline to NLPScorer
  • Feeds richer features (concept_coverage) into the SVM call
  • Exposes layer breakdowns in the pipeline result
  • Everything else (KG, NER, feedback, ELO) is unchanged.

Drop-in replacement for backend/scoring/pipeline.py
"""

from __future__ import annotations

from functools import lru_cache
from typing import Any

import joblib

from backend.integrations import (
    IntegrationError,
    call_with_supported_signature,
    load_module,
    locate_file,
    normalize_feedback,
)


def _coerce_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


@lru_cache(maxsize=1)
def _locate_svm_model_file() -> Any:
    for filename in ("svm_model_v11.joblib", "svm_model.joblib"):
        try:
            return locate_file(filename, group="model")
        except IntegrationError:
            continue
    raise IntegrationError(
        "Required integration file 'svm_model_v11.joblib' or 'svm_model.joblib' "
        "was not found in configured model paths."
    )


@lru_cache(maxsize=1)
def _load_svm_model() -> Any:
    return joblib.load(_locate_svm_model_file())


def _extract_score_value(payload: Any, keys: tuple[str, ...]) -> float | None:
    if isinstance(payload, dict):
        for key in keys:
            if key in payload:
                return _coerce_float(payload[key])
    elif payload is not None:
        return _coerce_float(payload)
    return None


# ── Layer 1/2/3 NLP scoring ───────────────────────────────────────────────────

def _run_nlp_score(
    answer_text: str,
    question_context: dict[str, Any],
    difficulty: str = "medium",
    candidate_baseline: float | None = None,
) -> tuple[float, Any]:
    """
    Run the v11 NLPScorer (3-layer) and return (overall_score, full_payload).
    Falls back to legacy interface if old nlp_scorer.py is in place.
    """
    module = load_module("nlp_scorer_patch", "nlp_scorer_patch.py")
    _scorer_cls = getattr(module, "PatchedNLPScorer", None) or getattr(module, "NLPScorer", None)

    if _scorer_cls is not None:
        scorer = _scorer_cls(model_path=str(_locate_svm_model_file()))
        result = call_with_supported_signature(
            scorer.compute_overall_score,
            answer_text=answer_text,
            answer=answer_text,
            question=question_context.get("question"),
            ideal_answer=question_context.get("ideal_answer"),
            reference_answer=question_context.get("ideal_answer"),
            ideal_keywords=question_context.get("ideal_keywords", ""),
            expected_keywords=question_context.get("ideal_keywords", ""),
            difficulty=difficulty,
            candidate_baseline=candidate_baseline,
        )
    elif hasattr(module, "compute_score"):
        # Legacy fallback
        result = call_with_supported_signature(
            module.compute_score,
            answer=answer_text,
            answer_text=answer_text,
            ideal_keywords=question_context.get("ideal_keywords", ""),
            ideal_answer=question_context.get("ideal_answer"),
        )
    else:
        raise IntegrationError(
            "nlp_scorer module does not expose a supported scoring interface."
        )

    score = _extract_score_value(result, ("overall_score", "final_score", "score"))
    return _coerce_float(score), result


# ── SVM features now use richer Layer 1 outputs ───────────────────────────────

def _run_svm_label(
    cos_similarity: float,
    length_ratio: float,
    keyword_coverage: float,
    word_count: int,
    concept_coverage: float = 0.5,   # NEW in v11
) -> str:
    """
    Run SVM with 5-feature vector (was 4 in v10).
    The extra feature improves label accuracy for technical answers.

    NOTE: If your existing svm_model was trained on 4 features, keep
    concept_coverage out and retrain ASAP (see RETRAINING.md).
    """
    model = _load_svm_model()
    feature_count = int(getattr(model, "n_features_in_", 4) or 4)
    if feature_count >= 5:
        features = [[
            cos_similarity,
            length_ratio,
            keyword_coverage,
            word_count,
            concept_coverage,
        ]]
    else:
        features = [[cos_similarity, length_ratio, keyword_coverage, word_count]]
    prediction = model.predict(features)
    if prediction is None or len(prediction) == 0:
        raise IntegrationError("SVM model returned no prediction.")
    return str(prediction[0])


# ── Anti-gaming guard ────────────────────────────────────────────────────────

def _run_answer_guard(answer_text: str, ideal_keywords: str = "") -> dict:
    module = load_module("answer_guard", "answer_guard.py")
    if not hasattr(module, "check_answer_quality"):
        # Guard unavailable — do not block scoring
        return {"cap_required": False, "score_cap": 100, "reason": ""}
    return module.check_answer_quality(answer_text, ideal_keywords)


# ── Unchanged helpers from v10 ────────────────────────────────────────────────

def _run_knowledge_graph(
    answer_text: str, question_context: dict[str, Any]
) -> tuple[float, Any]:
    module = load_module("knowledge_graph", "knowledge_graph.py")
    if not hasattr(module, "KnowledgeGraphScorer"):
        raise IntegrationError("knowledge_graph.py does not expose KnowledgeGraphScorer.")
    scorer = module.KnowledgeGraphScorer()
    result = call_with_supported_signature(
        scorer.score_answer,
        answer=answer_text,
        answer_text=answer_text,
        question=question_context.get("question"),
        ideal_answer=question_context.get("ideal_answer"),
        reference_answer=question_context.get("ideal_answer"),
        skill=question_context.get("skill"),
        sub_domain=question_context.get("sub_domain"),
    )
    score = _extract_score_value(result, ("kg_score", "score", "final_score"))
    kg_score = _coerce_float(score)
    if 0.0 <= kg_score <= 1.0:
        kg_score *= 100.0
    return kg_score, result


def _run_ner(answer_text: str) -> list[dict[str, Any] | str]:
    module = load_module("ner_scorer", "ner_scorer.py")
    if not hasattr(module, "NERScorer"):
        raise IntegrationError("ner_scorer.py does not expose NERScorer.")
    scorer = module.NERScorer()
    entities = call_with_supported_signature(
        scorer.extract_entities, answer=answer_text, answer_text=answer_text
    )
    if isinstance(entities, list):
        return entities
    return [] if entities is None else [entities]


def _run_feedback(
    answer_text: str,
    nlp_score: float,
    svm_label: str,
    kg_score: float,
    final_score: float,
    ner_entities: list[dict[str, Any] | str],
    question_context: dict[str, Any],
    nlp_payload: dict[str, Any] | None = None,   # NEW: pass layer breakdown
) -> dict[str, Any]:
    module = load_module("c4_feedback", "c4_feedback.py")
    if not hasattr(module, "generate_feedback"):
        raise IntegrationError("c4_feedback.py does not expose generate_feedback().")
    payload = call_with_supported_signature(
        module.generate_feedback,
        answer=answer_text,
        answer_text=answer_text,
        question=question_context.get("question"),
        ideal_answer=question_context.get("ideal_answer"),
        skill=question_context.get("skill"),
        sub_domain=question_context.get("sub_domain"),
        nlp_score=nlp_score,
        svm_label=svm_label,
        kg_score=kg_score,
        final_score=final_score,
        ner_entities=ner_entities,
        # Layer details for richer feedback (accepted by c4_feedback_v11)
        layer1_score=nlp_payload.get("layer1_score") if nlp_payload else None,
        layer2_score=nlp_payload.get("layer2_score") if nlp_payload else None,
        depth_score=nlp_payload.get("depth_score") if nlp_payload else None,
        structure_score=nlp_payload.get("structure_score") if nlp_payload else None,
    )
    return normalize_feedback(payload)


# ── Main entry point ───────────────────────────────────────────────────────────

def _compute_server_side_metrics(
    answer_text: str, ideal_answer: str, word_count: int
) -> tuple[float, float]:
    """
    Compute cos_similarity and length_ratio server-side from candidate answer
    vs ideal answer.  Mirrors what the frontend used to compute (token overlap
    ratio for similarity, capped word-count ratio for length).
    """
    import re as _re

    def _tok(text: str) -> set[str]:
        return set(_re.findall(r"[a-z0-9]+", text.lower()))

    ans_toks = _tok(answer_text)
    ideal_toks = _tok(ideal_answer) if ideal_answer else set()

    if ideal_toks:
        overlap = len(ans_toks & ideal_toks)
        cos_sim = overlap / len(ideal_toks)
    else:
        # No ideal: use answer self-length as proxy (matches old frontend fallback)
        cos_sim = min(word_count / 60, 1.0)

    length_ratio = min(word_count / max(len(ideal_answer.split()), 1), 3.0) if ideal_answer else min(word_count / 60, 1.5)
    return round(cos_sim, 4), round(length_ratio, 4)


def run_scoring_pipeline(
    *,
    answer_text: str,
    word_count: int = 0,
    engagement_label: str | None = None,
    wpm: float | None = None,
    pause_count: int | None = None,
    question_context: dict[str, Any] | None = None,
    difficulty: str = "medium",
    candidate_baseline: float | None = None,
) -> dict[str, Any]:
    """
    Full scoring pipeline.  Returns same top-level keys as v10, plus:
      layer1_score, layer2_score, layer3_score, scoring_breakdown, guard_applied
    cos_similarity / length_ratio are computed server-side (never from client).
    """
    question_context = question_context or {}

    # ── Anti-gaming guard (runs first) ────────────────────────────────────────
    guard = _run_answer_guard(
        answer_text,
        ideal_keywords=question_context.get("ideal_keywords", ""),
    )

    # ── NLP (v11 3-layer scorer) ──────────────────────────────────────────────
    nlp_score, nlp_payload = _run_nlp_score(
        answer_text, question_context, difficulty, candidate_baseline
    )

    # ── Server-side similarity metrics (replaces frontend computation) ─────────
    ideal_answer = question_context.get("ideal_answer", "")
    cos_similarity, length_ratio = _compute_server_side_metrics(
        answer_text, ideal_answer, word_count
    )

    # ── SVM label (uses richer feature set when retrained) ────────────────────
    svm_label = _run_svm_label(
        cos_similarity=cos_similarity,
        length_ratio=length_ratio,
        keyword_coverage=_coerce_float(
            nlp_payload.get("keyword_coverage") if isinstance(nlp_payload, dict) else 0.5
        ),
        word_count=word_count,
        concept_coverage=_coerce_float(
            nlp_payload.get("concept_coverage") if isinstance(nlp_payload, dict) else 0.5
        ),
    )

    # ── Knowledge Graph & NER ─────────────────────────────────────────────────
    kg_score, kg_payload = _run_knowledge_graph(answer_text, question_context)
    ner_entities = _run_ner(answer_text)

    # ── Final score: 85% NLP + 15% Knowledge Graph ───────────────────────────
    final_score = (0.85 * nlp_score) + (0.15 * kg_score)
    if final_score is None:
        raise IntegrationError(
            "No final_score was exposed by the scoring modules."
        )

    # ── Apply guard cap ───────────────────────────────────────────────────────
    if guard["cap_required"]:
        final_score = min(final_score, float(guard["score_cap"]))

    # ── Feedback ──────────────────────────────────────────────────────────────
    feedback = _run_feedback(
        answer_text=answer_text,
        nlp_score=nlp_score,
        svm_label=svm_label,
        kg_score=kg_score,
        final_score=round(final_score, 2),
        ner_entities=ner_entities,
        question_context=question_context,
        nlp_payload=nlp_payload if isinstance(nlp_payload, dict) else None,
    )

    # ── Guard message into feedback ───────────────────────────────────────────
    if guard["cap_required"]:
        _guard_messages = {
            "empty":            "Your answer was empty or too short to evaluate.",
            "gibberish":        "Your answer contained gibberish or non-meaningful characters and was capped.",
            "repetition":       "Your answer repeated the same word excessively. Please give a genuine response.",
            "too_short":        "Your answer was too brief (under 12 words). Aim for at least 2–3 sentences.",
            "keyword_stuffing": "Your answer appeared to stuff keywords without meaningful context.",
        }
        msg = _guard_messages.get(guard["reason"], "Your answer quality was flagged by the scoring guard.")
        feedback.setdefault("content", []).insert(0, msg)

    metadata = {
        "engagement_label": engagement_label,
        "wpm": _coerce_float(wpm, 0.0) if wpm is not None else None,
        "pause_count": int(pause_count) if pause_count is not None else None,
    }

    # ── Extract all breakdown fields from nlp_payload ─────────────────────────
    _p = nlp_payload if isinstance(nlp_payload, dict) else {}
    layer1_score     = _coerce_float(_p.get("layer1_score", 0.0))
    layer2_score     = _coerce_float(_p.get("layer2_score", 0.0))
    layer3_score     = _coerce_float(_p.get("layer3_score", 0.0))
    semantic_score   = _p.get("semantic_score")          # float or None
    tfidf_score      = _coerce_float(_p.get("tfidf_score", _p.get("cosine_similarity", 0.0)))
    keyword_coverage = _coerce_float(_p.get("keyword_coverage", 0.0))
    ner_score        = float(len(ner_entities))           # proxy: entity count

    scoring_breakdown: dict[str, Any] = {
        "layer1_score":     round(layer1_score, 2),
        "layer2_score":     round(layer2_score, 2),
        "layer3_score":     round(layer3_score, 2),
        "semantic_score":   round(semantic_score, 4) if semantic_score is not None else None,
        "tfidf_score":      round(tfidf_score, 4),
        "keyword_coverage": round(keyword_coverage, 4),
        "kg_score":         round(kg_score, 2),
        "ner_score":        ner_score,
        "guard_applied":    guard["reason"] if guard["cap_required"] else None,
        "final_score":      round(final_score, 2),
        "nlp_score":        round(nlp_score, 2),
        "svm_label":        svm_label,
        "feedback":         feedback,
        # additional sub-features
        "depth_score":      _coerce_float(_p.get("depth_score", 0.0)),
        "structure_score":  _coerce_float(_p.get("structure_score", 0.0)),
        "accuracy_score":   _coerce_float(_p.get("accuracy_score", 0.0)),
        "clarity_score":    _coerce_float(_p.get("clarity_score", 0.0)),
        "advanced_bonus":   _coerce_float(_p.get("advanced_bonus", 0.0)),
        "difficulty_bonus": _coerce_float(_p.get("difficulty_bonus", 0.0)),
    }

    return {
        # ── v10-compatible keys ───────────────────────────────────────────────
        "svm_label":    svm_label,
        "nlp_score":    round(nlp_score, 2),
        "kg_score":     round(kg_score, 2),
        "ner_entities": ner_entities,
        "final_score":  round(final_score, 2),
        "feedback":     feedback,
        "metadata":     metadata,

        # ── Full scoring breakdown (Change 4) ─────────────────────────────────
        "scoring_breakdown": scoring_breakdown,

        # ── Guard ─────────────────────────────────────────────────────────────
        "guard_applied": guard["reason"] if guard["cap_required"] else None,
    }
