# Phase B: Block contract and practice

## Scope and base

Branch: `codex/phase-b-block-practice`.

Worktree: `/tmp/interviv-publish/Downloads/mega 2 copy/.worktrees/phase-b-block-practice`.

Base: Phase A commit `04424938ba728c7cd2bde8acb9dd45f8b4fc7bc7` (verified clean before branching).

Verbal Ability was ported selectively from `phase21-verbal-ability` commit
`fe75a32ea9beccd33193fa072597909b2ddfeb93`: only
`backend/db/phase21_verbal_bank.py` and `docs/phase21_verbal_attribution.md`,
both byte-identical to the source. The older Verbal checkout was not used as
an application base; the newer Phase A platform was extended in place. The
separate `phase21-verbal-ability` worktree was inspected read-only and not
modified.

Phase B implements the product contract sections 2–4 for Verbal, OA, SQL, and
Interview blocks: the backward-compatible block contract, standalone entries,
the custom block builder, presets, builder drafts, answer-draft recovery, and
the candidate-safe catalog. Coding, Problems workspace execution, Phase D
learning connections, and Phase E audio/video remain later work.

## Functional changes

- `POST /session/start` accepts `blocks[]` with per-block stable `id`,
  `position`, `round_type`, `category` (verbal/oa/sql/interview),
  `skills`/topics, `count`, `duration_minutes`, `difficulty`, `question_ids`,
  `problem_ids`, `language`, `negative_marking`, and `review_policy`.
  Legacy `skills`/`round_plan`/`round_type`/`round_config` payloads are
  normalized into the same server-validated plan via `legacy_to_blocks`.
- Supported compositions include Verbal only, OA on DBMS only, SQL only,
  Interview only, Verbal → Interview → SQL, two OA blocks with different
  topics/settings, and OA + Verbal in requested order. Repeated blocks keep
  independent settings; `block_plan` and the expanded per-round plan are
  stored on the session alongside the derived legacy `round_plan`.
- Verbal and OA stay distinct categories sharing only the MCQ scorer. Valid
  legacy standalone Verbal requests (`skills=["Verbal Ability"]`,
  `round_type="mcq"`, `rounds_per_skill=1`) still work; Verbal composition
  with other skills requires blocks. Adding a Verbal block appends and never
  erases the sequence on either side.
- Backend enforcement: requested order, exact-topic filtering, upfront
  available-content validation (no session created on failure), ownership and
  valid-state checks, server-controlled activation (`started_at` at build;
  `expires_at = started_at + duration`; refresh never extends), stable
  assigned questions and option order, idempotent submission (409 on
  duplicates) and idempotent progression (existing next rounds are reused,
  never duplicated). No duplicate scoring, skipped blocks, or silent
  reductions after retries.
- Strict content errors explain availability, e.g. OOP requested 15 of 10:
  `Not enough OOP MCQ questions available: found 10, need 15.` Unknown
  question/problem IDs and topic-mismatched IDs return 422. Legacy launches
  without blocks keep the historical general-pool fallback only when strict
  matches are zero (fully unknown topics, preserving the demo contract);
  new blocks are always strict.
- SQL auto-select preserves the legacy default problem first, then fills
  from the verified bank. Explicit problem IDs are validated (unknown IDs
  are 422, not silent substitution).
- Practice Hub has four standalone entries (Verbal English MCQs, OA,
  SQL, Interview) plus the expanded custom builder: add/remove/reorder
  (button Up/Down keyboard alternatives, no drag required)/repeat per
  block, per-block settings, human labels (`OA · 12 questions`), and a
  total-time summary with sequence readout.
- User-scoped, versioned, validated presets (`GET/POST/GET{id}/PUT/DELETE
  /practice/presets`), autosaved builder drafts (`GET/PUT
  /practice/builder-draft`, server with localStorage fallback), and safe
  answer-draft recovery (`PUT/GET /session/{id}/draft`) for free-text,
  MCQ selections, and SQL queries. Drafts respect ownership and deadlines
  (401/403/400/409 as appropriate); submitted attempts are immutable and
  their drafts are cleared on submit.
- `/session/practice-bank` now returns OA MCQs, Verbal MCQs, and SQL
  problems with safe metadata (SQL includes prompt/schema; never correct
  option IDs, explanations, reference queries, checks, or hidden cases).
- The loud unsupported-round UI in `Interview.jsx` is unchanged and still
  covers genuinely unsupported types (e.g. coding before Phase C).

## Changed files and reasons

