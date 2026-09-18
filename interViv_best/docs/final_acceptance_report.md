# Final acceptance report (Phase 4B follow-up + local demo preparation)

- Branch: `qa/demo-acceptance`
- Worktree: `.worktrees/cursor-ai-design-acceptance` (app in `interViv_best/`)
- Starting tip (Phase 4B): `4363ef80c954baa7e89c7bc009e2a19d8280f9fe`
- Fix commit: `116322265f05b5b61c1635f1899a286cb410649c`
- Report commit: this file's commit (see log)
- Tree at report time: clean except this report + `docs/local_demo_guide.md`
- Folder to open in Muse Code:
  `/tmp/interviv-publish/Downloads/mega 2 copy/.worktrees/cursor-ai-design-acceptance`

No other feature phase was started. Reviewed-only selection, the
experimental evaluator, and live generation/narration remain at their
existing OFF settings. No scorer changes, no human-review fabrication,
no hint-coach import/retrain, no model downloads, no push/merge/deploy.

## 1. Checkout resolution

The `qa/demo-acceptance` branch and `.worktrees/cursor-ai-design-acceptance`
worktree already existed, clean, pinned exactly at the Phase 4B commit
`4363ef8`. Verified ancestry (`merge-base --is-ancestor`) and empty diff
against `phase4b/roadmap-coach` before continuing there. The root checkout
(`ticket-f/integrate-demo`, Tree 2) and all earlier worktrees were left
untouched; no stash/discard/reset/clean was performed anywhere. The editor
branch-switch dialog was not acted on.

## 2. Follow-up concurrency gap — closed

Phase 4B left scheduling limits application-level. Inspection confirmed
three concrete holes:

1. Cross-worker races: two workers could both pass `can_schedule_follow_up`
   on stale reads and both append, overspending parent/block/session
   budgets. The process-local submit lock does not span workers, and the
   partial unique index only fires later at round materialization.
2. Pending entries invisible to caps: scheduled-but-unmaterialized
   follow-ups live only in `expanded_plan`, which the parent/block counters
   never scanned — even sequential double-booking passed.
3. Full-doc rewrite hazard: the schedule path rewrote the whole session
   document; the fix writes only the three allocation columns.

Fix (`1163222`, 9 files, +1187/−53):

- `backend/db/follow_up_allocate.py` (new): optimistic concurrency on
  `sessions.revision`. Each attempt, inside one transaction on one
  connection: fresh-read the session, re-validate parent status,
  materialized+pending caps and mandatory reservation, apply a conditional
  `UPDATE ... WHERE id AND revision` touching only
  `expanded_plan_json`/`total_rounds`/`revision`, and insert the teaching
  exposure in the same transaction. Lost races roll back and retry with a
  fresh read (bounded); definitive cap failures return their reason
  immediately; exhaustion returns retryable `allocation_conflict` (route
  maps to 409). Round rows are never touched, so identities, snapshots,
  feedback, and narration jobs are preserved byte-for-byte. The memory
  backend runs the same read-validate-write inside the store-global lock.
- `modules/follow_ups.py`: caps count pending entries (matched by
  `follow_up_identity`); per-block limit honors a lower configured
  `max_follow_ups` (`block_follow_up_limit`, default 2).
- `backend/models/blocks.py`: optional `BlockSpec.max_follow_ups` (>= 0),
  threaded into normalized Interview block dicts.
- `alembic/versions/20260918_0016_*`: `sessions.revision INTEGER NOT NULL
  DEFAULT 0` (backfills 0); downgrade drops the column.
- `backend/routes/follow_ups.py`: delegates to the allocator; response
  shapes and status codes preserved, plus 409 on allocation conflict.
- `docs/phase4b_roadmap_coach_policy.md`: stale "caps remain
  application-level" bullet corrected.
- Assistance eligibility untouched: follow-ups still excluded from
  primary averages, Elo, mastery, and readiness (existing Phase 4A tests).

Residual scope (documented in the module): a full-doc session rewrite from
another worker (e.g. submit finalization) racing an allocation can still
clobber the committed plan entry. Single-process deployments are fully
serialized by the per-session submit lock held by both paths.

## 3. Verification (actual results, no overlapping counts)

Backend suite (`.venv/bin/python -m pytest tests/ -q`), run at the 4B tip
first for a baseline, then after the fix:

