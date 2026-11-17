# Build step 1c — offline review fixes, 17 November 2026

Base: owner-accepted `aff1408`, on `fix/coverage-on-ws2`. All six review items are addressed offline. Default routing/live flags remain off. No live catalog fetch, completion, pilot, launcher, build-step-2 work, dependency, migration or protected-source change was made. The owner will push; nothing was pushed by the agent.

## Fix locations and tests

New tests are in `tests/test_ai_interview_routing_step1c.py`: **55 parametrized cases**, all passing in both the focused and full runs. Existing test files are unchanged.

1. **Transport exceptions.** `modules/interview_llm.py:411` catches `OSError` and `http.client.HTTPException` around the admitted completion path, after the HTTP error classifier. `RemoteDisconnected`, `ConnectionResetError`, `IncompleteRead` and `ssl.SSLError` become `DispatchDeferred(network_unavailable)` with a four-second account backoff. Existing timeout/URLError classification is retained. Attempts remain spent, leases are released, and the existing finally block emits one usage event and one dispatch log entry. No raw transport error or personal text is logged.

   Test: `test_transport_disconnects_are_typed_network_deferrals_once` (`:78`), each of the four errors both directly from `_chat_once` and from a mocked response read. Existing `test_urlerror_is_a_typed_deferral_and_logs_once` remains unchanged and passes.

2. **Validate successful-HTTP response bodies.** `modules/interview_llm.py:48`, `:439` validates JSON/object/choices/message/content before returning text. An error envelope raises a typed `ProviderResponseDeferred`; dispatch at `:402` reuses `classify_http_error` for a valid embedded 400–599 code (integer or three-digit string), including body metadata and response headers. Missing/unknown codes become `provider_error`. Non-JSON or malformed shapes become `invalid_response`. Null, empty or whitespace-only content becomes `empty_response`; it never becomes the string `None`. Valid billed prompt/completion/total usage and returned IDs travel with the deferral and are logged even on rejection. `modules/interview_llm_budget.py:232` gives provider/malformed/empty responses a five-minute model backoff; embedded codes retain their account/model-specific decisions. There is no automatic retry.

   Tests: `test_http_200_provider_error_uses_embedded_code_and_preserves_billing` (`:95`), `test_non_json_or_non_object_200_response_is_typed_and_backed_off` (`:116`), `test_malformed_200_choices_preserve_billed_usage` (`:127`), `test_empty_200_content_backs_off_model_and_never_returns_none_text` (`:135`), `test_response_validation_itself_returns_typed_error_with_usage` (`:147`). These assert single logging, preserved billed totals, blocks/backoffs and next-candidate admission for empty content.

3. **Exact catalog canonical identity.** `modules/interview_llm.py:237`, `:389` adds only the requested entry's exact `canonical_slug` to the existing family/date rule. A free request also permits that canonical slug with `:free` removed. The new exception does not authorize other dates of a reordered alias, other entries' slugs, additional aliases or a free returned ID for a paid request. No provider-specific alias is hardcoded. Requested/returned ID attribution and billed usage remain intact.

   Tests: `test_paid_dispatch_accepts_only_its_exact_catalog_canonical_slug` (`:170`), `test_free_dispatch_accepts_canonical_slug_and_its_free_stripped_form` (`:189`), `test_canonical_slug_does_not_enable_extra_aliases_or_cross_entry_matching` (`:198`). The fixture requests `anthropic/claude-haiku-4.5` and advertises `anthropic/claude-4.5-haiku-20251001` as its canonical slug.

4. **Null provider context.** `modules/interview_llm.py:209` treats null `top_provider.context_length` like an absent value and uses the model context. A supplied non-null limit still must be a positive integer and may lower the effective context.

   Tests: `test_null_provider_context_uses_model_context_and_remains_eligible` (`:206`), `test_non_integer_or_nonpositive_provider_context_is_still_rejected` (`:214`); existing lower-provider-limit tests also pass.

