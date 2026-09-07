# Phase A: Home, navigation and Progress

## Scope and base

Branch: `codex/phase-a-home-progress`.

Worktree: `/tmp/interviv-publish/Downloads/mega 2 copy/.worktrees/phase-a-home-progress`.

The existing Practice, resources, ATS, Jobs, Coach, learning signals and revised session report were present only as uncommitted work in the original `ticket-f/integrate-demo` checkout. All corresponding feature branch names still pointed to `37eed95`. With the user's approval, that application work was copied into this isolated branch:

- `dba02e9`: inherited application snapshot, preserving its existing scorer/parser files byte-for-byte.
- `fcdb19f`: unchanged local evaluator script required by an inherited test; this is the immediate Phase A base.

The original checkout and the separate `phase21-verbal-ability` worktree were not edited. Private annotation files and pending research-document changes were excluded from the snapshot. Research at `37eed95` remains the committed starting history.

Verbal Ability at `fe75a32` is on a separate branch and is **not** present in this integrated feature snapshot. Phase A does not port that engine or implement the new block contract. Verbal integration/composition belongs to Phase B. Coding, the new Problems workspace, presets and answer-draft recovery remain later-phase work.

The handoff archive's Home Hub HTML is byte-identical to the earlier reference. Home uses direction 2b and Progress uses 3a. Design runtime, annotations, sample statistics and raw API labels were not imported.

## Functional changes

- `/home` is an authenticated action hub with Prepare, Target, Apply and Guide sections. It links to the existing interview, OA + SQL, individual-problem, custom-practice, resume-check, Jobs, Coach, gap, roadmap and resources experiences.
- New users receive Start practicing and Help me choose a path. Continue practice appears only when the authenticated summary endpoint finds an owned, active, unsubmitted session with a supported round and a valid existing time window.
- `/dashboard` is now aggregate Progress: measured target readiness, skill scores, real scored-session history, Elo changes, revisit rates and roadmap completion. Missing measurements remain unmeasured; measured zeros are displayed as zero.
- Login and signup default to `/home`. A shared validator preserves supported internal destinations, including dynamic interview/report/gap/roadmap routes and query strings. External URLs, protocol-relative destinations, encoded separator escapes, unsupported paths and authentication loops fall back to Home. Login/signup links preserve the validated return destination.
- Interview entry fetches the server session before mounting the existing interview screen. This enables owned deep links and prevents stale browser session storage from selecting the wrong round. Completed sessions open their report. API authentication errors return to sign-in; other errors remain readable and retryable.
- Target selection reuses the existing component and persistence API. Home updates its target-dependent links after Save.
- Resources now has a skill input, loading state, empty state and error state when entered from Home. Existing embedded resource components retain their previous default presentation.
- Home/Progress styling is restricted to `.hub-page` and uses existing theme tokens. Landing navigation remains usable at narrow widths.

## Changed files and reasons

