# Scorer versions

This file records identifiable scoring implementations. A version change is
required for algorithm, threshold, model, matching, guard, or configuration
changes. Input-bundle changes get a separate bundle version even when the
algorithm is unchanged.

`v1` is the original unify-shell baseline captured in Phase 0. It is not an
alias for whatever the current tree happens to contain. Replay uses the frozen
fixture and asset hashes. Later versions get their own fixtures and reports.
Do not overwrite `tests/fixtures/scorer_v1_baseline.json` to absorb a new
result.

| Version | Source commit | Status | Notes |
| --- | --- | --- | --- |
| v1 | `6659feda31b2f27d687f609d59e397911285a6ff` (`codex/unify-shell`) | frozen original baseline | Production path at capture. `LENGTH_RATIO_MULTIPLIER_ENABLED` off. Semantic runtime **full** (`sentence-transformers/all-MiniLM-L6-v2` revision `1110a243fdf4706b3f48f1d95db1a4f5529b4d41`). Classifier `modules/answer_quality_lr.joblib` sha256 `2897c8cc6283cbdb4815a78182188ea60c17b39876feefa2d67919f065f16dd7` (matches `modules/model_metadata.json`). |

## How to replay v1

From `interViv_best/`:

```
.venv/bin/python scripts/replay_scorer_v1_baseline.py
```

The replay hashes the listed source assets against `data/baselines/v1/SHA256SUMS.json`
and re-scores the pinned answers in `tests/fixtures/scorer_v1_baseline.json`.
It fails if hashes or per-item `final_score` / `guard_applied` / `nlp_score` /
`kg_score` differ. Missing MiniLM weights cannot claim v1; they are a different
runtime.

## What v1 is not

- Not permission to change the production scorer.
- Not a reproduction of the historical n=50 form study (r = 0.730 in later
  Tree 2 / protocol text). That study needs the form-response workbook, which
  is not on this branch.
- Not a rewrite of `docs/human_baseline_report.md`. That file on this commit
  is the 230-line report (n=30 r = 0.7392 plus appended n=50 r = 0.730) and
  stays unchanged. Pytest currently regenerates the n=30-only body; restore
  it from git after the suite (`git restore -- docs/human_baseline_report.md`).
