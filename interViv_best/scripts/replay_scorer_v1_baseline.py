"""Replay frozen scorer v1 items. Never writes the fixture."""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.runtime_env import apply_runtime_env

apply_runtime_env()

from backend.scoring.pipeline import run_scoring_pipeline  # noqa: E402

SUMS_PATH = PROJECT_ROOT / "data" / "baselines" / "v1" / "SHA256SUMS.json"
FIXTURE_PATH = PROJECT_ROOT / "tests" / "fixtures" / "scorer_v1_baseline.json"
TOL = 1e-9


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _check_hashes(manifest: dict) -> list[str]:
    failures = []
    for rel, meta in manifest["files"].items():
        path = PROJECT_ROOT / rel
        if not path.is_file():
            failures.append(f"missing {rel}")
            continue
        digest = _sha256(path)
        if digest != meta["sha256"]:
            failures.append(f"hash mismatch {rel}: got {digest}, expected {meta['sha256']}")
        if path.stat().st_size != meta["bytes"]:
            failures.append(f"size mismatch {rel}")
    return failures


def _score_item(item: dict) -> dict:
    pipeline_out = run_scoring_pipeline(
        answer_text=item["answer"],
        word_count=item["word_count"],
        engagement_label=item["engagement_label"],
        wpm=item["wpm"],
        pause_count=item["pause_count"],
        question_context={
            "question": item["question"],
            "ideal_answer": item["ideal_answer"],
            "ideal_keywords": item["ideal_keywords"],
            "keywords": item["keywords"],
            "skill": item["skill"],
        },
        difficulty=item["difficulty"],
        candidate_baseline=item["candidate_baseline"],
    )
    return {
        "final_score": round(float(pipeline_out.get("final_score", 0.0)), 2),
        "guard_applied": pipeline_out.get("guard_applied"),
        "nlp_score": round(float(pipeline_out.get("nlp_score", 0.0)), 2),
        "kg_score": round(float(pipeline_out.get("kg_score", 0.0)), 2),
    }


def main() -> int:
    if not SUMS_PATH.is_file() or not FIXTURE_PATH.is_file():
        print("v1 baseline artifacts missing", file=sys.stderr)
        return 2
    manifest = json.loads(SUMS_PATH.read_text())
    fixture = json.loads(FIXTURE_PATH.read_text())
    if not fixture.get("append_protected"):
        print("fixture is not marked append-protected", file=sys.stderr)
        return 2

    failures = _check_hashes(manifest)
    print(f"asset hashes: {len(manifest['files'])} files, {len(failures)} mismatch(es)")

    from modules.length_ratio_completeness import length_ratio_multiplier_enabled
    from modules.semantic_scorer import SemanticScorer, fallback_reason

    if length_ratio_multiplier_enabled():
        failures.append("LENGTH_RATIO_MULTIPLIER_ENABLED is on; v1 capture was off")
    probe = SemanticScorer().score("Encapsulation hides state.", "Encapsulation hides state.")
    expected_mode = fixture.get("semantic_runtime_mode")
    actual_mode = "full" if probe is not None else "lexical_fallback_degraded"
    if actual_mode != expected_mode:
        failures.append(
            f"semantic mode {actual_mode!r} != frozen {expected_mode!r} "
            f"(fallback={fallback_reason()!r})"
        )

    for item in fixture["items"]:
        got = _score_item(item)
        exp = item["result"]
        for key in ("final_score", "nlp_score", "kg_score"):
            if abs(float(got[key]) - float(exp[key])) > TOL:
                failures.append(f"{item['id']} {key}: got {got[key]}, frozen {exp[key]}")
        if got["guard_applied"] != exp["guard_applied"]:
            failures.append(
                f"{item['id']} guard_applied: got {got['guard_applied']!r}, "
                f"frozen {exp['guard_applied']!r}"
            )
        status = "OK" if not any(item["id"] in f for f in failures[-4:]) else "DIFF"
        print(
            f"{item['id']:22s}  final={got['final_score']:>6}  "
            f"guard={got['guard_applied'] or '-'}  {status}"
        )

    if failures:
        print(f"\n{len(failures)} replay failure(s):")
        for line in failures:
            print(f"  - {line}")
        return 1
    print(f"\nReplay matched {len(fixture['items'])} frozen items and asset hashes.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
