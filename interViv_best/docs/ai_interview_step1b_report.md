# Build step 1b — offline review fixes, 17 November 2026

Base: owner-accepted `6ebfac8`, on `fix/coverage-on-ws2`. This change addresses the seven routing review findings. Routing and live fetch remain default off. No live catalog fetch, completion, pilot, launcher, session integration or build-step-2 work was performed. No dependency, migration, scorer, evaluator, answer guard, assistance policy, eligibility, auth, local runner or session-route changes. Nothing pushed.

## Fixes and regression tests

All tests named below are in `tests/test_ai_interview_routing_review.py`. Parametrized cases are included in the final suite counts.

1. **Content eligibility and explicit owner selection.** `modules/interview_llm.py:58`, `:178`, `:192`, `:317`: real dispatch requires ordered `INTERVIEW_CONTENT_MODELS`, unless `INTERVIEW_ALLOW_CONTENT_DISCOVERY=true` explicitly permits discovery. Reject `openrouter/*`, rerankers, embeddings, non-text output, missing text input, invalid chat type, insufficient effective context (default 16,384, respecting a lower provider limit), nonzero/missing prices, or missing `structured_outputs`, `response_format` or `max_tokens`. The owner order is fully validated before transport. Offline injected overrides retain discovery for existing hooks. `scripts/list_interview_content_models.py:15` prints every eligible ID, effective context and supported parameters after the live/questions gate; it performs only the catalog GET and never completion/admission. Automatic inspection order is not a quality ranking; real dispatch is pinned by default.

   Tests: `test_catalog_probe_filters_tiny_reranker_router_and_keeps_chat_models`, `test_content_catalog_requires_text_chat_context_and_both_json_capabilities`, `test_configured_context_minimum_and_text_capable_input`, `test_real_content_dispatch_requires_owner_order_before_catalog_or_transport`, `test_real_content_dispatch_accepts_pinned_order_or_explicit_discovery`, `test_discovery_is_default_off_and_env_can_explicitly_enable_it`, `test_catalog_script_is_read_only_and_never_calls_completion`, `test_catalog_script_requires_live_flag_and_questions_consumer` (`:56`, `:76`, `:80`, `:89`, `:98`, `:110`, `:120`, `:132`).

2. **HTTP failures stop repeated sends.** `modules/llm_http_policy.py:64`: 400/422 content failures mean model unavailable with a five-minute model backoff; subsequent admission skips to the next candidate. 401/403 persists an authorization block until explicit operator clearance; 408 and every 5xx mean model unavailable. `modules/interview_llm_budget.py:187`, `:222` persists/enforces the blocks. No hidden retry: each new attempt re-enters admission and spends its own request. The first-model-400/422 then fourteen-admission probe sends once to that model and fourteen times to the next one.

   Tests: `test_reviewed_http_statuses_have_backoff_or_operator_stop` (400, 401, 403, 408, 422, 500, 504, 529), `test_rejected_content_model_does_not_repeat_for_fourteen_more_admissions` (400/422), `test_authorization_stop_survives_restart_days_and_credit_clear` (401/403) (`:143`, `:150`, `:169`). Existing 402/429 body/header tests remain unchanged.

3. **Network errors are typed deferrals.** `modules/interview_llm.py:373`: `URLError` becomes `DispatchDeferred(timeout|network_unavailable)` with a short account backoff. The reserved attempt stays counted, the lease is released, and exactly one usage event and one dispatch log entry are emitted. No raw URL error escapes the completion boundary, and no error body/personal text is logged.

   Test: `test_urlerror_is_a_typed_deferral_and_logs_once` (`:186`), covering connect timeout and network down through a mocked `urlopen`.

4. **Explicit returned-model acceptance.** `modules/interview_llm.py:212`, `:360`, `:392`, `:416`: compare exact vendor/model family after removing only a valid trailing `YYYYMMDD` or `YYYY-MM-DD` snapshot. A free request may report its base family without `:free`; a paid request may never report a free ID. Other versions, vendors, sizes and extra aliases fail. `Completion.model`, attribution and usage preserve the returned ID; `requested_model` is separate. Each admitted attempt logs both IDs (returned is null if no response). Billed tokens/returned IDs survive even a rejected family or truncation. Confirm this rule first in the future controlled live check below.

   Tests: `test_returned_model_family_rule_is_explicit`, `test_free_request_may_report_its_same_base_or_dated_family`, `test_dated_provider_slug_is_accepted_and_logged_with_requested_id`, `test_wrong_provider_family_still_logs_returned_id_and_billed_usage` (`:208`, `:212`, `:218`, `:236`).

5. **Offline journal inspection and explicit recovery.** `scripts/interview_llm_status.py:17`, `modules/interview_llm_budget.py:240`, `:245`, `:256`: default status reads counters, credit/access blocks, backoff deadlines, leases and scopes without creating a directory/lock/journal or changing bytes. Only explicit `--clear-credit-block` clears the persistent credit block; `--clear-access-block` separately clears 401/403 access. Neither refunds attempts or clears the other block. Missing accounts cannot be cleared. Configuration and commands are in `.env.example:149` and `docs/HANDOFF.md`.

   Tests: `test_status_script_default_is_byte_read_only_and_clear_is_explicit`, `test_status_script_access_clear_is_separate_from_credit_clear`, `test_status_script_does_not_create_a_missing_journal` (`:248`, `:263`, `:273`).

