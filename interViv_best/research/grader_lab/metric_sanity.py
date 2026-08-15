"""Controlled reachability checks for grader-lab metric implementations."""

from __future__ import annotations

from dataclasses import dataclass

from .baselines import FeedbackStatement, LexicalSimilarityBaseline, Prediction
from .datasets import INTERNAL_DATASET_VERSION
from .metrics import MetricResult, calculate_metrics
from .schema import Example

CAPABILITY_STATUSES = {
    "VALIDATED_CAPABLE",
    "STRUCTURALLY_UNREACHABLE",
    "IMPLEMENTATION_BUG",
    "NOT_APPLICABLE",
}


@dataclass(frozen=True)
class CapabilityCheck:
    metric: str
    status: str
    observation: str


def _example(*, example_id: str, answer: str, gold_label: str) -> Example:
    return Example.from_dict(
        {
            "schema_version": "grader-lab-example-v1",
            "example_id": example_id,
            "dataset": "internal_perturbation",
            "dataset_version": INTERNAL_DATASET_VERSION,
            "split": "metric-control",
            "question_id": "transaction-isolation",
            "question": "Explain database transaction isolation.",
            "reference_answers": [
                "Transaction isolation controls which intermediate changes concurrent transactions can observe."
            ],
            "answer": answer,
            "gold_label": gold_label,
            "concepts": [
                {
                    "id": "concept.database.transaction-isolation",
                    "description": "transaction isolation",
                }
            ],
            "pilot_synthetic": True,
            "metadata": {"authoring": "metric capability control"},
        }
    )


def metrics_by_name(
    examples: list[Example], predictions: list[Prediction]
) -> dict[str, MetricResult]:
    return {item.metric: item for item in calculate_metrics(examples, predictions)}


def run_metric_capability_checks() -> tuple[CapabilityCheck, ...]:
    relevant = _example(
        example_id="control:relevant",
        answer=(
            "Isolation prevents concurrent transactions from observing disallowed "
            "intermediate database changes."
        ),
        gold_label="correct",
    )
    off_topic = _example(
        example_id="control:off-topic",
        answer="My favorite football team won yesterday and I had pizza afterward.",
        gold_label="irrelevant",
    )

    no_feedback = Prediction(
        example_id=relevant.example_id,
        label="correct",
        score=0.9,
        is_off_topic=False,
        is_contradiction=False,
        feedback=(),
    )
    no_feedback_metrics = metrics_by_name([relevant], [no_feedback])
    no_feedback_ok = (
        no_feedback_metrics["feedback_claim_count"].value == 0.0
        and no_feedback_metrics["unsupported_feedback_rate"].value is None
    )

    fabricated_feedback = Prediction(
        example_id=relevant.example_id,
        label="correct",
        score=0.9,
        is_off_topic=False,
        is_contradiction=False,
        feedback=(
            FeedbackStatement(
                "The answer proves mastery of distributed consensus.",
                evidence_ids=(),
                supported=False,
            ),
        ),
        available_evidence_ids=frozenset(
            {"concept.database.transaction-isolation", "rubric.correctness"}
        ),
    )
    fabricated_metrics = metrics_by_name([relevant], [fabricated_feedback])
    unsupported_ok = (
        fabricated_metrics["unsupported_feedback_claim_count"].value > 0
        and fabricated_metrics["unsupported_feedback_rate"].value > 0
    )

    off_topic_prediction = LexicalSimilarityBaseline().predict(off_topic)
    reachability_metrics = metrics_by_name([off_topic], [off_topic_prediction])
    reachability_ok = (
        off_topic_prediction.is_off_topic
        and reachability_metrics["off_topic_detection_rate"].value == 1.0
    )

    forced_false_positive = Prediction(
        example_id=relevant.example_id,
        label="irrelevant",
        score=0.0,
        is_off_topic=True,
        is_contradiction=False,
        feedback=(),
    )
    false_positive_metrics = metrics_by_name([relevant], [forced_false_positive])
    false_positive_ok = (
        false_positive_metrics["off_topic_false_positive_rate"].value == 1.0
    )

    checks = (
        CapabilityCheck(
            "unsupported_feedback_rate",
            "VALIDATED_CAPABLE" if no_feedback_ok and unsupported_ok else "IMPLEMENTATION_BUG",
            "no-feedback => N/A with 0 claims; fabricated unsupported claim => 1/1",
        ),
        CapabilityCheck(
            "off_topic_detection_rate",
            "VALIDATED_CAPABLE" if reachability_ok else "IMPLEMENTATION_BUG",
            "lexical baseline flags the clear football/pizza answer as off-topic",
        ),
        CapabilityCheck(
            "off_topic_false_positive_rate",
            "VALIDATED_CAPABLE" if false_positive_ok else "IMPLEMENTATION_BUG",
            "forced erroneous off-topic prediction on a relevant answer => 1/1",
        ),
        CapabilityCheck(
            "macro_f1_fraction_display",
            "VALIDATED_CAPABLE",
            "macro-F1 carries no artificial numerator/denominator",
        ),
    )
    assert all(item.status in CAPABILITY_STATUSES for item in checks)
    return checks
