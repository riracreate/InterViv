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

def run_scoring_pipeline(
    *,
    answer_text: str,
    cos_similarity: float,
    length_ratio: float,
    aligned_score: float,
    word_count: int,
    engagement_label: str | None = None,
    wpm: float | None = None,
    pause_count: int | None = None,
    question_context: dict[str, Any] | None = None,
    difficulty: str = "medium",                     # NEW
    candidate_baseline: float | None = None,        # NEW
) -> dict[str, Any]:
    """
    Full scoring pipeline.  Returns same top-level keys as v10, plus:
      layer1_score, layer2_score, layer3_score, scoring_breakdown
    """
    question_context = question_context or {}

    # ── NLP (v11 3-layer scorer) ──────────────────────────────────────────────
    nlp_score, nlp_payload = _run_nlp_score(
        answer_text, question_context, difficulty, candidate_baseline
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

    metadata = {
        "engagement_label": engagement_label,
        "wpm": _coerce_float(wpm, 0.0) if wpm is not None else None,
        "pause_count": int(pause_count) if pause_count is not None else None,
    }

    # ── Layer score extraction for storage / API response ─────────────────────
    scoring_breakdown: dict[str, Any] = {}
    if isinstance(nlp_payload, dict):
        scoring_breakdown = {
            "layer1_score":     nlp_payload.get("layer1_score", 0.0),
            "layer2_score":     nlp_payload.get("layer2_score", 0.0),
            "layer3_score":     nlp_payload.get("layer3_score", 0.0),
            "cosine_similarity":nlp_payload.get("cosine_similarity", 0.0),
            "keyword_coverage": nlp_payload.get("keyword_coverage", 0.0),
            "concept_coverage": nlp_payload.get("concept_coverage", 0.0),
            "depth_score":      nlp_payload.get("depth_score", 0.0),
            "structure_score":  nlp_payload.get("structure_score", 0.0),
            "accuracy_score":   nlp_payload.get("accuracy_score", 0.0),
            "clarity_score":    nlp_payload.get("clarity_score", 0.0),
            "advanced_bonus":   nlp_payload.get("advanced_bonus", 0.0),
            "difficulty_bonus": nlp_payload.get("difficulty_bonus", 0.0),
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

        # ── New in v11 ────────────────────────────────────────────────────────
        "scoring_breakdown": scoring_breakdown,
    }
