# Phase Z — browser verification, stopped at the AV/scoring boundary

Observed September 8–9, 2026. This is a documentation-only phase, not a product fix or a declaration that the backlog is clear.

Branch: `codex/phase-b-block-practice`. Verified base: `6ae830338ad9c3b5e2173ff75341ab397fb78b68` (Phase Y). Chain root: `0442493` (Phase A). This documentation commit follows that base without rewriting it; obtain its exact ID with `git log -1 --format='%H %s' -- interViv_best/docs/phase_z_browser_verification.md` from the worktree root. The final delivery message records the ID after creation.

## Stop condition and evidence boundary

The Phase Z request says: **“If any signal reaches scoring, readiness or mastery, STOP and report.”** Source inspection confirmed an AV label crosses the scoring interface:

1. `frontend/src/pages/Interview.jsx:748–757` derives engagement from collected video samples and includes `engagement_label`, confidence and delta in the answer payload.
2. `backend/routes/answer.py:562–571` passes `request.engagement_label` into `score_round` for the interview scoring path.
3. `modules/scoring/__init__.py:52–61` forwards it to `run_scoring_pipeline`.
4. `backend/scoring/pipeline.py:697–702` retains the label in scoring metadata.

This is **source-confirmed data plumbing**, not a demonstrated live camera-to-score effect. In the inspected pipeline the label is metadata; it is not an input to the numeric formula. No runtime influence on a numeric score, readiness or mastery was established. No such influence is claimed. Nevertheless, the literal instruction includes reaching scoring, so further browser exercises stopped when this path was confirmed. Resumption needs an owner ruling on this boundary; this phase did not edit protected files or submit an AV-derived signal to prove a score effect.

`VERIFIED` below means a rendered browser observation, with owner evidence explicitly attributed. `PARTIAL` names the remaining gap or observed failed behavior. `STILL BLOCKED` means no browser closure; rows stopped before being exercised say so, rather than implying a missing tool. API/source/test observations are corroboration only. Historical claims are identified separately.

## Environment and evidence

- Existing isolated worktree: `/Users/praneetsharma/Downloads/mega 2 copy/.worktrees/phase-b-block-practice`; app in `interViv_best`.
- New disposable SQLite database: `/tmp/interviv-phase-z.t4v9Os/browser.db`, upgraded to the existing head when created. The September 9 restart reused it to preserve real UI attempts. No user database was reset or migrated.
- Backend: `127.0.0.1:18001`; frontend: `http://127.0.0.1:5174`. Ports `18000` and `5173` were not disturbed.
- Two disposable accounts were created through signup: Phase Z One and Phase Z Two. Passwords and the disposable signing secret are intentionally absent from repository documentation. Attempts used for this report were generated through the UI, not inserted into tables.
- Offline settings: `HF_HUB_OFFLINE=1`, `TRANSFORMERS_OFFLINE=1`, `HF_HUB_DISABLE_TELEMETRY=1`, `JOBS_LIVE_FETCH=0`, `LLM_LIVE_FETCH=0`, `QUESTION_GENERATION_MODE=csv`, `QUESTION_REQUIRE_LLM=false`; API/telemetry keys blank. No installs, fetches or downloads.
- SemanticScorer: September 8 localhost health reported `scoring.mode: full`, sentence-transformer loaded and no fallback reason. The restart loaded weights again. This is operational evidence, not browser proof about score correctness.
- Default sandbox startup failed: Vite `Error: listen EPERM: operation not permitted 127.0.0.1:5174`; Uvicorn reached `Application startup complete` then `[Errno 1] ... error while attempting to bind on address ('127.0.0.1', 18001): operation not permitted`. Narrowly approved localhost server starts then succeeded. These were session permission failures, not dependency failures.
- Disposable evidence logs: `backend-local.log`, `backend-tests.log`, `frontend-tests.log`, `build.log` in `/tmp/interviv-phase-z.t4v9Os`. Browser DOM/screenshot observations are in the task transcript; no durable screenshot bundle is claimed. Temporary logs may not survive machine cleanup.

