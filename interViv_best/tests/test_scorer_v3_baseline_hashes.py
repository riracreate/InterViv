"""Fast check that frozen v3 asset hashes match the working tree.

v3 = v2 + a letter-pair nonsense check built from the question bank's own text,
an exemption for words the question's reference material uses, and a rule that
caps fragments under eight words and under half the reference answer's length.
Only keyword_stuffing changes among the v2 items; two items are added.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SUMS_PATH = ROOT / "data" / "baselines" / "v3" / "SHA256SUMS.json"
FIXTURE_PATH = ROOT / "tests" / "fixtures" / "scorer_v3_baseline.json"
V2_FIXTURE_PATH = ROOT / "tests" / "fixtures" / "scorer_v2_baseline.json"


def test_v3_baseline_artifacts_exist() -> None:
    assert SUMS_PATH.is_file()
    assert FIXTURE_PATH.is_file()
    fixture = json.loads(FIXTURE_PATH.read_text())
    assert fixture["scorer_version"] == "v3"
    assert fixture["append_protected"] is True
    assert fixture["length_ratio_multiplier_enabled"] is False
    assert len(fixture["items"]) == 11


def test_v3_sha256sums_match_working_tree() -> None:
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


def test_v3_changes_only_the_intended_v2_results() -> None:
    v2 = {item["id"]: item["result"] for item in json.loads(V2_FIXTURE_PATH.read_text())["items"]}
    v3 = {item["id"]: item["result"] for item in json.loads(FIXTURE_PATH.read_text())["items"]}
    assert set(v3) - set(v2) == {"real_terms_not_gibberish", "short_fragment"}
    for item_id, result in v2.items():
        if item_id == "keyword_stuffing":
            continue
        assert v3[item_id] == result, item_id
    # v2 labelled the stuffed keyword list gibberish because "polymorphism" and
    # "abstraction" failed the old letter-pair check.
    assert v2["keyword_stuffing"]["guard_applied"] == "gibberish"
    assert v3["keyword_stuffing"]["guard_applied"] == "keyword_stuffing"
    assert v3["keyword_stuffing"]["final_score"] <= 35.0
    assert v3["real_terms_not_gibberish"]["guard_applied"] is None
    assert v3["short_fragment"]["guard_applied"] == "too_short"
    assert v3["short_fragment"]["final_score"] <= 20.0
