# Gibberish Guard Fix

Date: 2026-05-19

## Problem

Random answers such as `gctcititxi` and
`fvitugceigc vgcyutrxrtxtci` were reaching the normal scoring path and could
receive ordinary-looking scores.

## Fix

- The answer guard still runs before NLP/KG/NER scoring in
  `backend/scoring/pipeline.py`.
- Guard caps are now hard limits. A final score can never exceed the guard's
  `score_cap`.
- The previous too-short semantic softening was removed because it could exceed
  the guard cap.
- `modules/answer_guard.py` now checks:
  - empty and whitespace-only answers
  - too-short answers
  - random character strings
  - low meaningful-token count
  - abnormal vowel ratio
  - repeated character runs
  - repeated token ratio
  - keyboard spam and nonsense-token patterns
  - keyword stuffing
- User-facing feedback for incomplete/gibberish answers:
  "Your answer looks incomplete or gibberish. Please write a meaningful explanation."
- Regression tests now include the explicit examples `gctcititxi`,
  `fvitugceigc vgcyutrxrtxtci`, `asdfasdfasdf`, repeated `qwerty`,
  repeated `python`, empty answers, and whitespace-only answers.

## Caps

- empty / whitespace: max 5
- gibberish / random tokens: max 10
- repeated meaningless text: max 15
- too short: max 20
- keyword stuffing: max 35

## Verification

Run the focused guard regression suite with:

```text
.venv/bin/pytest tests/test_answer_guard.py tests/test_guard.py tests/test_guard_v2.py -q
```