The agent did not trigger browser speech recognition or send real audio for server transcription. The owner's separate manual browser recording is not a network audit; an unchecked server-transcription box cannot establish that browser speech recognition sent nothing externally.

## Findings — all unfixed

| ID | Severity | Observed problem and limits |
|---|---|---|
| Z-F00 | P1 contract review | The AV engagement label enters the scoring interface and metadata, as traced above. Source-only finding; numeric score contamination is **not established**. Verification stopped under the user's boundary. |
| Z-F01 | P1 | Fresh typed rounds showed `00:00`: standalone ML configured for 20 minutes immediately displayed time-ended copy and disabled submission. OA/review also displayed zero while still accepting answers. The Coding header showed `02:00` while its round timer showed `00:00`. `new Date(expiresAt)` plus known timezone-naive SQLite reads is a hypothesis, not a confirmed root cause. |
| Z-F02 | P1 | Expired unscored Coding session report showed Overall `0`, `Needs Work · 0% avg score`, DSA `0%`, a remedial plan and all-rounds-completed copy. Progress correctly showed unavailable/unscored and unchanged measured aggregates. The report turns missing evaluation into poor-performance presentation. |
| Z-F03 | P1 | After account-one signout and account-two signup in the same browser, account two inherited the first account's Coding/DSA/one-problem/one-minute builder draft. It displayed Saving and survived reload. Presets/history did not leak in these observations. A shared `interviv-builder-draft-v1` local-storage key corroborates the draft issue. |
| Z-F04 | P2 | In a two-OA-block session, the result after Python showed the next DBMS question with the previous Python score/selection. Question/result association was wrong on screen. |
| Z-F05 | P2 | The next one-question OA block began with `1 answered`; choosing its answer produced `2 answered` for one question. Selection/count state carried between blocks. |
| Z-F06 | P2 | A genuinely stale second tab submitted after the first tab had scored. The backend returned answer `409` and later draft `409`, but the stale UI showed no comprehensible error/toast and remained editable. This reaches the previously untested server rejection path; the user-facing requirement fails. |
| Z-F07 | P2 usability | Coding opened media calibration with a blank/unplayable preview, `0%` and zero samples. Skip did hand off to the Coding editor. The current gate deliberately includes Coding in source; this is an observed unnecessary media gate/obstruction, not evidence that the Verbal/OA gate regressed. |
| Z-F08 | P2, intermittent | Failed-to-fetch/recovery messages appeared on builder target loading, ML source recovery and Learn. Learn briefly showed empty notebook copy alongside other panels containing misses; reload later recovered the notebook. Reproducibility and root cause remain unestablished. |
| Z-F09 | P2 copy | Practice hub advertised Python execution/hidden-test scoring despite the current unavailable execution service. No live candidate execution was demonstrated. |

## Calibration, capture and permission record

The initial DBMS interview `6bc3b464-3a14-46f9-bc57-4ac7176191b3` skipped calibration and reported blocked camera access. Microphone copy was first “permission not yet requested”, later “permission denied”. The question countdown visibly decreased through approximately `1:57`, `0:58`, `0:18`, `0:12`. That countdown observation does not clear the typed-round deadline defect.

The owner authorized the initial prompt check, reported **“I clicked Allow”**, and authorized **one** camera retry. The agent clicked Turn camera on once after that retry authorization; the automated browser remained blocked. The exact number of browser/OS permission dialogs is not recorded. At least **one actual Allow click** was owner-reported; readiness and retry confirmations are not counted as extra permission grants.

The owner subsequently tested manually and supplied a screenshot showing a live camera thumbnail, `RECORDING`, a 13-word answer draft, `ENGAGEMENT NOFACE · 0%`, `BASELINE SKIPPED`, and an unchecked `Use server transcription` box. This verifies mic/camera capture **by owner manual evidence**. It does not verify successful calibration, actual face detection inference, server Whisper transcription, or a score derived from that draft. No assessment of the person's emotions or identity is made.