5. **Catalog completeness and inspection diagnostics.** `_fetch_catalog` at `modules/interview_llm.py:185` **does not follow pagination**: it makes one GET, then calls `catalog_rows` at `:172`. A `links.next` key, including null/empty values, fails closed with a clear pagination error and received-row count. Malformed links also fail closed. Router and script injection paths use the same validation, so they cannot accept a partial catalog. `scripts/list_interview_content_models.py:19`, `:29`, `:34` adds optional `--diagnostics`: total rows received, `links.next` presence, and Haiku's catalog ID/canonical slug, followed by the eligible free ID/context/parameter table. Default stdout remains compatible with the accepted script tests. No completion or journal is created by catalog inspection.

   Tests: `test_catalog_fetch_fails_closed_on_links_next_without_following_it` (`:222`), `test_paginated_injected_catalog_blocks_dispatch_before_admission` (`:234`), `test_catalog_script_reports_pagination_failure_without_eligible_output` (`:243`), `test_catalog_diagnostics_report_row_count_pagination_and_haiku_identity_without_completion` (`:251`). Pagination tests use mocked GETs or injected catalogs, never the live catalog.

6. **Configuration disclosures.** `.env.example:136` says discovery sorts IDs, not quality; `:144` requires a confirmed **$10 lifetime purchase** before `OPENROUTER_FREE_HIGH_LIMIT_CONFIRMED` is set. The catalog command now shows `--diagnostics`. This is documentation only; defaults/admission limits did not change. Manual review confirmed both comments. Existing `test_settings_are_separate_default_off_and_have_no_fixed_free_ids` verifies the default-off/high-limit settings; discovery behavior is covered by the unchanged catalog-order tests. No comment-only runtime test was added.

## Controlled live check — gated, not performed

Do nothing live until **this step is committed and the owner explicitly confirms credits above zero**. Use a scratch store and journal outside the repo, never the protected DB. Keep paid-content fallback and discovery disabled for the check. No live-check runner or pilot was added in this slice.

0. Run `scripts/list_interview_content_models --diagnostics` **once**, with the live/questions gate enabled. It makes a catalog GET only. Report total rows received, whether `links.next` was present, eligible free IDs, and Haiku 4.5's catalog ID/canonical slug. On pagination/completeness failure, report the error/count and stop. Otherwise **stop for the owner to choose ordered `INTERVIEW_CONTENT_MODELS`**; do not select models or make a completion before that reply.
1. After the owner names the models, make **one paid `role_skill_extraction` attempt**, no retry. Confirm requested/catalog-canonical/returned IDs and report prompt/completion/total tokens, latency and journal state before/after. Stop on any error or rejected identity.
2. Make **one free `bundle_generation` attempt**, with generic metadata and the first owner-pinned model explicitly selected. Use the routed completion boundary directly so no generation/check orchestration can add blind check, audit, repair, retry or fallback. Report the same IDs/usage/latency/journal fields. Stop after this call; nothing generated is servable.

The catalog command above is planning only, not an instruction executed during Step 1c. All fixtures and mock provider identities in the tests are offline data.

## Integrity

Protected DB: `/Users/praneetsharma/Downloads/mega 2 copy/interViv_best/local-data/interviv-local.sqlite3`.

```text
SHA256 before  93dfc4b9dd11ae4e974faa069eedd2f877f6f045c1c66cae90a2d61d108f2801
SHA256 after   93dfc4b9dd11ae4e974faa069eedd2f877f6f045c1c66cae90a2d61d108f2801
```

The accepted flag-off fixture `tests/fixtures/ai_routing_flag_off.json` remains byte-identical:

```text
c7bd7382554fd751b3c8b83986b18fa2ba73250629d4d5e33538e4ff1d6ead1f
```

All existing test files/assertions, including the accepted Step 1b catalog fixture metadata, are unchanged from `aff1408`. The existing flag-off transcript and fixture-hash tests pass. The owner older-branches block remains verbatim directly above BUILD ORDER in `docs/HANDOFF.md`. No scorer, evaluator, guard, assistance policy, eligibility, auth, local runner or session-route source changed.

## Full-suite verification

| Run | Passed | Skipped | Failed | Result |
|---|---:|---:|---:|---|
| Focused routing suites | 206 | 0 | 0 | 6.80 s; exit 0 |
| Full backend | 1,439 | 6 | 0 | 127.98 s; exit 0 |
| Full frontend | 243 | 0 | 0 | 7.59 s; exit 0 |

