from __future__ import annotations

import csv
from pathlib import Path

from research.grader_lab.baselines import Baseline, Prediction
from research.grader_lab.contradiction_analysis import (
    REQUIRED_COLUMNS,
    analyze_contradiction_misses,
    categorize_failure,
    resolve_baseline,
    write_analysis_reports,
)
from research.grader_lab.datasets import DatasetLoadResult, SEMEVAL_DATASET_VERSION
from research.grader_lab.schema import Example


def _example(
    *,
    example_id: str = "scientsbank:test",
    answer: str,
    reference: str,
) -> Example:
    return Example.from_dict(
        {
            "schema_version": "grader-lab-example-v1",
            "example_id": example_id,
            "dataset": "scientsbank",
            "dataset_version": SEMEVAL_DATASET_VERSION,
            "split": "test",
            "question_id": "q1",
            "question": "What happens?",
            "reference_answers": [reference],
            "answer": answer,
            "gold_label": "contradictory",
            "concepts": [{"id": "concept.test.fact", "description": "fact"}],
            "pilot_synthetic": False,
            "metadata": {},
        }
    )


class AlwaysMissBaseline(Baseline):
    name = "fake_second_baseline"

    def predict(self, example: Example) -> Prediction:
        return Prediction(
            example_id=example.example_id,
            label="partially_correct_incomplete",
            score=0.42,
            is_off_topic=False,
            is_contradiction=False,
            feedback=(),
        )

    def manifest_versions(self) -> dict[str, str]:
        return {"model": "fake-v1"}


def _datasets(example: Example) -> dict[str, DatasetLoadResult]:
    return {
        "scientsbank": DatasetLoadResult(
            name="scientsbank",
            status="loaded",
            version=SEMEVAL_DATASET_VERSION,
            path=Path("missing-test-fixture.jsonl"),
            examples=(example,),
        )
    }


def test_analyzer_accepts_configurable_fake_baseline_and_writes_required_fields(tmp_path):
    example = _example(
        answer="The kidney pumps blood.", reference="The heart pumps blood."
    )
    baseline = AlwaysMissBaseline()
    result = analyze_contradiction_misses(_datasets(example), baseline)
    assert result.baseline_name == "fake_second_baseline"
    assert result.dataset_counts["scientsbank"].missed == 1
    assert len(result.rows) == 1
    assert set(REQUIRED_COLUMNS) <= set(result.rows[0])

    csv_path, markdown_path = write_analysis_reports(result, tmp_path)
    with csv_path.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    assert rows[0]["baseline_name"] == "fake_second_baseline"
    assert rows[0]["interviv_score"] == "not_run"
    assert "Git commit hash" in markdown_path.read_text(encoding="utf-8")


def test_baseline_registry_is_configurable_without_analyzer_code_changes():
    resolved = resolve_baseline(
        "alternate", {"alternate": AlwaysMissBaseline}
    )
    assert isinstance(resolved, AlwaysMissBaseline)


def test_analyzer_runs_against_semantic_nli_relevance_and_finds_miss():
    example = _example(
        answer="The kidney pumps blood.", reference="The heart pumps blood."
    )
    baseline = resolve_baseline("semantic_nli_relevance")
    result = analyze_contradiction_misses(_datasets(example), baseline)
    assert result.baseline_name == "semantic_nli_relevance"
    assert result.dataset_counts["scientsbank"].missed == 1
    assert result.rows[0]["semantic_nli_score"] != "not_run"


def test_known_deterministic_categories():
    cases = {
        "NEGATION": _example(
            example_id="scientsbank:negation",
            answer="A closed path does not allow current to flow.",
            reference="A closed path allows current to flow.",
        ),
        "WRONG_ENTITY": _example(
            example_id="scientsbank:entity",
            answer="The kidney pumps blood.",
            reference="The heart pumps blood.",
        ),
        "FACTUAL_REVERSAL": _example(
            example_id="scientsbank:reversal",
            answer="The temperature decreases after heating.",
            reference="The temperature increases after heating.",
        ),
    }
    for expected, example in cases.items():
        decision = categorize_failure(example)
        assert decision.failure_category == expected
        assert decision.category_source == "deterministic_rule"
        assert decision.review_required is False


def test_uncertain_case_stays_unresolved_and_requires_review():
    example = _example(
        answer="This process is associated with plants.",
        reference="Photosynthesis converts light into chemical energy.",
    )
    decision = categorize_failure(example)
    assert decision.failure_category == "OTHER"
    assert decision.category_source == "unresolved"
    assert decision.review_required is True
