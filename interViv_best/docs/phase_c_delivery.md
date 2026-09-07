# Phase C: Coding execution and the Problems experience

## Scope and base

Branch: `codex/phase-b-block-practice`.

Worktree: `/Users/praneetsharma/Downloads/mega 2 copy/.worktrees/phase-b-block-practice`.

Base: Phase B.1 commit `39a7579e1e8f8c16d486ffb0bfa9c6431ada05f1`
(verified clean before starting; not amended).

Phase C makes `coding` a first-class timed round type backed by a
15-problem Python bank, a deterministic visible/hidden scorer, a
separate execution client, attempt persistence, and the Problems
experience (`/problems` catalog plus the in-round workspace). It was
delivered as C.1 (everything except a live execution backend) because
no execution service is reachable in this offline environment; the
unavailable outcome surfaces honestly as retryable instead of a
candidate zero. C.2 (connecting a real backend to the executor seam)
remains later work.

## Infrastructure inspection

Before building, the environment was inspected for execution options:

- Docker CLI is present but the daemon socket is unreachable.
- No Judge0-compatible code-execution API answers on localhost.
- No sandbox runtime for untrusted Python (nsjail/firejail/gVisor-class).
- No editor/execution npm packages were installed (offline constraint).

Per the task constraints, candidate Python is never executed
in-process and no homemade sandbox was built. `GET`-side availability
is machine-readable via `get_execution_status()` in
`backend/execution.py`.

## Functional changes

- Bank (`backend/db/phase_c_coding_bank.py`): 15 original Python
  problems (6 easy, 6 medium, 3 hard), each with 3 visible and
  5 hidden tests, an original reference solution passing all 8, and a
  plausible mutant passing all visible tests while failing at least
  one hidden test. `public_coding_problem()` is the single
  candidate-safe projection (statement, constraints, starter, visible
  examples only).
- Scorer (`modules/scoring/coding.py`, dispatched from
  `modules/scoring/__init__.py`): exactly
  `score = 100 x (0.6 x visible_pass_rate + 0.4 x hidden_pass_rate)`.
  A candidate compile or runtime failure caps the score at 25;
  timeouts count as ordinary failed tests. Hidden tests load
  server-side from the bank (never from the client); hidden outcomes
  are stripped to counts defensively, so hidden detail can never
  reach artifacts, feedback, or explanations.
- Execution boundary (`backend/execution.py`): owns running untrusted
  code. C.1 raises `ExecutionUnavailableError` (retryable, with the
  missing-infrastructure list); the `execute_python_tests` signature
  plus the documented error vocabulary
  (`compile`/`runtime`/`timeout`/`mismatch`) is the C.2 seam.
- Rounds: `coding` reuses Phase B start/validation/progression
  (`round_type` + `coding` category, 30-minute default, 1–5 problems
  per block, `problem_ids` pins). Stored round context is public-only
  (`coding_problem_public_context`); the round serializer additionally
  strips any hidden tests, solutions, or hidden execution detail
  under every review policy.
- `POST /session/coding/run`: non-mutating visible-examples preview
  (never scored). `POST /session/answer` for coding rolls back to
  `in_progress` on `ExecutionUnavailableError` (HTTP 503); the retry
  is a plain resubmit, never a 409.
- Attempts (`coding_submissions`, new table + migration
  `20260907_0005` + SQLAlchemy collection view): one row per submit
  attempt carrying the candidate's own source plus outcome
  counts/scores only. Migrations keep a single head.
- Catalog: `GET /problems` (list with difficulty/topic filters) and
  `GET /problems/{problem_id}` (detail), both auth-required and
  candidate-safe; `GET /session/practice-bank` additionally serves
  the 15 coding entries.
- Ownership: coding start/run/submit/resume/dashboard all require the
  owning user's JWT (401 anonymous, 403 cross-user), matching
  MCQ/SQL. Coding rounds are resumable inside their stored window.