| Files | Purpose |
| --- | --- |
| `backend/models/blocks.py` (new) | Block validation, legacy normalization, expansion, labels, time summary. Pure; no DB access. |
| `backend/models/session.py` | Optional block identity on rounds (`block_id`, `block_position`, `block_category`, `block_index`, `block_total`); legacy rounds unaffected. |
| `backend/routes/session.py` | Blocks request field, strict Verbal/OA selection, SQL validation + default-first auto-select, upfront content checks, block-aware start/resume, answer-draft endpoints, extended catalog. |
| `backend/routes/answer.py` | Block-ordered progression with idempotent reuse, per-block skills/difficulty/deadlines, draft clearing, block metadata in responses. |
| `backend/routes/practice.py` (new), `backend/main.py` | Presets and builder-draft CRUD; router wiring. |
| `backend/db/phase21_verbal_bank.py`, `docs/phase21_verbal_attribution.md` (ported) | Verbal bank + authorship record, byte-identical to `fe75a32`. |
| `frontend/src/lib/practiceBuilder.js` | Standalone/block mappers, builder list helpers, labels, client validation, preset/draft version guards. Legacy mappers untouched. |
| `frontend/src/lib/api.js` | Preset, builder-draft, and answer-draft client functions. |
| `frontend/src/pages/Practice.jsx` | Standalone sections, block builder UI, presets, autosaved drafts, Verbal bank filter. |
| `frontend/src/components/MCQRound.jsx`, `SQLRound.jsx`, `frontend/src/pages/Interview.jsx` | Debounced draft autosave + owned recovery with notices; unsupported-round UI preserved. |
| `tests/test_phaseB_blocks.py` (new) | 16 backend checks (list below). |
| `frontend/tests/blockBuilder.test.js` (new) | 9 builder-helper checks. |
| `docs/phase_b_delivery.md` | This delivery evidence and manual checklist. |

## Phase B.1 addendum: persistence repair (2026-09-07)

The Phase B evidence above overstated persistence. In-memory API tests
cannot establish durable recovery, and two defects were confirmed on the
real SQLAlchemy adapter:

1. `practice_presets`, `builder_drafts`, and `answer_drafts` raised
   `KeyError` because `SQLAlchemyDatabase` exposed only candidates,
   users, and sessions.
2. Session writes dropped `round_plan`, `round_config`, `block_plan`,
   `expanded_plan`, and `allow_unknown_topic_fallback`; round writes
   dropped all five block-identity fields. Recovery and block
   progression were therefore wrong on any SQLAlchemy-backed database.

The statement "No Alembic revision was needed" is corrected: revision
`20260907_0004_phaseb_persistence` (revising `20260907_0003`) adds the
five session columns, five round columns, and the `practice_presets`,
`builder_drafts`, and `answer_drafts` tables. Historical migrations are
untouched. New columns are nullable so legacy rows stay valid; sessions
predating the fallback flag read it as allowed, preserving the old
selection behavior for legacy rows.

The repair also closed a demonstrated submission race: two concurrent
submits for one round both returned 200 and both scored
(check-then-claim across separate transactions on every backend).
Submits are now serialized per session (single-process scope; a
multi-worker deployment would need a store-level conditional claim).

Corrected verification (disposable SQLite only; the user database was
never migrated, reset, or touched):

- New `tests/test_phaseB1_persistence.py` (11 tests): plan/round
  write-read fidelity, close/reopen recovery, a 5-block mixed/repeated
  flow through progression, preset/builder/answer recovery with
  ownership and immutability, sequential-retry single scoring, response
  leakage scan, threaded double-submit (one 200, one 409, one scoring),
  Alembic upgrade/downgrade/re-upgrade with store checks against the
  migrated schema, and legacy-session progression.
- Full backend suite: `388 passed, 1 skipped` (the skip is inherited).
- Frontend suite: 42/42. Production build passes. Scoring regression
  still shows only the 2 inherited guard-label failures.

## Preservation and policy notes

- The Phase B diff is empty for `backend/scoring/pipeline.py`, `modules/`,
  `data/`, `research/`, `frontend/src/pages/Dashboard.tsx`,
  `frontend/src/components/dashboard/`, `frontend/src/styles/theme.css`,
  and `frontend/src/index.css`. The Phase B text originally claimed no
  Alembic revision was needed; that claim was wrong for the SQLAlchemy
  backend and is corrected by the Phase B.1 addendum above (new revision
  `20260907_0004`; historical migrations untouched).
- Activation/deadline policy: a round activates when built (block 1 at
  session start; later blocks when the prior round is submitted). Timed
  MCQ/SQL/Verbal rounds get `expires_at = started_at + duration`.
  Interview blocks without an explicit budget stay untimed (legacy
  behavior); with a budget they are timed. `GET /session/{id}` is
  read-only and never extends deadlines.
- Interview answer modes supported: typed text plus existing browser and
  server transcription voice input on the interview page. No new modes
  are claimed.
- The research report regenerated by an inherited test was restored to
  its committed bytes after verification runs and is not part of this
  commit.