**Every failing node ID: none**, for focused routing, full backend and full frontend. The full backend contains all 55 new Step 1c cases plus the accepted 151 earlier routing cases. Five skips require local Piston runtimes; one requires a configured SQL DATABASE_URL. Existing warnings: 124.

The full backend used approved outside-sandbox execution because the accepted Step 1b run had already established that the sandbox denies psutil's sysctl inspection in existing runner tests. No failing sandbox rerun was repeated in Step 1c, and no runner/test changes were needed. Real outbound calls remain blocked by test fixtures; all new HTTP/catalog cases use overrides or injected fixtures. No live catalog was fetched.

Commands from `interViv_best` (frontend command from its `frontend/` directory):

```bash
DATABASE_URL='' INTERVIV_DISABLE_DOTENV=1 AI_INTERVIEW_ROUTING_ENABLED=0 HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 LLM_LIVE_FETCH=0 JOBS_LIVE_FETCH=0 .venv/bin/python -m pytest tests/test_ai_interview_routing.py tests/test_ai_interview_routing_review.py tests/test_ai_interview_routing_step1c.py -q --tb=short --junitxml=/private/tmp/interviv-step1c.b8NAYM/focused.xml
DATABASE_URL='' INTERVIV_DISABLE_DOTENV=1 AI_INTERVIEW_ROUTING_ENABLED=0 HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 LLM_LIVE_FETCH=0 JOBS_LIVE_FETCH=0 .venv/bin/python -m pytest -q -ra --junitxml=/private/tmp/interviv-step1c.b8NAYM/backend.xml
npm test
```

Python compilation and `git diff --check` passed. Raw logs/XML are at `/private/tmp/interviv-step1c.b8NAYM/`; this committed report preserves the results across restarts.

## Diffstat by file

Against accepted base `aff1408`:

| File (under `interViv_best/`) | Added | Removed |
|---|---:|---:|
| `.env.example` | 3 | 2 |
| `docs/HANDOFF.md` | 6 | 6 |
| `docs/ai_interview_step1c_report.md` | 93 | 0 |
| `docs/design/ai_interview_plan.md` | 8 | 4 |
| `modules/interview_llm.py` | 88 | 19 |
| `modules/interview_llm_budget.py` | 2 | 1 |
| `scripts/list_interview_content_models.py` | 15 | 4 |
| `tests/test_ai_interview_routing_step1c.py` | 263 | 0 |

## Step 1d — terminal pagination links, 17 November 2026

Base: accepted `fe7f1a0`. This addendum supersedes the earlier null/empty pagination rule and the credit gate for catalog inspection only. Completion calls remain unauthorized until the owner's credit confirmation. No pilot, build step 2, migration, dependency, protected-source change, launcher or push.

`modules/interview_llm.py:179` now accepts `links.next:null` and `links.next:""` as a complete catalog. A non-empty next link and malformed links still fail closed; `_fetch_catalog` still makes only one GET and does not follow pages. `scripts/list_interview_content_models.py:38` now reports whether a links field/object and next key are present plus their JSON values, as required for the authorized read. It stores no raw catalog in the repo and makes no completion call.

### The one authorized existing expectation change

| Test | Old expectation | New expectation |
|---|---|---|
| `test_catalog_fetch_fails_closed_on_links_next_without_following_it` | `tests/test_ai_interview_routing_step1c.py:229` at `fe7f1a0`: all three values (URL, null, empty string) raise `RoutingError`. | `tests/test_ai_interview_routing_step1c.py:230`: null/empty return the original catalog; `:232` retains the error for a non-empty URL. |

The single-GET assertion is unchanged (old `:231`, current `:234`). AST comparison confirms all other pre-existing test functions/assertions are unchanged. Two new test functions add eight cases: `test_malformed_links_still_fail_closed` (`tests/test_ai_interview_routing_step1c.py:270`) and `test_catalog_diagnostics_report_link_presence_and_values` (`:279`). The latter checks absent/empty/terminal link metadata without network or a journal.

### Step 1d verification

| Step 1d run | Passed | Skipped | Failed | Result |
|---|---:|---:|---:|---|
| Focused routing | 214 | 0 | 0 | 7.55 s; exit 0 |
| Full backend | 1,447 | 6 | 0 | 150.16 s; exit 0 |
| Full frontend | 243 | 0 | 0 | 9.12 s; exit 0 |

