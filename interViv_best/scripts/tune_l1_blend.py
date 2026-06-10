"""
tune_l1_blend.py — Grid-search the Layer-1 semantic/TF-IDF blend weight
against the n=30 human-baseline study.

Layer 1's cosine component currently blends:
    cos_sim = blend_w * semantic + (1 - blend_w) * tfidf
with blend_w hard-coded to 0.60 in modules/nlp_scorer.py.

This script grids blend_w over {0.0, 0.1, …, 1.0}, computes the Pearson
correlation between the resulting proxy and the per-row mean of three
human annotators, and reports the optimum.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import pearsonr

PROJECT_ROOT = Path(__file__).resolve().parent.parent
for cand in (PROJECT_ROOT / "modules", PROJECT_ROOT):
    s = str(cand)
    if cand.exists() and s not in sys.path:
        sys.path.insert(0, s)

from modules.nlp_scorer import _l1_tfidf_cosine, _tokenize  # noqa: E402
from modules.semantic_scorer import SemanticScorer  # noqa: E402


def _row_features(scorer: SemanticScorer, ideal: str, candidate: str) -> tuple[float, float]:
    sem = scorer.score(candidate, ideal)
    if sem is None:
        sem = 0.0
    ans_tokens = _tokenize(candidate)
    ideal_tokens = _tokenize(ideal)
    tfidf = _l1_tfidf_cosine(ans_tokens, ideal_tokens)
    return float(sem), float(tfidf)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--data",
        default=str(PROJECT_ROOT / "data" / "human_baseline_real_combined.xlsx"),
    )
    parser.add_argument(
        "--out",
        default=str(PROJECT_ROOT / "docs" / "l1_blend_tuning.md"),
    )
    args = parser.parse_args()

    df = pd.read_excel(args.data)
    required = {"ideal_answer", "candidate_answer", "annotator_1", "annotator_2", "annotator_3"}
    missing = required - set(df.columns)
    if missing:
        raise SystemExit(f"Missing columns in {args.data}: {missing}")

    print(f"Loaded {len(df)} rows from {args.data}")

    scorer = SemanticScorer()
    semantic, tfidf, human = [], [], []
    for _, row in df.iterrows():
        ideal = str(row["ideal_answer"]).strip()
        candidate = str(row["candidate_answer"]).strip()
        if not ideal or not candidate:
            continue
        s, t = _row_features(scorer, ideal, candidate)
        semantic.append(s)
        tfidf.append(t)
        human.append(np.mean([row["annotator_1"], row["annotator_2"], row["annotator_3"]]))

    semantic_a = np.asarray(semantic, dtype=float)
    tfidf_a = np.asarray(tfidf, dtype=float)
    human_a = np.asarray(human, dtype=float)
    print(f"Computed features for {len(human_a)} rows.")

    # Sanity probes: pure-semantic (1.0) and pure-tfidf (0.0) baselines.
    pure_sem_r, _ = pearsonr(semantic_a, human_a)
    pure_tfidf_r, _ = pearsonr(tfidf_a, human_a)
    print(f"  pure semantic Pearson r = {pure_sem_r:.4f}")
    print(f"  pure TF-IDF   Pearson r = {pure_tfidf_r:.4f}")
    print()

    weights = [round(w, 1) for w in np.arange(0.0, 1.01, 0.1)]
    grid: list[tuple[float, float]] = []
    print(f"{'blend_w (semantic)':>20}  {'(1-w) (tfidf)':>14}  {'Pearson r':>10}")
    for w in weights:
        proxy = w * semantic_a + (1.0 - w) * tfidf_a
        r, _ = pearsonr(proxy, human_a)
        grid.append((w, float(r)))
        print(f"{w:>20.2f}  {1.0 - w:>14.2f}  {r:>10.4f}")

    best_w, best_r = max(grid, key=lambda kv: kv[1])
    current_w = 0.60
    current_r = next(r for w, r in grid if abs(w - current_w) < 1e-6)
    delta = best_r - current_r
    print()
    print(f"Optimal blend_w_semantic = {best_w:.2f} with Pearson r = {best_r:.4f}")
    print(f"Current  blend_w_semantic = {current_w:.2f} with Pearson r = {current_r:.4f}")
    print(f"Delta    = {delta:+.4f}")
    print(
        "Decision: "
        + ("UPDATE nlp_scorer.py" if abs(delta) > 0.05 else "KEEP existing 60/40 (delta <= 0.05)")
    )

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    lines: list[str] = []
    lines.append("# Layer 1 blend tuning — grid search vs human baseline (n=30)")
    lines.append("")
    lines.append(f"Source: `{Path(args.data).name}` — 3 annotators, mean per row.")
    lines.append(f"Layer 1 blend formula: `cos_sim = w * semantic + (1 - w) * tfidf`.")
    lines.append("")
    lines.append("## Grid search (Pearson r vs human mean)")
    lines.append("")
    lines.append("| blend_w (semantic) | 1 - w (TF-IDF) | Pearson r |")
    lines.append("|--------------------|----------------|-----------|")
    for w, r in grid:
        marker = "  ← max" if abs(r - best_r) < 1e-9 else ""
        lines.append(f"| {w:.2f} | {1.0 - w:.2f} | {r:.4f}{marker} |")
    lines.append("")
    lines.append("## Pure-component baselines (sanity)")
    lines.append("")
    lines.append(f"- Pure semantic (w=1.00): Pearson r = {pure_sem_r:.4f}")
    lines.append(f"- Pure TF-IDF   (w=0.00): Pearson r = {pure_tfidf_r:.4f}")
    lines.append("")
    lines.append("## Decision")
    lines.append("")
    lines.append(f"- Optimal `w_semantic` = **{best_w:.2f}** (Pearson r = {best_r:.4f})")
    lines.append(f"- Current  `w_semantic` = 0.60 (Pearson r = {current_r:.4f})")
    lines.append(f"- Δ = {delta:+.4f}")
    if abs(delta) > 0.05:
        lines.append(f"- Action: **update** `modules/nlp_scorer.py` to use `w_semantic = {best_w:.2f}`.")
    else:
        lines.append("- Action: keep the existing 60/40 blend — the gain from tuning is below the 0.05 threshold.")
    out.write_text("\n".join(lines) + "\n")
    print(f"\nWrote {out}")


if __name__ == "__main__":
    main()
