"""Comparable grading baselines for the research harness."""

from __future__ import annotations

import os
import re
from collections import Counter
from dataclasses import dataclass, field
from typing import Any, Iterable

import numpy as np

from .schema import Example

EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
EMBEDDING_REVISION = "1110a243fdf4706b3f48f1d95db1a4f5529b4d41"

_WORD_RE = re.compile(r"[a-z0-9]+")
_STOPWORDS = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "at",
    "be",
    "because",
    "by",
    "for",
    "from",
    "how",
    "in",
    "is",
    "it",
    "of",
    "on",
    "or",
    "that",
    "the",
    "this",
    "to",
    "was",
    "were",
    "what",
    "when",
    "which",
    "with",
}
_NO_ANSWER_PATTERNS = (
    "i don't know",
    "i dont know",
    "no idea",
    "don't know",
    "dont know",
    "not sure",
)
_NEGATORS = {"no", "not", "never", "neither", "without", "cannot", "can't", "doesn't", "isn't"}
_OPPOSITES = (
    ("increase", "decrease"),
    ("more", "less"),
    ("higher", "lower"),
    ("open", "closed"),
    ("connected", "separated"),
    ("same", "different"),
    ("positive", "negative"),
    ("series", "parallel"),
    ("faster", "slower"),
)


@dataclass(frozen=True)
class FeedbackStatement:
    text: str
    evidence_ids: tuple[str, ...] = ()
    supported: bool = False


@dataclass(frozen=True)
class Prediction:
    example_id: str
    label: str
    score: float
    is_off_topic: bool
    is_contradiction: bool
    feedback: tuple[FeedbackStatement, ...]
    available_evidence_ids: frozenset[str] = field(default_factory=frozenset)
    resolved_gap_ids: frozenset[str] = field(default_factory=frozenset)
    metadata: dict[str, Any] = field(default_factory=dict)


class Baseline:
    name = "baseline"
    status = "ready"

    def predict(self, example: Example) -> Prediction:
        raise NotImplementedError

    def predict_many(self, examples: Iterable[Example]) -> list[Prediction]:
        return [self.predict(example) for example in examples]

    def manifest_versions(self) -> dict[str, str]:
        raise NotImplementedError


class LexicalSimilarityBaseline(Baseline):
    name = "lexical_similarity"

    def predict(self, example: Example) -> Prediction:
        similarity = max(
            (_token_f1(example.answer, reference) for reference in example.reference_answers),
            default=0.0,
        )
        no_answer = _looks_like_no_answer(example.answer)
        if no_answer:
            label = "non_domain"
        elif similarity >= 0.62:
            label = "correct"
        elif similarity >= 0.28:
            label = "partially_correct_incomplete"
        else:
            label = "irrelevant"
        off_topic = no_answer or similarity < 0.08
        resolved = _resolved_gap_ids(example, similarity, threshold=0.48)
        return Prediction(
            example_id=example.example_id,
            label=label,
            score=similarity,
            is_off_topic=off_topic,
            is_contradiction=False,
            feedback=(
                FeedbackStatement(
                    text=f"Token-overlap similarity was {similarity:.3f}.",
                    supported=True,
                ),
            ),
            available_evidence_ids=frozenset({"rubric.correctness"}),
            resolved_gap_ids=resolved,
            metadata={"algorithm": "content-token F1", "threshold_version": "v1"},
        )

    def manifest_versions(self) -> dict[str, str]:
        return {
            "algorithm": "content-token-f1-v1",
            "checkpoint": "none",
        }