Failing node IDs in all three runs: **none**. The six skips and 124 warnings have the same causes as Step 1c. Backend ran offline with the previously approved outside-sandbox sysctl access; all new catalog cases were mocked/injected. Python compilation and `git diff --check` passed. Logs/XML: `/private/tmp/interviv-step1d.kqX5sM/`; these committed counts survive restart.

Full backend command (frontend: `npm test` from `frontend/`):

```bash
DATABASE_URL='' INTERVIV_DISABLE_DOTENV=1 AI_INTERVIEW_ROUTING_ENABLED=0 HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 LLM_LIVE_FETCH=0 JOBS_LIVE_FETCH=0 .venv/bin/python -m pytest -q -ra --junitxml=/private/tmp/interviv-step1d.kqX5sM/backend.xml
```

Protected real DB SHA256 before/after this slice:

```text
before  93dfc4b9dd11ae4e974faa069eedd2f877f6f045c1c66cae90a2d61d108f2801
after   93dfc4b9dd11ae4e974faa069eedd2f877f6f045c1c66cae90a2d61d108f2801
```

Flag-off fixture SHA256 remains `c7bd7382554fd751b3c8b83986b18fa2ba73250629d4d5e33538e4ff1d6ead1f` (byte-identical).

### Authorized next action after this commit

Run `LLM_LIVE_FETCH=1 LLM_LIVE_CONSUMERS=questions .venv/bin/python -m scripts.list_interview_content_models --diagnostics` once. Catalog GET only; no credits or candidate text needed. Keep diagnostic output outside the repo; do not save the raw catalog there. Report total rows, links/next presence and values, eligible free IDs with context/parameters, and Haiku's ID/canonical slug. Then stop for the owner to choose ordered `INTERVIEW_CONTENT_MODELS`. Do not make any completion call or push. No live read was made during the offline verification before this commit.

### Step 1d diffstat

Against accepted `fe7f1a0`:

| File (under `interViv_best/`) | Added | Removed |
|---|---:|---:|
| `docs/ai_interview_step1c_report.md` | 54 | 0 |
| `modules/interview_llm.py` | 2 | 2 |
| `scripts/list_interview_content_models.py` | 6 | 0 |
| `tests/test_ai_interview_routing_step1c.py` | 26 | 2 |

## Step 1e — certifi TLS context and URLError diagnostics, 17 November 2026

Base: accepted `3f60f25`. The framework Python 3.12 build backing `.venv` starts with an empty default CA store (`x509_ca=0`), while `certifi` (`requirements.txt:18`) provides 120 root CAs. No dependency, migration, existing test assertion, launcher, protected-source file or session route changed; completion calls remain unauthorized until the owner confirms positive credits.

1. **Shared certifi SSL context.** `modules/interview_llm.py:40` constructs one module-level `_SSL_CTX = ssl.create_default_context(cafile=certifi.where())` and passes it to `urllib.request.urlopen` in both `_fetch_catalog` (`:192`) and `_chat_once` (`:451`), matching `bundle_generator.py`, `question_bank.py`, `question_runtime.py` and `role_skills.py`.
2. **Safe `URLError` reason reporting.** `scripts/list_interview_content_models.py:19`, `:54` formats `urllib.error.URLError` with the underlying reason's exception class, integer `errno`, uppercase ASCII OpenSSL `reason` mnemonic and integer `verify_code` (or integer HTTP status for `HTTPError`). Non-exception string reasons, headers, keys, URLs and bodies are never read or printed.
3. **Offline regressions.** Two appended functions in `tests/test_ai_interview_routing_step1c.py` add six cases (`:290` `test_routed_boundary_uses_shared_certifi_ssl_context`; `:318` `test_catalog_script_prints_urlerror_reason_and_codes_without_secrets`). AST comparison against `3f60f25` confirms zero pre-existing test functions or assertions changed.

### Step 1e verification

| Step 1e run | Passed | Skipped | Failed | Result |
|---|---:|---:|---:|---|
| Focused routing | 220 | 0 | 0 | 16.15 s; exit 0 |
| Full backend | 1,453 | 6 | 0 | 301.64 s; exit 0 |
| Full frontend | 243 | 0 | 0 | 16.60 s; exit 0 |

