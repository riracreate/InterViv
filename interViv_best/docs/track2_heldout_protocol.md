# Track 2 — Held-out length-ratio protocol (pre-registered)

**Status:** gates registered **before** any held-out computation in this track.
**Do not edit gate thresholds after reading held-out outcomes.**

## Phase 0 (unify-shell)

Copied onto this branch so the collection/import workflow is locatable from
the implementation tree. **Ratings are still outstanding.** Neither
`data/baseline_v2_heldout_ratings.xlsx` nor `.csv` is present. The evaluator
must report `HELD_OUT_ABSENT` and **must not invent ratings**.

`LENGTH_RATIO_MULTIPLIER_ENABLED` stays **off**. Do not enable it from this
pointer. Run:

```
.venv/bin/python scripts/evaluate_length_ratio_heldout.py
```

Keep collection items out of the future starter bank and tuning data.

## Current exploratory formula (contaminated)

Documented in `docs/human_baseline_report.md` (“A quantified remedy”). The
same-sample n=50 figures there are historical report claims until reproduced
on this branch (the form-response workbook is not in this checkout).

```
length_ratio = word_count(candidate) / word_count(reference)
multiplier   = clip(length_ratio / 0.45, 0.3, 1.0)
scaled_score = final_score * multiplier
```

- **Length unit:** whitespace word tokens (`str.split`), not characters.
- **Reference:** the ideal / reference answer shown to raters
  (`baseline_v2_blank.xlsx` reference column).
- **Where tuned:** on the **same n=50** form items used for the headline
  validity study. That is **training contamination**. Same-sample lift
  (r 0.730 → 0.788; Poor gap −35.1 → −22.4) is **not** evidence for
  production enablement.

Production currently does **not** apply this multiplier. The pipeline’s
existing `length_ratio` feature is a separate classifier input
(`min(answer_words / ideal_words, 3.0)`), not this completeness scale.

## Feature flag

| Name | Default | Meaning |
|------|---------|---------|
| `LENGTH_RATIO_MULTIPLIER_ENABLED` | **false** | When true, multiply pipeline `final_score` by the multiplier above (after guard cap). |

Flag must stay OFF in `.env.example` until held-out gates pass.

## Held-out data contract

Expected file (either path):

- `data/baseline_v2_heldout_ratings.xlsx`, or
- `data/baseline_v2_heldout_ratings.csv`

Required columns:

| Column | Meaning |
|--------|---------|
| `item_id` | Stable id (e.g. `row_id` from `baseline_v2_key.csv`) |
| `question` | Question text |
| `candidate_answer` | Answer scored |
| `reference_answer` | Ideal / reference text for length ratio |
| `label` | Dataset band label: `Poor` / `Average` / `Good` |
| `human_mean` | Mean of independent rater scores (0–100) |
| `system_score_current` | Optional; if absent, scorer recomputes |

**Disallowed sources for this track’s gate decision:**

- The n=50 form responses workbook (tuning set).
- Dataset `label` alone without `human_mean` (no rater agreement metrics).

If no file matching the contract exists, the evaluator must report
`HELD_OUT_ABSENT` and **must not invent ratings**.

## Pre-registered gates

Compare **current pipeline** (flag OFF) vs **length-ratio scaling** (same
scores × multiplier, or flag ON) on the held-out set:

| # | Gate | Pass condition |
|---|------|----------------|
| G1 | Poor-label completeness gap | Gap (`human_mean − system_mean` on Poor rows) improves by **≥ 10 points** (e.g. −35 → −25 or better) |
| G2 | Pearson r vs raters | `r_scaled − r_current` **≥ −0.02** (may not drop by more than 0.02) |
| G3 | Band κ vs human-mean bands | `κ_scaled − κ_current` **≥ −0.02** |
| G4 | False-Poor on Good | Among items with dataset label `Good`, count of system band Poor must **not increase** under scaling |

Band boundaries (unchanged): `< 31` Poor, `31–60` Average, `> 60` Good.

**All four gates must pass** to recommend enabling the flag. Any failure →
flag stays OFF; record fail in `TRACK2_RESULT.md`.

## Truncation guard (separate from multiplier)

`modules/answer_guard.py` may flag **truncated on-topic fragments**
(correct topical start, cut off mid-thought). Guards only **cap** scores;
they do not replace the scorer and do not enable the length-ratio flag.

## Evaluation command

```bash
python scripts/evaluate_length_ratio_heldout.py
```

Exit codes: `0` = gates evaluated and all passed, or held-out absent
(reported as skipped); `1` = held-out present but a gate failed; `2` =
input/contract error.

## Contamination reminder

Do not re-tune `0.45`, `0.3`, or `1.0` on the n=50 study set in this track.
Any retune requires a new protocol revision and a fresh held-out slice.