| Files | Purpose |
| --- | --- |
| `backend/routes/dashboard.py` | Add authenticated, allowlisted account summaries at `GET /dashboard/progress`; preserve the existing per-session report endpoint. |
| `frontend/src/pages/Home.jsx`, `Progress.jsx`, `styles/hub.css` | Separate actions from measured progress; implement the supplied light design direction with responsive layout rules. |
| `frontend/src/components/AccountPage.jsx` | Reuse account loading, sign-in handling, navigation, retry and sign-out for the two new screens. |
| `frontend/src/components/InterviewRoute.jsx`, `pages/Interview.jsx`, `lib/accountOverview.js` | Restore interview context from the server for continuation and authenticated deep links; format real scores and session labels. |
| `frontend/src/lib/authRedirect.js`, `pages/Login.jsx`, `Signup.jsx` | Validate and preserve return destinations consistently. |
| `frontend/src/App.jsx`, `components/AppNav.jsx`, `lib/appNav.js`, `pages/Landing.jsx` | Add Home, rename aggregate Dashboard to Progress, preserve the session-report route, connect landing navigation. |
| `frontend/src/lib/api.js` | Expose account summaries and HTTP status on errors so authentication failures differ from unavailable services. |
| `frontend/src/components/CompanySelector.jsx` | Optional save callback so Home can refresh confirmed target data. |
| `frontend/src/pages/Practice.jsx` | Preserve the requested mode through login and remove misleading Verbal/API terminology. No engine or builder-contract change. |
| `frontend/src/pages/Resources.jsx`, `components/ResourceLinks.jsx` | Make the generic resource entry usable without requiring users to construct URL parameters. |
| `tests/test_account_progress.py` | Seven checks covering auth, ownership, private-data exclusion, valid resumption, zeros and the signup-to-results lifecycle. |
| `frontend/tests/authRedirect.test.js`, `hubRendering.test.js`, `appNav.test.js` | Redirect attack cases, state restoration, real/unknown scores, rendered Home/Progress states and connected navigation. |
| `docs/phase_a_delivery.md` | This delivery evidence and manual checklist. |

## Preservation and resume policy

The Phase A diff is empty for `backend/scoring/pipeline.py`, `modules/`, `data/`, `frontend/src/pages/Dashboard.tsx`, `frontend/src/components/dashboard/`, `frontend/src/styles/theme.css` and `frontend/src/index.css`.

Session reports retain their existing component tree and theme. They are not wrapped in AccountPage or AppNav. New resource feedback is opt-in and is not enabled for the report's embedded resources. Screenshot/pixel comparison remains unverified because local server binding was blocked.

The new summary endpoint is read-only. It never activates a round, extends a deadline, updates a score or returns question contexts, candidate answers, reference solutions, hidden cases or execution artifacts. A timed MCQ/SQL round without a valid stored deadline is not advertised as resumable. Submitted, completed, finalizing, expired and unsupported rounds are not advertised as resumable.

Legacy technical rounds have no persisted server deadline; their existing UI timer is not a server-enforced limit. Phase A does not invent one. New per-block activation/deadline policy and draft recovery remain Phase B work.

## Observed verification

All checks used installed dependencies and offline environment settings. No packages, remote assets or repository refs were downloaded. API checks below used FastAPI TestClient; they were not HTTP requests to a running server.

