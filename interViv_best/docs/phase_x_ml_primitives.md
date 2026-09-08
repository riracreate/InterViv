# Phase X — ML primitives (Layers A and B)

**Delivered on `codex/phase-b-block-practice`.** Candidate submissions are stored
and left open; they are not run or scored. Layers A and B grade trusted pack
references and known-bad solutions in the test suite only.

## Base and boundaries

- Worktree: `.worktrees/phase-b-block-practice`.
- Branch: `codex/phase-b-block-practice`.
- Base: `e5a1bcceb1bb6805f2e1f94e29ff2cd13c58fdf3`.
- Chain root `0442493` is an ancestor.
- No execution service, no runtime LLM call, no Layer C or D scaffolding.
- Protected scorers, banks, and `backend/scoring/pipeline.py` were not edited.
- C.2, E.2, and phase21 integration were not started.

## What plugs in when execution lands

`grade(submitted_source, executed_outputs, suite=...)` is a pure function. A
future execution service would supply a complete case-keyed output mapping for
a candidate. This phase does not build that service, does not accept an
execution envelope on any API, and does not invent a numeric blend of
properties and static findings.

Missing outputs raise `ValueError` on the envelope; they are not recorded as
failed candidate properties.

## Problem packs

Packs live at `ml_primitives/<name>/v1/`. Public identity is
`<name>.v1`. Catalog reads `manifest.json` and `statement.md` only.

| ID | Properties | Static rules | Known-bad solutions (named target) |
| --- | --- | --- | --- |
| `softmax_stable.v1` | row sums to 1; no NaN on large logits; non-negative; argmax matches logits | approved dependencies; unshifted exponentiation; batch axis loop | `naive_exp` → no NaN on large logits; `batch_loop` → batch axis loop |
| `kmeans_lloyd.v1` | nearest-centroid assignment; inertia non-increasing; empty clusters keep previous centroid; assignment indices in range | approved dependencies; batch axis loop | `farthest` → nearest-centroid assignment; `sklearn_import` → approved dependencies |
| `attention_scores.v1` | last-axis sums to 1; no NaN on large scores; non-negative; scale applied | approved dependencies; unshifted exponentiation; batch axis loop | `missing_scale` → scale applied; `unshifted_exp` → unshifted exponentiation |
| `binary_auc.v1` | range in unit interval; perfect ranking is 1; inverted ranking is 0; ties are half | approved dependencies; score axis loop | `ignore_ties` → ties are half; `sklearn_import` → approved dependencies |
| `minmax_normalize.v1` | range in unit interval; no NaN on constant rows; extrema map to bounds; order preserved | approved dependencies; batch axis loop | `unguarded_divide` → no NaN on constant rows; `sklearn_import` → approved dependencies |
| `layer_norm.v1` | last-axis mean near zero; no NaN on constant rows; last-axis unit scale; translation invariant per row | approved dependencies; batch axis loop | `missing_eps` → no NaN on constant rows; `batch_loop` → batch axis loop |

`layer_norm` is the sixth problem: the distinct failure is zero-variance
division without `eps`, which min-max does not share.

Each pack stores its own seed and `rtol`/`atol` in `properties.py`. Layer A is
deterministic: the same source, seed, and outputs grade identically across
reloads.

## Unavailable, not zero

`POST /session/answer` for `ml_primitives` writes `ml_primitives_attempts`
then returns HTTP 503 with `submission_saved: true` and
`error_code: execution_unavailable`. The round stays `in_progress`. No
`final_score`, mastery, notebook, or readiness update runs. Round expiry does
not write a zero. Storage failure returns `submission_saved: false`.

The editor labels submissions ungraded. Mixed sessions can advance *into* an
ML round and cannot advance past it while scoring is unavailable.

## Persistence

Migration `20260908_0009` (parent `20260907_0008`) adds
`ml_primitives_attempts`. SQLAlchemy serializes every attempt field in both
directions. Tests write, read, dispose the engine, reopen, and re-read against
a disposable SQLite file; they also downgrade one revision and re-upgrade.

## Leakage

Hidden pack Python, property modules, known-bad solutions, static-rule
comments, and injected oracle fields do not appear on start, practice-bank,
resume, attempt history, dashboard progress, dashboard review, or notebook.

## Test pins changed

- `frontend/tests/blockBuilder.test.js`: standalone mode set already included
  `ml_primitives`; this phase also pins the ungraded block label.
