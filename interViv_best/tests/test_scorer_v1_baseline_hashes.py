"""Fast check that frozen v1 asset hashes still match the working tree."""
from __future__ import annotations

import hashlib
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


def test_v1_sha256sums_match_working_tree() -> None:
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
