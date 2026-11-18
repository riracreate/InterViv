# Scorer `v4` Diagnostics Errata (`2bcd3d7`)

- **Citable source**: Use **`data/baselines/v4_diagnostics/summary.json`** — **not** `data/baselines/v4/report.md` — when citing metrics for locked commit `2bcd3d7` (`scorer_version = "v4"`, verified against `data/baselines/v4/SHA256SUMS.json`). `data/baselines/v4/` is frozen and left unedited.

## Discrepancies vs `data/baselines/v4/report.md` (E1)

- **`n=50` Poor catch (`v4`, `n=20`) — differs**:
  - Committed `v4` guard (`2bcd3d7`): **`14/20` (`0.70`)** (`data/baselines/v4_diagnostics/summary.json`, `B.n50_poor`).
  - `data/baselines/v4/report.md` (`L16`) and `artifacts/scorer_v4_validation.json`: **`0.75` (`15/20`)** — stale relative to `2bcd3d7`.
- **Other figures in `data/baselines/v4/report.md`**: No other figure in `report.md` differs from `summary.json` or the `T3` Mohler tune measurement. Held-out Pearson point estimates (`0.618 / 0.606 / 0.662`), sensitivity without `E11–E12` (`0.608 / 0.648 / 0.592`), Mohler tune `v4` rates (`10.2%` FP / `78.9%` catch), and `n=50` `v4` vs 23-rater mean correlations (`r=0.318`, `Spearman=0.387`) match; single-series bootstrap CIs, `model_pred_alone`, `v3` Mohler tune and `n=50` Poor catch, local-DB gibberish (`18` rows), `v3` partial fixture (`88.9`), and full-dataset Mohler mean (`4.18/5`) were not re-measured in `summary.json` or `T3`.

## Guard Provenance (`00:40:32` vs `2bcd3d7` at `00:56:09`)

- `artifacts/scorer_v4_validation.json` was written at **`2026-11-16 00:40:32 +0530`**, `15m 37s` before commit `2bcd3d7` (**`2026-11-16 00:56:09 +0530`**).
- `modules/answer_guard_v4.py` changed in the working tree between the `00:40:32` validation run (`15/20` `n=50` Poor catch) and commit `2bcd3d7` (`14/20` `n=50` Poor catch). Because `answer_guard_v4.py` was uncommitted at `00:40:32`, the earlier version is not in git.

## Guard False Positives Comparison (`2bcd3d7` vs Parked `09:53` Patch)

| Split | Guard Variant | False Positives / Rate | Breakdown |
| :--- | :--- | :--- | :--- |
| **Mohler held-out** (`grade >= 4.5`, `n=482`) | Committed `2bcd3d7` (with `content_recall < 0.50` exemption) | **`10/482` (`2.07%`)** | `too_short: 8`, `off_topic: 1`, `repetition: 1` |
| **Mohler held-out** (`grade >= 4.5`, `n=482`) | Without `content_recall < 0.50` exemption (`09:53` run of parked patch `docs/parked/guard_short_cap_v4_1.patch`, archived in `artifacts/scorer_v4_diagnostics_edited_guard_0953.json`) | **`12/482` (`2.49%`)** | `too_short: 10`, `off_topic: 1`, `repetition: 1` |
| **Mohler tune** (`grade >= 4.5`, `n=945`) | Both variants (committed `2bcd3d7` and parked patch) | **`96/945` (`10.16%`)** | `too_short: 82`, `truncated_fragment: 7`, `repetition: 2`, `question_parroting: 2`, `off_topic: 2`, `gibberish: 1` |
