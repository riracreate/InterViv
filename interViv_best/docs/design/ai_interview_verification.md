# AI interview — verification and landing record, 17 November 2026

Read with [the design](ai_interview_plan.md). Source references below are relative to `interViv_best/` on `fix/coverage-on-ws2` at implementation merge `dd6e81c`, unless a branch is named. The working checkout is `/Users/praneetsharma/Downloads/mega 2 copy/.worktrees/coverage-ws2`. The main checkout's ignored `.env` and databases were inspected without importing the application or exposing credentials. SQLite connections used `mode=ro&immutable=1` and `PRAGMA query_only=ON`.

## Step 0 — landed, no push

| Item | Result |
|---|---|
| Main-folder backup branch | `codex/launcher-backup-20261117`, created from `10b81fa` |
| Launcher-only commit | `0d4df77`: the six requested files, including the existing tests, preserved without further feature edits |
| Separate handoff commit | `7084b67`: existing `docs/HANDOFF.md` edits preserved |
| Working line | Existing `fix/coverage-on-ws2` worktree, starting at `2d6025b` |
| Integration | Merge `dd6e81c`; `Practice.jsx` auto-merged with **no conflicts**; no manual resolution required |
| Older branches | Neither merged, deleted, reset nor edited; existing stash untouched |
| Main protected DB, before | `93dfc4b9dd11ae4e974faa069eedd2f877f6f045c1c66cae90a2d61d108f2801` |
| Main protected DB, after tests | `93dfc4b9dd11ae4e974faa069eedd2f877f6f045c1c66cae90a2d61d108f2801` |

No live model call, pilot, migration, dependency installation or `run_local.py` launch was made. Tests may import or exercise existing runner/config code; those files were not edited by this task. Changes already contained in the owner's `2d6025b` base are retained as requested.

### Full suites

All commands ran in the working checkout's `interViv_best/`, with empty `DATABASE_URL`, `INTERVIV_DISABLE_DOTENV=1`, `HF_HUB_OFFLINE=1`, `TRANSFORMERS_OFFLINE=1`, `LLM_LIVE_FETCH=0`, `JOBS_LIVE_FETCH=0`. Frontend commands ran in `frontend/`. Existing Python/Node dependency links were reused. `tests/conftest.py:21` removes real credentials/flags and `tests/conftest.py:118` blocks unmocked outbound traffic.

| Check | Result |
|---|---|
| `.venv/bin/python -m pytest -q -ra --junitxml=…/backend.xml`, sandbox | **1,224 passed, 6 skipped, 9 failed**, 111.63 s |
| Same complete suite, approved outside-sandbox rerun | **1,233 passed, 6 skipped, 0 failed**, 130.22 s; matches owner expectation |
| `npm test` | **243 passed, 0 failed, 0 skipped**, 22.39 s |
| `npm run build` | Exit **0**; Vite phase 75 s; existing Browserslist-age and large-chunk notices |

All nine initial failures were `PermissionError: [Errno 1] Operation not permitted (originated from sysctl() malloc 1/3)` through `backend/local_runner.py:172` / `psutil`. The sandbox blocks process RSS inspection; no runner or test was altered. The first Git permission attempt was declined; the user's later “continue” was followed by approved Git writes. The backend rerun likewise used the explicit tool approval, not a sandbox bypass.

Every failing node ID from the sandbox run (none failed in the approved rerun):

```text
tests/test_local_runner.py::test_worker_enforces_limits[while True:\n    pass\n-timeout]
tests/test_local_runner.py::test_worker_enforces_limits[import time\ntime.sleep(30)\n-timeout]
tests/test_local_runner.py::test_worker_enforces_limits[x = []\nwhile True:\n    x.append(bytearray(8_000_000))\n-memory]
tests/test_local_runner.py::test_candidate_failures_are_scored_outcomes[def two_sum(nums, target):\n    while True:\n        pass\n-timeout]
tests/test_ml_execution.py::test_buggy_variants_through_the_worker[layer_norm.v1:batch_loop]
tests/test_ml_execution.py::test_buggy_variants_through_the_worker[minmax_normalize.v1:unguarded_divide]
tests/test_ml_execution.py::test_buggy_variants_through_the_worker[softmax_stable.v1:batch_loop]
tests/test_ml_execution.py::test_buggy_variants_through_the_worker[softmax_stable.v1:naive_exp]
tests/test_ml_execution.py::test_candidate_errors_score_zero_with_a_kind[import numpy as np\ndef softmax(logits):\n    while True:\n        pass\n-timeout]
```

