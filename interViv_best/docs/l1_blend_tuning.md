# Layer 1 blend tuning — grid search vs human baseline (n=30)

Source: `human_baseline_real_combined.xlsx` — 3 annotators, mean per row.
Layer 1 blend formula: `cos_sim = w * semantic + (1 - w) * tfidf`.

## Grid search (Pearson r vs human mean)

| blend_w (semantic) | 1 - w (TF-IDF) | Pearson r |
|--------------------|----------------|-----------|
| 0.00 | 1.00 | 0.7740 |
| 0.10 | 0.90 | 0.7745  ← max |
| 0.20 | 0.80 | 0.7745 |
| 0.30 | 0.70 | 0.7739 |
| 0.40 | 0.60 | 0.7727 |
| 0.50 | 0.50 | 0.7709 |
| 0.60 | 0.40 | 0.7684 |
| 0.70 | 0.30 | 0.7654 |
| 0.80 | 0.20 | 0.7617 |
| 0.90 | 0.10 | 0.7575 |
| 1.00 | 0.00 | 0.7526 |

## Pure-component baselines (sanity)

- Pure semantic (w=1.00): Pearson r = 0.7526
- Pure TF-IDF   (w=0.00): Pearson r = 0.7740

## Decision

- Optimal `w_semantic` = **0.10** (Pearson r = 0.7745)
- Current  `w_semantic` = 0.60 (Pearson r = 0.7684)
- Δ = +0.0061
- Action: keep the existing 60/40 blend — the gain from tuning is below the 0.05 threshold.