class SemanticRelevanceBaseline(Baseline):
    """Embedding similarity plus a fixed, inspectable contradiction guard."""

    name = "semantic_nli_relevance"

    def __init__(self) -> None:
        self._model = None
        self._load_error: str | None = None
        os.environ.setdefault("HF_HUB_OFFLINE", "1")
        os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")
        try:
            from sentence_transformers import SentenceTransformer

            self._model = SentenceTransformer(
                EMBEDDING_MODEL,
                revision=EMBEDDING_REVISION,
                local_files_only=True,
            )
        except Exception as exc:  # pragma: no cover - environment-dependent path
            self._load_error = f"{type(exc).__name__}: {exc}"

    def predict(self, example: Example) -> Prediction:
        return self.predict_many([example])[0]

    def predict_many(self, examples: Iterable[Example]) -> list[Prediction]:
        items = list(examples)
        similarities = self._similarities(items)
        return [
            self._prediction(example, similarity)
            for example, similarity in zip(items, similarities, strict=True)
        ]

    def _similarities(self, examples: list[Example]) -> list[float]:
        if not examples:
            return []
        if self._model is None:
            return [
                max(
                    (_token_f1(item.answer, ref) for ref in item.reference_answers),
                    default=0.0,
                )
                for item in examples
            ]

        texts: list[str] = []
        answer_indexes: list[int] = []
        reference_indexes: list[list[int]] = []
        index_by_text: dict[str, int] = {}

        def add(text: str) -> int:
            normalized = text.strip()
            if normalized not in index_by_text:
                index_by_text[normalized] = len(texts)
                texts.append(normalized)
            return index_by_text[normalized]

        for example in examples:
            answer_indexes.append(add(example.answer or " "))
            reference_indexes.append([add(item) for item in example.reference_answers])

        encoded = self._model.encode(
            texts,
            batch_size=64,
            convert_to_numpy=True,
            normalize_embeddings=True,
            show_progress_bar=False,
        )
        similarities: list[float] = []
        for answer_index, ref_indexes in zip(
            answer_indexes, reference_indexes, strict=True
        ):
            answer_vector = encoded[answer_index]
            score = max(float(np.dot(answer_vector, encoded[index])) for index in ref_indexes)
            similarities.append(max(0.0, min(score, 1.0)))
        return similarities

    def _prediction(self, example: Example, similarity: float) -> Prediction:
        no_answer = _looks_like_no_answer(example.answer)
        contradiction = _contradiction_signal(example.answer, example.reference_answers, similarity)
        if no_answer:
            label = "non_domain"
        elif contradiction:
            label = "contradictory"
        elif similarity >= 0.67:
            label = "correct"
        elif similarity >= 0.40:
            label = "partially_correct_incomplete"
        else:
            label = "irrelevant"
        off_topic = no_answer or (similarity < 0.18 and not contradiction)
        resolved = _resolved_gap_ids(example, similarity, threshold=0.52)
        evidence = frozenset({"rubric.correctness", "rubric.coverage"})
        feedback = (
            FeedbackStatement(
                text=f"Embedding relevance was {similarity:.3f}.",
                evidence_ids=("rubric.correctness",),
                supported=True,
            ),
            FeedbackStatement(
                text=(
                    "A contradiction cue was detected."
                    if contradiction
                    else "No explicit contradiction cue was detected."
                ),
                evidence_ids=("rubric.coverage",),
                supported=True,
            ),
        )
        return Prediction(
            example_id=example.example_id,
            label=label,
            score=similarity,
            is_off_topic=off_topic,
            is_contradiction=contradiction,
            feedback=feedback,
            available_evidence_ids=evidence,
            resolved_gap_ids=resolved,
            metadata={
                "embedding_model": EMBEDDING_MODEL,
                "embedding_revision": EMBEDDING_REVISION,
                "fallback": self._model is None,
                "load_error": self._load_error,
                "contradiction_rule": "negation-and-antonym-v1",
            },
        )

    def manifest_versions(self) -> dict[str, str]:
        return {
            "embedding_model": EMBEDDING_MODEL,
            "embedding_revision": EMBEDDING_REVISION,
            "nli_component": "negation-and-antonym-heuristic-v1",
            "runtime": "local_checkpoint" if self._model is not None else "lexical_fallback",
            "load_error": self._load_error or "none",
        }