On September 9, starting one Coding block (`5ab2f733-fe84-4864-a297-5301f22db9fc`) rendered **Calibration**: “Look at the camera with a relaxed expression for 10 seconds”, a blank preview reported as “Unable to play media”, `0%`, zero samples and a `02:00` header timer. Skip eventually opened the Two Sum editor. Initial snapshots lagged the transition; **Skip is not reported broken**. Ten-second calibration completion with real frames remains unverified. No permission grant was simulated or overridden.

## Complete browser backlog disposition

This inventory consolidates repeated PARTIAL/STILL BLOCKED rows in E–Y delivery documents and the F/G/H/review-guide carry-forwards. L is recorded in the K assessment; Y is represented by its commit and the current task rather than a separate Y delivery file. D items carried into F are included. Non-browser infrastructure exclusions remain explicit at the end.

| # | Item / origin | Status | Browser method, outcome and precise gap |
|---|---|---|---|
| 1 | Calibration renders / M,L | VERIFIED | Coding start rendered the screen described above. Rendering alone does not prove a working calibration. |
| 2 | Calibration completes with real frames / M | PARTIAL | Screen stayed at zero samples in the agent browser; successful ten-second completion was not observed. Owner screenshot says baseline skipped. |
| 3 | Calibration skip and handoff / M | VERIFIED | Skip from the rendered Coding calibration led to the Two Sum editor. |
| 4 | Detection runs and result destination / M | PARTIAL | Owner screenshot displays NOFACE; actual detector execution was not instrumented. Source confirms label-to-scoring metadata path Z-F00; further runtime testing stopped. |
| 5 | Real audio → local-server transcript / E.1,M | STILL BLOCKED | No real audio submitted to local Whisper. Owner recording used an unchecked server-transcription option, so it does not close this check. |
| 6 | Transcript storage, ownership and no score / E.1,M | STILL BLOCKED | No real server transcript to inspect. Static route behavior is insufficient for browser closure; Z-F00 hold. |
| 7 | permission_not_requested / G,H | VERIFIED | Rendered microphone “permission not yet requested” banner during initial interview. |
| 8 | permission_denied / G,H | VERIFIED | Rendered denied camera/microphone messages, including after owner-reported Allow and the authorized retry. |
| 9 | no_device / G,H | STILL BLOCKED | No actual missing-device state induced; documented browser tool exposed no device-emulation capability. |
| 10 | unsupported_browser / G,H | STILL BLOCKED | No unsupported-browser UI exercised; source/unit branch is not a browser result. |
| 11 | service_unavailable for transcription / G,H | STILL BLOCKED | No real transcription request to produce this UI state. Coding unavailable is not the AV state. |
| 12 | capture_failed mid-session / G,H | STILL BLOCKED | No controlled mid-capture hardware failure induced. |
| 13 | interrupted_recoverable / G,H | STILL BLOCKED | No controlled track interruption/recovery verified. |
| 14 | Real mic/camera / E,F,G,M | VERIFIED | Owner's manual screenshot and explicit confirmation; agent browser permission remained denied. |
| 15 | Recorded-media owner scope, second-user read/delete denial, deletion, no paths or transmission / E.2,M | STILL BLOCKED | Durable media pipeline is not implemented and no real stored artifact was exercised. No blanket retention/privacy claim from the absence of a UI. |
| 16 | `/av/capabilities` distinct states as rendered UX / F | PARTIAL | Two permission banners observed. API capabilities listing does not prove the other five browser states. |
| 17 | No AV score fabricated / F | PARTIAL | No live numeric influence demonstrated. Source boundary Z-F00 prevents a clean no-signal claim; owner recording alone cannot clear this. |
| 18 | Verbal/OA no media under granted permission / L | PARTIAL | OA screens showed no media chrome/prompt. The agent did not possess a proven working grant; Verbal under a working grant was not exercised in Z. |
| 19 | Mixed Verbal → Interview gates per block / L | STILL BLOCKED | Not completed in Z; requires the media-permission condition and resolution of Z-F00. |
| 20 | Standalone ML start, statement, constraints, starter / X,X.1 | VERIFIED | Session `012627c9-9f86-4b1d-b02e-1a0f6b2bc159`: scaled attention statement and Python starter rendered in the real browser. |
| 21 | ML editor editability and recovery / X,X.1 | PARTIAL | Editor/starter rendered; edits and persisted recovery were not verified. Recovery warning appeared (Z-F08). |
| 22 | ML submit stored, retry, unavailable UI, no score / X,X.1 | PARTIAL | Honest unavailable panel rendered. Immediate expiry disabled Submit (Z-F01); acceptance, exact stored source and retry not browser-verified. Earlier ASGI evidence remains historical. |
| 23 | Mixed flow reaches/stays at ML correctly / X,X.1 | STILL BLOCKED | Mixed ML flow not exercised before Z-F00 stop. Earlier ASGI evidence is not browser closure. |
| 24 | Real socket and browser capability / X.1 | VERIFIED | Approved localhost servers served actual signup and rendered ML/OA/Coding screens. The old sandbox limitation no longer blocks this phase. |
| 25 | Expired Coding unscored/unavailable and no average move / Y | PARTIAL | Real natural expiry: Progress correctly excluded the attempt and retained measured values. Session report failed with zeros and Needs Work (Z-F02). |
| 26 | Unsafe login next variants (`//…`, `/login`, encoded) / F | STILL BLOCKED | Not individually exercised before Z-F00 stop; no claim based on shared sanitizer tests. |
| 27 | Home Continue / deep-link restore / F | STILL BLOCKED | Full interrupted-plan resume not closed before stop. Cross-owner deep-link denial below is a separate check. |
| 28 | Keyboard-only full Home/Progress / F | STILL BLOCKED | Full Tab/Enter tour not completed; builder keyboard observations do not close it. |
| 29 | Pre-A report pixel comparison / F | STILL BLOCKED | No frozen pre-A screenshot baseline available. |
| 30 | Repeated block types / F | PARTIAL | Two OA blocks completed, Python then DBMS, aggregate 50%; result association and answered count failed (Z-F04/05). |
| 31 | Preset save/load/delete / F | PARTIAL | Saved “Phase Z repeated OA”; removed a block and keyboard-loaded the preset to restore two blocks. Delete was not exercised before stop. |
| 32 | Submitted/expired answer-draft rejection / F | PARTIAL | Stale submitted-round draft returned 409 in logs, without visible error. Expired-draft UI rejection not separately verified. |
| 33 | Duplicate submit rejection / F,G,H | PARTIAL | Two real tabs reached server 409 after first submit; visible error requirement failed (Z-F06). Completed session remained two rounds/50%, without another scored round shown. |
| 34 | Keyboard-only builder / F | PARTIAL | Keyboard remove, load and reorder worked. Add/repeat/full keyboard-only sequence not fully closed. |
| 35 | Session/preset/draft ownership / F | PARTIAL | Account two saw “You cannot access another user's session” for account one's session; preset absent. Builder draft leaked and survived reload (Z-F03). |
| 36 | Three Coding entry paths / G | VERIFIED | Z exercised missing custom-builder path → Two Sum editor. Standalone and Problems starts remain G's historical browser evidence, not repeated in Z. This row establishes rendering, not execution. |
| 37 | Unexpired Coding 503 retry rather than 409 / F | PARTIAL | Z exercised natural expiry and visible “This round is no longer active”, corroborated by coding/run 409. That is not the unexpired 503 retry check; historical first-submit evidence remains. |
| 38 | Target prefill does not override explicit topic / G | VERIFIED | Account two explicitly chose Python, then saved TCS/entry Software Engineer target. Start still rendered a Python OA question although role weights name other skills. |
| 39 | Target prefill ATS/Coach/Practice / D,F | PARTIAL | Practice target selection/save and explicit-topic case observed. ATS/Coach prefills not exercised before stop. |
| 40 | Resume upload → ATS selection / D,F | STILL BLOCKED | Not exercised before stop; no upload or selection claim. |
| 41 | Jobs sample labeling, including warm cache / D,F,N | STILL BLOCKED | Not exercised in Z before stop. O's historical browser verification remains separately attributed; no fresh closure claimed here. |
| 42 | Mistakes notebook / actual retry set / D,F | VERIFIED | Real missed Python question appeared in Learn. Create & start retry yielded five Python questions; one wrong and four blank completed at 0%. No synthetic attempts inserted. |
| 43 | Hint-assisted vs unassisted miss / D,F | PARTIAL | Real unassisted misses observed; no new hint-assisted pair before stop. G's historical assisted/unassisted browser evidence is preserved, not rerun. |
| 44 | Notebook/bookmark/target ownership / D,F | PARTIAL | Account two Learn showed no account-one misses, retry sets, schedule or bookmarks. Account one had no saved bookmark for a meaningful bookmark ownership test; target comparison after second-account save not completed. |
| 45 | Per-block results and next practice from real outcomes / G | PARTIAL | Learn retry suggestions used real misses. Repeated-round result association failed Z-F04; blanket result correctness is downgraded. |
| 46 | Progress/mastery unchanged after spaced review / I | VERIFIED | Browser before/after isolated correct review retained scored-session count, measured skill scores, rounds and Elo; Learn interval moved to three days. Detailed values below. |
| 47 | C.2/runner, E.2 durable AV, automatic diagrams, speech readiness, phase21 integration / E,K,U | STILL BLOCKED | Explicitly excluded or not implemented; no Docker spike, installation, integration or invented capability attempted. |

