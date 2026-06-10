# Phase 2 Task 2 Evidence - Student Skill Graph

Date: 2026-05-18
Mode: authenticated user, in-memory fallback smoke plus SQL-compatible
persistence layer.

## What Landed

- `modules/skill_graph.py`
  - `StudentSkillGraph`
  - `SkillNode`
  - resume initialization
  - per-round rolling score and Elo updates
  - weak-skill query
- `modules/concept_mastery.py`
  - `ConceptMastery`
  - `MasteryLevel`: `Mastered`, `Strong`, `Weak`, `Untested`
- `backend/routes/learning.py`
  - `GET /skill-graph/{user_id}`
  - `GET /mastery/{user_id}`
- `backend/routes/resume.py`
  - seeds skill graph after authenticated resume upload
- `backend/routes/session.py`
  - seeds skill graph for authenticated quick-start sessions
- `backend/routes/answer.py`
  - updates skill graph and concept mastery after round persistence
- `backend/db/sqlalchemy_store.py`
  - fixed SQL-backed session round attachment so persisted rounds are visible
    to learning updates
- `tests/test_skill_graph.py`

## Protected Areas

`backend/scoring/pipeline.py` was not modified for this task. It already
surfaced `covered_concepts` and `missing_concepts` in the scoring breakdown.
No scoring formula, weights, classifier, dataset, or LLM-as-judge path was
changed.

## 3-Round Skill Graph Evidence

```json
{
  "user_id": "ccda0f26-8ff5-4daf-81c0-2b0b98004109",
  "skills": [
    {
      "name": "DBMS",
      "current_score": 41.29,
      "current_elo": 1208.38,
      "attempts": 1
    },
    {
      "name": "DSA",
      "current_score": 43.74,
      "current_elo": 1209.17,
      "attempts": 1
    },
    {
      "name": "Python",
      "current_score": 66.78,
      "current_elo": 1216.54,
      "attempts": 1
    }
  ]
}
```

## Concept Mastery Evidence

The mastery endpoint tracked concept-level state after the same 3-round
session, including:

```text
DBMS: ACID Strong, atomicity Weak
DSA: dynamic programming Strong, index Weak
Python: decorator Strong, generator Weak
```

## Tests

```text
$ .venv/bin/pytest tests/ -v
49 passed, 6 warnings in 20.24s
```

