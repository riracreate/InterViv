# Phase D: Connected preparation and learning

## Step 0 — inherited-evidence discrepancies

Recorded before any Phase D product work, and committed separately as
`670f5ea`. The protected scorer was not modified.

### (a) scoring_regression.py failure count

Phases A–B.1 recorded exactly two known failures. Phase C reported
4/8 FAILs, byte-identical on `39a7579`. Re-run on this machine, with
offline settings, against disposable scratch worktrees (since removed):

| Commit | Label | Failures |
| --- | --- | --- |
| `0442493` Phase A | 2/8 | identical pair below |
| `1601e91` Phase B | 2/8 | identical pair below |
| `39a7579` Phase B.1 | 2/8 | identical pair below |
| `98d3813` Phase C / C.1 | 2/8 | identical pair below |

The two failures, identical at every listed commit:

| case | guard produced | guard expected | score | within expected band |
| --- | --- | --- | --- | --- |
| `gibberish` | `repetition` | `gibberish` | 6.06 | yes `[0, 25]` |
| `keyword_stuffing` | `gibberish` | `keyword_stuffing` | 10.00 | yes `[0, 40]` |

The other six cases (`excellent`, `paraphrase`, `partial`, `empty`,
`excessive_repetition`, `off_topic`) passed at every listed commit.
`scripts/scoring_regression.py`, `modules/answer_guard.py`, and
`backend/scoring/pipeline.py` are byte-identical across
`0442493..98d3813`.

The count did not move from two to four at any of those commits. The
Phase C "4/8 FAILs" figure is not reproducible here. A commit that
introduced two extra failures **cannot be determined** from this
environment; the extra two failures were not observed.

**Corrected inherited baseline: 2/8 guard-label mismatches** (scores
inside bands). Later phases must not treat 4/8 as the baseline.

### (b) docs/human_baseline_report.md

Phase B.1 reported a clean tree. Phase C reported a 163-line deletion
described as pre-existing.

In this worktree the working-tree file matched the committed bytes at
both `39a7579` and `98d3813` (230 lines,
MD5 `5421f9f0fd6efad395666c545e5cf76a`). No restoration was required
at the start of Phase D.

The 163-line deletion **is** what the inherited test produces. Running
`tests/test_change5_baseline.py::test_analysis_produces_report`
executes `scripts/baseline_analysis.py`, which overwrites
`docs/human_baseline_report.md` with the original n=30 analysis and
drops the appended n=50 validation study (230 → 68 lines; diffstat
1 insertion, 163 deletions). That is regenerated research output, not
an uncommitted Phase C edit. After the full suite it was restored to
the committed bytes and is not part of this commit. The research
study was not reopened.

## Scope and base

Branch: `codex/phase-b-block-practice`.

Worktree: `/tmp/interviv-publish/Downloads/mega 2 copy/.worktrees/phase-b-block-practice`.

Base: Phase C / C.1 commit `98d3813c83d0e00f04807d4ef442e8a0d2bf0cde`
(plus Step 0 docs commit `670f5ea`, not amended).

Phase D connects shared target context, resume/JD analysis, job-linked
preparation, coach, resources, and evidence-backed learning features.
C.2 (live coding execution) and Phase E were not started. No push or
merge.

## Functional changes

- Shared target context (`GET/PUT/DELETE /target-context/me`): one
  server-validated record per user carrying company, role, selected
  job/JD, and resume reference. Partial updates preserve unspecified
  fields; explicit nulls clear. Company/role are mirrored onto the
  users row with the same slug→db-id conversion as the legacy target
  endpoint so existing readiness consumers keep working. Selecting a
  target is intent, not evidence: it does not change mastery or
  readiness math.
- Connected hops: Jobs can target a listing; Upload stores the resume
  reference; Coach/ATS/Practice prefill from the shared context
  without overriding fields the user has already typed; Gap and
  Roadmap send weak-area skills to Practice as prefill only.
- Mistakes notebook (`GET /learning/notebook/me`): built only from
  submitted scored rounds. A user with no scored attempts sees an
  empty state (`counts: null`, `empty_reason: no_scored_attempts`),
  not zeros. Coding rounds are disclosed as excluded because execution
  is unavailable; they are never listed as solved, scored, or missed.
- Retry sets: generated from genuinely missed topics, persisted,
  owned, startable as Phase B blocks (Verbal stays distinct from OA).
- Bookmarks for MCQ/SQL/coding items; candidate-safe titles only.
- Hint and solution-use metadata recorded at the point of use.
  Submit snapshots assistance for **this** session/round (or unscoped
  events inside the round window). A later review does not taint a
  future unassisted retry. Hint payloads do not include keys,
  explanations, or hidden tests. MCQ explanations unlock only after a
  recorded attempt.
- Assisted and unassisted populations are stored on the round and
  returned alongside (not mixed into) mastery, skill-graph, and
  readiness payloads.