- `frontend/tests/interviewMediaGate.test.js`: ML round renders without
  calibration or a score (added with the round view).

No existing render expectation was weakened.

## Checks

All run from `interViv_best` with `.venv/bin/python` (a symlink to the
parent checkout venv; NumPy 2.4.4, PyYAML 6.0.3):

- `python -m pytest tests/ -q` → `526 passed, 1 skipped, 55 warnings
  in 70.90s`.
- Phase X files only (`test_phaseX_grading/packs/persistence/session`)
  → `37 passed in 4.96s`.
- `cd frontend && npm test` → 56 pass, 0 fail. Targeted:
  `tests/interviewMediaGate.test.js` 5 pass,
  `tests/blockBuilder.test.js` 13 pass.
- `npm run build` → `tsc && vite build`, `built in 9.48s`.
- `python scripts/scoring_regression.py` → 2/8 failed, as expected:
  `gibberish` guard `repetition` (6.06), `keyword_stuffing` guard
  `gibberish` (10.00).
- `DISABLE_SEMANTIC_SCORING=1 python scripts/scoring_regression.py` →
  4/8 failed, as expected (`paraphrase` 39.75, `gibberish`,
  `keyword_stuffing`, `off_topic` guard None).
- `python -m alembic heads` → single head `20260908_0009`.
- `git diff --check` → clean.
- `docs/human_baseline_report.md`: the pytest run rewrote it to 68
  lines; restored with `git checkout --` to 230 lines, MD5
  `5421f9f0fd6efad395666c545e5cf76a`.
- `refs/rescue/*` unchanged: `phase21-blob-06bc5daf 06bc5daf…0b5f`,
  `phase21-blob-65bf858a 65bf858a…4490`,
  `phase21-blob-8405effd 8405effd…011c`,
  `phase21-verbal-ui 381c7841…4c83` (full hashes in session report).
- Protected paths untouched: `git status` shows nothing under
  `backend/scoring/`; no bank, guard, or pipeline edits.

## Browser verification

No Playwright/Selenium in the venv and no browser MCP in this
environment, so no desktop browser was driven. The planned substitute
(disposable uvicorn on a non-colliding port) was attempted and blocked:
`uvicorn backend.main:app --host 127.0.0.1 --port 18234` failed with
`[Errno 1] ... operation not permitted` on bind, the `--uds` variant
failed the same way, and escalated execution is unavailable in this
profile. Ports 18000/5173 were never touched, and the developer's
existing database was never pointed at.

What ran instead: the real FastAPI app over ASGI transport
(`TestClient`, `raise_server_exceptions=False`) against a disposable,
migrated SQLite file (`/tmp/phasex_http_18234.db`, alembic head
`20260908_0009`) with a real `POST /auth/signup`. Throwaway probe
`/tmp/phasex_http_probe.py` (not committed): 21/21 checks passed.

- ML round starts and public statement/editor payload is present:
  VERIFIED (ASGI + disposable SQLite + real signup). Resume
  `active_round` is `ml_primitives`/`in_progress`; context id
  `softmax_stable.v1`, title 14 chars, statement 480 chars,
  `scoring_available: false`, `starter_code` present; no sentinels.
- Submit stored, 503 unavailable, no score: VERIFIED (same method).
  Submit → HTTP 503, detail `code: execution_unavailable`,
  `submission_saved: true`, `retryable: true`, `attempt_id` set, no
  `score` key; `GET /ml-primitives/attempts` returns the exact source
  bytes with `status: unavailable`; the row survives engine dispose
  and reopen (count still 1).
- Mixed session reaches ML and does not advance past it: VERIFIED
  (same method). Interview round scored 13.51, advanced into
  `ml_primitives` (`minmax_normalize.v1`, unscored); ML submit → 503
  stored; resume still shows ML `in_progress` with `final_score:
  null`; dashboard average 13.51 equals the interview score and ML
  appears in `unscored_rounds` with `execution_unavailable`; no
  sentinels on any payload.
- Render half: VERIFIED via the committed suites —
  `interviewMediaGate.test.js` (5 pass: ML renders without
  calibration/score) and `blockBuilder.test.js` (13 pass: ungraded ML
  label pinned).
- Socket-level HTTP and a real desktop browser: STILL BLOCKED in this
  environment (sandbox denies all listener binds). The behaviors above
  are proven at the ASGI + disposable-SQLite level, not over TCP.
