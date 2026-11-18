# AI interview build step 1 — 17 November 2026

Base: accepted `3384dd0`, branch `fix/coverage-on-ws2`. **Routing/privacy only. Stop after this commit.** No session-route integration, build step 2, pilot or live provider call was made. All existing test files/expectations are unchanged; 80 new offline cases were added. No scorer/evaluator/guard/assistance-policy/eligibility/auth/local-runner implementation, migration or dependency changed.

## Implemented boundary

- `AI_INTERVIEW_ROUTING_ENABLED=0` by default. Separate `INTERVIEW_CONTENT_MODELS` and `INTERVIEW_CONVERSATION_MODEL`; legacy model variables do not select models in the enabled boundary.
- Content candidates come lazily from the OpenRouter catalog: explicit zero prompt/completion price, zero request charge when specified, and a `structured_outputs` capability. Automatic order is deterministic by ID, at most three candidates; an optional owner order is checked in full. There are no fixed free IDs. The catalog is cached for 300 seconds; refresh failure refuses dispatch. No catalog was fetched live during this work.
- Conversation purposes (including raw JD/role, resume, interviewer and debrief) are classified as personal independently of the optional caller marker. Only paid `anthropic/claude-haiku-4.5` is permitted. Marked personal text cannot enter the content lane. Guards run before transport/overrides and on every retry/fallback admission. Classification is an API/data-provenance contract, not an automatic PII detector: future adapters must mark personal inputs and supply only generic bundle inputs to content.
- Existing bundle and role-skill override hooks exercise the same enabled boundary; offline hooks require an injected catalog and must respect explicit consumer denial. Actual HTTP additionally requires the global live flag. `interviewer` is a recognized consumer; bundle/role dispatch uses `questions` and respects consumer selection. Live role retries recheck the consumer/global gate.
- The enabled boundary has no hidden HTTP retry. Error bodies, `limit_source`, `Retry-After` (seconds/date) and reset timestamps (seconds/milliseconds) classify daily quota, minute limits, in-flight budget, shared upstream capacity, credits/key exhaustion and unknown quota. A 402 or 429 can be a daily cap. Daily caps stop all free candidates until reset; model outages can select the next validated candidate on a later admission. Typed deferrals expose their reason/deadline to the future worker adapter; this slice does not wire queue/session progression.
- Paid content fallback defaults off and requires an explicit flag; it never bypasses exhausted credits. Actual attempts log model, purpose, tokens/latency and sanitized error category once using existing usage storage. Metadata contains no prompts, answers or resumes. Actual generation-model attribution is retained when routing falls back.

## Durable admission and restart

`RequestBudget` uses an atomic JSON journal with `flock`, file/directory fsync and a shared lock file. It is **single-host, across threads/processes**, not a distributed lock. All processes/keys for the same OpenRouter account must use the same absolute `INTERVIEW_LLM_STATE_PATH` and non-secret `INTERVIEW_LLM_ACCOUNT` label. The default path is under ignored `artifacts/`, outside the real DB; a `.sqlite3` journal path is refused.

Before each completion attempt: reserve one of **2** global slots; count the attempt durably; enforce a **20-in-60-seconds** sliding free window, **4 seconds** between content starts, and **50 free/day** (1,000 only with explicit confirmed entitlement). Failed attempts are not refunded. Catalog GETs carry no candidate text and are metadata discovery, not completion attempts/free-model quota requests.

Per-interview counters are **6N+1 content / N+2 conversation**, with N fixed at 2 or 4; changing N on the same ID is refused. Caps persist across process/day restarts. UTC midnight resets the daily free count; clock rollback cannot reset it. Dead process slots are reclaimed, while live/uninspectable owners retain their slots. Corrupt/unavailable storage blocks dispatch. Credit exhaustion remains blocked until the explicit operator clear action after credits are corrected; clearing it does not refund counters. A stable `interview_scope(id, N)` is required, so no unbudgeted route integration is silently enabled.

Flag-off compatibility deliberately retains the old transport's 402/429 retry behavior and explicit `allow_live=True` contract; existing assertions require them. The new enabled boundary has no `allow_live=True` bypass of the global gate. Offline overrides remain test-only dispatch substitutes. Other legacy LLM callers are not rerouted by this slice. Explicit consumer denial now also blocks the legacy bundle/role override paths, as requested.

## Design review applied

The separate content-plan call adds nothing necessary: paid setup already returns generic skill/topic/weight information, and deterministic allocation can turn confirmed skills into slots. **It is removed**, saving one content request per interview. Approved hard caps remain 17/31 total; they are ceilings, not planned consumption. Revised estimates at repo prices:

| N | Content attempts; input/output tokens | Conversation attempts; input/output tokens | Free content + paid conversation | Explicit all-paid content alternative |
|---|---|---|---|---|
| 2 | 4; 1,870 / 3,634.5 | 4; 5,649.33 / 1,749.33 | ~$0.014396 | ~$0.0344385 |
| 4 | 8; 3,740 / 7,269 | 6; 8,049.33 / 2,449.33 | ~$0.020296 | ~$0.060381 |