Failing node IDs in all three runs: **none**. The six skips and 124 warnings have the same causes as Steps 1c–1d. Backend ran offline with all outbound calls mocked/blocked; Python compilation and `git diff --check` passed. Logs/XML: `/private/tmp/interviv-step1e.71GMTa/`.

Full backend command (frontend: `npm test` from `frontend/`):

```bash
DATABASE_URL='' INTERVIV_DISABLE_DOTENV=1 AI_INTERVIEW_ROUTING_ENABLED=0 HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 LLM_LIVE_FETCH=0 JOBS_LIVE_FETCH=0 .venv/bin/python -m pytest -q -ra --junitxml=/private/tmp/interviv-step1e.71GMTa/backend.xml
```

Protected real DB SHA256 before/after this slice:

```text
before  93dfc4b9dd11ae4e974faa069eedd2f877f6f045c1c66cae90a2d61d108f2801
after   93dfc4b9dd11ae4e974faa069eedd2f877f6f045c1c66cae90a2d61d108f2801
```

Flag-off fixture SHA256 remains `c7bd7382554fd751b3c8b83986b18fa2ba73250629d4d5e33538e4ff1d6ead1f` (byte-identical).

### Step 1e diffstat

Against accepted `3f60f25`:

| File (under `interViv_best/`) | Added | Removed |
|---|---:|---:|
| `docs/ai_interview_step1c_report.md` | 44 | 0 |
| `modules/interview_llm.py` | 5 | 2 |
| `scripts/list_interview_content_models.py` | 22 | 0 |
| `tests/test_ai_interview_routing_step1c.py` | 59 | 0 |

## Step 1f — reasoning control, truncation precedence and resilient content order, 17 November 2026

Base: accepted `3f787c8`. In the two-call controlled live check on `3f787c8`, paid `role_skill_extraction` (`anthropic/claude-haiku-4.5`) succeeded (`765` prompt / `404` completion / `0` reasoning tokens, `finish_reason="stop"`, `3,028 ms`), while free `bundle_generation` (`nvidia/nemotron-3.5-super-vl:free`) spent all `2,200` completion tokens in `message.reasoning` (`completion_tokens_details.reasoning_tokens=2200`, `finish_reason="length"`, `message.content=null`). Default flags remain off; no migration, dependency, launcher, session-route or protected-source file changed, and nothing was pushed.

1. **Content-lane reasoning control.** `modules/interview_llm.py:39`, `:75`, `:89`, `:266`, `:459`, `:565` reads both structured `entry["reasoning"]` metadata (`mandatory` / `required`, `default_enabled`, `supports_max_tokens`) when present and the live OpenRouter catalog fields quoted from the Step 1e `--diagnostics` read (`supported_parameters` containing `"reasoning"`, `"include_reasoning"` on all six eligible `:free` entries including `nvidia/nemotron-3.5-super-vl:free`, and `"reasoning_effort"` on the two effort-capable entries, plus `pricing.internal_reasoning` / `default_parameters.reasoning`):
   - Not mandatory: sends `reasoning={"enabled": False, "exclude": True}` and leaves `max_tokens` at the purpose budget.
   - Mandatory with `supports_max_tokens`: sends `reasoning={"max_tokens": INTERVIEW_CONTENT_REASONING_MAX_TOKENS, "exclude": True}` (default `1024`) and sets `max_tokens = purpose_budget + cap`, clamped strictly below `effective_context - prompt` (and `top_provider.max_completion_tokens` when positive).
   - Mandatory without a token budget: sends `reasoning={"effort": "low", "exclude": True}` when `"reasoning_effort"` is in `supported_parameters` (else `{"exclude": True}`) and adds the same clamped headroom.
   - Missing `"reasoning"` in `supported_parameters` or missing reasoning metadata: sends no `reasoning` field.
   - Conversation lane (`PERSONAL_PURPOSES`): never sends `reasoning` or alters `max_tokens`.

2. **Truncation before empty content and `reasoning_tokens` telemetry.** `modules/interview_llm.py:54`, `:519`, `:547`, `:589`, `:601` and `modules/interview_llm_budget.py:31`, `:234` check `choices[0].get("finish_reason") == "length"` ahead of `message.content` emptiness, raising `ProviderResponseDeferred("truncated")` → `DispatchDeferred("truncated")` with `reasoning_tokens` extracted from `usage.completion_tokens_details`, applying a 5-minute model backoff, logging `status="truncated"` / `error="truncated"` in `llm_usage`, and recording `reasoning_tokens` (integer count only, never reasoning prose) on `interview_llm_dispatch`.

