from __future__ import annotations

import csv
import json
import socket
from pathlib import Path

from research.grader_lab.manifest import RunManifest
from research.grader_lab.report import deferred_rows, metric_rows, write_reports
from research.grader_lab.metrics import MetricResult
from research.grader_lab.datasets import DatasetLoadResult
from research.grader_lab.structured_judge import StructuredJudgeBaseline

LAB_ROOT = Path(__file__).resolve().parents[1]


def _manifest() -> RunManifest:
    return RunManifest(
        run_id="grader-lab-test",
        generated_at_utc="2026-08-15T00:00:00+00:00",
        git_commit="a" * 40,
        git_dirty=False,
        dataset_versions={
            "internal_perturbation": {
                "version": "grader-lab-perturbations-v1",
                "status": "loaded",
                "examples": "1",
                "sha256": "sha256:test",
            }
        },
        model_versions={
            "structured_llm_rubric_judge": {
                "structured_judge": "unscoped",
                "execution": "deferred_zero_api_calls",
            }
        },
        runtime_versions={"python": "test"},
    )


def test_deferred_structured_judge_reported_without_network(monkeypatch, tmp_path):
    network_attempts = 0

    def fail_connect(*_args, **_kwargs):
        nonlocal network_attempts
        network_attempts += 1
        raise AssertionError("network call attempted")

    monkeypatch.setattr(socket.socket, "connect", fail_connect)
    judge = StructuredJudgeBaseline()
    rows = deferred_rows(judge)
    csv_path, markdown_path = write_reports(
        results_dir=tmp_path,
        manifest=_manifest(),
        rows=rows,
    )
    assert judge.api_call_count == 0
    assert network_attempts == 0
    assert rows[0]["baseline_status"] == "deferred"
    assert "deferred" in csv_path.read_text(encoding="utf-8")
    markdown = markdown_path.read_text(encoding="utf-8")
    assert "Comparison status: INCOMPLETE" in markdown
    assert "zero API/network calls" in markdown


def test_structured_judge_config_is_hard_deferred():
    config = json.loads(
        (LAB_ROOT / "structured_judge_config.example.json").read_text(
            encoding="utf-8"
        )
    )
    assert config["status"] == "deferred"
    assert config["enabled"] is False
    assert config["api_calls_allowed"] == 0
    assert config["provider"] is None
    assert config["model"] is None


def test_claims_ledger_has_required_columns_and_claims():
    ledger = (LAB_ROOT / "CLAIMS_LEDGER.md").read_text(encoding="utf-8")
    header = next(line for line in ledger.splitlines() if line.startswith("| Claim |"))
    for column in (
        "Claim",
        "Supporting metric",
        "Evidence source",
        "Status",
        "Notes / risks",
    ):
        assert column in header
    assert ledger.count("| interViv") >= 4
    assert "interViv's semantic scoring path executes as intended in production" in ledger
    for required_status in ("untested", "synthetic_only", "needs_human_study"):
        assert required_status in ledger


def test_every_generated_report_has_complete_run_manifest(tmp_path):
    rows = deferred_rows(StructuredJudgeBaseline())
    csv_path, markdown_path = write_reports(
        results_dir=tmp_path,
        manifest=_manifest(),
        rows=rows,
    )
    with csv_path.open(encoding="utf-8", newline="") as handle:
        csv_rows = list(csv.DictReader(handle))
    assert csv_rows
    for row in csv_rows:
        assert row["git_commit"] == "a" * 40
        assert "grader-lab-perturbations-v1" in row["dataset_versions"]
        assert "deferred_zero_api_calls" in row["model_versions"]

    markdown = markdown_path.read_text(encoding="utf-8")
    assert "Git commit hash" in markdown
    assert "Dataset versions" in markdown
    assert "Baseline model/checkpoint versions" in markdown
    assert "a" * 40 in markdown


def test_macro_f1_report_fraction_is_dash(tmp_path):
    dataset = DatasetLoadResult(
        name="internal_perturbation",
        status="loaded",
        version="grader-lab-perturbations-v1",
        path=Path("internal.jsonl"),
    )
    rows = metric_rows(
        dataset=dataset,
        baseline_name="test",
        metrics=[MetricResult("macro_f1", 0.5, None, None)],
    )
    _, markdown_path = write_reports(
        results_dir=tmp_path, manifest=_manifest(), rows=rows
    )
    macro_line = next(
        line for line in markdown_path.read_text(encoding="utf-8").splitlines()
        if "macro_f1" in line
    )
    assert "| — |" in macro_line
    assert "/1000000" not in macro_line
