# Post-Eval Task 1 — Baseline Analysis

## Status

Completed.

## Verification

- `scripts/baseline_analysis.py` defaults to `data/human_baseline_real_combined.xlsx`.
- Annotator columns are detected dynamically from columns beginning with `annotator_`.
- `--output` is supported for writing alternate reports.
- Default report: `docs/human_baseline_report.md`.
- Persona report: `docs/persona_validation_report.md`.

## Primary Human Baseline Result

- Rows analysed: 30
- Annotators: annotator_1, annotator_2, annotator_3
- Average Cohen kappa: 0.642
- Pearson r: 0.7392

## Persona Validation Result

- Rows analysed: 200
- Annotators: annotator_1, annotator_2, annotator_3, annotator_4
- Average Cohen kappa: 0.640
- Pearson r: 0.9578

## Smoke Test

`python tests/test_change5_baseline.py`

Result: 4/4 passed.