3. **Resilient owner content order.** `modules/interview_llm.py:226`, `:404` skips absent or ineligible entries in `INTERVIEW_CONTENT_MODELS` with one structured warning (`interview_llm_content_candidate_skipped`) and a fixed reason code (`absent_from_catalog`, `disallowed_model_kind`, `unsupported_modalities`, `insufficient_context`, `nonzero_or_missing_price`, `missing_structured_params`). Duplicate IDs fail closed before catalog lookup; when zero eligible candidates remain (and `ALLOW_PAID_CONTENT_FALLBACK` is off), `content_candidates` fails closed with `RoutingError` and zero attempts spent.

### The one authorized existing expectation change

| Test | Old expectation | New expectation |
|---|---|---|
| `test_invalid_owner_id_anywhere_in_order_blocks_before_dispatch` | `tests/test_ai_interview_routing.py:111-119` at `3f787c8`: `content_models=(FREE_A, model)` raised `RoutingError` with `calls == []`. | `tests/test_ai_interview_routing.py:111-136`: `content_models=(model, FREE_A)` skips `model` with one structured warning + fixed reason code and dispatches `FREE_A`; `content_models=(model,)` still raises `RoutingError` before admission with zero attempts spent and no journal created. |

AST comparison across `test_ai_interview_routing.py`, `test_ai_interview_routing_review.py` and `test_ai_interview_routing_step1c.py` against `3f787c8` confirms no other pre-existing test function or assertion changed. Four appended test functions in `tests/test_ai_interview_routing_step1c.py` (`:384`, `:420`, `:466`, `:497`) add 17 offline cases.

### Step 1f verification

| Step 1f run | Passed | Skipped | Failed | Result |
|---|---:|---:|---:|---|
| Focused routing | 237 | 0 | 0 | 6.78 s; exit 0 |
| Full backend | 1,470 | 6 | 0 | 139.62 s; exit 0 |
| Full frontend | 243 | 0 | 0 | 10.10 s; exit 0 |

Failing node IDs in all three runs: **none**. Logs/XML: `/private/tmp/interviv-step1f.KQw6oi/`.

Protected real DB SHA256 before/after this slice:

```text
before  93dfc4b9dd11ae4e974faa069eedd2f877f6f045c1c66cae90a2d61d108f2801
after   93dfc4b9dd11ae4e974faa069eedd2f877f6f045c1c66cae90a2d61d108f2801
```

Flag-off fixture SHA256 remains `c7bd7382554fd751b3c8b83986b18fa2ba73250629d4d5e33538e4ff1d6ead1f` (byte-identical).

### Step 1f diffstat

Against accepted `3f787c8`:

| File (under `interViv_best/`) | Added | Removed |
|---|---:|---:|
| `.env.example` | 2 | 0 |
| `docs/ai_interview_step1c_report.md` | 55 | 0 |
| `modules/interview_llm.py` | 160 | 38 |
| `modules/interview_llm_budget.py` | 3 | 2 |
| `tests/test_ai_interview_routing.py` | 23 | 7 |
| `tests/test_ai_interview_routing_step1c.py` | 220 | 0 |

## Step 1g — Independent checker lane (offline)

Accepted base: `fc1c15d` (Step 1f). Blind-answer and check-audit no longer reuse the generation model when routing is on.

### What changed

1. **`INTERVIEW_CHECK_MODELS`.** Owner-ordered checker IDs with the same eligibility, skip-with-warning, and content-lane reasoning rules as `INTERVIEW_CONTENT_MODELS`. Real checker dispatch requires this list (or explicit discovery opt-in). `bundle_blind_answer` and `bundle_check_audit` resolve through `check_candidates` / `resolve_check_model`; generation and regeneration stay on content models. Content lane only; personal text remains forbidden.

