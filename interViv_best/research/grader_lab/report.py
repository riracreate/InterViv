"""CSV and Markdown report rendering with embedded run manifests."""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

from .datasets import DatasetLoadResult
from .manifest import RunManifest
from .metrics import MetricResult
from .structured_judge import StructuredJudgeBaseline

CSV_COLUMNS = (
    "run_id",
    "generated_at_utc",
    "git_commit",
    "git_dirty",
    "dataset_versions",
    "model_versions",
    "section",
    "dataset",
    "dataset_status",
    "dataset_version",
    "baseline",
    "baseline_status",
    "metric",
    "value",
    "numerator",
    "denominator",
    "pilot_synthetic",
    "note",
)


def metric_rows(
    *,
    dataset: DatasetLoadResult,
    baseline_name: str,
    metrics: list[MetricResult],
) -> list[dict[str, Any]]:
    pilot = dataset.name == "internal_perturbation"
    section = "synthetic_only_pilot" if pilot else "benchmark_validated"
    return [
        {
            "section": section,
            "dataset": dataset.name,
            "dataset_status": dataset.status,
            "dataset_version": dataset.version,
            "baseline": baseline_name,
            "baseline_status": "ready",
            "metric": item.metric,
            "value": "N/A" if item.value is None else f"{item.value:.6f}",
            "numerator": "" if item.numerator is None else item.numerator,
            "denominator": "" if item.denominator is None else item.denominator,
            "pilot_synthetic": "true" if pilot else "false",
            "note": item.note,
        }
        for item in metrics
    ]


def deferred_rows(
    judge: StructuredJudgeBaseline,
) -> list[dict[str, Any]]:
    return [
        {
            "section": "deferred_baselines",
            "dataset": "all",
            "dataset_status": "not_run",
            "dataset_version": "n/a",
            "baseline": judge.name,
            "baseline_status": "deferred",
            "metric": "deferred",
            "value": "",
            "numerator": "",
            "denominator": "",
            "pilot_synthetic": "false",
            "note": (
                "Deferred by policy; zero API/network calls made. "
                "Comparison table is incomplete."
            ),
        }
    ]


def pending_access_rows(
    datasets: dict[str, DatasetLoadResult],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for result in datasets.values():
        if result.status != "pending_access":
            continue
        rows.append(
            {
                "section": "pending_access",
                "dataset": result.name,
                "dataset_status": "pending_access",
                "dataset_version": result.version,
                "baseline": "all",
                "baseline_status": "pending_access",
                "metric": "pending_access",
                "value": "",
                "numerator": "",
                "denominator": "",
                "pilot_synthetic": "false",
                "note": result.note,
            }
        )
    return rows


def write_reports(
    *,
    results_dir: str | Path,
    manifest: RunManifest,
    rows: list[dict[str, Any]],
) -> tuple[Path, Path]:
    output = Path(results_dir)
    output.mkdir(parents=True, exist_ok=True)
    csv_path = output / "grader_lab_results.csv"
    markdown_path = output / "grader_lab_report.md"
    manifest_dict = manifest.to_dict()
    manifest_fields = {
        "run_id": manifest.run_id,
        "generated_at_utc": manifest.generated_at_utc,
        "git_commit": manifest.git_commit,
        "git_dirty": str(manifest.git_dirty).lower(),
        "dataset_versions": json.dumps(
            manifest.dataset_versions, sort_keys=True, separators=(",", ":")
        ),
        "model_versions": json.dumps(
            manifest.model_versions, sort_keys=True, separators=(",", ":")
        ),
    }
    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_COLUMNS)
        writer.writeheader()
        for row in rows:
            writer.writerow({**manifest_fields, **row})

    markdown_path.write_text(
        _render_markdown(manifest_dict, rows), encoding="utf-8"
    )
    return csv_path, markdown_path