Final full backend suite (`pytest tests/ -q`, with the inherited report-writing test's output restored afterward):

```text
361 passed, 1 skipped, 8 warnings in 41.04s
Preserved the research report after its inherited test.
```

The skipped test is `test_unique_skill_url_constraint_sqlalchemy`: `DATABASE_URL` is not set. No database configuration or migration was changed for this check.

Final targeted Phase A API checks:

```text
7 passed in 4.47s
```

These include signup, login, starting a DBMS MCQ session, seeing its resumable summary, submitting a blank answer, seeing a measured zero in history, and fetching the existing report. The full inherited suite also exercises supported technical/MCQ/SQL flows and their security contracts.

Frontend `npm --offline test`:

```text
# tests 33
# pass 33
# fail 0
# skipped 0
```

`npm --offline run build -- --outDir /private/tmp/interviv-phase-a-build`:

```text
✓ 2869 modules transformed.
✓ built in 9.49s
```

The build retains the existing warning for a chunk above 500 kB (face-api). The external temporary output directory is deliberately not emptied, preserving any project build output.

`scripts/scoring_regression.py` still exits 1 with the same two inherited guard-label mismatches:

```text
gibberish          6.06  [0, 25]  repetition/gibberish           FAIL
keyword_stuffing  10.00  [0, 40]  gibberish/keyword_stuffing     FAIL
2/8 case(s) failed.
```

Both scores remain within their expected bands. The protected scorer was not changed.

The first inherited-suite run failed because the copied snapshot omitted `scripts/evaluate_length_ratio_heldout.py`; the unchanged dependency was included in `fcdb19f`, and the final suite above passes. An inherited baseline test writes the research report. Its output was restored to the committed bytes after each full run; the research study and its pending recruitment/date TODOs were not revised.

`git diff --check` passes. The scoped commit contains only Phase A files listed above; the snapshot commits are separate inherited evidence.

## Local startup result

Neither server remained running. The backend loaded cached weights and completed application startup, then the sandbox rejected its bind:

```text
INFO:     Application startup complete.
ERROR:    [Errno 1] error while attempting to bind on address ('127.0.0.1', 8000): operation not permitted
INFO:     Waiting for application shutdown.
INFO:     Application shutdown complete.
```

Frontend:

```text
error when starting dev server:
Error: listen EPERM: operation not permitted 127.0.0.1:5173
```

No network-permission request or bind workaround was attempted. Browser journeys, visible countdown behavior, responsive visual inspection and the session-report screenshot comparison are NOT VERIFIED.

## Manual browser check

Run each server in a separate local Terminal window. Keep each `cd` as its own command.

Backend:

```bash
cd "/tmp/interviv-publish/Downloads/mega 2 copy/.worktrees/phase-a-home-progress/interViv_best"
```

```bash
HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 HF_DATASETS_OFFLINE=1 HF_HUB_DISABLE_TELEMETRY=1 QUESTION_GENERATION_MODE=csv QUESTION_REQUIRE_LLM=false OPENAI_API_KEY= OPENROUTER_API_KEY= ADZUNA_APP_ID= ADZUNA_APP_KEY= PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
```

Frontend:

```bash
cd "/tmp/interviv-publish/Downloads/mega 2 copy/.worktrees/phase-a-home-progress/interViv_best/frontend"
```

```bash
npm --offline run dev -- --host 127.0.0.1
```

Open `http://127.0.0.1:5173/home`. Stop each server with `Ctrl+C` in its Terminal window. The current default in-memory backend loses temporary accounts/sessions when stopped.

1. Visit `/home` signed out; confirm sign-in, then Home. Register a new test account and verify the two starter actions and unmeasured Progress state.
2. Visit `/login?next=%2Fpractice%3Fmode%3Dcustom`; after login confirm the custom-practice screen. Repeat through the Sign up link to confirm it keeps the destination. External `next=https://example.test`, `next=//example.test`, `next=/%5cexample.test` and `next=/login` must return to Home.
3. Follow Home's interview, OA + SQL, problem-practice and custom-practice links. Confirm each lands on the corresponding existing setup. Verbal is not available on this base; do not interpret it as HR/free-text practice. Do not start Coding.
4. Start a supported session, return to Home, and use Continue practice. Confirm the same question/option order and existing MCQ/SQL deadline. Complete it; Continue must disappear unless a different eligible session exists. Open an owned interview deep link after login and verify server state is restored.
5. Choose and save a company/role. Confirm Home's target, Gap and Roadmap links update. A target selection alone must not turn unmeasured readiness into a numeric score.
6. Score a round, then inspect Progress history and the report link. A measured zero must remain `0%`. Sign into another account; the first account's history and Continue action must not appear.
7. Follow Resume check, Jobs, Coach and Resources. Search Resources for `DBMS`, then an unsupported skill to check its empty state. Keep external resource links closed during offline checks. Jobs must retain its sample-data/source labeling; Coach must use the local fallback with the command above.
8. Inspect at desktop, 768 px and 375 px widths. Use keyboard Tab/Enter on navigation, actions and target controls. Check readable layout and table scrolling without page-wide overflow.
9. Compare `/dashboard/:sessionId` with the inherited session report using the same data and viewport. Its appearance and separate dark layout must be unchanged. This visual comparison was not performed by the agent.

Phase B through E remain planned. No push, merge, database reset, dependency upgrade, coding execution or new research experiment is part of this delivery.
