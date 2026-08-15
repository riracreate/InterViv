from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest

from research.grader_lab.baselines import FeedbackStatement, Prediction
from research.grader_lab.datasets import (
    DatasetLoadResult,
    INTERNAL_DATASET_VERSION,
    load_registered_datasets,
)
from research.grader_lab.metrics import calculate_metrics
from research.grader_lab.metric_sanity import run_metric_capability_checks
from research.grader_lab.report import metric_rows
from research.grader_lab.schema import Example, SchemaValidationError, load_jsonl

LAB_ROOT = Path(__file__).resolve().parents[1]


def _payload(**overrides):
    payload = {
        "schema_version": "grader-lab-example-v1",
        "example_id": "internal:test",
        "dataset": "internal_perturbation",
        "dataset_version": INTERNAL_DATASET_VERSION,
        "split": "pilot",
        "question_id": "q1",
        "question": "Why does the bulb light?",
        "reference_answers": ["A closed path lets current flow."],
        "answer": "A closed path lets current flow.",
        "gold_label": "correct",
        "concepts": [
            {"id": "concept.circuit.closed-path", "description": "closed path"}
        ],
        "pilot_synthetic": True,
        "metadata": {},
    }
    payload.update(overrides)
    return payload


def test_jsonl_schema_accepts_bundled_internal_set():
    examples = load_jsonl(LAB_ROOT / "data" / "internal_perturbations.jsonl")
    assert examples
    assert all(item.pilot_synthetic for item in examples)
    assert {item.perturbation_type for item in examples} >= {
        "off_topic",
        "vague",
        "keyword_stuffed",
        "contradiction",
        "partial",
        "followup_resolution",
    }


@pytest.mark.parametrize(
    "change",
    [
        {"reference_answers": []},
        {"gold_label": "almost_correct"},
        {"concepts": [{"id": "bad-id", "description": "closed path"}]},
        {"pilot_synthetic": False},
    ],
)
def test_jsonl_schema_rejects_invalid_records(change):
    with pytest.raises(SchemaValidationError):
        Example.from_dict(_payload(**change))


def test_metric_calculation_includes_evidence_citation_completeness():
    first = Example.from_dict(_payload(example_id="internal:first"))
    second = Example.from_dict(
        _payload(
            example_id="internal:second",
            gold_label="contradictory",
            answer="The circuit is open.",
        )
    )
    predictions = [
        Prediction(
            example_id=first.example_id,
            label="correct",
            score=0.9,
            is_off_topic=False,
            is_contradiction=False,
            feedback=(
                FeedbackStatement(
                    "Supported", ("rubric.correctness",), supported=True
                ),
            ),
            available_evidence_ids=frozenset({"rubric.correctness"}),
        ),
        Prediction(
            example_id=second.example_id,
            label="contradictory",
            score=0.8,
            is_off_topic=False,
            is_contradiction=True,
            feedback=(FeedbackStatement("Free text", supported=False),),
            available_evidence_ids=frozenset({"rubric.correctness"}),
        ),
    ]
    metrics = {item.metric: item for item in calculate_metrics([first, second], predictions)}
    assert metrics["grading_accuracy"].value == 1.0
    assert metrics["contradiction_detection_rate"].value == 1.0
    assert metrics["evidence_citation_completeness"].value == 0.5
    assert metrics["unsupported_feedback_rate"].value == 0.5
    assert metrics["feedback_claim_count"].value == 2.0
    assert metrics["unsupported_feedback_claim_count"].value == 1.0


def test_no_feedback_is_na_not_zero_and_positive_control_detects_failure():
    example = Example.from_dict(_payload())
    no_feedback = Prediction(
        example_id=example.example_id,
        label="correct",
        score=1.0,
        is_off_topic=False,
        is_contradiction=False,
        feedback=(),
    )
    metrics = {item.metric: item for item in calculate_metrics([example], [no_feedback])}
    assert metrics["feedback_claim_count"].value == 0.0
    assert metrics["unsupported_feedback_claim_count"].value == 0.0
    assert metrics["unsupported_feedback_rate"].value is None

    fabricated = replace(
        no_feedback,
        feedback=(
            FeedbackStatement(
                "Fabricated mastery claim", evidence_ids=(), supported=False
            ),
        ),
    )
    metrics = {item.metric: item for item in calculate_metrics([example], [fabricated])}
    assert metrics["feedback_claim_count"].value == 1.0
    assert metrics["unsupported_feedback_claim_count"].value == 1.0
    assert metrics["unsupported_feedback_rate"].value == 1.0


def test_metric_capability_controls_are_reachable():
    checks = {item.metric: item for item in run_metric_capability_checks()}
    assert all(item.status == "VALIDATED_CAPABLE" for item in checks.values())
    assert "off_topic_detection_rate" in checks
    assert "off_topic_false_positive_rate" in checks


def test_missing_ricechem_is_pending_access_not_failure(tmp_path):
    registry = load_registered_datasets(tmp_path)
    assert registry["ricechem"].status == "pending_access"
    assert registry["ricechem"].examples == ()
    assert registry["scientsbank"].status == "missing"


def test_resolved_evidence_rows_are_labeled_pilot_synthetic():
    followup = Example.from_dict(
        _payload(
            example_id="internal:followup",
            followup={
                "parent_example_id": "internal:parent",
                "trigger_gap_id": "concept.circuit.closed-path",
                "gold_resolves_trigger_gap": True,
            },
        )
    )
    prediction = Prediction(
        example_id=followup.example_id,
        label="correct",
        score=0.9,
        is_off_topic=False,
        is_contradiction=False,
        feedback=(
            FeedbackStatement(
                "Cited", ("concept.circuit.closed-path",), supported=True
            ),
        ),
        available_evidence_ids=frozenset({"concept.circuit.closed-path"}),
        resolved_gap_ids=frozenset({"concept.circuit.closed-path"}),
    )
    result = DatasetLoadResult(
        name="internal_perturbation",
        status="loaded",
        version=INTERNAL_DATASET_VERSION,
        path=Path("internal.jsonl"),
        examples=(followup,),
    )
    rows = metric_rows(
        dataset=result,
        baseline_name="test",
        metrics=calculate_metrics([followup], [prediction]),
    )
    resolved_row = next(row for row in rows if row["metric"] == "resolved_evidence_rate")
    assert resolved_row["pilot_synthetic"] == "true"
    assert resolved_row["section"] == "synthetic_only_pilot"


def test_single_turn_data_does_not_emit_resolved_evidence_metric():
    example = Example.from_dict(_payload())
    prediction = Prediction(
        example_id=example.example_id,
        label="correct",
        score=1.0,
        is_off_topic=False,
        is_contradiction=False,
        feedback=(),
    )
    metric_names = {item.metric for item in calculate_metrics([example], [prediction])}
    assert "resolved_evidence_rate" not in metric_names


def test_macro_f1_has_no_artificial_fraction():
    example = Example.from_dict(_payload())
    prediction = Prediction(
        example_id=example.example_id,
        label="correct",
        score=1.0,
        is_off_topic=False,
        is_contradiction=False,
        feedback=(),
    )
    metrics = {item.metric: item for item in calculate_metrics([example], [prediction])}
    macro = metrics["macro_f1"]
    assert macro.value == 1.0
    assert macro.numerator is None
    assert macro.denominator is None
