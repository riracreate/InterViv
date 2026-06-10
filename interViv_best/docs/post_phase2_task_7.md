# Phase 2 Task 7 Evidence - Adaptive Question Selector

Date: 2026-05-18
Mode: original app, in-memory fallback smoke. The LLM transport was stubbed
for the evidence run so no OpenRouter network call was made.

## What Landed

- `modules/adaptive_question_selector.py`
  - adaptive target selection from gap analysis when a role exists
  - skill-graph fallback when no company/role is selected
  - weakest-concept selection from concept mastery
  - difficulty matched from current Elo
  - Task 7 prompt extension when target concepts exist
- `backend/routes/answer.py`
  - persists the completed round first
  - updates skill graph and concept mastery
  - recomputes the adaptive target from fresh state
  - generates the next question with targeted concepts
- `backend/routes/session.py`
  - passes adaptive target concepts through the question helper
- `tests/test_adaptive_selector.py`

The protected `modules/question_bank.py` was not edited. The adaptive selector
wraps the prompt behavior around the existing question-generation path.

## Prompt Extension

```text
Generate a question that primarily tests the following concepts: {concept_list}.
The question should naturally require the candidate to demonstrate understanding
of these concepts.
```

## 6-Round Trees and Dynamic Programming Smoke

```text
SEEDED_WEAK_CONCEPTS
{
  "dynamic programming": "Weak",
  "tree": "Weak"
}
ROUNDS 3-6 TARGET CHECK
{
  "round": 3,
  "question": "For DSA, solve a problem that requires dynamic programming, tree; explain the algorithm choice and analyze time complexity.",
  "target_concepts": [
    "dynamic programming",
    "tree"
  ],
  "mentions_tree_or_dp": true
}
{
  "round": 4,
  "question": "For DSA, solve a problem that requires dynamic programming, tree; explain the algorithm choice and analyze time complexity.",
  "target_concepts": [
    "dynamic programming",
    "tree"
  ],
  "mentions_tree_or_dp": true
}
{
  "round": 5,
  "question": "For DSA, solve a problem that requires dynamic programming, tree; explain the algorithm choice and analyze time complexity.",
  "target_concepts": [
    "dynamic programming",
    "tree"
  ],
  "mentions_tree_or_dp": true
}
{
  "round": 6,
  "question": "For DSA, solve a problem that requires dynamic programming, linked list; explain the algorithm choice and analyze time complexity.",
  "target_concepts": [
    "dynamic programming",
    "linked list"
  ],
  "mentions_tree_or_dp": true
}
THREE GENERATED QUESTIONS
round 3: For DSA, solve a problem that requires dynamic programming, tree; explain the algorithm choice and analyze time complexity.
round 4: For DSA, solve a problem that requires dynamic programming, tree; explain the algorithm choice and analyze time complexity.
round 5: For DSA, solve a problem that requires dynamic programming, tree; explain the algorithm choice and analyze time complexity.
PROMPT_EXTENSION_COUNT 5
```

## Tests

```text
$ .venv/bin/pytest tests/ -q
98 passed, 10 warnings in 16.13s
```