Skips: five Piston integration cases require the local executor/runtimes (`tests/test_coding_piston_integration.py:20`); one resource uniqueness case requires configured SQL storage (`tests/test_learning_resources.py:89`). Logs and JUnit: `/private/tmp/interviv-ai-plan.PVpGRx/{backend.log,backend.xml,backend-unsandboxed.log,backend-unsandboxed.xml,frontend.log,frontend-build.log}`. These are local verification artifacts, not repository content.

## Step 1 — findings a–h

### a. The gate is closed — confirmed, with scope qualification

In the **main** checkout, `.env:20` has `QUESTION_GENERATION_MODE=llm`, `.env:24` selects `openrouter`, `.env:27` has a nonempty OpenRouter key, `.env:28` selects `anthropic/claude-haiku-4.5`. `LLM_LIVE_FETCH` is absent throughout that file and absent from the inspecting shell. Its absence returns false at `modules/llm_outbound_gate.py:17`; question dispatch additionally requires a permitted consumer and mode at `modules/llm_outbound_gate.py:69`. The coverage worktree has no `.env` of its own. This verifies file/shell configuration, not the environment of any already-running external process.

Correction to a possible universal reading: bundle/admin paths can explicitly pass `allow_live=True` (`modules/bundle_generator.py:850`), and test overrides bypass the live flag (`bundle_generator.py:838`). Those were not invoked here. Future staged calls must honor both the global and consumer gates; the current bundle boundary checks only the global flag.

### b. 15 November usage — confirmed and made precise

`interViv_best/interviv.db` SHA256: `75f178c6131788f02e6e52a142119f2d54135e6c8f478cbe35e27c76f763611e`. Its `llm_usage_events` has **39 events**, all dated `2026-11-15`: 33 `bundle_generation`, one `bundle_blind_answer`, one `bundle_check_audit`, one `bundle_regeneration`, three `role_skill_extraction`. Of the 33 generations, **29 are errors containing HTTP 402; four are ok**. All successful calls used `anthropic/claude-haiku-4.5`. Usage records are written at `modules/bundle_generator.py:894` / `modules/llm_usage.py:70`; timestamps are UTC (`llm_usage.py:27`). Date filtering below uses the stored UTC date, not India-local calendar conversion.

Read-only SQL and results:

```sql
SELECT COUNT(*), SUM(status='ok'), SUM(status='error'),
       SUM(status='error' AND error LIKE '%402%')
FROM llm_usage_events
WHERE purpose='bundle_generation'
  AND SUBSTR(created_at,1,10)='2026-11-15';
-- 33 | 4 | 29 | 29

SELECT AVG(prompt_tokens), AVG(completion_tokens), AVG(total_tokens),
       AVG(latency_ms), MIN(latency_ms), MAX(latency_ms)
FROM llm_usage_events
WHERE purpose='bundle_generation' AND status='ok'
  AND SUBSTR(created_at,1,10)='2026-11-15';
-- 803 | 1616.25 | 2419.25 | 22791.5 | 9640 | 61161
```

Thus “about 23 s” is correct; this is a successful **generation-call** mean, not end-to-end validated-bundle latency. Failed generations are not in the successful-token denominator. A 402 in these paid-model logs does not establish that a free daily cap caused it.

### c. Stored bundles — confirmed; status belongs to the versions table

The main `local-data/interviv-local.sqlite3` contains **0** `question_bundles` and **0** `question_bundle_versions`; it has **no `llm_usage_events` table**. `interviv.db` contains **1** bundle identity and **1 rejected version**, with no reviewed/auto-checked inventory. `question_bundles` itself has no `status` column; status is on `question_bundle_versions` (`modules/bundle_store.py:152`). No migration was applied to the real DB.

```sql
SELECT COUNT(*) FROM question_bundles;
SELECT COUNT(*) FROM question_bundle_versions;
SELECT status, COUNT(*) FROM question_bundle_versions GROUP BY status;
-- Real DB: 0; 0; no status groups.
-- interviv.db: 1; 1; rejected | 1.
```

### d. Thin live path and unattached follow-ups — confirmed, with a correction

