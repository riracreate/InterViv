# interViv Phase 3B Status

Date: 2026-09-17

Phase 3B delivers feedback delivery and blocked-session recovery on the
Phase 3A tip (`3c073a5`). Scoring algorithms and activation gates are unchanged.

## Current State

- Shared session ownership on answer, continue, GET session, dashboard, feedback.
- Ideal/reference disclosure only after `status == completed` (not `content_blocked`).
- Active and `content_blocked` sessions with `review_policy=after_session` do not
  expose answer keys, explanations, or reference ideals via dashboard, answer,
  session, or feedback responses.
- Optional dashboard MCQ key display feature deferred; completed review uses
  `GET /session`.
- `POST /session/{id}/continue` recovers from `content_blocked` without rescoring.
- `progression_blocked_reason` persisted (migration `20260915_0013`).
- Snapshot v2 adds reference + scorer provenance for new freezes only.
- Feedback allowlist endpoint; narration validator; fakeable provider; live gen off.
- Interview: retry-continuation + rules-first feedback polling with unmount /
  round-advance cleanup and terminal stop.

## Gates (unchanged defaults)

- `REVIEWED_BUNDLES_ONLY` — off
- `EXPERIMENTAL_CONCEPT_EVALUATOR` — off
- `LLM_LIVE_FETCH` — off

## Verification

- Broader Phase 3B-related pytest: 59 passed
- Frontend: 112 passed; tsc clean; production build OK
- Scoring regression: 6 pass / 2 known failures
- Replay: 8/8 + asset hashes
- Report hash: `eb69fdb59cbf35250bdfe96492ba6b37fe8ac4bce9994fd71f25d57c65d3d2ea`
- Browser QA: pending

## Not in Phase 3B

- Live narration activation, reviewed-only activation,
  Gemma/hint-coach, scoring changes, push/merge/deploy.
- Dashboard MCQ answer-key display feature (deferred).
- Adzuna integration (separate `jobs/adzuna-integration` branch).