These are estimates, not new measurements; optional resume +1,500 input tokens adds ~$0.0015. The [design](design/ai_interview_plan.md) now records real preset estimate labels (15/22/48 rather than “30”), hiding the longer option without a practical track, weighted skill preselection/swaps, validated runtime model selection, the approved review/veto/quote rules, and Drill availability. **Before build step 2 changes any auto-checked measurement behavior, enumerate every affected existing assertion with file:line and old/new expectation, then stop for approval.** No such behavior or assertion was changed here.

## Tests (committed restart-safe summary)

All runs used `DATABASE_URL='' INTERVIV_DISABLE_DOTENV=1 AI_INTERVIEW_ROUTING_ENABLED=0 HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 LLM_LIVE_FETCH=0 JOBS_LIVE_FETCH=0`. New tests opt into routing only with fake catalog/transport/override hooks. Existing `tests/conftest.py` blocks unmocked network and real `.env` loading.

| Check | Result |
|---|---|
| New routing tests, final | **80 passed**, 5.61 s |
| Full backend, sandbox: `.venv/bin/python -m pytest -q -ra` | **1,304 passed, 6 skipped, 6 failed**, 105.74 s |
| Full backend, first approved rerun (before the final role-hook-format cases) | **1,310 passed, 6 skipped, 0 failed**, 127.53 s |
| Full backend, final approved rerun | **1,313 passed, 6 skipped, 0 failed**, 130.88 s |
| Full frontend: `npm test` | **243 passed, 0 failed, 0 skipped**, 7.35 s |

Every initial failure was the existing `PermissionError: [Errno 1] Operation not permitted (originated from sysctl() malloc 1/3)` through unchanged `backend/local_runner.py:172` / psutil. Exact failing node IDs (none failed in the approved rerun):

```text
tests/test_local_runner.py::test_worker_enforces_limits[while True:\n    pass\n-timeout]
tests/test_local_runner.py::test_worker_enforces_limits[import time\ntime.sleep(30)\n-timeout]
tests/test_local_runner.py::test_worker_enforces_limits[x = []\nwhile True:\n    x.append(bytearray(8_000_000))\n-memory]
tests/test_local_runner.py::test_candidate_failures_are_scored_outcomes[def two_sum(nums, target):\n    while True:\n        pass\n-timeout]
tests/test_ml_execution.py::test_buggy_variants_through_the_worker[binary_auc.v1:ignore_ties]
tests/test_ml_execution.py::test_candidate_errors_score_zero_with_a_kind[import numpy as np\ndef softmax(logits):\n    while True:\n        pass\n-timeout]
```

Skipped: five Piston cases require the local executor/runtimes; the learning-resource uniqueness test requires configured SQL storage. No runner/test workaround or expectation edit was used.

Coverage includes model-price/capability/ID validation, personal-purpose and explicit-marker refusals before dispatch, consumer/global gates, restart/daily/minute quotas, immutable interview caps, concurrent independent instances, a genuinely crashed subprocess reservation, storage failure, timeout/fallback admission, error-body privacy actual-model usage logging, and dict/JSON-string/list role-hook formats. The flag-off test drives real start/answer/session/feedback/report routes and existing override/cache hooks on temporary SQLite storage.

`tests/fixtures/ai_routing_flag_off.json` was captured at `3384dd0` **before application source edits**, using the newly added harness. SHA256: `c7bd7382554fd751b3c8b83986b18fa2ba73250629d4d5e33538e4ff1d6ead1f`. Time/identity fields are normalized and floating results compare to six decimals; scores, eligibility, questions and feedback remain compared. This fixture is committed, not regenerated by tests. Raw logs/JUnit are additionally at `/private/tmp/interviv-ai-step1.D4sWZU/`; this summary and all failure IDs survive independently of those logs.

## Real database integrity

Path: main checkout `interViv_best/local-data/interviv-local.sqlite3`.

```text
Before: 93dfc4b9dd11ae4e974faa069eedd2f877f6f045c1c66cae90a2d61d108f2801
After:  93dfc4b9dd11ae4e974faa069eedd2f877f6f045c1c66cae90a2d61d108f2801
```

No write to the real DB, live provider/model-catalog call, pilot, migration, dependency addition, `run_local.py` launch or push. Existing frontend and backend route files are unchanged from `3384dd0`.

## Diffstat by file against 3384dd0

| File | Added | Removed |
|---|---:|---:|
| `interViv_best/.env.example` | 18 | 0 |
| `interViv_best/docs/HANDOFF.md` | 8 | 4 |
| `interViv_best/docs/ai_interview_step1_report.md` | 92 | 0 |
| `interViv_best/docs/design/ai_interview_plan.md` | 20 | 20 |
| `interViv_best/docs/design/ai_interview_verification.md` | 2 | 0 |
| `interViv_best/modules/bundle_generator.py` | 45 | 15 |
| `interViv_best/modules/interview_llm.py` | 318 | 0 |
| `interViv_best/modules/interview_llm_budget.py` | 186 | 0 |
| `interViv_best/modules/llm_http_policy.py` | 79 | 0 |
| `interViv_best/modules/llm_outbound_gate.py` | 1 | 1 |
| `interViv_best/modules/role_skills.py` | 45 | 6 |
| `interViv_best/tests/ai_routing_harness.py` | 119 | 0 |
| `interViv_best/tests/fixtures/ai_routing_flag_off.json` | 1955 | 0 |
| `interViv_best/tests/test_ai_interview_routing.py` | 549 | 0 |
