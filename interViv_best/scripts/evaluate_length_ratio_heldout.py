"""
evaluate_length_ratio_heldout.py — Held-out gate check for the completeness multiplier.

Reads data/baseline_v2_heldout_ratings.{xlsx,csv} per docs/track2_heldout_protocol.md.
Does not invent labels. Does not rewrite system-score CSVs.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats
from sklearn.metrics import cohen_kappa_score

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from modules.length_ratio_completeness import (  # noqa: E402
    apply_completeness_multiplier,
    completeness_multiplier,
)

HELDOUT_CANDIDATES = (
    ROOT / "data" / "baseline_v2_heldout_ratings.xlsx",
    ROOT / "data" / "baseline_v2_heldout_ratings.csv",
)

REQUIRED_COLUMNS = {
    "item_id",
    "question",
    "candidate_answer",
    "reference_answer",
    "label",
    "human_mean",
}


def band(score: float) -> int:
    if score < 31:
        return 0
    if score <= 60:
        return 1
    return 2


def resolve_heldout_path() -> Path | None:
    for path in HELDOUT_CANDIDATES:
        if path.is_file():
            return path
    return None


def load_heldout(path: Path) -> pd.DataFrame:
    if path.suffix.lower() in {".xlsx", ".xls"}:
        df = pd.read_excel(path)
    else:
        df = pd.read_csv(path)
    missing = REQUIRED_COLUMNS - set(df.columns)
    if missing:
        raise ValueError(f"Held-out file missing columns: {sorted(missing)}")
    return df


def ensure_system_scores(df: pd.DataFrame) -> pd.DataFrame:
    if "system_score_current" in df.columns and df["system_score_current"].notna().all():
        out = df.copy()
        out["system_score_current"] = out["system_score_current"].astype(float)
        return out

    from backend.scoring.pipeline import run_scoring_pipeline

    scores = []
    for _, row in df.iterrows():
        result = run_scoring_pipeline(
            answer_text=str(row["candidate_answer"]),
            question_context={
                "question": str(row["question"]),
                "ideal_answer": str(row["reference_answer"]),
            },
        )
        scores.append(float(result["final_score"]))
    out = df.copy()
    out["system_score_current"] = scores
    return out


def evaluate_gates(df: pd.DataFrame) -> tuple[list[tuple[str, bool, str]], bool]:
    human = df["human_mean"].to_numpy(dtype=float)
    current = df["system_score_current"].to_numpy(dtype=float)
    scaled = np.array(
        [
            apply_completeness_multiplier(
                float(s),
                str(cand),
                str(ref),
            )[0]
            for s, cand, ref in zip(
                current,
                df["candidate_answer"],
                df["reference_answer"],
            )
        ],
        dtype=float,
    )

    poor = df["label"].astype(str).str.strip().str.lower() == "poor"
    good = df["label"].astype(str).str.strip().str.lower() == "good"

    gap_current = float(human[poor].mean() - current[poor].mean()) if poor.any() else float("nan")
    gap_scaled = float(human[poor].mean() - scaled[poor].mean()) if poor.any() else float("nan")
    gap_improve = gap_scaled - gap_current  # less negative / more positive is improvement

    r_current, _ = stats.pearsonr(current, human)
    r_scaled, _ = stats.pearsonr(scaled, human)

    human_band = np.array([band(x) for x in human])
    k_current = float(cohen_kappa_score(human_band, [band(x) for x in current]))
    k_scaled = float(cohen_kappa_score(human_band, [band(x) for x in scaled]))

    false_poor_current = int(((np.array([band(x) for x in current]) == 0) & good.to_numpy()).sum())
    false_poor_scaled = int(((np.array([band(x) for x in scaled]) == 0) & good.to_numpy()).sum())

    gates = [
        (
            "G1_poor_gap_improve_ge_10",
            bool(gap_improve >= 10.0 - 1e-9),
            f"gap_current={gap_current:.3f} gap_scaled={gap_scaled:.3f} improve={gap_improve:.3f}",
        ),
        (
            "G2_pearson_drop_le_0.02",
            bool((r_scaled - r_current) >= -0.02 - 1e-12),
            f"r_current={r_current:.4f} r_scaled={r_scaled:.4f} delta={r_scaled - r_current:.4f}",
        ),
        (
            "G3_band_kappa_drop_le_0.02",
            bool((k_scaled - k_current) >= -0.02 - 1e-12),
            f"k_current={k_current:.4f} k_scaled={k_scaled:.4f} delta={k_scaled - k_current:.4f}",
        ),
        (
            "G4_false_poor_on_good_not_increased",
            false_poor_scaled <= false_poor_current,
            f"false_poor_current={false_poor_current} false_poor_scaled={false_poor_scaled}",
        ),
    ]
    return gates, all(ok for _, ok, _ in gates)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--path", type=Path, default=None)
    args = parser.parse_args(argv)

    path = args.path or resolve_heldout_path()
    if path is None:
        print("HELD_OUT_ABSENT")
        print(
            "No data/baseline_v2_heldout_ratings.xlsx|csv found. "
            "Gates not evaluated. See docs/track2_heldout_protocol.md."
        )
        return 0

    try:
        df = load_heldout(path)
        df = ensure_system_scores(df)
        gates, all_pass = evaluate_gates(df)
    except Exception as exc:  # noqa: BLE001
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    print(f"heldout_path={path}")
    print(f"n_items={len(df)}")
    for name, ok, detail in gates:
        print(f"{name}: {'PASS' if ok else 'FAIL'} — {detail}")
    # Sanity: multiplier helper is importable (used by gate path).
    _ = completeness_multiplier("short answer here", "a much longer reference answer with many words")
    if all_pass:
        print("ALL_GATES_PASS")
        return 0
    print("GATES_FAILED — leave LENGTH_RATIO_MULTIPLIER_ENABLED off")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
