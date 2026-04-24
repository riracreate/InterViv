"""
baseline_analysis.py — Analyse human baseline annotation sheet.

Reads data/human_baseline_sheet.csv (after annotators fill annotator_1..4).
Produces docs/human_baseline_report.md with:
  - Inter-rater agreement (Cohen's Kappa for each pair + average)
  - System vs human correlation (Pearson r + p-value)
  - Confusion matrix (Good/Average/Poor bands)
  - Top-5 cases of system-human disagreement

Usage:  python scripts/baseline_analysis.py [--sheet path/to/sheet.csv]
"""

from __future__ import annotations

import argparse
import math
import pathlib
import sys
from itertools import combinations
from typing import Optional

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import pandas as pd
import numpy as np
from scipy.stats import pearsonr
from sklearn.metrics import cohen_kappa_score

DATA_PATH   = ROOT / "data"  / "human_baseline_sheet.csv"
REPORT_PATH = ROOT / "docs"  / "human_baseline_report.md"

ANNOTATOR_COLS = ["annotator_1", "annotator_2", "annotator_3", "annotator_4"]


def score_to_band(score: float) -> str:
    """Bucket a 0–100 score into Good/Average/Poor."""
    if score >= 61:
        return "Good"
    if score >= 31:
        return "Average"
    return "Poor"


def cohen_kappa_bands(a: pd.Series, b: pd.Series) -> float:
    """Compute Cohen's Kappa between two annotator columns (band-level)."""
    valid = a.notna() & b.notna()
    if valid.sum() < 2:
        return float("nan")
    a_bands = a[valid].apply(score_to_band)
    b_bands = b[valid].apply(score_to_band)
    try:
        return cohen_kappa_score(a_bands, b_bands, labels=["Good", "Average", "Poor"])
    except Exception:
        return float("nan")


def confusion_matrix_bands(human_mean: pd.Series, system: pd.Series) -> dict:
    """Confusion matrix between human mean bands and system bands."""
    bands = ["Good", "Average", "Poor"]
    matrix = {actual: {pred: 0 for pred in bands} for actual in bands}
    for h, s in zip(human_mean, system):
        if pd.notna(h) and pd.notna(s):
            matrix[score_to_band(h)][score_to_band(s)] += 1
    return matrix


def top_disagreements(df: pd.DataFrame, human_mean: pd.Series, n: int = 5) -> pd.DataFrame:
    """Return the n rows where |system_score - human_mean| is largest."""
    df = df.copy()
    df["human_mean"] = human_mean
    df["delta"] = (df["system_score"] - df["human_mean"]).abs()
    return (
        df[df["human_mean"].notna()]
        .sort_values("delta", ascending=False)
        .head(n)[["question", "answer", "system_score", "human_mean", "delta"]]
        .reset_index(drop=True)
    )


