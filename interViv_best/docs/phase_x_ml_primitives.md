# Phase X — ML primitives (Layers A and B)

**Delivered on `codex/phase-b-block-practice`.** Candidate submissions are stored
and left open; they are not run or scored. Layers A and B grade trusted pack
references and known-bad solutions in the test suite only.

## Base and boundaries

- Worktree: `.worktrees/phase-b-block-practice`.
- Branch: `codex/phase-b-block-practice`.
- Base: `e5a1bcceb1bb6805f2e1f94e29ff2cd13c58fdf3`.
- Implementation: `56ec00d3592a224d2b46826b9c2d03ab81c85c99`
  (`feat(phase-x)`; 81 files). `32b4a0b` held this delivery doc and
  the review-guide pointer only — corrected in Phase X.1.
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

CORRECTION (Phase X.1): browser verification was not performed. No
desktop browser was driven, no page was rendered, and no HTTP ran over
a socket. Phase X labeled the fallback results below VERIFIED; every
such item is downgraded to PARTIAL here. The fallback evidence is kept
because the route-level results are sound, but an in-process client
cannot find the class of defect this project has repeatedly found only
by rendering a page — three real defects so far; cf. Phase H, which
downgraded nine claims for exactly this reason.

What blocked the real check: no Playwright/Selenium in the venv and no
browser MCP in this environment, and the planned substitute
(disposable uvicorn on a non-colliding port) could not bind:
`uvicorn backend.main:app --host 127.0.0.1 --port 18234` failed with
`[Errno 1] ... operation not permitted`, the `--uds` variant failed
the same way, and escalated execution is unavailable in this profile.
This was a session capability limit, not a machine limit: Phase D's
delivery doc records uvicorn binding `127.0.0.1:8000` in this sandbox
profile, and Phase O ran a disposable stack on `127.0.0.1:18001` /
`127.0.0.1:5174`. A session with socket access can clear these items.
Ports 18000/5173 were never touched, and the developer's existing
database was never pointed at.

What ran instead: the real FastAPI app over ASGI transport
(`TestClient`, `raise_server_exceptions=False`) against a disposable,
migrated SQLite file (`/tmp/phasex_http_18234.db`, alembic head
`20260908_0009`) with a real `POST /auth/signup`. Throwaway probe
`/tmp/phasex_http_probe.py` (not committed): 21/21 checks passed.

- ML round starts and public statement/editor payload is present:
  PARTIAL (was VERIFIED). Exercised: start + resume routes over ASGI
  with real signup on disposable SQLite; `active_round`
  `ml_primitives`/`in_progress`; context id `softmax_stable.v1`,
  title 14 chars, statement 480 chars, `scoring_available: false`,
  `starter_code` present; no sentinels. Not exercised: HTTP over a
  socket, or the React editor rendering this payload in a browser.
- Submit stored, 503 unavailable, no score: PARTIAL (was VERIFIED).
  Exercised: submit route returns HTTP 503 with `code:
  execution_unavailable`, `submission_saved: true`, `retryable: true`,
  `attempt_id` set and no `score` key; `GET /ml-primitives/attempts`
  returns the exact source bytes with `status: unavailable`; the row
  survives engine dispose and reopen on disposable SQLite. Not
  exercised: status propagation over socket HTTP, the unavailable UI
  as displayed in a browser, or retry from the real editor.
- Mixed session reaches ML and does not advance past it: PARTIAL (was
  VERIFIED). Exercised: interview round scored 13.51 and advanced into
  `ml_primitives` (`minmax_normalize.v1`, unscored); ML submit → 503
  stored; resume still shows ML `in_progress` with `final_score:
  null`; dashboard average 13.51 equals the interview score; ML in
  `unscored_rounds` with `execution_unavailable`; no sentinels. Not
  exercised: multi-round navigation in a real browser, or Interview /
  media-gate behavior around the stuck round.
- Render half: PARTIAL (was VERIFIED via the committed suites).
  Exercised: `node --test` suites — `interviewMediaGate.test.js`
  (5 pass: ML gating without calibration/score) and
  `blockBuilder.test.js` (13 pass: ungraded ML label pinned) — prove
  component logic. Not exercised: rendering in a real browser engine;
  no page was loaded and no DOM was interacted with.
- Socket-level HTTP and a real desktop browser: STILL BLOCKED (kept).
  The behaviors above are proven at the ASGI + disposable-SQLite
  level, not over TCP and not in a browser.
