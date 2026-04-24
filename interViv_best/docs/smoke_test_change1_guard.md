# Smoke Test — Change 1: Anti-Gaming Guard

**Date:** 2026-04-24  
**File tested:** `modules/answer_guard.py`  
**Test file:** `tests/test_guard.py`

## Results

```
  PASS  test_empty_answer
  PASS  test_gibberish_answer
  PASS  test_repetition_answer
  PASS  test_too_short_answer
  PASS  test_good_answer_no_cap

5/5 passed
```

## Case details

| Test | Input | Expected cap | Expected reason | Result |
|------|-------|-------------|-----------------|--------|
| empty | `""` | 5 | `empty` | PASS |
| gibberish | `"asdfasdf qwer hjkl"` | 10 | `gibberish` | PASS |
| repetition | `"docker docker docker docker docker docker"` | 15 | `repetition` | PASS |
| too_short | `"containers are good"` | 20 | `too_short` | PASS |
| good answer | 70-word Docker explanation | no cap | — | PASS |

## Integration

- Guard runs in `backend/scoring/pipeline.py` **before** the NLP scorer.
- After `final_score` is computed, `min(final_score, guard["score_cap"])` is applied.
- If a cap fires, the guard reason is prepended to `feedback["content"]` so the UI shows the issue.
- `guard_applied` key is included in the pipeline return dict (None if no cap, reason string otherwise).
