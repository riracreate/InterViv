# Smoke Test — Change 5: Human Baseline Evaluation Scripts

**Date:** 2026-04-25
**Test file:** `tests/test_change5_baseline.py`

## Results

```
  PASS  test_baseline_sheet_exists_and_has_correct_columns
  PASS  test_baseline_sheet_row_count
  PASS  test_baseline_system_scores_in_range
  PASS  test_analysis_produces_report

4/4 passed
```

## What was verified

### `data/human_baseline_real_combined.xlsx`
- 30 real human-baseline rows
- 3 independent annotators plus `ann_mean`, `ann_std`, and `system_score`
- `system_score` values are in the valid 0-100 range

### `docs/human_baseline_report.md`
Generated from the real combined workbook:
- Average κ: 0.642 (Substantial inter-rater agreement)
- Pearson r: 0.7392 (p=0.0000) — system correlates significantly with the human mean

## How to use for viva

1. Use `data/human_baseline_real_combined.xlsx` as the primary real-human evidence
2. Keep `data/persona_validation_final.xlsx` as separate methods validation only
3. Run: `python scripts/baseline_analysis.py`
4. Report saved to `docs/human_baseline_report.md` — cite in viva

### `docs/persona_validation_report.md`
Generated from `data/persona_validation_final.xlsx` (separate methods validation, not primary human baseline):
- 4 annotators detected dynamically
- Average κ: 0.640 (Substantial)
- Pearson r: 0.9578 (p=0.0000)

## Scripts

| Script | Purpose |
|--------|---------|
| `scripts/human_baseline.py` | Legacy generator for annotation sheets |
| `scripts/baseline_analysis.py` | Reads CSV/XLSX sheets, computes κ + Pearson r + confusion matrix. Annotator columns detected dynamically. Supports `--output` flag to redirect report. |

## Usage

```
# Default: reads human_baseline_real_combined.xlsx, writes docs/human_baseline_report.md
python scripts/baseline_analysis.py

# Persona validation sheet with separate output
python scripts/baseline_analysis.py --sheet data/persona_validation_final.xlsx --output docs/persona_validation_report.md
```