`modules/question_runtime.py:1043` tries stored bundle selection; on miss, `:1076` calls `build_question_prompt`, whose response schema at `:152` lacks required concepts and whose returned row at `:1104` has no bundle pin. No call to `generate_and_check_bundle` occurs in that live branch. The inline follow-up decider therefore stops at **`no_pinned_bundle`** (`modules/follow_ups.py:803`), before concept-gap matching. Plain string `followups` from the thin schema are not a substitute for concept-targeted bundle follow-ups (`follow_ups.py:629`).

Correction: stored bundle candidate payloads intentionally hide required concepts too; their pin resolves the full grading material server-side at `modules/bundle_scoring.py:95` and `:116`. It is the thin live row's missing pin/full bundle contract, not just the public absence of concepts, that prevents attachment. `generate_question` also skips its own bundle-selector block in reviewed-only mode (`question_runtime.py:1046`); strict reviewed routing is handled by callers. The future adapter must respect this rather than blindly replacing every caller.

Coverage changes still permit staged reference-free template fallback: `question_runtime.py:911`, `:941`; S2b leaves that turn unscored at `backend/routes/answer.py:891`. The new preparing state must replace this staged escape.

### e. Behavioural CSV — confirmed

`data/behavioural_questions_v1.csv` is absent in both main and coverage checkouts. Its default path is `modules/staged_flow.py:91`; missing-file loading returns `[]` at `:328`; the planner records `behavioural_bank_missing_or_empty` at `:633`. No bank was built. A generic non-technical **core skill** should not be confused with this separate optional HR stage.

### f. Bundle status and Elo — the owner rule is not enforced today

| Status | Normal serving today | Can an ordinary first core answer reach Elo/readiness today? | Required future behavior |
|---|---|---|---|
| `reviewed` | Yes | Yes, if non-null and independently eligible | Same, all existing exclusions retained |
| `auto_checked` | Yes when reviewed-only is false | **Yes**: no bundle-status check in the Elo path | Practice-only; no Elo/readiness contribution |
| `generated`, `rejected`, `draft`, `in_review`, `retired` | No through the normal selector | Not normally reached; no claim of a submission-time trust fence | Never serve; reject stale/invalid pins safely |

Evidence: `modules/bundle_selector.py:93` floors normal selection at reviewed/auto-checked and `:106` disables unchecked generated versions. `bundle_scoring.py:95` resolves content without testing its status. `backend/routes/answer.py:1076` computes ordinary eligibility, and `:1106` updates Elo based on that decision, non-null score and practice/review exclusions, **not bundle review status**. `modules/assistance_policy.py:298` excludes follow-ups but contains no reviewed-bundle trust rule. `backend/evidence_kind.py:168` filters primary rounds by score/eligibility, not review status.

This is visible in existing expectations: `tests/test_slice1_inline_follow_ups.py:1727` seeds `auto_checked` core content; `:1853` calls such a core answer eligible, and `:1895` includes the core mean in readiness. Those tests passed unchanged; this task does not silently redefine them. Every follow-up remains excluded regardless of parent trust. Add the trust restriction at orchestration/report evidence boundaries in a later slice without changing eligibility logic or scoring formulas.

### g. Model settings and HTTP errors — verified

| Call today | Model/provider resolution | Error handling |
|---|---|---|
| Thin question generation | `question_bank._llm_provider`: `QUESTION_LLM_PROVIDER`; `auto` picks OpenAI first when its key exists, then OpenRouter, else Ollama. OpenRouter model: `QUESTION_LLM_MODEL` → `OPENROUTER_MODEL` → `google/gemini-2.5-flash`. OpenAI uses its own default; Ollama has its own chain (`modules/question_bank.py:267`). | `question_runtime.py:508` catches HTTP errors generically; **402 and 429 both consume the generic retry loop**, normally 3 attempts (`:53`, `:555`), then return None/fallback. No credit-specific exception. |
| Bundle generation/regeneration | Same provider/model resolver (`bundle_generator.py:121`), with a fallback when it cannot resolve; no independent content/conversation separation. | `_post_json` (`:499`) treats **every 402** as `LLMCreditExhaustedError`, no retry (`:517`); **429** retries with delays 2/4/8/16 s, up to 5 attempts (`:525`). It does not distinguish daily from minute quota or obey reset headers. |
| Blind check and E.3 audit | `BUNDLE_CHECK_MODEL` → configured `OPENROUTER_MODEL` when applicable → generation model; `BUNDLE_CHECK_PROVIDER` can override provider (`bundle_generator.py:137`). Thus `QUESTION_LLM_MODEL` is not globally above the checker setting. | Same bundle transport. |
| Role/skill extraction | `role_skills.py:1575` uses the **same question provider/model**, not a dedicated role model variable; gated by the live flag at `:1561`. | `role_skills.py:1330` stops immediately on 402; `:1352` retries 429, 4 attempts with 2/4/8 s delays (`:1257`). No daily-cap classification. |

