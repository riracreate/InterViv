"""Research-only component ablations for the current interViv scorer.

This module never changes production configuration or code. It replays the
production pipeline and derives explicitly documented final-aggregation-term
ablations from the returned scoring breakdown.
"""

from __future__ import annotations

import csv
import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from .baselines import EMBEDDING_MODEL, EMBEDDING_REVISION, Prediction
from .datasets import DEFAULT_DATA_DIR, DatasetLoadResult, load_registered_datasets
from .manifest import RunManifest, build_manifest
from .metrics import MetricResult, calculate_metrics
from .schema import Example
from .structured_judge import StructuredJudgeBaseline

DEFAULT_RESULTS_DIR = Path(__file__).resolve().parent / "results"
CONFIGURATIONS = (
    "full_interviv",
    "without_semantic",
    "without_classifier_term",
    "without_keyword_term",
    "without_tfidf_term",
    "without_guards",
)
PAPER_METRICS = (
    "grading_accuracy",
    "macro_f1",
    "off_topic_detection_rate",
    "off_topic_false_positive_rate",
    "contradiction_detection_rate",
)
TERM_WEIGHTS = {
    "without_classifier_term": ("classifier_term", 0.25),
    "without_keyword_term": ("keyword_term", 0.20),
    "without_tfidf_term": ("tfidf_term", 0.10),
}
_NO_ANSWER = ("i don't know", "i dont know", "no idea", "don't know", "dont know", "not sure")


@dataclass(frozen=True)
class AblationResult:
    rows: tuple[dict[str, str], ...]
    manifest: RunManifest


class AblationRunner:
    def __init__(self) -> None:
        self.full_semantic_applicable = 0
        self.full_semantic_calls = 0
        self.full_semantic_fallbacks = 0
        self.without_semantic_fallbacks = 0

    def predict_many(
        self, examples: Iterable[Example]
    ) -> dict[str, list[Prediction]]:
        predictions = {name: [] for name in CONFIGURATIONS}
        for example in examples:
            item = self._predict_one(example)
            for name in CONFIGURATIONS:
                predictions[name].append(item[name])
        return predictions

    def _predict_one(self, example: Example) -> dict[str, Prediction]:
        from backend.scoring import pipeline

        context = {
            "question": example.question,
            "ideal_answer": " ".join(example.reference_answers),
            "ideal_keywords": ", ".join(
                concept.description for concept in example.concepts[:8]
            ),
            "skill": str(example.metadata.get("module") or example.dataset),
            "sub_domain": example.question_id,
        }
        previous = os.environ.pop("DISABLE_SEMANTIC_SCORING", None)
        try:
            full_payload = pipeline.run_scoring_pipeline(
                answer_text=example.answer, question_context=context
            )
            os.environ["DISABLE_SEMANTIC_SCORING"] = "1"
            no_semantic_payload = pipeline.run_scoring_pipeline(
                answer_text=example.answer, question_context=context
            )
        finally:
            if previous is None:
                os.environ.pop("DISABLE_SEMANTIC_SCORING", None)
            else:
                os.environ["DISABLE_SEMANTIC_SCORING"] = previous

        full_breakdown = full_payload.get("scoring_breakdown", {})
        no_semantic_breakdown = no_semantic_payload.get("scoring_breakdown", {})
        applicable = bool(example.answer.strip() and context["ideal_answer"].strip())
        if applicable:
            self.full_semantic_applicable += 1
        if full_breakdown.get("semantic_scoring_available"):
            self.full_semantic_calls += 1
        if applicable and full_breakdown.get("semantic_component_source") == "lexical_fallback":
            self.full_semantic_fallbacks += 1
        if applicable and no_semantic_breakdown.get("semantic_component_source") == "lexical_fallback":
            self.without_semantic_fallbacks += 1

        result = {
            "full_interviv": _prediction(
                example, full_payload, float(full_payload.get("final_score", 0.0))
            ),
            "without_semantic": _prediction(
                example,
                no_semantic_payload,
                float(no_semantic_payload.get("final_score", 0.0)),
            ),
        }
        for name, (term, weight) in TERM_WEIGHTS.items():
            score = _score_without_term(full_payload, term=term, weight=weight)
            result[name] = _prediction(example, full_payload, score)
        result["without_guards"] = _prediction(
            example,
            full_payload,
            _uncapped_score(full_payload),
            guards_enabled=False,
        )
        return result

    def manifest_versions(self) -> dict[str, str]:
        from backend.scoring import pipeline

        metadata = pipeline.get_model_metadata()
        return {
            "adapter": "interviv-ablation-v1",
            "pipeline": "backend.scoring.pipeline@workspace_commit",
            "classifier_model": str(metadata.get("model_type") or "unknown"),
            "classifier_version": str(metadata.get("version") or "unknown"),
            "classifier_artifact": str(
                metadata.get("artifact_sha256_actual") or "unknown"
            ),
            "semantic_model": EMBEDDING_MODEL,
            "semantic_revision": EMBEDDING_REVISION,
            "full_semantic_applicable_count": str(self.full_semantic_applicable),
            "full_semantic_function_call_count": str(self.full_semantic_calls),
            "full_semantic_fallback_count": str(self.full_semantic_fallbacks),
            "without_semantic_lexical_fallback_count": str(
                self.without_semantic_fallbacks
            ),
            "term_ablation_policy": (
                "remove named final-score term; renormalize remaining base weights; "
                "retain bonuses and guard cap"
            ),
            "without_guards_policy": "use pre-cap production score and suppress guard label",
        }


