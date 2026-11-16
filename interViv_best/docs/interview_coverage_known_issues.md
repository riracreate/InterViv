# Interview coverage: known issues left open

Observed in the browser walkthrough of the interview coverage fix on
2026-11-15 (offline, `fix/interview-coverage-references`). Neither is fixed
here. They are recorded so they are not mistaken for regressions or lost.

## 1. Review hints are not specific to the round's skill (feedback relevance)

After each answer the interview page shows a line such as
"Review: CAP, caching, microservices". In a session on AWS, Azure, CI/CD and
Docker, every round showed that same line.

- The line is `currentConcepts.missing` in `frontend/src/pages/Interview.jsx`.
- It comes from the knowledge-graph layer of the scorer, which looks concepts
  up by the question's bank skill (`question_context.skill` in
  `backend/scoring/pipeline.py`). Questions tagged `aws`, `azure`, `ci/cd` and
  `docker` are all filed under the bank skill System Design, so they share
  that skill's concept graph.
- The questions and their reference answers were about the round's own skill.
  Only the hint is generic.

This is a feedback-relevance issue in how the hint is chosen, separate from
question relevance. Changing it means changing what the scoring pipeline
reports, so it needs its own decision. Scoring is unchanged by the coverage
fix.

## 2. Console messages during a session

- `GET /session/{id}/draft?round=N` returns 404 once for each newly opened
  round. The backend answers "No draft found." because nothing has been
  typed yet. The page then shows an empty answer field. Present before the
  coverage fix.
- One `400` appeared in the browser console during the walkthrough. It is
  not in the backend request log, which recorded only the draft lookups above
  as non-2xx. Its source was not identified.

No change was made for either. A fix for the 400 would be a guess until the
request is identified.