6. **Content-only pre-generation batch allowance.** `modules/interview_llm.py:112`, `:315`, `:329`, `modules/interview_llm_budget.py:161`, `:171`: a distinct batch ID and positive explicit `max_requests` replace interview N-based caps only inside the content batch. The allowance is immutable across restarts and shares daily/minute/pacing/concurrency admission. Conversation purposes are rejected before catalog or transport. `scripts/pregenerate_bundles.py:845`, `:960`, `:1034`, `:1098` requires `--max-requests`, supports stable `--batch-id`, uses cached generic role profiles, and stops on a typed deferral. Paid role extraction must be prepared separately. The existing protected-real-DB check remains first; it was not weakened. Dry-run/legacy flag-off behavior is retained.

   Tests: `test_batch_scope_exceeds_interview_cap_but_obeys_explicit_budget_and_restart`, `test_batch_scope_never_admits_conversation_purposes`, `test_batch_and_interview_share_daily_and_concurrency_limits`, `test_batch_scope_requires_a_positive_explicit_request_budget`, `test_pregeneration_uses_content_batch_scope_and_stops_at_request_cap`, `test_routed_pregeneration_requires_budget_and_cached_roles_before_dispatch`, `test_pregeneration_cli_forwards_explicit_batch_arguments` (`:283`, `:299`, `:306`, `:326`, `:332`, `:356`, `:366`). The scripted 30-request case uses existing offline overrides and fake generation only; no pre-generation run/pilot was launched.

7. **Lease expiry and completed-interview cleanup.** `modules/interview_llm_budget.py:100`, `:139`, `:204`, `:250`: leases store start/expiry and last for `max(120 seconds, request timeout + 60 seconds)`. Dead/expired owners release capacity without refunds. `finish_interview` removes detailed finished counters after active leases end, retaining only a compact closed-ID timestamp so pruning cannot create a fresh allowance. This explicit lifecycle API is tested; no completion hook was added to session routes.

   Tests: `test_lease_expiry_exceeds_request_timeout_and_expired_slot_is_reclaimed`, `test_finished_interview_is_pruned_without_refund_or_id_reuse` (`:375`, `:386`).

## Operator commands

Run from `interViv_best`. Scripts read exported settings/arguments; they do not load `.env` automatically. The status command is offline and read-only by default:

```bash
.venv/bin/python -m scripts.interview_llm_status --journal /absolute/path/limits.json --account default
```

After resolving credits, repeat with `--clear-credit-block`. After correcting credentials/access behind 401/403, use `--clear-access-block`. A credit block deliberately survives daily reset and restart. Default status displays stored state without expiring/pruning/resetting it; the next normal admission performs journal maintenance.

For a separately authorized catalog inspection only, this command prints ID/context/parameters and makes no completion call:

```bash
LLM_LIVE_FETCH=1 LLM_LIVE_CONSUMERS=questions .venv/bin/python -m scripts.list_interview_content_models
```

The catalog command was tested with injected fixtures only; it was not run against the live endpoint. Choose an ordered `INTERVIEW_CONTENT_MODELS` from its output. `INTERVIEW_ALLOW_CONTENT_DISCOVERY=false`, `ALLOW_PAID_CONTENT_FALLBACK=false` and the routing/live flags remain the defaults. Batch callers must choose an explicit attempt cap and reuse the reported batch ID when resuming; changing IDs does not bypass account limits.

## Controlled live check — planning only

Wait for the owner's go-ahead and credits above zero. Use an isolated scratch store/journal, pinned eligible content ID, and the ordinary routing gates; never the protected real DB. No live-check implementation or execution is included here.

1. **First confirm returned model IDs/family acceptance.** Make exactly one paid `role_skill_extraction` call. Record requested and returned IDs, confirm an exact/datestamped same-family result passes, and verify the structured dispatch log plus usage attribution. Stop on an unexpected/missing ID or any error; do not retry.
2. Make exactly one free `bundle_generation` call with generic metadata and the pinned free candidate. Do not run blind checking, audit, repair, retries, fallback or a pilot. The resulting unreviewed content is not servable.
3. For each call, report requested/returned ID, prompt/completion/total tokens, latency and the journal status before/after, including counters, blocks, backoffs and leases. Stop after these two completion attempts.

## Integrity and unchanged expectations

The protected DB is `/Users/praneetsharma/Downloads/mega 2 copy/interViv_best/local-data/interviv-local.sqlite3`. SHA256 before and after verification:

```text
before  93dfc4b9dd11ae4e974faa069eedd2f877f6f045c1c66cae90a2d61d108f2801
after   93dfc4b9dd11ae4e974faa069eedd2f877f6f045c1c66cae90a2d61d108f2801
```

`tests/fixtures/ai_routing_flag_off.json` is byte-identical to the accepted base:

