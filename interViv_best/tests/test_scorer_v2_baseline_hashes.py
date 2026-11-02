"""Fast check that frozen v2 asset hashes match the working tree.

v2 = v1 + the entity_swap guard. The eight v1 items must score identically
under v2; only the new entity_swap item is added.
"""
from __future__ import annotations

import hashlib
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


def test_v2_sha256sums_match_working_tree() -> None:
    manifest = json.loads(SUMS_PATH.read_text())
    assert manifest["algorithm"] == "sha256"
    mismatches = []
    for rel, meta in manifest["files"].items():
        path = ROOT / rel
        if not path.is_file():
            mismatches.append(f"missing {rel}")
            continue
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        if digest != meta["sha256"]:
            mismatches.append(f"{rel}: {digest} != {meta['sha256']}")
    assert mismatches == []


def test_v2_keeps_every_v1_result() -> None:
    v1 = {item["id"]: item["result"] for item in json.loads(V1_FIXTURE_PATH.read_text())["items"]}
    v2 = {item["id"]: item["result"] for item in json.loads(FIXTURE_PATH.read_text())["items"]}
    assert set(v2) - set(v1) == {"entity_swap"}
    for item_id, result in v1.items():
        assert v2[item_id] == result, item_id
    assert v2["entity_swap"]["guard_applied"] == "entity_swap"
    assert v2["entity_swap"]["final_score"] <= 35.0