Background bundle processing catches the typed 402, requeues without burning the job attempt and aborts that worker pass (`modules/bundle_jobs.py:399`, `:517`). Generic 429/timeout failures instead consume job attempts (`:415`), in addition to transport retries. The batch script's 402-abort/cache-resume behavior is pinned by `tests/test_ws2_batch_robustness.py:352`; no batch was invoked here. `LLM_CONSUMERS` currently contains only questions/coach/narration (`modules/llm_outbound_gate.py:27`); role extraction and bundle dispatch currently consult the global flag rather than that consumer narrowing.

OpenRouter errors must be interpreted with structured source/body/headers rather than assuming that 402 always means permanent credit exhaustion or 429 always means transient RPM. The owner's daily-cap-as-either requirement is included in the design. Current official [rate-limit guidance](https://openrouter.ai/blog/llm-api-rate-limits/) also distinguishes free daily/minute limits, provider shared capacity, in-flight budget, key limits and credits. No provider request was sent; only public documentation/model pages were read.

### h. Older branches and reusable pieces — checked against the follow-up message

`git rev-list --count fix/coverage-on-ws2..codex/step0-slice1` = **8**; the corresponding count for `codex/policy-stage-a` = **1** (`307a6a5`). Both merge bases against the working line are **`dc5fdfed6f56c0f581760b8b81ca8c11cdb3d526`**. `f0ca6bb` is **not** an ancestor. Their policy code overlaps through copying, not ancestry; the step0 version has later amendments. The retained checkout for the file/line references below is `.worktrees/step0-slice1/interViv_best/`.

**Qualification to “only”**: these are the two relevant unmerged interview-policy/follow-up lines, not the only unmerged branches in the entire repository. `git branch --no-merged fix/coverage-on-ws2` also lists historical branches including `cins`, `codex/phase-b-block-practice`, `fix/keyword-stuffing-fpr` and `phase21-verbal-ability`. Nothing outside this task was merged or discarded. The owner's block is preserved verbatim in the handoff, with this qualification linked above it.

| Proposed pure reuse | Verified source and limits | Planned treatment |
|---|---|---|
| `answer_bands.py` | Imports seven `BAND_*` thresholds at `:7`; labels at `:18`, classifier at `:21`. `backend/config.py:15`–`:22` and `docs/policy_stage_a_report.md:19` explicitly label calibration `in_sample_n50`. | Use only as a restrictive action/escalation veto from deterministic diagnostics. No rescoring, readiness, model authorization or claimed out-of-sample validity. |
| `validate_system_prompt` | `modules/system_follow_ups.py:149`; max 300 at `:40`, exactly one `?`, feedback-pattern rejection and no rubric alias absent from the answer (`:157`, `:174`). It **does not explicitly reject every mention of “reference answer”** or paraphrased reference leakage. | Copy the pure validator and its needed helpers/constants, not the trigger registry or launcher. Add a reference-language/overlap wrapper and tests. Concept targeting alone is insufficient for safe follow-up text. |
| Adaptive policy/graph | `modules/adaptive_policy.py:129` rejects budgets outside 8–12; `:288` emits COVER/PROBE_HARDER/BRIDGE/END; `modules/adaptive_skill_graph.py:15` fixes 11 skills and `:32` rejects unknowns. Local observed-Elo math is at `adaptive_policy.py:187`, not a production scorer. | Adapt to 2/4 core slots and arbitrary job skills, initially COVER with tightly restricted PROBE_HARDER; no BRIDGE/unconfirmed skill routing. Never write its observed ratings to production Elo. |
| Go-live document | `docs/adaptive_policy_go_live_criteria.md:7` actually calls for ≥200 sessions/1,000 proposals, `:9` a 200-proposal two-reviewer sample plus ≥100 harder probes; `:18` ≥90% sensible, `:19` ≤5% false harder probes with a confidence-bound condition. | The proposed **100 interviewer turns**, zero invented quotes and zero leaked references are a **new preregistered adaptation**, not claims that the old document already contains them. Keep raw labels, adjudication, strata and denominators. No review/pilot now. |
| `FollowUpSection.tsx` | `frontend/src/components/dashboard/FollowUpSection.tsx:16`; presents supplied items as unscored, outside charts/averages (`:25`). No backend config import. | Adapt presentation to new debrief evidence. Do not copy its old backend predicates/report wiring wholesale. |
| Flag-off transcript harness | `tests/slice1_harness.py:1` and `:24`; real routes with stubbed bank/scorer, normalization includes digest/time/IDs. Assertion at `tests/test_slice1_system_follow_ups.py:1178`. | Reuse method, capture a reviewed **ws2** baseline; do not bless unrelated old snapshots as new truth or normalize away scores/eligibility. |