def _render_markdown(manifest: dict[str, Any], rows: list[dict[str, Any]]) -> str:
    sections = {
        "benchmark_validated": "Benchmark-validated metrics",
        "synthetic_only_pilot": "Synthetic-only pilot metrics",
        "deferred_baselines": "Deferred baselines",
        "pending_access": "Pending-access datasets",
    }
    lines = [
        "# interViv grader-lab report",
        "",
        "> **Comparison status: INCOMPLETE.** The structured LLM rubric judge is explicitly `deferred`; no API or network call was made.",
        "",
        "## Run manifest",
        "",
        "| Field | Value |",
        "| --- | --- |",
        f"| Run ID | `{manifest['run_id']}` |",
        f"| Generated at (UTC) | `{manifest['generated_at_utc']}` |",
        f"| Git commit hash | `{manifest['git_commit']}` |",
        f"| Dirty worktree | `{str(manifest['git_dirty']).lower()}` |",
        "| Dataset versions | " + _escape_cell(_compact_json(manifest["dataset_versions"])) + " |",
        "| Baseline model/checkpoint versions | "
        + _escape_cell(_compact_json(manifest["model_versions"]))
        + " |",
        "| Runtime versions | "
        + _escape_cell(_compact_json(manifest["runtime_versions"]))
        + " |",
        "",
        "No number in this report should be cited externally without retaining this manifest.",
        "",
    ]
    for section, title in sections.items():
        section_rows = [row for row in rows if row["section"] == section]
        lines.extend([f"## {title}", ""])
        if section == "synthetic_only_pilot":
            lines.extend(
                [
                    "All rows below are labeled `pilot_synthetic=true`. Resolved-evidence rate is computed only here; single-turn benchmarks cannot validate it.",
                    "",
                ]
            )
        if not section_rows:
            lines.extend(["No rows.", ""])
            continue
        lines.extend(
            [
                "| Dataset | Baseline | Status | Metric | Value | n/N | pilot_synthetic | Notes |",
                "| --- | --- | --- | --- | ---: | ---: | --- | --- |",
            ]
        )
        for row in section_rows:
            fraction = (
                f"{row['numerator']}/{row['denominator']}"
                if row.get("denominator") not in ("", None)
                else "—"
            )
            value = row.get("value") or "—"
            lines.append(
                "| {dataset} | {baseline} | {status} | {metric} | {value} | {fraction} | {pilot} | {note} |".format(
                    dataset=_escape_cell(str(row["dataset"])),
                    baseline=_escape_cell(str(row["baseline"])),
                    status=_escape_cell(
                        str(row.get("baseline_status") or row.get("dataset_status"))
                    ),
                    metric=_escape_cell(str(row["metric"])),
                    value=_escape_cell(str(value)),
                    fraction=_escape_cell(fraction),
                    pilot=_escape_cell(str(row["pilot_synthetic"])),
                    note=_escape_cell(str(row.get("note") or "")),
                )
            )
        lines.append("")

    lines.extend(
        [
            "## Interpretation limits",
            "",
            "- SciEntsBank, BEETLE, and RiceChem are single-turn datasets. They do not benchmark follow-up resolution.",
            "- Evidence-citation completeness measures structural traceability to `rubric.*` or `concept.*` IDs; it does not by itself prove that feedback is pedagogically correct.",
            "- Unsupported-feedback rate requires a backing scorer signal or adjudicated source. It is distinct from whether that support is explicitly cited; human review remains necessary for substantive support quality.",
            "- The interViv row is produced by a research adapter around the current scorer/guard output. Production application logic is unchanged.",
            "- The semantic baseline uses a pinned local embedding checkpoint and an inspectable negation/antonym heuristic; it is not a trained NLI classifier.",
            "",
        ]
    )
    return "\n".join(lines)


def _compact_json(value: Any) -> str:
    return "`" + json.dumps(value, sort_keys=True, separators=(",", ":")) + "`"


def _escape_cell(value: str) -> str:
    return value.replace("|", "\\|").replace("\n", " ")