class InterVivCurrentBaseline(Baseline):
    """Research adapter around the unmodified production scorer/guard contract."""

    name = "interviv_current_scorer_guard"

    def __init__(self, *, enable_semantic: bool = True) -> None:
        self.enable_semantic = enable_semantic
        self._last_semantic_trace: dict[str, Any] = {}
        self._prediction_count = 0
        self._semantic_applicable_count = 0
        self._semantic_function_call_count = 0
        self._semantic_fallback_count = 0
        self._semantic_not_applicable_count = 0
        self._semantic_fallback_reasons: Counter[str] = Counter()

    def predict(self, example: Example) -> Prediction:
        previous_semantic_setting = os.environ.get("DISABLE_SEMANTIC_SCORING")
        if not self.enable_semantic:
            os.environ["DISABLE_SEMANTIC_SCORING"] = "1"
        try:
            from backend.scoring import pipeline

            ideal_answer = " ".join(example.reference_answers)
            ideal_keywords = ", ".join(
                concept.description for concept in example.concepts[:8]
            )
            payload = pipeline.run_scoring_pipeline(
                answer_text=example.answer,
                question_context={
                    "question": example.question,
                    "ideal_answer": ideal_answer,
                    "ideal_keywords": ideal_keywords,
                    "skill": str(example.metadata.get("module") or example.dataset),
                    "sub_domain": example.question_id,
                },
            )
        finally:
            if not self.enable_semantic:
                if previous_semantic_setting is None:
                    os.environ.pop("DISABLE_SEMANTIC_SCORING", None)
                else:
                    os.environ["DISABLE_SEMANTIC_SCORING"] = previous_semantic_setting
        final_score = float(payload.get("final_score", 0.0))
        guard_reason = payload.get("guard_applied")
        breakdown = payload.get("scoring_breakdown", {})
        semantic_score = breakdown.get("semantic_score")
        semantic_available = bool(breakdown.get("semantic_scoring_available"))
        semantic_source = breakdown.get("semantic_component_source")
        fallback_reason = breakdown.get("semantic_fallback_reason")
        semantic_applicable = bool(example.answer.strip() and ideal_answer.strip())
        semantic_function_called = semantic_available and semantic_score is not None
        fallback_called = semantic_applicable and semantic_source == "lexical_fallback"
        self._prediction_count += 1
        if semantic_applicable:
            self._semantic_applicable_count += 1
        else:
            self._semantic_not_applicable_count += 1
        if semantic_function_called:
            self._semantic_function_call_count += 1
        if fallback_called:
            self._semantic_fallback_count += 1
            self._semantic_fallback_reasons[str(fallback_reason or "unreported")] += 1
        self._last_semantic_trace = {
            "semantic_requested": self.enable_semantic,
            # In the production contract this flag can become true only after
            # SemanticScorer.score(...) returns a non-null similarity.
            "semantic_function_called": semantic_function_called,
            "semantic_score": semantic_score,
            "model_load_attempted": self.enable_semantic
            and fallback_reason != "disabled_by_env",
            "model_load_success": semantic_available,
            "fallback_called": fallback_called,
            "fallback_reason": fallback_reason,
            "semantic_component_source": semantic_source,
        }
        if guard_reason in {"empty", "gibberish"} or _looks_like_no_answer(example.answer):
            label = "non_domain"
        elif guard_reason in {
            "off_topic",
            "keyword_stuffing",
            "question_parroting",
            "low_density",
            "repetition",
        }:
            label = "irrelevant"
        elif final_score >= 65.0:
            label = "correct"
        elif final_score >= 35.0:
            label = "partially_correct_incomplete"
        else:
            label = "irrelevant"

        evidence = set(example.valid_evidence_ids)
        feedback = _interviv_feedback(payload, example)
        resolved = _resolved_gap_ids(example, final_score / 100.0, threshold=0.52)
        return Prediction(
            example_id=example.example_id,
            label=label,
            score=final_score / 100.0,
            is_off_topic=guard_reason == "off_topic",
            is_contradiction=False,
            feedback=feedback,
            available_evidence_ids=frozenset(evidence),
            resolved_gap_ids=resolved,
            metadata={
                "guard_reason": guard_reason,
                "scoring_schema_version": payload.get("scoring_schema_version"),
                "semantic_component_source": (
                    breakdown.get("semantic_component_source")
                ),
                **self._last_semantic_trace,
                "research_adapter": "interviv-current-v1",
            },
        )

    def manifest_versions(self) -> dict[str, str]:
        from backend.scoring import pipeline
        from modules.scoring_schema import SCORING_SCHEMA_VERSION

        metadata = pipeline.get_model_metadata()
        if not self.enable_semantic:
            semantic_runtime = "disabled_lexical_fallback"
        elif self._prediction_count == 0:
            semantic_runtime = "enabled_not_yet_executed"
        elif self._semantic_fallback_count:
            semantic_runtime = "mixed_semantic_and_lexical_fallback"
        elif self._semantic_function_call_count == self._semantic_applicable_count:
            semantic_runtime = "semantic_all_applicable_predictions"
        else:
            semantic_runtime = "semantic_execution_incomplete"
        return {
            "pipeline": "backend.scoring.pipeline@workspace_commit",
            "scoring_schema": SCORING_SCHEMA_VERSION,
            "classifier_model": str(metadata.get("model_type") or "unknown"),
            "classifier_version": str(metadata.get("version") or "unknown"),
            "classifier_artifact": str(metadata.get("artifact_sha256_actual") or "unknown"),
            "semantic_model": EMBEDDING_MODEL,
            "semantic_revision": EMBEDDING_REVISION,
            "semantic_runtime": semantic_runtime,
            "prediction_count": str(self._prediction_count),
            "semantic_applicable_count": str(self._semantic_applicable_count),
            "semantic_function_call_count": str(self._semantic_function_call_count),
            "semantic_fallback_count": str(self._semantic_fallback_count),
            "semantic_not_applicable_count": str(self._semantic_not_applicable_count),
            "semantic_fallback_reasons": (
                ",".join(
                    f"{reason}:{count}"
                    for reason, count in sorted(self._semantic_fallback_reasons.items())
                )
                or "none"
            ),
            "adapter": "interviv-current-v1",
        }