The working `backend/config.py:10` proceeds directly from frozen semantic constants into Settings (`:15`); `rg 'POLICY_|BAND_' backend/config.py` finds **no matches**. Only band/policy modules require those imports; the component and harness do not all depend on these constants. The step0 policy also imports a pure `non_follow_up_rounds` helper (`modules/adaptive_policy.py:21`) absent from the working line. Copy such a helper with the policy if needed, not the old route integration. `answer_bands.py` and `adaptive_skill_graph.py` are unchanged between the two older lines; `adaptive_policy.py` differs by 76 lines and config by 7, so choose provenance deliberately.

## Eight-commit comparison: product path superseded, not complete equivalence

| Commit unique to `codex/step0-slice1` | What the working line supplies / what remains distinct |
|---|---|
| `82dd9e8` pure policy, graph, bands | **Not superseded as reusable pure code**; these modules are absent on ws2. Working coverage distribution is `backend/models/blocks.py:132`; it is not the old policy. Reuse only after adaptation (finding h). |
| `9c9b5f2` policy documentation | Historical provenance/go-live protocol still useful; not a runtime gap to merge. See old `docs/policy_stage_a_report.md:19` and go-live `:3`. |
| `0a2e05d` system-trigger allocation | **Superseded for staged follow-up behavior** by actual concept-gap decisions (`modules/follow_ups.py:731`) and atomic splice (`:855`). Old `system_follow_ups.py:77` defaults to proposing nothing; no generic trigger registry is needed for the new interview. |
| `5ac1334` B1 review, prompt checks, races | Current eligibility/caps and prepared-row checks are at `follow_ups.py:664`, with conflict/idempotency coverage at `tests/test_slice1_inline_follow_ups.py:1005`. The old pure prompt validator remains reusable. No claim of identical old plan-serializer/transcript coverage. |
| `4c61354` B2 next-target isolation, snapshots, reports | **Not fully superseded.** Old next-target freezing/private initiator and separate report accounting differ. Current next-target choice is `backend/routes/answer.py:1619`; current snapshot exclusion handles inline bundle follow-ups (`modules/attempt_snapshot.py:147`, `:193`), not every old generic-system predicate. Do not import old route changes with new semantics. |
| `f0ca6bb` narrower candidate-touching predicate | **Not an ancestor and not a drop-in replacement.** Old `follow_ups.py:497` defines system-or-unreviewed, `:525` retains reviewed candidate follow-ups in history. Current inline detection is `follow_ups.py:974`; manual reviewed behavior is pinned by `tests/test_slice1_inline_follow_ups.py:1636`. Current snapshot replay (`attempt_snapshot.py:280`) lacks the old broad legacy-marker guard; it cannot be claimed byte-equivalent. |
| `dadb8d4` derived progress/report section | S1b client score/feedback masks (`backend/routes/answer.py:1968`), follow-up UI (`frontend/src/pages/Interview.jsx:1314`) and P1 outcomes (`modules/follow_ups.py:1154`) cover the intended current flow. Old mandatory-index payloads and separate `FollowUpSection.tsx:16` are additional presentation/accounting work, not already present in equivalent form. |
| `b3f5961` development preview launcher | **Obsolete for this direction.** Old `scripts/dev_system_follow_ups.py:44` emits a fixed generic preview; ws2 has real bundle-targeted follow-ups and a resumable staged screen (`frontend/src/lib/stagedSession.js:60`). Preserve the branch; do not run/copy this launcher. |

