"""Baseline-agnostic analysis of missed gold contradictions.

Categories are conservative deterministic annotations for exploration, not
human-validated semantic ground truth.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable, Mapping

from .baselines import (
    Baseline,
    InterVivCurrentBaseline,
    LexicalSimilarityBaseline,
    Prediction,
    SemanticRelevanceBaseline,
)
from .datasets import DatasetLoadResult, load_registered_datasets
from .manifest import RunManifest, build_manifest
from .schema import Example
from .structured_judge import StructuredJudgeBaseline

DEFAULT_RESULTS_DIR = Path(__file__).resolve().parent / "results"
DEFAULT_BASELINE = "semantic_nli_relevance"
INTERVIV_NOT_RUN = "not_run"

REQUIRED_COLUMNS = (
    "sample_id",
    "dataset",
    "question",
    "reference_answer",
    "candidate_answer",
    "gold_label",
    "baseline_name",
    "semantic_nli_score",
    "lexical_score",
    "interviv_score",
    "failure_category",
    "category_source",
    "category_confidence",
    "review_required",
)

CSV_COLUMNS = REQUIRED_COLUMNS + (
    "interviv_score_status",
    "run_id",
    "generated_at_utc",
    "git_commit",
    "dataset_version",
    "dataset_source",
    "dataset_sha256",
    "license_status",
    "baseline_model_checkpoint",
    "classifier_artifact_version",
    "semantic_runtime_status",
    "runtime_versions",
    "structured_llm_judge_status",
    "ricechem_status",
)

ALLOWED_CATEGORIES = {
    "NEGATION",
    "FACTUAL_REVERSAL",
    "CAUSAL_REVERSAL",
    "WRONG_ENTITY",
    "WRONG_RELATION",
    "PARTIAL_PLUS_FALSE_CLAIM",
    "REFERENCE_CONFLICT",
    "OTHER",
}

_TOKEN_RE = re.compile(r"[a-z0-9]+")
_NEGATORS = {"no", "not", "never", "without", "cannot", "isnt", "doesnt", "wont"}
_OPPOSITES = (
    ("increase", "decrease"),
    ("increases", "decreases"),
    ("increased", "decreased"),
    ("higher", "lower"),
    ("more", "less"),
    ("open", "closed"),
    ("connected", "separated"),
    ("positive", "negative"),
    ("series", "parallel"),
    ("faster", "slower"),
    ("before", "after"),
    ("accepts", "rejects"),
    ("true", "false"),
)
_RELATION_VERBS = {
    "causes",
    "contains",
    "controls",
    "creates",
    "decreases",
    "flows",
    "increases",
    "lights",
    "maintains",
    "produces",
    "pumps",
    "removes",
    "stores",
    "uses",
}
_STOP = {
    "a", "an", "and", "are", "as", "at", "by", "for", "from", "in",
    "is", "it", "of", "on", "or", "that", "the", "this", "to", "was",
    "were", "when", "which", "with",
}


@dataclass(frozen=True)
class CategoryDecision:
    failure_category: str
    category_source: str
    category_confidence: float
    review_required: bool


@dataclass(frozen=True)
class DatasetCounts:
    gold_contradictory: int
    detected: int
    missed: int
    analyzed: int


@dataclass(frozen=True)
class AnalysisResult:
    baseline_name: str
    rows: tuple[dict[str, str], ...]
    dataset_counts: dict[str, DatasetCounts]
    manifest: RunManifest


BaselineFactory = Callable[[], Baseline]


def default_baseline_factories() -> dict[str, BaselineFactory]:
    return {
        "lexical_similarity": LexicalSimilarityBaseline,
        "semantic_nli_relevance": SemanticRelevanceBaseline,
        "interviv_current_scorer_guard": InterVivCurrentBaseline,
    }


def resolve_baseline(
    identifier: str,
    factories: Mapping[str, BaselineFactory] | None = None,
) -> Baseline:
    registry = dict(factories or default_baseline_factories())
    try:
        return registry[identifier]()
    except KeyError as exc:
        raise ValueError(
            f"Unknown baseline {identifier!r}; available: {', '.join(sorted(registry))}"
        ) from exc


def categorize_failure(example: Example) -> CategoryDecision:
    references = example.reference_answers
    if _references_conflict(references):
        return CategoryDecision("REFERENCE_CONFLICT", "deterministic_rule", 0.99, True)

    combined_reference = " ".join(references)
    if _negation_mismatch(example.answer, combined_reference):
        return CategoryDecision("NEGATION", "deterministic_rule", 0.95, False)
    if _causal_reversal(example.answer, references):
        return CategoryDecision("CAUSAL_REVERSAL", "deterministic_rule", 0.95, False)
    if _opposite_pair(example.answer, combined_reference):
        return CategoryDecision("FACTUAL_REVERSAL", "deterministic_rule", 0.94, False)
    if _wrong_entity(example.answer, references):
        return CategoryDecision("WRONG_ENTITY", "deterministic_rule", 0.90, False)
    if _wrong_relation(example.answer, references):
        return CategoryDecision("WRONG_RELATION", "deterministic_rule", 0.86, True)

    # Deliberately do not infer PARTIAL_PLUS_FALSE_CLAIM from similarity alone.
    # That category needs manual review unless an exact future rule is defined.
    return CategoryDecision("OTHER", "unresolved", 0.0, True)


def analyze_contradiction_misses(
    datasets: Mapping[str, DatasetLoadResult],
    baseline: Baseline,
    *,
    lexical_baseline: Baseline | None = None,
    interViv_baseline: Baseline | None = None,
) -> AnalysisResult:
    lexical = lexical_baseline or LexicalSimilarityBaseline()
    loaded = [
        item
        for name, item in datasets.items()
        if name in {"scientsbank", "beetle"} and item.status == "loaded"
    ]
    target_examples = [
        example
        for dataset in loaded
        for example in dataset.examples
        if example.gold_label == "contradictory"
    ]
    target_predictions = _prediction_map(baseline.predict_many(target_examples))
    lexical_predictions = _prediction_map(lexical.predict_many(target_examples))

    if baseline.name == "interviv_current_scorer_guard":
        interViv = baseline
        interViv_predictions = target_predictions
    elif interViv_baseline is not None:
        interViv = interViv_baseline
        interViv_predictions = _prediction_map(
            interViv_baseline.predict_many(target_examples)
        )
    else:
        interViv = None
        interViv_predictions = {}

    versions = {
        baseline.name: baseline.manifest_versions(),
        lexical.name: lexical.manifest_versions(),
        "interviv_current_scorer_guard": (
            interViv.manifest_versions()
            if interViv is not None
            else _not_run_interviv_versions()
        ),
        "structured_llm_rubric_judge": StructuredJudgeBaseline().manifest_versions(),
    }
    manifest = build_manifest(dict(datasets), versions)
    rows: list[dict[str, str]] = []
    counts: dict[str, DatasetCounts] = {}

    for dataset in loaded:
        contradictions = [
            item for item in dataset.examples if item.gold_label == "contradictory"
        ]
        detected = sum(
            target_predictions[item.example_id].is_contradiction
            for item in contradictions
        )
        misses = [
            item
            for item in contradictions
            if not target_predictions[item.example_id].is_contradiction
        ]
        counts[dataset.name] = DatasetCounts(
            gold_contradictory=len(contradictions),
            detected=detected,
            missed=len(misses),
            analyzed=len(misses),
        )
        manifest_dataset = manifest.dataset_versions[dataset.name]
        for example in misses:
            decision = categorize_failure(example)
            target_prediction = target_predictions[example.example_id]
            lexical_prediction = lexical_predictions[example.example_id]
            interViv_prediction = interViv_predictions.get(example.example_id)
            semantic_score = (
                target_prediction.score
                if baseline.name == "semantic_nli_relevance"
                else "not_run"
            )
            rows.append(
                {
                    "sample_id": example.example_id,
                    "dataset": example.dataset,
                    "question": example.question,
                    "reference_answer": " || ".join(example.reference_answers),
                    "candidate_answer": example.answer,
                    "gold_label": example.gold_label,
                    "baseline_name": baseline.name,
                    "semantic_nli_score": _score(semantic_score),
                    "lexical_score": _score(lexical_prediction.score),
                    "interviv_score": (
                        _score(interViv_prediction.score)
                        if interViv_prediction is not None
                        else INTERVIV_NOT_RUN
                    ),
                    "failure_category": decision.failure_category,
                    "category_source": decision.category_source,
                    "category_confidence": f"{decision.category_confidence:.2f}",
                    "review_required": str(decision.review_required).lower(),
                    "interviv_score_status": (
                        "clean_semantic_run"
                        if interViv_prediction is not None
                        else INTERVIV_NOT_RUN
                    ),
                    "run_id": manifest.run_id,
                    "generated_at_utc": manifest.generated_at_utc,
                    "git_commit": manifest.git_commit,
                    "dataset_version": manifest_dataset["version"],
                    "dataset_source": manifest_dataset["source"],
                    "dataset_sha256": manifest_dataset["sha256"],
                    "license_status": manifest_dataset["license_status"],
                    "baseline_model_checkpoint": json.dumps(
                        versions[baseline.name], sort_keys=True, separators=(",", ":")
                    ),
                    "classifier_artifact_version": versions[
                        "interviv_current_scorer_guard"
                    ]["classifier_artifact"],
                    "semantic_runtime_status": versions[baseline.name].get(
                        "runtime", "not_reported"
                    ),
                    "runtime_versions": json.dumps(
                        manifest.runtime_versions,
                        sort_keys=True,
                        separators=(",", ":"),
                    ),
                    "structured_llm_judge_status": "deferred_zero_api_calls",
                    "ricechem_status": manifest.dataset_versions.get("ricechem", {}).get(
                        "status", "not_registered"
                    ),
                }
            )
    return AnalysisResult(baseline.name, tuple(rows), counts, manifest)


def write_analysis_reports(
    result: AnalysisResult, results_dir: str | Path = DEFAULT_RESULTS_DIR
) -> tuple[Path, Path]:
    output = Path(results_dir)
    output.mkdir(parents=True, exist_ok=True)
    csv_path = output / "contradiction_error_analysis.csv"
    markdown_path = output / "contradiction_error_analysis.md"
    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_COLUMNS)
        writer.writeheader()
        writer.writerows(result.rows)
    markdown_path.write_text(_render_markdown(result), encoding="utf-8")
    return csv_path, markdown_path


def _render_markdown(result: AnalysisResult) -> str:
    manifest = result.manifest.to_dict()
    datasets = sorted(result.dataset_counts)
    category_by_dataset = {
        dataset: Counter(
            row["failure_category"] for row in result.rows if row["dataset"] == dataset
        )
        for dataset in datasets
    }
    provenance = Counter(row["category_source"] for row in result.rows)
    lines = [
        "# Contradiction miss error analysis",
        "",
        f"Target baseline: `{result.baseline_name}`. Only gold contradictions missed by this baseline are categorized.",
        "",
        "> Exploratory analysis only: deterministic categories are not human-validated semantic ground truth.",
        "",
        "## Dataset counts",
        "",
        "| Dataset | Gold contradictory | Detected | Missed | Analyzed |",
        "| --- | ---: | ---: | ---: | ---: |",
    ]
    for dataset in datasets:
        count = result.dataset_counts[dataset]
        lines.append(
            f"| {dataset} | {count.gold_contradictory} | {count.detected} | {count.missed} | {count.analyzed} |"
        )
    lines.extend(
        [
            "",
            "## Category counts",
            "",
            "| Category | " + " | ".join(datasets) + " | Total |",
            "| --- | " + " | ".join("---:" for _ in datasets) + " | ---: |",
        ]
    )
    for category in sorted(ALLOWED_CATEGORIES):
        values = [category_by_dataset[name][category] for name in datasets]
        lines.append(
            f"| {category} | " + " | ".join(str(value) for value in values) + f" | {sum(values)} |"
        )
    lines.extend(
        [
            "",
            "## Category provenance",
            "",
            "| Source | Count | Meaning |",
            "| --- | ---: | --- |",
            f"| deterministic_rule | {provenance['deterministic_rule']} | Explicit lexical/syntactic rule matched; still requires research review. |",
            f"| manually_reviewed | {provenance['manually_reviewed']} | No manual annotations were added in this run. |",
            f"| unresolved | {provenance['unresolved']} | Labeled `OTHER`; human review required. |",
            "",
            "## Reproducibility manifest",
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
            "| Baseline/model/checkpoint/classifier configuration | `"
            + _json(manifest["model_versions"])
            + "` |",
            "| Runtime versions | `" + _json(manifest["runtime_versions"]) + "` |",
            "",
            "interViv scores in the CSV were recomputed through the corrected research adapter when `interviv_score_status=clean_semantic_run`; no prior fallback-only scores were reused.",
            "",
            "## Deferred baselines",
            "",
            "The structured LLM rubric judge is `deferred`; its interface has no client or transport and made zero API/network calls.",
            "",
            "## Pending-access datasets",
            "",
            "RiceChem is `pending_access`. No files were present, downloaded, or analyzed.",
            "",
            "## Limitations",
            "",
            "- Automatic rules detect only narrow surface forms; `OTHER` is intentionally preferred to speculative categorization.",
            "- `deterministic_rule` is provenance, not a human gold label. Rows still need adjudication before paper claims or taxonomy-level error rates.",
            "- The target is a pinned local embedding model plus a negation/antonym heuristic, not a trained NLI checkpoint.",
            "- SciEntsBank and BEETLE are single-turn benchmarks; this report says nothing about follow-up resolution.",
            "- The structured LLM rubric judge remains deferred and made zero API/network calls.",
            "- RiceChem remains `pending_access` and was not analyzed.",
            "",
        ]
    )
    return "\n".join(lines)


def _prediction_map(predictions: Iterable[Prediction]) -> dict[str, Prediction]:
    result = {item.example_id: item for item in predictions}
    return result


def _not_run_interviv_versions() -> dict[str, str]:
    versions = InterVivCurrentBaseline().manifest_versions()
    versions.update(
        {
            "semantic_runtime": "not_run_in_this_analysis",
            "analysis_execution": "not_run",
            "classifier_feature_order": (
                "nlp_cosine_similarity,clarity_score,keyword_coverage,"
                "server_word_count,concept_coverage"
            ),
            "classifier_preprocessing": "StandardScaler from saved sklearn Pipeline",
        }
    )
    return versions


def _score(value: float | str) -> str:
    return f"{value:.6f}" if isinstance(value, float) else value


def _tokens(text: str) -> list[str]:
    return _TOKEN_RE.findall(text.lower().replace("'", ""))


def _content_tokens(text: str) -> set[str]:
    return {token for token in _tokens(text) if token not in _STOP and len(token) > 1}


def _has_negator(text: str) -> bool:
    return bool(set(_tokens(text)) & _NEGATORS)


def _negation_mismatch(left: str, right: str) -> bool:
    return (
        _has_negator(left) != _has_negator(right)
        and len(_content_tokens(left) & _content_tokens(right)) >= 2
    )


def _opposite_pair(left: str, right: str) -> bool:
    left_tokens, right_tokens = set(_tokens(left)), set(_tokens(right))
    return any(
        (
            a in left_tokens
            and b not in left_tokens
            and b in right_tokens
            and a not in right_tokens
        )
        or (
            b in left_tokens
            and a not in left_tokens
            and a in right_tokens
            and b not in right_tokens
        )
        for a, b in _OPPOSITES
    )


def _causal_parts(text: str) -> tuple[set[str], set[str]] | None:
    normalized = " ".join(_tokens(text))
    match = re.search(r"(.+?)\b(?:causes?|leads to|results in)\b(.+)", normalized)
    if not match:
        return None
    return _content_tokens(match.group(1)), _content_tokens(match.group(2))


def _causal_reversal(answer: str, references: tuple[str, ...]) -> bool:
    candidate = _causal_parts(answer)
    if not candidate:
        return False
    for reference in references:
        expected = _causal_parts(reference)
        if expected and candidate[0] & expected[1] and candidate[1] & expected[0]:
            return True
    return False


def _relation_frame(text: str) -> tuple[str, str, set[str]] | None:
    tokens = _tokens(text)
    for index, token in enumerate(tokens):
        if token not in _RELATION_VERBS:
            continue
        subjects = [item for item in tokens[:index] if item not in _STOP]
        objects = {item for item in tokens[index + 1 :] if item not in _STOP}
        if subjects and objects:
            return subjects[-1], token, objects
    return None


def _wrong_entity(answer: str, references: tuple[str, ...]) -> bool:
    candidate = _relation_frame(answer)
    if not candidate:
        return False
    for reference in references:
        expected = _relation_frame(reference)
        if (
            expected
            and candidate[1] == expected[1]
            and candidate[0] != expected[0]
            and bool(candidate[2] & expected[2])
        ):
            return True
    return False


def _wrong_relation(answer: str, references: tuple[str, ...]) -> bool:
    candidate = _relation_frame(answer)
    if not candidate:
        return False
    for reference in references:
        expected = _relation_frame(reference)
        if (
            expected
            and candidate[0] == expected[0]
            and candidate[1] != expected[1]
            and bool(candidate[2] & expected[2])
        ):
            return True
    return False


def _references_conflict(references: tuple[str, ...]) -> bool:
    for index, left in enumerate(references):
        for right in references[index + 1 :]:
            tokens = set(_tokens(left)) | set(_tokens(right))
            if "non" in tokens:
                # Do not erase meaning from compounds such as non-zero.
                continue
            removable = _NEGATORS | {"do", "does", "did"}
            left_content = _content_tokens(left) - removable
            right_content = _content_tokens(right) - removable
            # Only sentences identical after removal of an explicit standalone
            # negator are safe enough to call conflicting automatically.
            if (
                left_content == right_content
                and bool(left_content)
                and _negation_mismatch(left, right)
            ):
                return True
    return False


def _json(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":")).replace("|", "\\|")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline", default=DEFAULT_BASELINE)
    parser.add_argument("--results-dir", type=Path, default=DEFAULT_RESULTS_DIR)
    args = parser.parse_args()
    baseline = resolve_baseline(args.baseline)
    interViv = (
        baseline
        if baseline.name == "interviv_current_scorer_guard"
        else InterVivCurrentBaseline(enable_semantic=True)
    )
    result = analyze_contradiction_misses(
        load_registered_datasets(), baseline, interViv_baseline=interViv
    )
    csv_path, markdown_path = write_analysis_reports(result, args.results_dir)
    print(csv_path)
    print(markdown_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