def main(sheet_path: Optional[pathlib.Path] = None) -> None:
    path = sheet_path or DATA_PATH
    print(f"Reading {path} ...")
    df = pd.read_csv(path)

    # Coerce annotator columns to float
    present_annotators = [c for c in ANNOTATOR_COLS if c in df.columns]
    for col in present_annotators:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    df["system_score"] = pd.to_numeric(df["system_score"], errors="coerce")

    filled_annotators = [c for c in present_annotators if df[c].notna().any()]
    if not filled_annotators:
        print("ERROR: No annotator columns have been filled in yet.")
        print(f"  Fill in {present_annotators} in {path.name}, then re-run.")
        sys.exit(1)

    # Human mean across filled annotators
    human_mean = df[filled_annotators].mean(axis=1)

    # ── Inter-rater agreement ─────────────────────────────────────────────────
    kappa_pairs = {}
    for a, b in combinations(filled_annotators, 2):
        kappa_pairs[f"{a} vs {b}"] = cohen_kappa_bands(df[a], df[b])

    kappa_values = [v for v in kappa_pairs.values() if not math.isnan(v)]
    avg_kappa = float(np.mean(kappa_values)) if kappa_values else float("nan")

    # ── Pearson correlation ───────────────────────────────────────────────────
    valid_mask = df["system_score"].notna() & human_mean.notna()
    n_valid = valid_mask.sum()

    if n_valid >= 2:
        r, p_val = pearsonr(df.loc[valid_mask, "system_score"], human_mean[valid_mask])
    else:
        r, p_val = float("nan"), float("nan")

    # ── Confusion matrix ──────────────────────────────────────────────────────
    cm = confusion_matrix_bands(human_mean, df["system_score"])

    # ── Top-5 disagreements ───────────────────────────────────────────────────
    top5 = top_disagreements(df, human_mean, n=5)

    # ── Build report ──────────────────────────────────────────────────────────
    def kappa_interpret(k: float) -> str:
        if math.isnan(k): return "N/A"
        if k >= 0.80: return "Almost perfect"
        if k >= 0.60: return "Substantial"
        if k >= 0.40: return "Moderate"
        if k >= 0.20: return "Fair"
        return "Slight / poor"

    lines = [
        "# Human Baseline Report — interViv Scoring System",
        "",
        f"**Generated from:** `{path.name}`  ",
        f"**Rows analysed:** {n_valid}  ",
        f"**Annotators with data:** {', '.join(filled_annotators)}",
        "",
        "---",
        "",
        "## 1. Inter-Rater Agreement (Cohen's κ)",
        "",
        "| Pair | κ | Interpretation |",
        "|------|---|----------------|",
    ]
    for pair, k in kappa_pairs.items():
        k_str = f"{k:.3f}" if not math.isnan(k) else "N/A"
        lines.append(f"| {pair} | {k_str} | {kappa_interpret(k)} |")

    avg_kappa_str = f"{avg_kappa:.3f}" if not math.isnan(avg_kappa) else "N/A"
    lines += [
        f"| **Average** | **{avg_kappa_str}** | **{kappa_interpret(avg_kappa)}** |",
        "",
        "> κ interpretation: <0.20 Slight, 0.20–0.40 Fair, 0.40–0.60 Moderate, 0.60–0.80 Substantial, >0.80 Almost perfect",
        "",
        "---",
        "",
        "## 2. System vs Human Correlation (Pearson r)",
        "",
        f"| Metric | Value |",
        f"|--------|-------|",
        f"| Pearson r | {f'{r:.4f}' if not math.isnan(r) else 'N/A'} |",
        f"| p-value   | {f'{p_val:.4f}' if not math.isnan(p_val) else 'N/A'} |",
        f"| n         | {n_valid} |",
        "",
    ]

    if not math.isnan(r):
        sig = "statistically significant (p < 0.05)" if p_val < 0.05 else "not statistically significant (p ≥ 0.05)"
        lines.append(f"> The system-human correlation is **{r:.3f}**, {sig}.")

    lines += [
        "",
        "---",
        "",
        "## 3. Confusion Matrix (Good / Average / Poor bands)",
        "",
        "Rows = Human mean band  ·  Columns = System predicted band",
        "",
        "| Human \\ System | Good | Average | Poor |",
        "|-----------------|------|---------|------|",
    ]
    for actual in ["Good", "Average", "Poor"]:
        row = cm[actual]
        lines.append(f"| **{actual}** | {row['Good']} | {row['Average']} | {row['Poor']} |")

    lines += [
        "",
        "---",
        "",
        "## 4. Top-5 System-Human Disagreements",
        "",
        "| # | Question (truncated) | Answer (truncated) | System | Human | Delta |",
        "|---|----------------------|--------------------|--------|-------|-------|",
    ]
    for i, row in top5.iterrows():
        q   = str(row["question"])[:60].replace("|", "\\|")
        ans = str(row["answer"])[:50].replace("|", "\\|")
        lines.append(
            f"| {i+1} | {q}... | {ans}... | {row['system_score']:.0f} | {row['human_mean']:.0f} | {row['delta']:.0f} |"
        )

    lines += [
        "",
        "---",
        "",
        "## 5. Notes",
        "",
        "- **System score** is the NLP score from the 3-layer hybrid scorer (v11) without KG blending.",
        "- **Annotator scale**: 0–30 = Poor, 31–60 = Average, 61–100 = Good.",
        "- Band boundaries: score < 31 → Poor, 31–60 → Average, > 60 → Good.",
    ]

    report = "\n".join(lines)
    REPORT_PATH.write_text(report, encoding="utf-8")
    print(f"\nReport written to {REPORT_PATH}")
    print(f"\nKey results:")
    print(f"  Average κ: {avg_kappa_str} ({kappa_interpret(avg_kappa)})")
    r_str = f"{r:.4f}" if not math.isnan(r) else "N/A"
    p_str = f"{p_val:.4f}" if not math.isnan(p_val) else "N/A"
    print(f"  Pearson r: {r_str}  (p={p_str})")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--sheet", type=pathlib.Path, default=None)
    args = parser.parse_args()
    main(args.sheet)