No additional interactive PARTIAL/STILL BLOCKED items were found in J/P/Q's offline audits beyond the carry-forwards above. U's infrastructure experiments are excluded by the task, not browser checks silently treated as passed. Prior VERIFIED items outside this backlog were not comprehensively re-audited.

## Reproduction records and before/after values

### Repeated OA and real duplicate rejection

Session `73bca963-a353-4b2d-93fc-e6a5e222a5c9`: builder configured two one-question OA blocks, saved/reloaded/reordered to Python then DBMS. Python tuple/list question: wrong option B submitted, score 0%. The stale second tab selected A after the first tab's submit and submitted; backend log records `POST /session/answer ... 409 Conflict`, then stale draft `PUT ... 409 Conflict`. Its rendered page had no visible rejection message.

The primary result displayed the next DBMS B+ tree versus hash-index question with the previous Python score and selected B. Next Round began with one answer counted; selecting correct A made the counter two for one question. Final UI: two rounds, Average 50%, final Elo 1204.57. These observations show the duplicate path was reached and expose the UI defects; server status alone does not clear the UX requirement.

### Review must not change measured mastery

Before review, Progress displayed two scored sessions and two measured skills: DBMS 53% (underlying meter 52.5), two rounds, Elo 1205; Python 0%, one round, Elo 1195. Elo change labels were DBMS +4.57 and Python −4.83; readiness Not measured.