def run_ablation(
    *, data_dir: str | Path = DEFAULT_DATA_DIR
) -> AblationResult:
    os.environ.setdefault("HF_HUB_OFFLINE", "1")
    os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")
    datasets = load_registered_datasets(data_dir)
    runner = AblationRunner()
    rows: list[dict[str, str]] = []
    for dataset_name in ("scientsbank", "beetle", "internal_perturbation"):
        dataset = datasets[dataset_name]
        if dataset.status != "loaded":
            continue
        predictions = runner.predict_many(dataset.examples)
        for configuration in CONFIGURATIONS:
            metrics = {
                item.metric: item
                for item in calculate_metrics(
                    dataset.examples, predictions[configuration]
                )
            }
            for metric_name in PAPER_METRICS:
                rows.append(
                    _metric_row(
                        dataset, configuration, metrics[metric_name]
                    )
                )
    versions = {
        "interviv_ablation": runner.manifest_versions(),
        "structured_llm_rubric_judge": StructuredJudgeBaseline().manifest_versions(),
    }
    manifest = build_manifest(datasets, versions)
    _stamp_rows(rows, manifest)
    return AblationResult(tuple(rows), manifest)


def write_ablation_reports(
    result: AblationResult, results_dir: str | Path = DEFAULT_RESULTS_DIR
) -> tuple[Path, Path]:
    output = Path(results_dir)
    output.mkdir(parents=True, exist_ok=True)
    csv_path = output / "interviv_ablation_results.csv"
    md_path = output / "interviv_ablation_report.md"
    columns = tuple(result.rows[0]) if result.rows else ()
    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        writer.writerows(result.rows)
    md_path.write_text(_render_markdown(result), encoding="utf-8")
    return csv_path, md_path


def _prediction(
    example: Example,
    payload: dict[str, Any],
    score: float,
    *,
    guards_enabled: bool = True,
) -> Prediction:
    reason = payload.get("guard_applied") if guards_enabled else None
    normalized = " ".join(example.answer.lower().split())
    no_answer = not normalized or any(marker in normalized for marker in _NO_ANSWER)
    if guards_enabled and (reason in {"empty", "gibberish"} or no_answer):
        label = "non_domain"
    elif guards_enabled and reason in {
        "off_topic", "keyword_stuffing", "question_parroting", "low_density", "repetition"
    }:
        label = "irrelevant"
    elif score >= 65.0:
        label = "correct"
    elif score >= 35.0:
        label = "partially_correct_incomplete"
    else:
        label = "irrelevant"
    return Prediction(
        example_id=example.example_id,
        label=label,
        score=max(0.0, min(score / 100.0, 1.0)),
        is_off_topic=bool(guards_enabled and reason == "off_topic"),
        is_contradiction=False,
        feedback=(),
        metadata={"configuration": "ablation", "guard_reason": reason},
    )


def _uncapped_score(payload: dict[str, Any]) -> float:
    formula = payload.get("scoring_breakdown", {}).get("formula_breakdown", {})
    base = float(formula.get("base_score", 0.0))
    bonuses = float(formula.get("kg_bonus", 0.0)) + float(
        formula.get("ner_bonus", 0.0)
    )
    penalty = float(formula.get("brevity_penalty", 0.0))
    return max(0.0, min(base + bonuses - penalty, 100.0))


def _score_without_term(
    payload: dict[str, Any], *, term: str, weight: float
) -> float:
    formula = payload.get("scoring_breakdown", {}).get("formula_breakdown", {})
    base = float(formula.get("base_score", 0.0))
    removed = float(formula.get(term, 0.0))
    renormalized_base = max(0.0, base - removed) / (1.0 - weight)
    score = renormalized_base + float(formula.get("kg_bonus", 0.0)) + float(
        formula.get("ner_bonus", 0.0)
    ) - float(formula.get("brevity_penalty", 0.0))
    guard = payload.get("scoring_breakdown", {}).get("guard", {})
    cap = guard.get("score_cap") if guard.get("applied") else None
    if cap is not None:
        score = min(score, float(cap))
    return max(0.0, min(score, 100.0))