def _interviv_feedback(payload: dict[str, Any], example: Example) -> tuple[FeedbackStatement, ...]:
    raw = payload.get("feedback") or {}
    statements: list[FeedbackStatement] = []
    for text in raw.get("content", []) or []:
        if str(text).strip():
            statements.append(
                FeedbackStatement(
                    str(text), ("rubric.correctness",), supported=True
                )
            )
    for text in raw.get("weakness", []) or []:
        if str(text).strip():
            statements.append(
                FeedbackStatement(str(text), ("rubric.coverage",), supported=True)
            )
    next_step = str(raw.get("next_step") or "").strip()
    if next_step:
        evidence_id = (
            example.followup.trigger_gap_id
            if example.followup is not None
            else "rubric.coverage"
        )
        statements.append(
            FeedbackStatement(next_step, (evidence_id,), supported=True)
        )
    if not statements:
        statements.append(
            FeedbackStatement(
                "No feedback statement was returned.",
                ("rubric.correctness",),
                supported=False,
            )
        )
    return tuple(statements)


def _tokens(text: str, *, content_only: bool = True) -> set[str]:
    tokens = set(_WORD_RE.findall((text or "").lower()))
    if content_only:
        tokens = {item for item in tokens if item not in _STOPWORDS and len(item) > 1}
    return tokens


def _token_f1(left: str, right: str) -> float:
    left_tokens = _tokens(left)
    right_tokens = _tokens(right)
    if not left_tokens or not right_tokens:
        return 0.0
    overlap = len(left_tokens & right_tokens)
    precision = overlap / len(left_tokens)
    recall = overlap / len(right_tokens)
    if precision + recall == 0:
        return 0.0
    return 2.0 * precision * recall / (precision + recall)


def _looks_like_no_answer(text: str) -> bool:
    normalized = " ".join((text or "").lower().split())
    return not normalized or any(pattern in normalized for pattern in _NO_ANSWER_PATTERNS)


def _contradiction_signal(
    answer: str, references: tuple[str, ...], similarity: float
) -> bool:
    if similarity < 0.16:
        return False
    answer_tokens = _tokens(answer, content_only=False)
    reference_tokens = _tokens(" ".join(references), content_only=False)
    answer_negated = bool(answer_tokens & _NEGATORS)
    reference_negated = bool(reference_tokens & _NEGATORS)
    if answer_negated != reference_negated and len(answer_tokens & reference_tokens) >= 2:
        return True
    for left, right in _OPPOSITES:
        if (left in answer_tokens and right in reference_tokens) or (
            right in answer_tokens and left in reference_tokens
        ):
            return True
    return False


def _resolved_gap_ids(
    example: Example, relevance_score: float, *, threshold: float
) -> frozenset[str]:
    if example.followup is None or relevance_score < threshold:
        return frozenset()
    gap_id = example.followup.trigger_gap_id
    description_tokens = _tokens(example.concept_description(gap_id))
    answer_tokens = _tokens(example.answer)
    if description_tokens and not (description_tokens & answer_tokens):
        return frozenset()
    return frozenset({gap_id})
