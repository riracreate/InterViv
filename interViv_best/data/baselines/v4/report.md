# Scorer v4 baseline report

Flag: `SCORER_VERSION=v4` (default remains v3). Split: `data/mohler_question_split_v1.json`
(53 tune / 28 held-out questions, seed 20261116, committed before training).

## Held-out (789 answers, 28 questions, evaluated once)
- blended cosine r=0.618 [0.545, 0.680]; v4 without model r=0.606 [0.522, 0.679];
  v4 with model r=0.662 [0.581, 0.721]; model alone r=0.667 [0.588, 0.734].
  Question-cluster bootstrap 95% CIs (B=2000). Model kept: beats blended cosine
  on point estimate; CIs overlap, so treat the gain as suggestive, not proven.
- Sensitivity without E11-E12 (527 answers): blended 0.608, v4 with 0.648, v4 without 0.592.

## Guards (Mohler tune, design data)
- False positives on grade >= 4.5: v3 21.6% -> v4 10.2%.
- Catch on grade <= 1.0: v3 84.2% -> v4 78.9% (only 19 such tune answers).
- n=50 Poor catch: v3 0.80, v4 0.75 (n=20). Local-DB gibberish rounds: 18 rows, v4 catch 1.00.

## Status: not accepted for enabling

v4 stays behind `SCORER_VERSION=v4` and cannot become the default until a
fresh human set exists. From the diagnostics step onward, n=50 is a
development set, not an external test: it is used for diagnosis, so its
numbers no longer count as held-out evidence.

## External scale check (n=50; development set from now on)
- v4 vs 23-rater mean r=0.318 (Spearman 0.387). Weak: Mohler calibration plus
  removal of length signals does not transfer to the length-confounded n=50 set,
  where v3's r=0.94 is largely word count (r=0.90 alone). Do not enable v4 by
  default on this evidence.

## Known limits
- Calibration (isotonic, Mohler tune) saturates the top: v3 "partial" fixture
  item scores 88.9 under v4. Mohler grades skew high (mean 4.18/5).
- Training/serving share modules/scoring_features.py. No word-count,
  length-ratio, clarity, or pinned keyword feature is used.