## Observed verification

All checks used installed dependencies and offline settings. API checks
used FastAPI TestClient, not a running server. The worktree reuses the
existing `.venv` and frontend `node_modules` via untracked, gitignored
symlinks (verification only; not committed).

Full backend suite (`pytest tests/ -q`):

```text
377 passed, 1 skipped, 15 warnings in 38.02s
```

The skip is the inherited `test_unique_skill_url_constraint_sqlalchemy`
(`DATABASE_URL` not set). The 16 new Phase B tests cover: legacy Verbal
standalone, legacy Verbal-mix rejection, Verbal/OA/SQL/Interview via
blocks, DBMS strictness + OOP available-count error, Verbal → Interview →
SQL completion with duplicate rejection, two OA topics, Verbal-append
order, refresh stability (IDs, option order, deadline), draft
save/recover/ownership/deadline/immutability, presets CRUD + versions,
builder drafts, safe catalog counts/leakage, legacy unknown fallback vs
block strictness, and session ownership.

Frontend `npm --offline test`:

```text
# tests 42
# pass 42
# fail 0
```

This is 33 inherited plus 9 new block-builder checks. An earlier run
showed 3 environmental failures (missing `node_modules`/`.venv` in the
fresh worktree); after linking the installed dependencies, all pass.

Production build (`npm --offline run build -- --outDir
/private/tmp/interviv-phase-b-build`):

```text
✓ built in 4.51s
```

Only the inherited face-api chunk-size warning remains.

`scripts/scoring_regression.py` still reports the same 2 inherited
guard-label mismatches (scores within bands); the protected scorer was
not changed:

```text
gibberish          repetition/gibberish           FAIL
keyword_stuffing   gibberish/keyword_stuffing     FAIL
2/8 case(s) failed.
```

`git diff --check` passes.

## Local startup result

The backend completed startup, then the sandbox rejected its bind:

```text
INFO:     Application startup complete.
ERROR:    [Errno 1] error while attempting to bind on address ('127.0.0.1', 8000): operation not permitted
INFO:     Waiting for application shutdown.
INFO:     Application shutdown complete.
```

No network-permission request or bind workaround was attempted. Browser
journeys, countdown behavior, responsive visual inspection, and the
session-report appearance comparison are NOT VERIFIED.

## Manual browser check

Run each server in a separate local Terminal window. Keep each `cd` as
its own command.

Backend:

```bash
cd "/tmp/interviv-publish/Downloads/mega 2 copy/.worktrees/phase-b-block-practice/interViv_best"
```

```bash
HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 HF_DATASETS_OFFLINE=1 HF_HUB_DISABLE_TELEMETRY=1 QUESTION_GENERATION_MODE=csv QUESTION_REQUIRE_LLM=false OPENAI_API_KEY= OPENROUTER_API_KEY= ADZUNA_APP_ID= ADZUNA_APP_KEY= PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
```

Frontend:

```bash
cd "/tmp/interviv-publish/Downloads/mega 2 copy/.worktrees/phase-b-block-practice/interViv_best/frontend"
```

```bash
npm --offline run dev -- --host 127.0.0.1
```

Open `http://127.0.0.1:5173/practice`. Stop each server with `Ctrl+C`.
The default in-memory backend loses temporary accounts/sessions when
stopped.

1. Start each standalone: Verbal (English MCQs, 5 questions), OA on DBMS
   only (5 questions, all DBMS), SQL only, Interview only (1 question).
   Confirm human labels and no raw type names.
2. Build Verbal → Interview → SQL in the custom builder; confirm the
   summary readout and total minutes. Start, complete all three blocks
   in order, and confirm per-block progression.
3. Build two OA blocks (DBMS easy 4 questions; Python medium 3
   questions); confirm independent topics/counts and-requested order.
4. Request OA on OOP with count 15; confirm a 422-style message naming
   found 10 / need 15 with no silent fill.
5. Refresh mid-assessment; confirm identical questions, option order,
   and deadline. Type a free-text draft, refresh, and confirm recovery
   with the notice. Submit twice; confirm the second is rejected.
6. Save a builder preset, reload the builder, load the preset, and
   delete it. Confirm autosaved drafts restore after leaving and
   returning to `mode=custom`.
7. Sign into a second account; confirm the first account's sessions,
   drafts, presets, and builder draft are not visible.
8. Use only keyboard (Tab/Enter/Space) for add, Up/Down, Repeat, Remove,
   and per-block inputs. Check 375 px, 768 px, and desktop widths.
9. Open a completed session report at `/dashboard/:sessionId`; confirm
   the preserved appearance (NOT VERIFIED by the agent).

Phase C through E remain planned. No push, merge, database reset,
dependency upgrade, or coding execution is part of this delivery.