def _metric_row(
    dataset: DatasetLoadResult, configuration: str, metric: MetricResult
) -> dict[str, str]:
    return {
        "run_id": "",
        "generated_at_utc": "",
        "git_commit": "",
        "git_dirty": "",
        "dataset_manifest": "",
        "model_manifest": "",
        "section": (
            "synthetic_only_pilot"
            if dataset.name == "internal_perturbation"
            else "benchmark_validated"
        ),
        "dataset": dataset.name,
        "dataset_status": dataset.status,
        "dataset_version": dataset.version,
        "configuration": configuration,
        "metric": metric.metric,
        "value": "N/A" if metric.value is None else f"{metric.value:.6f}",
        "numerator": "" if metric.numerator is None else str(metric.numerator),
        "denominator": "" if metric.denominator is None else str(metric.denominator),
        "pilot_synthetic": str(dataset.name == "internal_perturbation").lower(),
    }


def _stamp_rows(rows: list[dict[str, str]], manifest: RunManifest) -> None:
    dataset_json = json.dumps(
        manifest.dataset_versions, sort_keys=True, separators=(",", ":")
    )
    model_json = json.dumps(
        manifest.model_versions, sort_keys=True, separators=(",", ":")
    )
    for row in rows:
        row.update(
            {
                "run_id": manifest.run_id,
                "generated_at_utc": manifest.generated_at_utc,
                "git_commit": manifest.git_commit,
                "git_dirty": str(manifest.git_dirty).lower(),
                "dataset_manifest": dataset_json,
                "model_manifest": model_json,
            }
        )


def _render_markdown(result: AblationResult) -> str:
    manifest = result.manifest.to_dict()
    lines = [
        "# interViv research-only ablation report",
        "",
        "> The structured LLM rubric judge remains `deferred`; comparison coverage is incomplete and zero API/network calls were made.",
        "",
        "## Run manifest",
        "",
        "| Field | Value |",
        "| --- | --- |",
        f"| Run ID | `{manifest['run_id']}` |",
        f"| Generated at (UTC) | `{manifest['generated_at_utc']}` |",
        f"| Git commit hash | `{manifest['git_commit']}` |",
        f"| Dirty worktree | `{str(manifest['git_dirty']).lower()}` |",
        "| Dataset versions/checksums/sources/licenses | `"
        + _json(manifest["dataset_versions"])
        + "` |",
        "| Model/checkpoint/classifier/configuration | `"
        + _json(manifest["model_versions"])
        + "` |",
        "| Runtime versions | `" + _json(manifest["runtime_versions"]) + "` |",
        "",
        "## Benchmark-validated metrics",
        "",
    ]
    lines.extend(_metric_table(result.rows, section="benchmark_validated"))
    lines.extend(
        [
            "## Synthetic-only pilot metrics",
            "",
            "All rows in this section are `pilot_synthetic=true`; they are not benchmark evidence.",
            "",
        ]
    )
    lines.extend(_metric_table(result.rows, section="synthetic_only_pilot"))
    lines.extend(
        [
            "## Deferred baselines",
            "",
            "The structured LLM rubric judge is `deferred` and made zero API/network calls.",
            "",
            "## Pending-access datasets",
            "",
            "RiceChem is `pending_access`; no files were present or downloaded.",
            "",
            "## Interpretation limits",
            "",
            "- `without_semantic` executes the production lexical fallback and therefore also changes the classifier's first input feature.",
            "- Classifier, keyword, and TF-IDF variants remove only the named final aggregation term and renormalize remaining base weights. Correlated evidence retained in upstream features is not erased.",
            "- `without_guards` removes the hard cap and explicit off-topic flag but leaves all underlying scorer components unchanged.",
            "- All configurations inherit the current pipeline's lack of an explicit contradiction output; contradiction recall is therefore expected to remain zero.",
            "- Ablation results measure component sensitivity on these datasets, not learner readiness or hiring outcomes.",
            "",
        ]
    )
    return "\n".join(lines)


def _metric_table(rows: tuple[dict[str, str], ...], *, section: str) -> list[str]:
    selected = [row for row in rows if row["section"] == section]
    lines = [
        "| Dataset | Configuration | Metric | Value | n/N | pilot_synthetic |",
        "| --- | --- | --- | ---: | ---: | --- |",
    ]
    for row in selected:
        fraction = (
            f"{row['numerator']}/{row['denominator']}"
            if row["denominator"]
            else "—"
        )
        lines.append(
            f"| {row['dataset']} | {row['configuration']} | {row['metric']} | "
            f"{row['value']} | {fraction} | {row['pilot_synthetic']} |"
        )
    lines.append("")
    return lines


def _json(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":")).replace("|", "\\|")


def main() -> int:
    result = run_ablation()
    csv_path, md_path = write_ablation_reports(result)
    print(csv_path)
    print(md_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
