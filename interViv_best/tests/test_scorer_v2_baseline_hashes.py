"""Fast check that the frozen v2 baseline record is intact (the tree is v3 now).

v2 = v1 + the entity_swap guard. The eight v1 items scored identically under
v2; only the entity_swap item was added.
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SUMS_PATH = ROOT / "data" / "baselines" / "v2" / "SHA256SUMS.json"
FIXTURE_PATH = ROOT / "tests" / "fixtures" / "scorer_v2_baseline.json"
V1_FIXTURE_PATH = ROOT / "tests" / "fixtures" / "scorer_v1_baseline.json"


def test_v2_baseline_artifacts_exist() -> None:
    assert SUMS_PATH.is_file()
    assert FIXTURE_PATH.is_file()
    fixture = json.loads(FIXTURE_PATH.read_text())
    assert fixture["scorer_version"] == "v2"
    assert fixture["append_protected"] is True
    assert fixture["length_ratio_multiplier_enabled"] is False
    assert len(fixture["items"]) == 9


def test_v2_manifest_is_frozen_record() -> None:
    # The working tree is scorer v3 now (see docs/scorer_versions.md and
    # tests/test_scorer_v3_baseline_hashes.py). v2 stays as the historical
    # record of commit 071284b; it is replayable only from that commit.
    manifest = json.loads(SUMS_PATH.read_text())
    assert manifest["algorithm"] == "sha256"
    assert "af82b24adb2355628eaf42e20fc9a43491e45c81" in manifest["source_commit"]
    assert all(len(meta["sha256"]) == 64 for meta in manifest["files"].values())


def test_v2_keeps_every_v1_result() -> None:
    v1 = {item["id"]: item["result"] for item in json.loads(V1_FIXTURE_PATH.read_text())["items"]}
    v2 = {item["id"]: item["result"] for item in json.loads(FIXTURE_PATH.read_text())["items"]}
    assert set(v2) - set(v1) == {"entity_swap"}
    for item_id, result in v1.items():
        assert v2[item_id] == result, item_id
    assert v2["entity_swap"]["guard_applied"] == "entity_swap"
    assert v2["entity_swap"]["final_score"] <= 35.0
