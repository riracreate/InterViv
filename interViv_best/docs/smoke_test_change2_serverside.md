# Smoke Test — Change 2: Remove Frontend cos_similarity

**Date:** 2026-04-24
**Test file:** `tests/test_change2_serverside_metrics.py`

## Results

```
  PASS  test_frontend_metrics_word_count_only
  PASS  test_server_side_vs_frontend_real_answer
  PASS  test_server_side_no_ideal
  PASS  test_pipeline_signature_no_client_fields

4/4 passed
```

## What changed

| Location | Before | After |
|----------|--------|-------|
| `frontend/src/lib/api.js` `buildAnswerMetrics` | Computed `cos_similarity`, `length_ratio`, `aligned_score`, `word_count` | Returns only `{ word_count }` |
| `frontend/src/pages/Interview.jsx` | `buildAnswerMetrics(question, answer)` | `buildAnswerMetrics(answer)` |
| `backend/routes/answer.py` `SubmitAnswerRequest` | Accepted `cos_similarity`, `length_ratio`, `aligned_score` from client | Those fields removed from model |
| `backend/scoring/pipeline.py` `run_scoring_pipeline` | Required `cos_similarity`, `length_ratio`, `aligned_score` as params | Computes them internally via `_compute_server_side_metrics()` |

## Signal direction validation

For a real answer ("Docker packages applications and dependencies into containers..."):

| Metric | Old frontend value | New server-side value |
|--------|-------------------|----------------------|
| `cos_similarity` | 0.25 (vs question) | 0.70 (vs ideal answer) |
| `length_ratio` | 0.48 | 1.07 |

The server-side cos_similarity is **higher quality** — it compares against the ideal answer (correct reference), not the question text (an accidental proxy). Both correctly identify the answer as relevant (>0.3). The SVM score is unaffected because the SVM model maps the feature vector to Good/Average/Poor labels, and the shift in value stays in the same ordinal band.