Review `d74d8d51-8cfe-4908-9fab-646ea324bbfd` came from the actual missed tuple/list question. Correct answer completed at 100% with Elo 1195.17. Progress retained the same measured values and counts; the review history row was Not measured. Learn showed interval three days, last correct, next due 12/09/2026. A later measured retry changed measured history normally; it was not part of the isolated comparison.

### Natural Coding expiry and report contradiction

Builder created one Coding/DSA problem with one minute, session `5ab2f733-fe84-4864-a297-5301f22db9fc`. After calibration Skip, Two Sum, starter code, Run Examples and Submit Final Solution rendered. The actual deadline elapsed. Submit gave no visible feedback; Run Examples said “This round is no longer active.” Backend corroborated coding/run 409.

Progress: Coding 0/1 scored, one unscored/coding unavailable, Not measured; the prior measured values above remained unchanged. `/dashboard/5ab2f733-fe84-4864-a297-5301f22db9fc` instead displayed Overall 0, Needs Work/0%, one skill assessed, DSA 0%, “Rebuild DSA”, zero score layers and all-rounds-completed copy. No Coding execution or candidate score was generated by this check.

### Account isolation and explicit target

Account-one draft was Coding/DSA, one problem, one minute. After signout and real account-two signup, the builder showed that same draft with Saving; reload retained it. Account-one named preset was absent. Visiting its OA session displayed the owner-denial alert. Learn was empty for the second account.

