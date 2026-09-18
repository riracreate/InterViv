# Final acceptance report (Phase 4B follow-up + local demo preparation)

- Branch: `qa/demo-acceptance`
- Worktree: `.worktrees/cursor-ai-design-acceptance` (app in `interViv_best/`)
- Starting tip (Phase 4B): `4363ef80c954baa7e89c7bc009e2a19d8280f9fe`
- Fix commit (allocation): `116322265f05b5b61c1635f1899a286cb410649c`
- Fix commit (write races): `37bfd069985deca649c6d24357e4440518f2185f`
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

Residual scope at that time (documented in the module): a full-doc
session rewrite from another worker (e.g. submit finalization) racing an
allocation could still clobber the committed plan entry. That residual is
now closed by §3 below; the module docstring was updated to describe the
shared protocol instead.

## 3. Submit-versus-schedule race — closed

Inspection confirmed the store itself did read-modify-write: SQL
`sessions.update_one` re-read the document, merged `$set`, and rewrote
every column plus all round rows, so any commit landing between its read
and write was silently dropped — a submit/continue commit could erase a
concurrently scheduled follow-up entry, and vice versa a stale `rounds`
payload could erase a committed round.

Fix (`37bfd06`): every session writer joins one optimistic-concurrency
protocol instead.

- `backend/db/sqlalchemy_store.py`: `sessions.update_one` writes ONLY the
  columns named by top-level `$set` keys (unknown keys still dropped,
  exotic operators keep a full but still conditional write), bumps
  `sessions.revision` on every write, and gates the write twice: the
  caller's `expected_revision` (from its own read, now exposed as
  `revision` on session docs) must match, and the conditional
  `UPDATE ... WHERE id AND revision` must affect exactly one row —
  otherwise `SessionWriteConflict` with nothing persisted. No-op `$set`s
  perform no write and no bump.
- `backend/db/memory.py`: accepts and ignores `expected_revision`
  (single-process; routes already serialize there).
- `backend/db/follow_up_allocate.py`: the allocator now goes through the
  same store call (one transaction per attempt), keeping its retry budget
  and `allocation_conflict` mapping.
- `backend/routes/answer.py`: the submit commit retries (max 3) on
  conflict — reload, revalidate round ownership (a round finalized by a
  co-held claim is a 409, a wiped claim is reclaimed conditionally, an
  expired round keeps its 400), re-run progression against the fresh
  session, and re-commit. Scoring runs once per request; the losing
  attempt rolls back before Elo, narration, or learning effects run, so
  retries cannot duplicate them. Exhaustion is a controlled 409. Expiry
  marks reload/re-decide; scoring-failure, incomplete-design, and
  ml-primitives rollbacks share one guarded release (skip when the state
  moved on).
- `backend/routes/session_continue.py`: same bounded reload/re-decide
  loop; a loser finds the winner's open round and returns it instead of
  appending a duplicate.
- `backend/routes/session.py` (coding dry-run slot) and
  `backend/routes/learning_hub.py` (review-config stamp): conditional
  write with one reload/revalidate retry.
- Round claims stay round-row-only by design (no revision bump); the
  final commit's revision gate is what serializes outcomes. Double-held
  claims resolve to winner-plus-409/retake, as before.

The four baseline failures were also resolved (verified failing
identically at the 4B tip `4363ef8` in the untouched Phase 4B worktree,
then fixed here):