| Run | Passed | Skipped | Failed |
|-----|-------:|-------:|-------:|
| Baseline `4363ef8` | 727 | 1 | 4 (pre-existing, listed below) |
| After fix `1163222` | 746 | 1 | same 4, no new failures |

The +19 are `tests/test_follow_up_allocation.py`: pending-aware caps,
configured limits, threaded races on independent SQL connections with no
shared Python lock (same parent → single winner; different parents on the
final block slot → single winner + `block_follow_up_cap`; session-cap race
invariants), rollback proofs on both backends, round-row identity
preservation, revision increments, route behavior incl. 409 mapping, and
0016 upgrade/downgrade + legacy backfill on disposable databases.

Pre-existing failures (identical before/after; ML-primitives/PhaseX/PhaseY
areas, unrelated to follow-ups — not touched):

- `test_phaseX_persistence.py::test_upgrade_store_downgrade_one_revision_reupgrade_store`
  (pins head `20260915_0013`; actual head is newer)
- `test_phaseX_persistence.py::test_unavailable_submission_and_ownership_on_durable_adapter`
  (round-doc drift: `is_follow_up`/` Timer` keys)
- `test_phaseX_session.py::test_mixed_session_reaches_ml_and_stays_open_without_a_score`
- `test_phaseY_expiry.py::test_503_seams_intact_after_expiry_change`

Frontend (same checkout): `npm test -- --run` → 118/118 pass;
`npx tsc --noEmit` → clean; `npm run build` → succeeds (chunk-size warning
only; `dist/` is gitignored).

Frozen checks: `scripts/scoring_regression.py` → 6 PASS / 2 known FAIL with
exactly the expected guards (`gibberish`→`repetition`,
`keyword_stuffing`→`gibberish`); scorer behavior and frozen expectations
untouched. `scripts/replay_scorer_v1_baseline.py` → all 8 items matched
plus asset hashes. `docs/human_baseline_report.md` SHA-256 verified
`eb69fdb5…3d2ea` (intact).

Test-hygiene notes: the run also fixed two test-only issues exposed by the
new file sorting earlier — `test_sql_conversation_survives_reopen` now
upgrades to head for live store use (pinned-chain assertions untouched),
and the new migration tests use programmatic alembic config so `env.py`'s
`logging.fileConfig` cannot disable loggers process-wide (pre-existing
order fragility, documented here, `env.py` itself untouched).

## 4. Local demo preparation

Sandbox blocks socket bind (`operation not permitted`) and `setsid` is
unavailable on macOS, so backend/frontend servers and browser QA could not
run here — same restriction as before; no repeated retries were attempted.
All available checks ran in-process via TestClient instead: a throwaway
probe (`/tmp/demo_journeys.py`, kept out of the repo) verified 42/42
journey checks: auth, standalone Verbal/OA/SQL/Interview start+answer,
mixed/repeated blocks with 3 separate block-metric groups, resume,
assessment-vs-coached defaults, HTTP follow-up schedule + double-refusal,
feedback disclosure, fresh-user roadmap (starter plan, no fabricated
readiness, explicit note), coach create/message/reopen, study-plan task
completion with measured mastery unchanged, Jobs list/detail/practice
handoff, and executor/coach status messages.

Effective runtime modes observed in this checkout (no secrets present —
only `.env.example` exists):

- Database: in-memory (no `DATABASE_URL`); accounts/sessions reset on
  backend restart.
- Jobs: `fixture` provenance (no `ADZUNA_APP_ID`/`ADZUNA_APP_KEY`).
- Piston: unavailable; API reports honestly ("Code execution is
  unavailable in this environment…").
- Ollama (`gemma2:2b` @ 127.0.0.1:11434): not reachable; API reports
  honestly with curated-hint fallback.

Exact Mac startup commands, URLs, and the manual browser checklist
(including refresh/resume, deadlines, assisted answers, reports/disclosure
timing, roadmap variants, jobs handoffs, mobile/desktop layout, keyboard
focus, sign-out) are in `docs/local_demo_guide.md`. No servers are left
running: managed processes end with this session.

## 5. Commits

- `1163222` fix(acceptance): enforce follow-up allocation atomically in
  storage (code + migration + 19 tests + policy correction).
- Report/guide commit: this file + `docs/local_demo_guide.md` (see log
  for SHA).
