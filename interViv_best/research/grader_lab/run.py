"""Execute the grader-lab comparison without modifying production logic."""

from __future__ import annotations

import argparse
import os
from pathlib import Path

from .baselines import (
    InterVivCurrentBaseline,
    LexicalSimilarityBaseline,
    SemanticRelevanceBaseline,
)
from .datasets import DEFAULT_DATA_DIR, DatasetLoadResult, load_registered_datasets
from .manifest import build_manifest
from .metrics import calculate_metrics
from .report import deferred_rows, metric_rows, pending_access_rows, write_reports
from .structured_judge import StructuredJudgeBaseline

DEFAULT_RESULTS_DIR = Path(__file__).resolve().parent / "results"


def run_lab(
    *,
    data_dir: str | Path = DEFAULT_DATA_DIR,
    results_dir: str | Path = DEFAULT_RESULTS_DIR,
    max_examples_per_dataset: int | None = None,
    enable_interviv_semantic: bool = True,
) -> tuple[Path, Path]:
    os.environ.setdefault("HF_HUB_OFFLINE", "1")
    os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")
    datasets = load_registered_datasets(data_dir)
    if max_examples_per_dataset is not None:
        if max_examples_per_dataset <= 0:
            raise ValueError("max_examples_per_dataset must be positive")
        datasets = {
            name: DatasetLoadResult(
                name=item.name,
                status=item.status,
                version=(
                    f"{item.version};deterministic_head={max_examples_per_dataset}"
                    if item.status == "loaded"
                    else item.version
                ),
                path=item.path,
                examples=item.examples[:max_examples_per_dataset],
                note=(
                    f"{min(len(item.examples), max_examples_per_dataset)} example deterministic head sample"
                    if item.status == "loaded"
                    else item.note
                ),
            )
            for name, item in datasets.items()
        }

    baselines = [
        LexicalSimilarityBaseline(),
        SemanticRelevanceBaseline(),
        InterVivCurrentBaseline(enable_semantic=enable_interviv_semantic),
    ]
    judge = StructuredJudgeBaseline()
    rows: list[dict[str, object]] = []
    for dataset_name in ("scientsbank", "beetle", "internal_perturbation"):
        dataset = datasets[dataset_name]
        if dataset.status != "loaded":
            continue
        for baseline in baselines:
            predictions = baseline.predict_many(dataset.examples)
            metrics = calculate_metrics(dataset.examples, predictions)
            rows.extend(
                metric_rows(
                    dataset=dataset,
                    baseline_name=baseline.name,
                    metrics=metrics,
                )
            )

    rows.extend(deferred_rows(judge))
    rows.extend(pending_access_rows(datasets))
    versions = {
        baseline.name: baseline.manifest_versions() for baseline in baselines
    }
    versions[judge.name] = judge.manifest_versions()
    manifest = build_manifest(datasets, versions)
    return write_reports(results_dir=results_dir, manifest=manifest, rows=rows)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, default=DEFAULT_DATA_DIR)
    parser.add_argument("--results-dir", type=Path, default=DEFAULT_RESULTS_DIR)
    parser.add_argument("--max-examples-per-dataset", type=int)
    parser.add_argument(
        "--disable-interviv-semantic",
        action="store_true",
        help=(
            "Explicitly disable the current interViv pipeline's local semantic component. "
            "The default matches production configuration and attempts the local checkpoint."
        ),
    )
    args = parser.parse_args()
    csv_path, markdown_path = run_lab(
        data_dir=args.data_dir,
        results_dir=args.results_dir,
        max_examples_per_dataset=args.max_examples_per_dataset,
        enable_interviv_semantic=not args.disable_interviv_semantic,
    )
    print(csv_path)
    print(markdown_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