- Frontend: `/problems` page (browse, filter, preview, start a coding
  round), `CodingRound` workspace in the interview flow (statement,
  visible examples, Python editor with starter code, draft autosave,
  run-examples preview with an explicit execution-unavailable panel,
  aggregate-only score review), coding standalone mode and builder
  category in the Practice Hub, nav entry, and `/problems` added to
  the auth-redirect allowlist.

## Contract changes disclosed

Phase C intentionally changes what `coding` means, so four existing
test pins were updated with assertions otherwise unchanged:

- `tests/test_account_progress.py`: `coding` is now a supported
  resumable kind; the unsupported-kind probe uses `whiteboard`.
- `tests/test_practice_hub_session.py`: `coding` is now a supported
  `round_plan` type; the unknown-type probe uses `whiteboard`.
- `frontend/tests/appNav.test.js`: nav gains the Problems entry.
- `frontend/tests/blockBuilder.test.js`: standalone set gains coding.
- `frontend/tests/authRedirect.test.js`: `/problems` moves from the
  rejected-path list to the accepted-destination list.

## Verification

- `pytest tests/`: 427 passed, 1 skipped.
- `npm test` (frontend): 44 passed.
- `npm run build`: clean (`tsc` + `vite build`).
- `alembic heads`: single head `20260907_0005`.
- `scripts/scoring_regression.py`: 4/8 FAILs, byte-identical on the
  base commit `39a7579` (verified via a scratch worktree, since
  removed) — pre-existing offline-model behavior, no Phase C
  regression.
- `git diff --check`: clean.

## Known limits and manual checklist (NOT VERIFIED)

Localhost startup is sandbox-blocked here
(`PermissionError: [Errno 1] Operation not permitted` on
`127.0.0.1` bind), so no browser verification was performed. Manual
steps in an unrestricted terminal:

1. Start the API and the frontend dev server per `docs/deployment.md`.
2. Sign up, open `/problems`, filter by difficulty/topic, preview a
   problem, and start a coding round.
3. In the workspace, run the examples: expect the amber
   execution-unavailable panel (C.1 has no backend).
4. Submit: expect HTTP 503 with the round left open; retry and expect
   503 again (not 409); confirm the attempt rows in
   `coding_submissions`.
5. Build a mixed Verbal → Coding → SQL session in the Practice Hub
   and confirm block order, timers, and resume from Progress.

## Inherited-evidence correction (recorded at Phase D start)

This addendum is not a Phase C code change. It corrects two evidence
claims so later phases inherit accurate figures. The protected scorer
was not modified.

### (a) scoring_regression.py failure count

Phases A–B.1 recorded exactly two known failures. Phase C reported
4/8 FAILs, byte-identical on `39a7579`. Re-run on this machine, with
offline settings, against disposable scratch worktrees (since removed):

| Commit | Label | Failures |
| --- | --- | --- |
| `0442493` Phase A | 2/8 | identical pair below |
| `1601e91` Phase B | 2/8 | identical pair below |
| `39a7579` Phase B.1 | 2/8 | identical pair below |
| `98d3813` Phase C / C.1 (HEAD) | 2/8 | identical pair below |

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

**Corrected inherited baseline for later phases: 2/8 guard-label
mismatches** (scores inside bands). Do not treat 4/8 as the baseline.

### (b) docs/human_baseline_report.md

Phase B.1 reported a clean tree and restored the research report after
the inherited suite. Phase C reported a 163-line deletion described as
pre-existing.

In this worktree the working-tree file matches the committed bytes at
both `39a7579` and `98d3813` (230 lines,
MD5 `5421f9f0fd6efad395666c545e5cf76a`). No restoration was required.

The 163-line deletion **is** what the inherited test produces. Running
`tests/test_change5_baseline.py::test_analysis_produces_report`
executes `scripts/baseline_analysis.py`, which overwrites
`docs/human_baseline_report.md` with the original n=30 analysis and
drops the appended n=50 validation study (230 → 68 lines; diffstat
1 insertion, 163 deletions). That is regenerated research output, not
an uncommitted Phase C edit. It was not committed. The research study
was not reopened.
