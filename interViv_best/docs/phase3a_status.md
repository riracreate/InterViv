# interViv Phase 3A Status

Date: 2026-09-17

Phase 3A delivers reliable persistence and feedback infrastructure on top of
Phase 2 modular practice. Scoring algorithms, reviewed-bundle activation,
the experimental concept evaluator, and live narration generation remain
unchanged and off where gated.

## Current State

- Atomic session start: new candidate + session + Elo seeds commit together;
  failed starts leave no orphan candidate.
- Atomic attempt commit: round result, session transition, attempt snapshot,
  Elo, and narration-job enqueue share one transaction (memory: lock +
  snapshot/restore).
- `content_blocked` session status when the next question cannot be supplied
  after a successful evaluation; scored answer and learning Elo are kept;
  duplicate submit returns 409.
- Immutable attempt snapshots with digest; solution-bearing content stays
  server-side behind existing disclosure checks.
- Narration-job outbox with leases, claim-token fencing, bounded retries;
  with live generation disabled jobs finish as `skipped` with deterministic
  rules feedback (not permanently pending).
- Explicit topics remain strict under both reviewed-bundle policies; metadata
  load failure preserves selection and blocks unrestricted start while a
  topic is still shown.

## Gates (unchanged defaults)

- `REVIEWED_BUNDLES_ONLY` — off
- `EXPERIMENTAL_CONCEPT_EVALUATOR` — off
- `LLM_LIVE_FETCH` — off (narration finishes `skipped`)

## Migrations

- `20260914_0011` — attempt snapshot JSON on rounds
- `20260914_0012` — `narration_jobs` outbox

## Verification snapshot

- Full pytest: see `docs/phase3a_implementation_report.md`
- Scoring regression: 6/8 pass; 2 known guard-label failures (unchanged)
- Replay: 8/8 frozen items + asset hashes
- `docs/human_baseline_report.md` sha256:
  `eb69fdb59cbf35250bdfe96492ba6b37fe8ac4bce9994fd71f25d57c65d3d2ea`
- Browser QA: pending

## Not in Phase 3A

- Phase 3B work, activation of reviewed-only mode, live narration providers,
  Gemma integration, hint-coach, scoring changes, push/merge/deploy.
