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

## What was generated

### `data/human_baseline_sheet.csv`
- 200 rows (50 questions × 4 answers each)
- system_score range: 12.0–83.6, mean: 54.3
- Columns: question, ideal_answer, ideal_keywords, answer, system_score, annotator_1..4

### `docs/human_baseline_report.md`
Generated from 10 dummy-filled rows. Sample output:
- Average κ: 0.768 (Substantial inter-rater agreement on dummy data)
- Pearson r: 0.987 (p=0.000) — system correlates strongly with human in this test

## How to use for viva

1. Share `data/human_baseline_sheet.csv` with 2–4 annotators
2. Each annotator fills their column (0–30 = Poor, 31–60 = Average, 61–100 = Good)
3. Run: `python scripts/baseline_analysis.py`
4. Report saved to `docs/human_baseline_report.md` — cite in viva

## Scripts

| Script | Purpose |
|--------|---------|
| `scripts/human_baseline.py` | Generates annotation sheet from dataset |
| `scripts/baseline_analysis.py` | Reads filled sheet, computes κ + Pearson r + confusion matrix |
