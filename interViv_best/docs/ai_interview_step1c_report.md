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