Account two then selected Python and one OA question, selected and saved TCS / Software Engineer (entry), and started session `f3197d52-e27e-4f23-9c87-e582b3ac2270`. The question rendered was Python tuple/list. No answer was submitted by the agent before the stop. The session ID is corroborated by local request logs; the explicit-topic claim rests on the observed question UI.

## Validation and preservation

No source changes were made. Installed dependencies only. Backend tests used offline flags and `DATABASE_URL=''`; the frozen baseline file was byte-saved and restored in a finally block because the existing test rewrites it. The production build went to the disposable directory.

```text
$ .venv/bin/python -m pytest tests/ -q -p no:cacheprovider
539 passed, 1 skipped, 54 warnings in 101.60s (0:01:41)

$ npm --offline test
1..56
# tests 56
# pass 56
# fail 0
# cancelled 0
# skipped 0
# todo 0
# duration_ms 2588.476084

$ npm --offline run build -- --outDir /tmp/interviv-phase-z.t4v9Os/build
2876 modules transformed.
(!) Some chunks are larger than 500 kB after minification.
✓ built in 12.29s

$ .venv/bin/python -m alembic heads
20260908_0009 (head)
```

The backend skip is the inherited unset-DATABASE_URL check. Warnings include HTTP 422 naming and Alembic path_separator deprecations. The existing face-api chunk is 664.20 kB. These are not new failures. `scoring_regression.py` was not rerun in Phase Z: the request's 2/8 full and 4/8 degraded failures remain an **inherited baseline**, not a new measured result.

Frozen report remains 230 lines by `wc -l`, MD5 `5421f9f0fd6efad395666c545e5cf76a`. Final diff/status/ref checks and documentation commit are recorded at delivery. No tests were repeated just because documentation changed.

The unrelated untracked worktree-root `mega 2 copy.code-workspace` appeared during verification and was preserved. It is not part of Phase Z and is not to be staged or deleted. Consequently, the requested **unqualified-clean tree cannot be claimed**. The final report must show its exact status even when all tracked Phase Z documentation is committed.

Final pre-commit preservation check returned:

```text
refs/rescue/phase21-blob-06bc5daf 06bc5daf6d26cfced8744eb829d5350fc39d0b5f blob unchanged=True
refs/rescue/phase21-blob-65bf858a 65bf858acb49281e10b42410a952293b0c2c4490 blob unchanged=True
refs/rescue/phase21-blob-8405effd 8405effdaaa1004b2753686df24dac813478011c blob unchanged=True
refs/rescue/phase21-verbal-ui 381c7841c62c65fafec62c0a4b03b4abc5534c83 commit unchanged=True
stash@{0} de47735fd14fa500bf463134e1f9bfa670d1be2c On fix/offtopic-threshold-sweep: wip before keyword-stuffing branch
Frozen baseline MD5: 5421f9f0fd6efad395666c545e5cf76a
Frozen baseline newline count: 230
git diff --check: no output, exit 0
```

All four rescue objects were reachable via `git cat-file -t` and matched the starting snapshot; the entire stash list matched. Nothing was pushed, merged, reset, rebased or amended. The browser backlog is incomplete at the explicit stop condition; a handoff is not authorization to fix the product or continue past that condition.
