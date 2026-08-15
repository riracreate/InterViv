"""Metric definitions for diagnostic grading, evidence, and follow-ups."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from .baselines import Prediction
from .schema import Example, LABELS


@dataclass(frozen=True)
class MetricResult:
    metric: str
    value: float | None
    numerator: int | None
    denominator: int | None
    note: str = ""


def calculate_metrics(
    examples: Iterable[Example], predictions: Iterable[Prediction]
) -> list[MetricResult]:
    items = list(examples)
    predicted = list(predictions)
    if len(items) != len(predicted):
        raise ValueError("Examples and predictions must have equal length")
    by_id = {item.example_id: item for item in items}
    if len(by_id) != len(items):
        raise ValueError("Example IDs must be unique")
    if {item.example_id for item in predicted} != set(by_id):
        raise ValueError("Prediction IDs must match example IDs exactly")
    ordered_predictions = {item.example_id: item for item in predicted}

    correct = sum(
        ordered_predictions[item.example_id].label == item.gold_label for item in items
    )
    results = [
        MetricResult(
            "grading_accuracy",
            _ratio(correct, len(items)),
            correct,
            len(items),
        )
    ]

    f1_values: list[float] = []
    for label in LABELS:
        gold_positive = {item.example_id for item in items if item.gold_label == label}
        if not gold_positive:
            continue
        predicted_positive = {
            item.example_id for item in predicted if item.label == label
        }
        true_positive = len(gold_positive & predicted_positive)
        false_positive = len(predicted_positive - gold_positive)
        false_negative = len(gold_positive - predicted_positive)
        precision = _ratio(true_positive, true_positive + false_positive) or 0.0
        recall = _ratio(true_positive, true_positive + false_negative) or 0.0
        f1 = 0.0 if precision + recall == 0 else 2 * precision * recall / (precision + recall)
        f1_values.append(f1)
    macro_f1 = sum(f1_values) / len(f1_values) if f1_values else None
    results.append(
        MetricResult(
            "macro_f1",
            macro_f1,
            None,
            None,
            "Macro-average across labels present in gold data.",
        )
    )

    on_topic = [
        item for item in items if item.gold_label not in {"irrelevant", "non_domain"}
    ]
    off_topic_false_positives = sum(
        ordered_predictions[item.example_id].is_off_topic for item in on_topic
    )
    results.append(
        MetricResult(
            "off_topic_false_positive_rate",
            _ratio(off_topic_false_positives, len(on_topic)),
            off_topic_false_positives,
            len(on_topic),
            "Predicted off-topic among gold on-topic answers.",
        )
    )

    gold_off_topic = [
        item for item in items if item.gold_label in {"irrelevant", "non_domain"}
    ]
    off_topic_hits = sum(
        ordered_predictions[item.example_id].is_off_topic for item in gold_off_topic
    )
    results.append(
        MetricResult(
            "off_topic_detection_rate",
            _ratio(off_topic_hits, len(gold_off_topic)),
            off_topic_hits,
            len(gold_off_topic),
            "Explicit off-topic flag recall over gold irrelevant/non-domain answers.",
        )
    )

    contradictions = [item for item in items if item.gold_label == "contradictory"]
    contradiction_hits = sum(
        ordered_predictions[item.example_id].is_contradiction
        for item in contradictions
    )
    results.append(
        MetricResult(
            "contradiction_detection_rate",
            _ratio(contradiction_hits, len(contradictions)),
            contradiction_hits,
            len(contradictions),
            "Recall on gold contradictory answers.",
        )
    )

    feedback_count = 0
    supported_count = 0
    cited_count = 0
    for prediction in predicted:
        for statement in prediction.feedback:
            feedback_count += 1
            if statement.supported:
                supported_count += 1
            valid_ids = set(statement.evidence_ids) & set(
                prediction.available_evidence_ids
            )
            if any(
                evidence_id.startswith(("rubric.", "concept."))
                for evidence_id in valid_ids
            ):
                cited_count += 1
    unsupported_count = feedback_count - supported_count
    results.extend(
        [
            MetricResult(
                "feedback_claim_count",
                float(feedback_count),
                feedback_count,
                None,
                "Number of emitted feedback statements evaluated as claims.",
            ),
            MetricResult(
                "unsupported_feedback_claim_count",
                float(unsupported_count),
                unsupported_count,
                None,
                "Number of feedback claims without a backing scorer signal or adjudicated source.",
            ),
            MetricResult(
                "unsupported_feedback_rate",
                _ratio(unsupported_count, feedback_count),
                unsupported_count,
                feedback_count,
                "N/A when feedback_claim_count is zero; otherwise unsupported claims divided by all feedback claims.",
            ),
            MetricResult(
                "evidence_citation_completeness",
                _ratio(cited_count, feedback_count),
                cited_count,
                feedback_count,
                "Statements citing an explicit rubric.* or concept.* ID.",
            ),
        ]
    )

    followups = [item for item in items if item.followup is not None]
    if followups:
        resolved_correct = 0
        for item in followups:
            prediction = ordered_predictions[item.example_id]
            predicted_resolved = item.followup.trigger_gap_id in prediction.resolved_gap_ids
            if predicted_resolved == item.followup.gold_resolves_trigger_gap:
                resolved_correct += 1
        results.append(
            MetricResult(
                "resolved_evidence_rate",
                _ratio(resolved_correct, len(followups)),
                resolved_correct,
                len(followups),
                "Exact-trigger-gap resolution judgment accuracy; synthetic pilot only.",
            )
        )
    return results


def _ratio(numerator: int, denominator: int) -> float | None:
    if denominator == 0:
        return None
    return numerator / denominator