```text
c7bd7382554fd751b3c8b83986b18fa2ba73250629d4d5e33538e4ff1d6ead1f
```

`test_flag_off_fixture_remains_byte_identical` (`tests/test_ai_interview_routing_review.py:400`) pins that hash. The existing flag-off transcript test still compares the live-off path to this unchanged fixture. AST comparison against `6ebfac8` confirms all **39 existing test function bodies and 75 assertion nodes** in `tests/test_ai_interview_routing.py` are unchanged. Its catalog helper only gains the context, text modalities and max-token capability metadata that the stricter validation requires. No other existing test file or expectation changed.

## Full-suite verification

| Run | Passed | Skipped | Failed | Result |
|---|---:|---:|---:|---|
| Initial full backend, sandbox | 1,370 | 6 | 14 | 234.33 s; one new validation bug and thirteen sysctl permission failures |
| Final full backend, approved outside-sandbox rerun | 1,384 | 6 | 0 | 133.91 s; exit 0 |
| Full frontend, `npm test` | 243 | 0 | 0 | 7.35 s; exit 0 |

The final backend contains **71 new review regression cases**, all passing, and all 80 original routing cases. Five skips require the local Piston executor/runtimes; one requires a configured SQL DATABASE_URL. Existing warnings remain (124). The initial new `[change6]` failure revealed that an empty list model type fell back to chat; validation now rejects it. All thirteen other initial failures originate in `backend/local_runner.py:172` / psutil's sandbox-denied `sysctl` memory inspection. The approved full offline rerun passed them without modifying the runner or existing tests. Final backend/frontend failing node IDs: **none**.

Every initial failing backend node ID (including the corrected new regression):

```text
tests/test_ai_interview_routing_review.py::test_content_catalog_requires_text_chat_context_and_both_json_capabilities[change6]
tests/test_local_runner.py::test_worker_runs_code_and_reports_ok
tests/test_local_runner.py::test_worker_enforces_limits[while True:\n    pass\n-timeout]
tests/test_local_runner.py::test_worker_enforces_limits[import time\ntime.sleep(30)\n-timeout]
tests/test_local_runner.py::test_worker_enforces_limits[x = []\nwhile True:\n    x.append(bytearray(8_000_000))\n-memory]
tests/test_local_runner.py::test_candidate_imports_and_file_access_are_refused
tests/test_local_runner.py::test_allowed_stdlib_and_numpy_work
tests/test_local_runner.py::test_candidate_failures_are_scored_outcomes[def two_sum(nums, target):\n    while True:\n        pass\n-timeout]
tests/test_local_runner.py::test_coding_round_runs_and_scores_without_docker
tests/test_ml_execution.py::test_style_findings_are_reported_but_not_scored
tests/test_ml_execution.py::test_candidate_errors_score_zero_with_a_kind[import numpy as np\ndef softmax(logits):\n    raise ValueError('nope')\n-runtime]
tests/test_ml_execution.py::test_candidate_errors_score_zero_with_a_kind[import numpy as np\ndef softmax(logits):\n    while True:\n        pass\n-timeout]
tests/test_ml_execution.py::test_candidate_errors_score_zero_with_a_kind[import numpy as np\ndef softmax(logits):\n    return [str(x) for x in logits]\n-invalid_output]
tests/test_ml_execution.py::test_candidate_errors_score_zero_with_a_kind[import numpy as np\nraise RuntimeError('top level')\n-load]
```

Full backend command (both runs; outside-sandbox permission differs, output filenames differ):

```bash
DATABASE_URL='' INTERVIV_DISABLE_DOTENV=1 AI_INTERVIEW_ROUTING_ENABLED=0 HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 LLM_LIVE_FETCH=0 JOBS_LIVE_FETCH=0 .venv/bin/python -m pytest -q -ra --junitxml=/private/tmp/interviv-step1b.lMm6B6/backend-final.xml
```

Full frontend: `npm test` from `frontend/`. Routing tests use injected catalogs, completion overrides or mocked `urlopen`; no live catalog or provider was reached. Python compilation and `git diff --check` passed. Raw logs/XML are in `/private/tmp/interviv-step1b.lMm6B6/`; this committed summary preserves the results and failure IDs across restarts.

## Diffstat by file

Against accepted base `6ebfac8`:

| File (under `interViv_best/`) | Added | Removed |
|---|---:|---:|
| `.env.example` | 17 | 2 |
| `docs/HANDOFF.md` | 8 | 6 |
| `docs/ai_interview_step1b_report.md` | 134 | 0 |
| `docs/design/ai_interview_plan.md` | 10 | 4 |
| `modules/interview_llm.py` | 134 | 26 |
| `modules/interview_llm_budget.py` | 99 | 11 |
| `modules/llm_http_policy.py` | 9 | 2 |
| `scripts/interview_llm_status.py` | 45 | 0 |
| `scripts/list_interview_content_models.py` | 38 | 0 |
| `scripts/pregenerate_bundles.py` | 52 | 4 |
| `tests/test_ai_interview_routing.py` | 3 | 1 |
| `tests/test_ai_interview_routing_review.py` | 402 | 0 |