- Progress/history: coding-only sessions appear with
  `average_score: null` and `unscored_rounds[].reason =
  execution_unavailable`. `coding_coverage` states what is excluded.
  Session reports add `coverage` and per-block results with
  evidence-backed next-practice suggestions.
- Alembic `20260907_0006` revises `20260907_0005` (confirmed single
  head). New collections are registered on
  `SQLAlchemyDatabase.__getitem__` and every field serializes in both
  directions.

## Contract changes disclosed

Phase D adds a Learn surface, so two existing frontend pins were
updated with assertions otherwise unchanged:

- `frontend/tests/appNav.test.js`: nav gains the Learn entry.
- `frontend/tests/authRedirect.test.js`: `/learn` moves onto the
  accepted-destination list.

`frontend/tests/blockBuilder.test.js` gains `applyTargetPrefill`
checks (prefill applies only when the topic list is not explicit).

## Verification

All checks used installed dependencies and offline settings. API
checks used FastAPI TestClient except the localhost bind smoke below.
The user's database was never migrated, reset, or touched.

- `pytest tests/ -q`: `446 passed, 1 skipped` in 63.05s.
  The skip is the inherited `test_unique_skill_url_constraint_sqlalchemy`
  (`DATABASE_URL` not set).
- New Phase D checks (19): target round-trip and SQLAlchemy
  dispose/reopen, Alembic upgrade/downgrade/re-upgrade with a single
  head, target does not override an explicit topic, preferences do not
  change mastery, empty notebook is absence not zeros, notebook only
  contains recorded misses, retry sets draw from missed topics,
  assisted/unassisted stay separated, hint metadata does not leak
  answers, coding contributes no scored evidence, ownership, leakage
  scan, and a Phase B/C contract smoke (mixed Verbal→OA, OOP 15/10
  content-limit, refresh stability, idempotent 409, coding 503).
- `npm --offline test`: 45 passed, 0 failed.
- `npm --offline run build -- --outDir /private/tmp/interviv-phase-d-build`:
  clean (`tsc` + `vite build` in 5.26s). Inherited face-api chunk-size
  warning remains.
- `alembic heads`: single head `20260907_0006`.
- `scripts/scoring_regression.py`: 2/8 FAILs, identical to the
  corrected Step 0 baseline (guard-label mismatches; scores inside
  bands). Protected scorer untouched.
- `git diff --check`: clean.
- Inherited `test_change5_baseline` rewrote
  `docs/human_baseline_report.md`; it was restored to committed bytes
  after the suite.

Localhost bind was **not** sandbox-blocked in this environment:

```text
INFO:     Application startup complete.
INFO:     Uvicorn running on http://127.0.0.1:8000
VITE v5.4.21  ready in 226 ms
➜  Local:   http://127.0.0.1:5173/
```

`GET http://127.0.0.1:8000/docs` and `/openapi.json` returned 200.
Servers were stopped afterward. No browser tool was available, so
visual journeys, countdown behavior, and responsive inspection are
**NOT VERIFIED**. API success is not treated as UI proof.

## Known limits

- Coding execution remains UNAVAILABLE (C.1). C.2 is not in this
  phase. Attempts are retryable 503s, not candidate zeros.
- The submit lock is still process-local (B.1).
- SQLite datetime reads are tz-naive. Pre-existing.
- Resume/JD fit is not an employer ATS score or hiring probability.
  Existing sample-job source/freshness labels are unchanged.
- Resource links point at existing local records only; they do not
  fetch or embed remote video.

## Manual browser check (NOT VERIFIED)

Run each server in a separate local Terminal window. Keep each `cd`
as its own command.

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

Open `http://127.0.0.1:5173/home`. Stop each server with `Ctrl+C`.

1. Sign in. Save a company/role from Home. Confirm `/ats`, `/coach`,
   and `/practice` prefill it and do not overwrite typed topics.
2. Upload a resume, then open ATS and confirm the resume reference is
   already selected. Target a sample job from `/jobs`; confirm the
   listing is labelled as sample data.
3. Miss some OA questions without hints; open `/learn`. Confirm the
   notebook lists those misses, not zeros, and Create retry set only
   uses those topics.
4. Start a new attempt, open Hint first, then submit. Confirm the
   notebook marks that item assisted and leaves an unassisted miss
   separate.
5. Start a coding round, Run and Submit. Confirm the unavailable
   panel, HTTP 503 with the round left open, Progress showing
   unscored/unavailable (not 0%), and Problems status
   `attempted · unscored` (not solved).
6. Sign into a second account; confirm the first account's target,
   notebook, retry sets, and bookmarks are absent.
7. Check 375 px, 768 px, and desktop. Keep external resource links
   closed during offline checks.

Phase E remains planned. No push, merge, C.2, or Phase E work is
part of this delivery.
