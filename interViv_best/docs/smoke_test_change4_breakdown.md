# Smoke Test — Change 4: Persist Scoring Breakdown Per Round

**Date:** 2026-04-25
**Test file:** `tests/test_change4_breakdown.py`

## Results

```
  PASS  test_pipeline_returns_scoring_breakdown
  PASS  test_scoring_breakdown_keys_complete
  PASS  test_scoring_breakdown_types
  PASS  test_answer_route_returns_breakdown

4/4 passed
```

## What changed

### backend/scoring/pipeline.py
`run_scoring_pipeline` now returns a `scoring_breakdown` dict with all of:

| Field | Type | Source |
|-------|------|--------|
| `layer1_score` | float | nlp_payload |
| `layer2_score` | float | nlp_payload |
| `layer3_score` | float | nlp_payload |
| `semantic_score` | float \| None | nlp_payload (None if model unavailable) |
| `tfidf_score` | float | nlp_payload |
| `keyword_coverage` | float | nlp_payload |
| `kg_score` | float | KG scorer |
| `ner_score` | float | entity count |
| `guard_applied` | str \| None | answer guard |
| `final_score` | float | computed |
| `nlp_score` | float | computed |
| `svm_label` | str | SVM model |
| `feedback` | dict | C4 feedback |

### backend/routes/answer.py
Round document in MongoDB now stores `scoring_breakdown` and `guard_applied`.
API response includes `scoring_breakdown` so Dashboard gets it.

### frontend Dashboard
- `mapRealDataToDashboard` forwards `r.scoring_breakdown` to each round object
- `ScoringBreakdownPanel` component: collapsible per-round panels showing:
  ```
  Final 74
  ├── Content match  ×55% = 41  (Semantic: 0.78, TF-IDF: 0.62, Keywords: 70%)
  ├── Answer quality ×25% = 18
  ├── ML judgment    ×20% = 15  (predicted: Good)
  └── Knowledge graph: 60 (blended at 15%)
  ```
- Panel is inserted between RoundTimeline and StrengthsWeaknesses