2. **Same-vendor refusal.** Unless `INTERVIEW_ALLOW_SELF_CHECK=true` (default false), a checker whose vendor prefix (casefold before `/`) equals the active generator's is skipped with reason `same_vendor_as_generator`, or refused with `RoutingError` when no independent candidate remains. Generator identity comes from the batch/interview scope (`bundle_regeneration` or `bundle_generation`), else the configured content model.

3. **Actual checker on the bundle.** `resolve_checker_provider_and_model` returns the check lane. Step E records `interview_llm.actual_model("bundle_blind_answer", …)` on auto-check attribution, including model-backoff failover to the next independent checker. Scope seeds the author model before the blind check so vendor filtering sees the writer.

### Offline verification

| Step 1g run | Passed | Skipped | Failed | Result |
|---|---:|---:|---:|---|
| Focused routing | 241 | 0 | 0 | 7.18 s; exit 0 |
| Full backend | 1,474 | 6 | 0 | 139.73 s; exit 0 |
| Full frontend | 243 | 0 | 0 | 8.85 s; exit 0 |

```text
DATABASE_URL='' INTERVIV_DISABLE_DOTENV=1 AI_INTERVIEW_ROUTING_ENABLED=0 HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 LLM_LIVE_FETCH=0 JOBS_LIVE_FETCH=0 .venv/bin/python -m pytest tests/test_ai_interview_routing.py tests/test_ai_interview_routing_review.py tests/test_ai_interview_routing_step1c.py -q --tb=short --junitxml=/private/tmp/interviv-step1g/focused.xml
DATABASE_URL='' INTERVIV_DISABLE_DOTENV=1 AI_INTERVIEW_ROUTING_ENABLED=0 HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 LLM_LIVE_FETCH=0 JOBS_LIVE_FETCH=0 .venv/bin/python -m pytest -q -ra --junitxml=/private/tmp/interviv-step1g/backend.xml
cd frontend && npm test -- --run
```

Failing node IDs in all three runs: **none**. The six skips and 124 warnings have the same causes as Steps 1c–1f. Python compilation and `git diff --check` passed. Logs/XML: `/private/tmp/interviv-step1g/`.

Protected real DB SHA256 before/after this slice:

```text
before  93dfc4b9dd11ae4e974faa069eedd2f877f6f045c1c66cae90a2d61d108f2801
after   93dfc4b9dd11ae4e974faa069eedd2f877f6f045c1c66cae90a2d61d108f2801
```

Flag-off fixture SHA256 remains `c7bd7382554fd751b3c8b83986b18fa2ba73250629d4d5e33538e4ff1d6ead1f` (byte-identical).

AST comparison against `fc1c15d` confirms zero pre-existing test function bodies changed in `test_ai_interview_routing.py`, `test_ai_interview_routing_review.py`, or `test_ai_interview_routing_step1c.py`. Three appended tests (`:592`, `:694`, `:767`) add four offline nodes covering independent routing + actual-model recording, same-vendor refuse/allow/missing-list, and shared eligibility/reasoning/privacy rules.

### Step 1g diffstat

Against accepted `fc1c15d`:

| File (under `interViv_best/`) | Added | Removed |
|---|---:|---:|
| `.env.example` | 4 | 0 |
| `docs/ai_interview_step1c_report.md` | 51 | 0 |
| `modules/bundle_generator.py` | 8 | 1 |
| `modules/interview_llm.py` | 110 | 14 |
| `tests/test_ai_interview_routing_step1c.py` | 262 | 0 |

## Step 1h — Strict content-lane JSON schema (offline)

Accepted base: `a1d90d7`. The one-bundle live run rejected both generations at Step E.1 because calibration examples used `text` instead of `answer`. The prompt said "matching the schema below" and never included a schema or named the `answer` field.

### What changed

1. **Strict `json_schema` on the routed content lane.** `modules/interview_llm.py:75`, `:131`, `:149`, `:733`. `bundle_generation` and `bundle_regeneration` send `response_format.type=json_schema` with `strict: true` and the generation keys (`question` through `calibration_examples`). Calibration items require `author_level`, `expected_band`, `answer`. Follow-ups require `prompt`, `targets_concept`. Counts: required concepts 3–4, optional 1–2, misconceptions 1–2, follow-ups and calibration exactly 2. `bundle_check_audit` sends the same strict form with `root_cause`, `issue_type`, `missed_concepts`, `fixes`. `bundle_blind_answer` stays prose and sends no `response_format`. There is no fallback to `json_object` if a provider rejects the schema.

