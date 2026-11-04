"""Fast check that the frozen v1 baseline record is intact (the tree is v2 now)."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SUMS_PATH = ROOT / "data" / "baselines" / "v1" / "SHA256SUMS.json"
FIXTURE_PATH = ROOT / "tests" / "fixtures" / "scorer_v1_baseline.json"


def test_v1_baseline_artifacts_exist() -> None:
    assert SUMS_PATH.is_file()
    assert FIXTURE_PATH.is_file()
    fixture = json.loads(FIXTURE_PATH.read_text())
    assert fixture["scorer_version"] == "v1"
    assert fixture["append_protected"] is True
    assert fixture["length_ratio_multiplier_enabled"] is False
    assert len(fixture["items"]) == 8


def test_v1_manifest_is_frozen_record() -> None:
    # The working tree is scorer v2 now (see docs/scorer_versions.md and
    # tests/test_scorer_v2_baseline_hashes.py). v1 stays as the historical
    # record of commit 6659feda; it is replayable only from that commit.
    manifest = json.loads(SUMS_PATH.read_text())
    assert manifest["algorithm"] == "sha256"
    assert manifest["source_commit"] == "6659feda31b2f27d687f609d59e397911285a6ff"
    assert all(len(meta["sha256"]) == 64 for meta in manifest["files"].values())