Working S1b/P1/S2 code and tests substantiate the actual replacement: `tests/test_slice1_inline_follow_ups.py:1491` masks inline score/breakdown; `:1723` tests deferred core feedback; `:1909` tests prompt-echo/three states; `modules/staged_flow.py:48` supplies presets, `:471` server-deferred feedback; `backend/routes/answer.py:891` supplies S2b generic-core null scoring. The product direction is served by ws2 without merging a divergent generic-follow-up stack. Finding h deliberately preserves the older pieces that are not superseded.

## Estimate worksheet (not measured future performance)

Price source: `tests/test_ws2_batch_robustness.py:1273`–`:1276` has Haiku prompt `$0.000001`/token and completion `$0.000005`/token. This is a repository fixture, not a current provider price query. Existing cost aggregation is `scripts/pregenerate_bundles.py:606`; pilot aggregation at `:640` is currently aggregate, so the per-model rejection table is proposed work.

| Call | Requests | Input/output tokens | Haiku-equivalent cost | Latency and evidence |
|---|---|---|---|---|
| Content plan | 1 | 700 / 300 | $0.002200 | Estimate, 3–6 s; no dedicated plan-call observation |
| Bundle generation | 1/core | 803 / 1,616.25 | $0.00888425 | Logged successful mean 22.7915 s, n=4; range 9.640–61.161 s |
| Blind answer check | 1/core | 132 / 201 | $0.001137 | Logged 3.950 s, n=1 |
| Check audit (failure path) | ≤1/affected core within cap | 891 / 226 | $0.002021 | Logged 3.904 s, n=1 |
| Regeneration (failure path) | ≤1/affected core within cap | 2,238 / 1,650 | $0.010488 | Logged 36.825 s, n=1; another blind check adds 132/201, $0.001137, ~3.950 s proxy |
| Role/setup extraction | 1 paid | 749.333 / 349.333 | $0.002496 | Logged mean 2.7477 s, n=3; resume-aware extraction is not measured |
| Interviewer turn | 1/core paid | 1,200 / 350 | $0.002950 | Estimate 2–5 s; entire call deadline 6 s, no retry |
| Debrief | 1 paid | 2,500 / 700 | $0.006000 | Estimate 6–12 s; proposed 15 s deadline then deterministic evidence view |
| Optional resume allowance | no extra request if combined with setup | +1,500 / 0 | +$0.001500 | Estimate; cap displayed input length, never silently truncate evidence quotes |

Only generation, blind answer, check audit, regeneration and role extraction have historical observations; the sample sizes are too small for p95 claims. Content-model token counts and service times are **paid-model proxies**, not free-model measurements. Free content cost is $0 under the listed free variants; tokens, daily requests and latency are still recorded. A failed request with no provider usage is recorded as unknown billed tokens/cost, not proved zero cost merely because the logger has zeros.

For N core slots, happy-path content = `1 + 2N` requests, `700 + 935N` input and `300 + 1817.25N` output; paid equivalent `$0.0022 + N×$0.01002125`. Conversation = `N + 2` requests, `3249.333 + 1200N` input and `1049.333 + 350N` output; `$0.008496 + N×$0.00295`. Thus N=2 totals **9 requests**, free-content cost ~$0.014396 / all-paid ~$0.0366385; N=4 totals **15 requests**, ~$0.020296 / ~$0.062581. Cache hits can eliminate content requests and cached setup; they do not eliminate the interviewer turn for each new answer.

One audit + regeneration + recheck adds **3 requests, 3,261 input / 2,077 output tokens**, ~$0.013646 paid-equivalent and ~44.679 s serial service time per affected slot. Every actual dispatch, including schema repair, retry and a fallback model, uses the global and per-interview counters. Hard limits override this illustrative retry path: `6N+1` content + `N+2` conversation = `7N+3` total, 17/31. Budget exhaustion stops preparation rather than raising these caps. No measured free latency or prospective pilot acceptance rate is claimed.

## Exact owner push commands — not executed

```bash
cd "/Users/praneetsharma/Downloads/mega 2 copy"
git push -u origin codex/launcher-backup-20261117
git push -u origin fix/coverage-on-ws2
```

Stop after the design/handoff documentation commit. Review questions are in design item 11; future implementation or pilot is not started.
