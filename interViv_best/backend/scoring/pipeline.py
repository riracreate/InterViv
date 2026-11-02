"""
pipeline_v11.py — Updated scoring pipeline for interViv v11.
=============================================================
Key changes from v10:
  • Passes difficulty + candidate_baseline to NLPScorer
  • Feeds richer features (concept_coverage) into the ML classifier call
  • Exposes layer breakdowns in the pipeline result
  • Everything else (KG, NER, feedback, ELO) is unchanged.

Drop-in replacement for backend/scoring/pipeline.py
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import re
from functools import lru_cache
from pathlib import Path
from typing import Any

import joblib

from backend.integrations import (
    IntegrationError,
    call_with_supported_signature,
    load_module,
    locate_file,
    normalize_feedback,
)
from modules.scoring_schema import (
    FINAL_SCORE_WEIGHTS,
    KG_BONUS_MAX,
    NER_BONUS_MAX_ENTITIES,
    NER_BONUS_PER_ENTITY,
    SCORING_SCHEMA_VERSION,
    build_concepts_summary,
    build_guard_summary,
    build_rubric_scores,
)

logger = logging.getLogger(__name__)

_WORD_RE = re.compile(r"[A-Za-z0-9_+#.]+")
_CLASSIFIER_LABEL_SCORE = {"Good": 0.75, "Average": 0.50, "Poor": 0.20}


def _coerce_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


@lru_cache(maxsize=1)
def _locate_classifier_model_file() -> Path:
    for filename in (
        "answer_quality_lr.joblib",
        "answer_quality_gb.joblib",
        "gradient_boosting_classifier.joblib",
        "answer_quality_rf.joblib",
        "svm_model_v11.joblib",
        "svm_model.joblib",
    ):
        try:
            return locate_file(filename, group="model")
        except IntegrationError:
            continue
    raise IntegrationError(
        "Required classifier model artifact was not found in configured model paths. "
        "Expected answer_quality_lr.joblib, answer_quality_gb.joblib, answer_quality_rf.joblib, "
        "gradient_boosting_classifier.joblib, svm_model_v11.joblib, or svm_model.joblib."
    )


def _locate_svm_model_file() -> Path:
    """Deprecated compatibility wrapper; use _locate_classifier_model_file()."""
    return _locate_classifier_model_file()


@lru_cache(maxsize=1)
def _load_classifier_model() -> Any:
    return joblib.load(_locate_classifier_model_file())


def _load_svm_model() -> Any:
    """Deprecated compatibility wrapper; use _load_classifier_model()."""
    return _load_classifier_model()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return "sha256:" + digest.hexdigest()


@lru_cache(maxsize=1)
def load_model_metadata() -> dict[str, Any]:
    """Load read-only model metadata and verify the artifact checksum."""
    artifact_path = _locate_classifier_model_file()
    metadata_path = artifact_path.with_name("model_metadata.json")
    metadata: dict[str, Any] = {
        "artifact_path": str(artifact_path),
        "metadata_path": str(metadata_path),
        "metadata_available": metadata_path.exists(),
    }

    if metadata_path.exists():
        with metadata_path.open("r", encoding="utf-8") as handle:
            metadata.update(json.load(handle))
    else:
        logger.warning("Model metadata missing at %s", metadata_path)

    actual_sha = _sha256_file(artifact_path)
    metadata["artifact_sha256_actual"] = actual_sha
    expected_sha = metadata.get("artifact_sha256")
    metadata["artifact_checksum_verified"] = bool(expected_sha and expected_sha == actual_sha)
    if expected_sha and expected_sha != actual_sha:
        logger.warning(
            "Model artifact checksum mismatch for %s: expected %s, got %s",
            artifact_path,
            expected_sha,
            actual_sha,
        )
    return metadata


def get_model_metadata() -> dict[str, Any]:
    return dict(load_model_metadata())

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
        scorer = _scorer_cls(model_path=str(_locate_classifier_model_file()))
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


# ── ML classifier features now use richer Layer 1 outputs ─────────────────────

def _classifier_features(
    cos_similarity: float,
    length_ratio: float,
    keyword_coverage: float,
    word_count: int,
    concept_coverage: float = 0.5,
) -> list[list[float]]:
    model = _load_classifier_model()
    feature_count = int(getattr(model, "n_features_in_", 4) or 4)
    if feature_count >= 5:
        return [[
            cos_similarity,
            length_ratio,
            keyword_coverage,
            word_count,
            concept_coverage,
        ]]
    return [[cos_similarity, length_ratio, keyword_coverage, word_count]]


def _run_classifier(
    cos_similarity: float,
    length_ratio: float,
    keyword_coverage: float,
    word_count: int,
    concept_coverage: float = 0.5,
) -> dict[str, Any]:
    """Run the answer-quality classifier and expose label + confidence."""
    model = _load_classifier_model()
    features = _classifier_features(
        cos_similarity=cos_similarity,
        length_ratio=length_ratio,
        keyword_coverage=keyword_coverage,
        word_count=word_count,
        concept_coverage=concept_coverage,
    )
    prediction = model.predict(features)
    if prediction is None or len(prediction) == 0:
        raise IntegrationError("Answer quality classifier returned no prediction.")

    label = str(prediction[0])
    probabilities: dict[str, float] = {}
    confidence: float | None = None
    if hasattr(model, "predict_proba"):
        proba = model.predict_proba(features)[0]
        classes = [str(item) for item in getattr(model, "classes_", [])]
        probabilities = {
            classes[index]: round(float(value), 4)
            for index, value in enumerate(proba)
            if index < len(classes)
        }
        confidence = probabilities.get(label)
        if confidence is None and len(proba):
            confidence = float(max(proba))

    label_score = _CLASSIFIER_LABEL_SCORE.get(label, 0.50)
    return {
        "label": label,
        "confidence": round(confidence, 4) if confidence is not None else None,
        "probabilities": probabilities,
        "score_component": label_score,
        "features": features[0],
        "model_type": get_model_metadata().get("model_type"),
    }


def _run_svm_label(
    cos_similarity: float,
    length_ratio: float,
    keyword_coverage: float,
    word_count: int,
    concept_coverage: float = 0.5,
) -> str:
    """Deprecated compatibility wrapper; use _run_classifier()."""
    return str(
        _run_classifier(
            cos_similarity=cos_similarity,
            length_ratio=length_ratio,
            keyword_coverage=keyword_coverage,
            word_count=word_count,
            concept_coverage=concept_coverage,
        )["label"]
    )


# ── Anti-gaming guard ────────────────────────────────────────────────────────

def _run_answer_guard(
    answer_text: str,
    ideal_keywords: str = "",
    question_text: str = "",
    ideal_answer: str = "",
) -> dict:
    module = load_module("answer_guard", "answer_guard.py")
    # Prefer v2 (parroting/fluff/off-topic) when available; fall back to v1.
    if hasattr(module, "check_answer_quality_v2"):
        return module.check_answer_quality_v2(
            answer_text,
            question_text=question_text,
            ideal_keywords=ideal_keywords,
            ideal_answer=ideal_answer,
        )
    if hasattr(module, "check_answer_quality"):
        return module.check_answer_quality(
            answer_text,
            ideal_keywords=ideal_keywords,
            question_text=question_text,
        )
    return {"cap_required": False, "score_cap": 100, "reason": ""}


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
    guard_reason: str | None = None,
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
        guard_reason=guard_reason,
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


def _server_word_count(answer_text: str) -> int:
    return len(_WORD_RE.findall(answer_text or ""))


def _semantic_or_lexical_component(
    semantic_score: float | None,
    tfidf_score: float,
    keyword_coverage: float,
    concept_coverage: float,
    layer1_score: float,
) -> tuple[float, str]:
    if semantic_score is not None:
        return max(0.0, min(semantic_score, 1.0)), "semantic"

    # TF-IDF/keyword overlap is harsher than embedding similarity on valid
    # paraphrases, so the fallback expands lexical evidence slightly but caps it
    # below a confident semantic match.
    lexical = max(
        tfidf_score * 1.60,
        keyword_coverage * 0.95,
        concept_coverage * 1.15,
        (layer1_score / 100.0) * 1.15,
    )
    return max(0.0, min(lexical, 0.86)), "lexical_fallback"


def _calibrated_final_score(
    *,
    semantic_component: float,
    classifier_component: float,
    keyword_coverage: float,
    tfidf_score: float,
    kg_score: float,
    ner_score: float,
    brevity_penalty: float,
) -> tuple[float, dict[str, Any]]:
    semantic_term = FINAL_SCORE_WEIGHTS["semantic_or_lexical"] * semantic_component
    classifier_term = FINAL_SCORE_WEIGHTS["classifier"] * classifier_component
    keyword_term = FINAL_SCORE_WEIGHTS["keyword"] * keyword_coverage
    tfidf_term = FINAL_SCORE_WEIGHTS["tfidf"] * tfidf_score
    base_score = 100.0 * (semantic_term + classifier_term + keyword_term + tfidf_term)

    kg_bonus = min(max(kg_score / 100.0, 0.0), 1.0) * KG_BONUS_MAX
    ner_bonus = min(max(ner_score, 0.0), NER_BONUS_MAX_ENTITIES) * NER_BONUS_PER_ENTITY
    final_score = max(0.0, min(base_score + kg_bonus + ner_bonus - brevity_penalty, 100.0))

    formula = (
        "100*("
        f"{FINAL_SCORE_WEIGHTS['semantic_or_lexical']:.2f}*semantic_or_lexical + "
        f"{FINAL_SCORE_WEIGHTS['classifier']:.2f}*classifier + "
        f"{FINAL_SCORE_WEIGHTS['keyword']:.2f}*keyword + "
        f"{FINAL_SCORE_WEIGHTS['tfidf']:.2f}*tfidf"
        ") + kg_bonus + ner_bonus - penalties"
    )
    return final_score, {
        "formula": formula,
        "scoring_schema_version": SCORING_SCHEMA_VERSION,
        "semantic_term": round(semantic_term * 100.0, 2),
        "classifier_term": round(classifier_term * 100.0, 2),
        "keyword_term": round(keyword_term * 100.0, 2),
        "tfidf_term": round(tfidf_term * 100.0, 2),
        "kg_bonus": round(kg_bonus, 2),
        "ner_bonus": round(ner_bonus, 2),
        "brevity_penalty": round(brevity_penalty, 2),
        "base_score": round(base_score, 2),
    }


def _build_score_explanation(
    *,
    final_score: float,
    semantic_available: bool,
    semantic_component_source: str,
    keyword_details: dict[str, Any] | None,
    guard_reason: str | None,
    guard_softened: bool,
    tfidf_score: float,
    keyword_coverage: float,
) -> dict[str, Any]:
    covered: list[str] = []
    missed: list[str] = []
    for item in (keyword_details or {}).get("matches", []):
        if item.get("covered"):
            covered.append(str(item.get("keyword")))
        else:
            missed.append(str(item.get("keyword")))

    strengths: list[str] = []
    weaknesses: list[str] = []
    if semantic_available:
        strengths.append("strong semantic match")
    elif semantic_component_source == "lexical_fallback" and not guard_reason:
        strengths.append("lexical fallback used because semantic scoring was unavailable")
    if covered:
        strengths.append("covered " + ", ".join(covered[:2]))
    if missed:
        weaknesses.append("missed " + ", ".join(missed[:2]))
    if keyword_coverage < 0.45:
        weaknesses.append("low expected keyword coverage")
    if tfidf_score < 0.25:
        weaknesses.append("low overlap with the reference answer")

    if guard_reason:
        summary = "Answer was capped by the anti-gaming guard."
    elif guard_softened:
        summary = "Short answer matched the reference semantically, so only a small brevity penalty was applied."
    elif final_score >= 75:
        summary = "Strong conceptual match with enough supporting terminology."
    elif final_score >= 55:
        summary = "Partially correct answer; improve by covering the missing expected concepts."
    else:
        summary = "Weak match to the reference answer and expected concepts."

    return {
        "summary": summary,
        "strengths": strengths[:4],
        "weaknesses": weaknesses[:4],
        "guard_reason": guard_reason,
        "semantic_available": semantic_available,
    }


def _debug_scoring_log(payload: dict[str, Any]) -> None:
    if os.getenv("DEBUG_SCORING", "").lower() not in {"1", "true", "yes"}:
        return
    logger.info("DEBUG_SCORING %s", json.dumps(payload, default=str, ensure_ascii=True))


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
    client_word_count = word_count
    word_count = _server_word_count(answer_text)

    # ── Anti-gaming guard (runs first) ────────────────────────────────────────
    guard = _run_answer_guard(
        answer_text,
        ideal_keywords=question_context.get("ideal_keywords", ""),
        question_text=question_context.get("question", "") or "",
        ideal_answer=question_context.get("ideal_answer", "") or "",
    )

    # ── NLP (v11 3-layer scorer) ──────────────────────────────────────────────
    nlp_score, nlp_payload = _run_nlp_score(
        answer_text, question_context, difficulty, candidate_baseline
    )
    _p = nlp_payload if isinstance(nlp_payload, dict) else {}

    layer1_score     = _coerce_float(_p.get("layer1_score", 0.0))
    layer2_score     = _coerce_float(_p.get("layer2_score", 0.0))
    layer3_score     = _coerce_float(_p.get("layer3_score", 0.0))
    raw_semantic     = _p.get("semantic_score")
    semantic_score   = _coerce_float(raw_semantic) if raw_semantic is not None else None
    tfidf_score      = _coerce_float(_p.get("tfidf_score", _p.get("cosine_similarity", 0.0)))
    keyword_coverage = _coerce_float(_p.get("keyword_coverage", 0.0))
    concept_coverage = _coerce_float(_p.get("concept_coverage", 0.0))
    semantic_available = bool(_p.get("semantic_scoring_available", semantic_score is not None))
    semantic_fallback_reason = _p.get("semantic_fallback_reason")
    keyword_details = _p.get("keyword_coverage_details") if isinstance(_p.get("keyword_coverage_details"), dict) else None

    # ── Server-side similarity metrics (replaces frontend computation) ─────────
    ideal_answer = question_context.get("ideal_answer", "")
    cos_similarity, length_ratio = _compute_server_side_metrics(
        answer_text, ideal_answer, word_count
    )

    # ── Classifier label/probability ──────────────────────────────────────────
    classifier = _run_classifier(
        cos_similarity=_coerce_float(_p.get("cosine_similarity", cos_similarity)),
        length_ratio=_coerce_float(_p.get("clarity_score", length_ratio)),
        keyword_coverage=keyword_coverage,
        word_count=word_count,
        concept_coverage=concept_coverage,
    )
    svm_label = str(classifier["label"])

    # ── Knowledge Graph & NER ─────────────────────────────────────────────────
    kg_score, kg_payload = _run_knowledge_graph(answer_text, question_context)
    ner_entities = _run_ner(answer_text)
    ner_score = float(len(ner_entities))           # proxy: entity count

    # Surface concept hits/misses from the KG scorer for round persistence
    # and for the dashboard's "Concepts you covered / missed" panel.
    if isinstance(kg_payload, dict):
        kg_label = str(kg_payload.get("kg_label") or "")
        covered_concepts = [str(x) for x in (kg_payload.get("found_nodes") or [])]
        missing_concepts = [str(x) for x in (kg_payload.get("missing_key") or [])]
    else:
        kg_label = ""
        covered_concepts = []
        missing_concepts = []

    # ── Guard cap audit: caps are hard limits. The guard runs before scoring,
    # and final_score must never exceed the selected score_cap.
    effective_guard = dict(guard)
    guard_softened = False
    brevity_penalty = 0.0

    semantic_component, semantic_component_source = _semantic_or_lexical_component(
        semantic_score=semantic_score,
        tfidf_score=tfidf_score,
        keyword_coverage=keyword_coverage,
        concept_coverage=concept_coverage,
        layer1_score=layer1_score,
    )
    final_score, formula_breakdown = _calibrated_final_score(
        semantic_component=semantic_component,
        classifier_component=_coerce_float(classifier.get("score_component"), 0.50),
        keyword_coverage=keyword_coverage,
        tfidf_score=tfidf_score,
        kg_score=kg_score,
        ner_score=ner_score,
        brevity_penalty=brevity_penalty,
    )

    # ── Apply guard cap ───────────────────────────────────────────────────────
    if effective_guard.get("cap_required"):
        final_score = min(final_score, float(effective_guard["score_cap"]))

    # ── Optional completeness multiplier (default OFF; n=50-contaminated) ─────
    # Formula: clip(word_len_ratio / 0.45, 0.3, 1.0). See docs/track2_heldout_protocol.md.
    length_ratio_multiplier_applied = False
    completeness_length_ratio = None
    completeness_multiplier = None
    from modules.length_ratio_completeness import (
        apply_completeness_multiplier,
        length_ratio_multiplier_enabled,
    )

    if length_ratio_multiplier_enabled():
        final_score, completeness_length_ratio, completeness_multiplier = (
            apply_completeness_multiplier(
                final_score,
                answer_text,
                ideal_answer,
            )
        )
        length_ratio_multiplier_applied = True

    # ── Feedback ──────────────────────────────────────────────────────────────
    _gr = effective_guard.get("reason") if effective_guard.get("cap_required") else None
    feedback = _run_feedback(
        answer_text=answer_text,
        nlp_score=nlp_score,
        svm_label=svm_label,
        kg_score=kg_score,
        final_score=round(final_score, 2),
        ner_entities=ner_entities,
        question_context=question_context,
        nlp_payload=nlp_payload if isinstance(nlp_payload, dict) else None,
        guard_reason=_gr,
    )

    # ── Guard message into feedback ───────────────────────────────────────────
    if effective_guard.get("cap_required"):
        _guard_messages = {
            "empty":              "Your answer looks incomplete or gibberish. Please write a meaningful explanation.",
            "gibberish":          "Your answer looks incomplete or gibberish. Please write a meaningful explanation.",
            "repetition":         "Your answer looks incomplete or gibberish. Please write a meaningful explanation.",
            "too_short":          "Your answer looks incomplete or gibberish. Please write a meaningful explanation.",
            "keyword_stuffing":   "Your answer appeared to stuff keywords without meaningful context.",
            "question_parroting": "Your answer mostly repeats the question. Explain the concept in your own words.",
            "low_density":        "Your answer looks incomplete or gibberish. Please write a meaningful explanation.",
            "off_topic":          "Your answer doesn't seem to address the question. Re-read the question and focus on its specific topic.",
            "truncated_fragment": "Your answer stops mid-sentence. Finish the explanation so it can be scored fully.",
            "entity_swap":        "Your answer gives each side the other side's properties. Check which properties belong to which.",
        }
        msg = _guard_messages.get(effective_guard["reason"], "Your answer quality was flagged by the scoring guard.")
        feedback.setdefault("content", []).insert(0, msg)
    elif guard_softened:
        feedback.setdefault("content", []).insert(
            0,
            "Your answer was brief, but the semantic match was strong, so only a small brevity penalty was applied.",
        )

    metadata = {
        "engagement_label": engagement_label,
        "wpm": _coerce_float(wpm, 0.0) if wpm is not None else None,
        "pause_count": int(pause_count) if pause_count is not None else None,
        "server_word_count": word_count,
    }

    score_explanation = _build_score_explanation(
        final_score=final_score,
        semantic_available=semantic_available,
        semantic_component_source=semantic_component_source,
        keyword_details=keyword_details,
        guard_reason=effective_guard["reason"] if effective_guard.get("cap_required") else None,
        guard_softened=guard_softened,
        tfidf_score=tfidf_score,
        keyword_coverage=keyword_coverage,
    )

    guard_score_cap = (
        effective_guard.get("score_cap")
        if effective_guard.get("cap_required")
        else None
    )
    rubric = build_rubric_scores(
        semantic_component=semantic_component,
        classifier_component=_coerce_float(classifier.get("score_component"), 0.50),
        keyword_coverage=keyword_coverage,
        concept_coverage=concept_coverage,
        kg_score=kg_score,
        depth_score=_p.get("depth_score", 0.0),
        structure_score=_p.get("structure_score", 0.0),
        clarity_score=_p.get("clarity_score", 0.0),
        length_ratio=length_ratio,
        score_cap=guard_score_cap,
    )
    concepts = build_concepts_summary(
        covered_concepts=covered_concepts,
        missing_concepts=missing_concepts,
    )
    guard_summary = build_guard_summary(
        guard,
        effective_guard,
        softened=guard_softened,
    )

    scoring_breakdown: dict[str, Any] = {
        "scoring_schema_version": SCORING_SCHEMA_VERSION,
        "rubric":          rubric,
        "concepts":        concepts,
        "guard":           guard_summary,
        "layer1_score":     round(layer1_score, 2),
        "layer2_score":     round(layer2_score, 2),
        "layer3_score":     round(layer3_score, 2),
        "semantic":         round(semantic_component, 4),
        "semantic_component_source": semantic_component_source,
        "semantic_score":   round(semantic_score, 4) if semantic_score is not None else None,
        "semantic_scoring_available": semantic_available,
        "semantic_fallback_reason": semantic_fallback_reason,
        "tfidf_score":      round(tfidf_score, 4),
        "tfidf":            round(tfidf_score, 4),
        "keyword_coverage": round(keyword_coverage, 4),
        "keyword_coverage_details": keyword_details,
        "concept_coverage": round(concept_coverage, 4),
        "kg_score":         round(kg_score, 2),
        "kg_label":         kg_label,
        "missing_concepts": missing_concepts,
        "covered_concepts": covered_concepts,
        "kg_payload":       kg_payload,
        "ner_score":        ner_score,
        "server_word_count": word_count,
        "client_word_count_ignored": client_word_count,
        "guard_applied":    effective_guard["reason"] if effective_guard.get("cap_required") else None,
        "guard_reason":     guard.get("reason") or None,
        "guard_softened":   guard_softened,
        "guards_fired":     guard.get("guards_fired", []),
        "guard_caps":       [
            item.get("score_cap")
            for item in guard.get("guards_fired", [])
            if item.get("score_cap") is not None
        ],
        "final_score":      round(final_score, 2),
        "nlp_score":        round(nlp_score, 2),
        "svm_label":        svm_label,
        "classifier_label": svm_label,
        "classifier_confidence": classifier.get("confidence"),
        "classifier_probabilities": classifier.get("probabilities", {}),
        "classifier_component": round(_coerce_float(classifier.get("score_component"), 0.50), 4),
        "classifier_model_type": classifier.get("model_type"),
        "formula":          formula_breakdown["formula"],
        "formula_breakdown": formula_breakdown,
        "score_explanation": score_explanation,
        "feedback":         feedback,
        # additional sub-features
        "depth_score":      _coerce_float(_p.get("depth_score", 0.0)),
        "structure_score":  _coerce_float(_p.get("structure_score", 0.0)),
        "accuracy_score":   _coerce_float(_p.get("accuracy_score", 0.0)),
        "clarity_score":    _coerce_float(_p.get("clarity_score", 0.0)),
        "advanced_bonus":   _coerce_float(_p.get("advanced_bonus", 0.0)),
        "difficulty_bonus": _coerce_float(_p.get("difficulty_bonus", 0.0)),
        "length_ratio_multiplier_enabled": length_ratio_multiplier_applied,
        "completeness_length_ratio": (
            round(completeness_length_ratio, 4)
            if completeness_length_ratio is not None
            else None
        ),
        "completeness_multiplier": (
            round(completeness_multiplier, 4)
            if completeness_multiplier is not None
            else None
        ),
    }

    _debug_scoring_log(
        {
            "question": question_context.get("question"),
            "candidate_answer": answer_text,
            "server_word_count": word_count,
            "ideal_answer": ideal_answer,
            "ideal_keywords": question_context.get("ideal_keywords", ""),
            "semantic_score": semantic_score,
            "tfidf_score": tfidf_score,
            "keyword_coverage": keyword_coverage,
            "concept_ngram_overlap": concept_coverage,
            "layer1_score": layer1_score,
            "layer2_score": layer2_score,
            "layer3_score": layer3_score,
            "classifier_label": svm_label,
            "classifier_probability": classifier.get("confidence"),
            "kg_score": kg_score,
            "ner_score": ner_score,
            "guards_fired": guard.get("guards_fired", []),
            "rubric": rubric,
            "guard": guard_summary,
            "final_score": round(final_score, 2),
            "formula_breakdown": formula_breakdown,
        }
    )

    return {
        # ── v10-compatible keys ───────────────────────────────────────────────
        "svm_label":    svm_label,
        "nlp_score":    round(nlp_score, 2),
        "kg_score":     round(kg_score, 2),
        "ner_entities": ner_entities,
        "final_score":  round(final_score, 2),
        "feedback":     feedback,
        "metadata":     metadata,
        "score_explanation": score_explanation,
        "scoring_schema_version": SCORING_SCHEMA_VERSION,
        "rubric":       rubric,
        "concepts":     concepts,
        "guard":        guard_summary,

        # ── Full scoring breakdown (Change 4) ─────────────────────────────────
        "scoring_breakdown": scoring_breakdown,

        # ── Guard ─────────────────────────────────────────────────────────────
        "guard_applied": effective_guard["reason"] if effective_guard.get("cap_required") else None,
    }