2. **Prompt skeleton.** `modules/bundle_generator.py:950` replaces "matching the schema below" with an explicit JSON skeleton naming every key, including calibration `answer` and follow-up `targets_concept` (must be a required-concept id). The same skeleton is on the regeneration prompt. `<= 35` and `>= 90` are unchanged, so `tests/test_ws2_batch_robustness.py:961` and `:975` stay true.

3. **`json_object` kept off the content schema.** Conversation `role_skill_extraction` under routing, and `bundle_generation` with routing off (legacy OpenRouter/OpenAI path), still send `{"type": "json_object"}`.

### Approved existing expectation changes

| Test | Old | New |
|---|---|---|
| `test_real_content_dispatch_accepts_pinned_order_or_explicit_discovery` | `tests/test_ai_interview_routing_review.py:107` at `a1d90d7`: `response_format == {"type": "json_object"}` | `:107`: `json_schema`, `strict` true, name `bundle_generation`, generation keys plus calibration `answer` and follow-up `targets_concept` |
| `test_checker_candidates_share_eligibility_skip_warnings_reasoning_and_privacy_rules` | `tests/test_ai_interview_routing_step1c.py:806` at `a1d90d7`: audit `response_format == {"type": "json_object"}` | `:806` keeps `max_tokens == 400 + 1024`; audit format is `json_schema`, `strict` true, name `bundle_check_audit`, keys `root_cause`, `issue_type`, `missed_concepts`, `fixes` |

AST comparison against `a1d90d7` confirms no other pre-existing test function changed. Two appended tests (`:838`, `:898`) cover E.1 rejection of a `text` calibration key, E.1 acceptance of `answer`, regeneration schema, and `json_object` on the conversation lane and the flag-off generation path.

### Step 1h verification

| Step 1h run | Passed | Skipped | Failed | Result |
|---|---:|---:|---:|---|
| Focused routing | 243 | 0 | 0 | 7.46 s; exit 0 |
| Full backend | 1,476 | 6 | 0 | 149.35 s; exit 0 |
| Full frontend | 243 | 0 | 0 | 10.63 s; exit 0 |

```text
DATABASE_URL='' INTERVIV_DISABLE_DOTENV=1 AI_INTERVIEW_ROUTING_ENABLED=0 HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 LLM_LIVE_FETCH=0 JOBS_LIVE_FETCH=0 .venv/bin/python -m pytest tests/test_ai_interview_routing.py tests/test_ai_interview_routing_review.py tests/test_ai_interview_routing_step1c.py -q --tb=line --junitxml=/private/tmp/interviv-step1h/focused.xml
DATABASE_URL='' INTERVIV_DISABLE_DOTENV=1 AI_INTERVIEW_ROUTING_ENABLED=0 HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 LLM_LIVE_FETCH=0 JOBS_LIVE_FETCH=0 .venv/bin/python -m pytest -q -ra --junitxml=/private/tmp/interviv-step1h/backend.xml
cd frontend && npm test -- --run
```

Failing node IDs in all three runs: **none**. The six skips and 124 warnings have the same causes as Steps 1c–1g. Python compilation and `git diff --check` passed. Logs/XML: `/private/tmp/interviv-step1h/`.

Protected real DB SHA256 before/after this slice:

```text
before  93dfc4b9dd11ae4e974faa069eedd2f877f6f045c1c66cae90a2d61d108f2801
after   93dfc4b9dd11ae4e974faa069eedd2f877f6f045c1c66cae90a2d61d108f2801
```

Flag-off fixture SHA256 remains `c7bd7382554fd751b3c8b83986b18fa2ba73250629d4d5e33538e4ff1d6ead1f` (byte-identical).

### Step 1h diffstat

Against accepted `a1d90d7`:

| File (under `interViv_best/`) | Added | Removed |
|---|---:|---:|
| `docs/ai_interview_step1c_report.md` | 51 | 0 |
| `modules/bundle_generator.py` | 41 | 7 |
| `modules/interview_llm.py` | 143 | 4 |
| `tests/test_ai_interview_routing_review.py` | 12 | 1 |
| `tests/test_ai_interview_routing_step1c.py` | 126 | 1 |
