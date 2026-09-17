# Phase 3A implementation report

Reliable persistence and feedback infrastructure only. **Stop before Phase 3B.**

## 1. Location and commits

| Item | Value |
| --- | --- |
| Worktree | `/Users/praneetsharma/Downloads/mega 2 copy/.worktrees/cursor-ai-design-phase3a` |
| App root | `interViv_best/` |
| Branch | `phase3a/persistence-feedback` |
| Base | `dfe68db9d651c19a5f05bf57c8fe11ce49fad9aa` (`phase2/modular-practice`) |
| Runtime | Python 3.12 via `.venv`; frontend Node tests via `npm test` |

Earlier worktrees (phase0/1a/1b/2, coding-practice, phase-b, Tree 2) were left untouched. No push. No merge. No deployment.

Final tip and commit list are recorded at the end of this document after the local commit sequence.

## 2. What changed

### A. Explicit-topic contract

- Explicit block/session topics stay strict under `REVIEWED_BUNDLES_ONLY` off or on. Unsuppliable scope returns an unavailable outcome (probe + start 422) — no silent topic substitution.
- No topic selected preserves unrestricted legacy relaxation (including session-level pins).
- Multi-skill blocks require the topic on every selected skill, or return a clear “Split the block” validation error; skills are never silently dropped.
- Practice UI: on topic-metadata load failure, an explicit selection is preserved and start is blocked with Retry / Clear topic. Unrestricted start is allowed only when no topic is held. Never starts unrestricted while the UI still shows a selected topic.

### B. Atomic session start

- New candidate + session + Elo seeds commit inside `atomic(db)`.
- Content failures (unknown topic, empty inventory) run before any write.
- Mid-commit store failures roll back completely: no orphan candidate, no session missing from its candidate. Existing candidates are never deleted to compensate.

### C. Atomic attempt commit

Shared attempt commit persists together:

- Authoritative round result (score, feedback, explanation).
- Session transition (`active` / `completed` / `content_blocked`).
- Immutable `attempt_snapshot` (inputs, pinned reference identity/content, scorer provenance, result, evaluated signals) with digest.
- Candidate Elo update for measured rounds.
- Exactly one narration job (deterministic id).

SQLAlchemy uses one ambient transaction; memory mode snapshot/restores under its lock (no restart-durability claim for memory).

**Next-question unavailable (expected):** scored answer, Elo, snapshot, feedback, and narration job commit; session becomes `content_blocked` with `progression_blocked_reason`. Duplicate submit → 409; no rescore, no second Elo/narration, no skipped/false next round.

**Unrelated commit failure (503):** score does not persist; round stays `finalizing` for stale-claim takeover on retry.

Skill-graph / concept-mastery updates remain post-commit best-effort (unchanged numerical path); 409 prevents double application after a successful commit.

### D. Snapshots and rules feedback

- Snapshots are server-side; candidate APIs keep ownership/disclosure stripping (no solution-bearing snapshot leakage).
- Deterministic explanations use established scoring outputs only. Experimental concept evaluator stays off. Historical records are not rewritten.

### E. Narration jobs (no live generation)

- Durable outbox table/collection with statuses `queued|processing|done|failed|skipped`.
- Exclusive claim via `claim_token` + `lease_until`; expired leases reclaim; stale workers cannot overwrite a newer claim’s result.
- Bounded retries (`MAX_ATTEMPTS=3`).
- With `LLM_LIVE_FETCH=0`, workers finish as `skipped` with the deterministic rules-feedback artifact — not permanently pending. No Gemma / live provider calls. Provider work (when later enabled) stays outside scoring transactions.

## 3. Migrations / rollback

| Revision | Change |
| --- | --- |
| `20260914_0011` | `attempt_snapshot_json` on session rounds |
| `20260914_0012` | `narration_jobs` table (incl. `claim_token`, `lease_until`, `skipped`) |

Rollback: `alembic downgrade 20260914_0010` (or parent of 0011) drops both Phase 3A objects. Application code on this branch expects those columns/tables when using SQLAlchemy; memory mode needs no migration.

## 4. Gates kept off

- `REVIEWED_BUNDLES_ONLY` default off (tests toggle for gate-on cases).
- `EXPERIMENTAL_CONCEPT_EVALUATOR` off.
- Live narration / `LLM_LIVE_FETCH` off.
- No fabricated reviews; real bundle review status unchanged.
- No scoring algorithm changes; no hint-coach; no Gemma download/train/integrate.

## 5. Tests and verification

### Phase 3A suites

```
.venv/bin/python -m pytest tests/test_phase3a_*.py tests/test_phase2_availability.py tests/test_phase2_topics.py -q
```

### Full backend

```
.venv/bin/python -m pytest tests/ -q
→ 674 passed, 1 skipped, 96 warnings in ~135s
```

### Scoring regression (unchanged known failures)

```
.venv/bin/python scripts/scoring_regression.py
→ 2/8 failed
  gibberish: guard_applied='repetition', expected 'gibberish'
  keyword_stuffing: guard_applied='gibberish', expected 'keyword_stuffing'
```

Established baseline: six passing cases, two known guard-label mismatches. Not “fixed” in this phase.

### Frozen replay + research hash

```
.venv/bin/python scripts/replay_scorer_v1_baseline.py
→ Replay matched 8 frozen items and asset hashes.

docs/human_baseline_report.md sha256 (unchanged):
eb69fdb59cbf35250bdfe96492ba6b37fe8ac4bce9994fd71f25d57c65d3d2ea
```

### Frontend

```
cd frontend && npm test -- --run → 102 passed
tsc --noEmit → exit 0
```

TestClient/API suites do not verify rendered UI.

### Browser verification: PENDING

Same environment restriction as Phase 2: no reliable browser tooling / sandbox bind limits. Pending local QA (do not treat API tests as render proof):

1. Interview mode: select topic, kill topic metadata (or block `/practice/bank`), confirm start disabled with Retry/Clear; clear topic → unrestricted start allowed.
2. Topic exhaustion mid-session: answer commits, UI shows blocked progression, retry answer → conflict, report still shows score.
3. Custom builder multi-skill incompatible topic: clear validation, no silent skill drop.

## 6. Limitations

- Memory `atomic()` is single-process snapshot/restore, not durable across restarts.
- Skill-graph / concept-mastery remain post-commit best-effort (Elo + snapshot + narration are in the attempt transaction).
- Narration worker is opt-in (`python -m modules.narration_jobs --once`); no background daemon in this phase.
- Reviewed-only activation, experimental evaluator, and live generation stay disabled.
- Browser QA pending.

## 7. Final commit

Base: `dfe68db9d651c19a5f05bf57c8fe11ce49fad9aa` (`phase2/modular-practice`).

Commits on `phase3a/persistence-feedback` (oldest first):

1. `1f3ed59` `feat(phase3a): atomic start/attempt commit, snapshots, narration outbox`
2. `3011fee` `feat(phase3a): close explicit-topic contract and metadata-failure start gate`
3. `docs(phase3a): implementation report and status` — tip SHA is this docs commit
   (`git rev-parse HEAD` / handoff).