- `test_phaseX_persistence.py::test_upgrade_store_downgrade_one_revision_reupgrade_store`:
  stale head pin (`20260915_0013`; the chain has grown twice since, most
  recently by this task's own `20260918_0016`). Test-only fix: pin tracks
  the current head; the downgrade/reupgrade assertions are unchanged.
- `test_phaseX_persistence.py::test_unavailable_submission_and_ownership_on_durable_adapter`,
  `test_phaseX_session.py::test_mixed_session_reaches_ml_and_stays_open_without_a_score`,
  `test_phaseY_expiry.py::test_503_seams_intact_after_expiry_change`: one
  root cause — the `ml_primitives` 503 path claimed the round but never
  released it (unlike the coding 503 path, which rolls back), leaving
  `finalizing` instead of `in_progress`, including on the user-visible
  resume payload. Product fix in `answer.py`: the claim is always
  released on that path (attempt stored or store failure), so the round
  stays openly resubmittable. No scoring-code change: the tests'
  forbidden-scoring mocks still hold, and auth checks are untouched. The
  persistence test now compares session content modulo the version
  counter and pins exactly two release writes.

## 4. Verification (actual results, no overlapping counts)

Backend suite (`.venv/bin/python -m pytest tests/ -q`):

| Run | Passed | Skipped | Failed |
|-----|-------:|-------:|-------:|
| Baseline `4363ef8` | 727 | 1 | 4 (pre-existing) |
| After fix `1163222` | 746 | 1 | same 4, no new failures |
| After fix `37bfd06` | 758 | 1 | 0 |

The +12 are `tests/test_session_write_races.py` (+8) plus the 4 resolved
failures. The race tests simulate independent workers (fresh lock per
call — no shared process exclusion; independent SQL connections; a
barrier forces both sides to commit from the same stale snapshot) and
reopen the database before asserting: submit-vs-schedule (both effects
survive in either serialization order; scored once; one narration job,
one exposure, one Elo delta per round; exactly three session writes),
continue-vs-schedule (single appended round, pending entry preserved),
forced allocator conflicts (rollback leaves no exposures/entries),
distinct-parent scheduler race (attempts exactly [1, 2] — a proven
conflict plus clean retry), double continue (one append; loser's retry
writes nothing), the store protocol directly (stale raises with zero
partial writes; unconditioned writes stay field-scoped; unknown-key and
no-op parity), memory-adapter parity, and submit reclaiming a claim
wiped by a racing writer. The three route-race tests were also run
against pre-fix code in a throwaway worktree (removed afterwards): all
fail there, all pass here.

Frontend: unchanged by this task (no frontend files touched), so the
checks already performed on this checkout stand as-is: `npm test --
--run` → 118/118 pass; `npx tsc --noEmit` → clean; `npm run build` →
succeeds (chunk-size warning only; `dist/` is gitignored). Not re-run.

Frozen checks (re-run after the fix, identical to the recorded
baseline): `scripts/scoring_regression.py` → 6 PASS / 2 known FAIL with
exactly the expected guards (`gibberish`→`repetition`,
`keyword_stuffing`→`gibberish`); scorer behavior and frozen expectations
untouched. `scripts/replay_scorer_v1_baseline.py` → all 8 items matched
plus asset hashes. `docs/human_baseline_report.md` SHA-256 verified
`eb69fdb59cbf35250bdfe96492ba6b37fe8ac4bce9994fd71f25d57c65d3d2ea`
(`eb69fdb5…3d2ea`, intact).

Test-hygiene notes: the run also fixed two test-only issues exposed by the
new file sorting earlier — `test_sql_conversation_survives_reopen` now
upgrades to head for live store use (pinned-chain assertions untouched),
and the new migration tests use programmatic alembic config so `env.py`'s
`logging.fileConfig` cannot disable loggers process-wide (pre-existing
order fragility, documented here, `env.py` itself untouched). This round
adds one more of the same kind: both threaded-SQL fixtures now clear the
`get_settings` cache at teardown (previously only the SQLAlchemy caches),
after the new file exposed a stale-`DATABASE_URL` leak into the
following `test_skill_graph.py` (product code untouched).

## 5. Local demo preparation

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
handoff, and executor/coach status messages. The probe was re-run after
the `37bfd06` race fix with the same result (42 passed, 0 failed), so the
advertised journeys are unaffected by the new write protocol.

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

## 6. Commits

- `1163222` fix(acceptance): enforce follow-up allocation atomically in
  storage (code + migration + 19 tests + policy correction).
- `05a9d30` docs(acceptance): record final verification and local demo
  guide.
- `37bfd06` fix(acceptance): serialize concurrent session writes on
  revision protocol (store + routes + 8 race tests + ml-release fix +
  head-pin/test-hygiene fixes).
- Report/guide commit: this file + `docs/local_demo_guide.md` (see log
  for SHA).
