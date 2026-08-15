# Contradiction miss error analysis

Target baseline: `semantic_nli_relevance`. Only gold contradictions missed by this baseline are categorized.

> Exploratory analysis only: deterministic categories are not human-validated semantic ground truth.

## Dataset counts

| Dataset | Gold contradictory | Detected | Missed | Analyzed |
| --- | ---: | ---: | ---: | ---: |
| beetle | 355 | 148 | 207 | 207 |
| scientsbank | 539 | 170 | 369 | 369 |

## Category counts

| Category | beetle | scientsbank | Total |
| --- | ---: | ---: | ---: |
| CAUSAL_REVERSAL | 0 | 0 | 0 |
| FACTUAL_REVERSAL | 0 | 1 | 1 |
| NEGATION | 0 | 0 | 0 |
| OTHER | 207 | 368 | 575 |
| PARTIAL_PLUS_FALSE_CLAIM | 0 | 0 | 0 |
| REFERENCE_CONFLICT | 0 | 0 | 0 |
| WRONG_ENTITY | 0 | 0 | 0 |
| WRONG_RELATION | 0 | 0 | 0 |

## Category provenance

| Source | Count | Meaning |
| --- | ---: | --- |
| deterministic_rule | 1 | Explicit lexical/syntactic rule matched; still requires research review. |
| manually_reviewed | 0 | No manual annotations were added in this run. |
| unresolved | 575 | Labeled `OTHER`; human review required. |

## Reproducibility manifest

| Field | Value |
| --- | --- |
| Run ID | `grader-lab-20260815T161440Z` |
| Generated at (UTC) | `2026-08-15T16:14:40.829288+00:00` |
| Git commit hash | `8758ecfed5171176add2d1905173aeac58ee914a` |
| Dirty worktree | `true` |
| Dataset versions/checksums/sources/licenses | `{"beetle":{"examples":"1258","license_status":"CC BY-SA 3.0; commercial use permitted with attribution/share-alike","sha256":"sha256:4ae5156dbbcb9a9afe25d050cc5ab37c341461bc342739c4de1bac4bddd831d9","source":"https://github.com/myrosia/semeval-2013-task7/tree/5157c69f914e8c581045c03e98f96398d40a91b8","status":"loaded","version":"semeval-2013-task7-5way@5157c69f914e8c581045c03e98f96398d40a91b8;Core/test"},"internal_perturbation":{"examples":"17","license_status":"interViv project material","sha256":"sha256:6a28c698b5e1d413c3be1074e4ee3b39eca7f6fafd938d758475e75d4e52eaed","source":"repository-local synthetic fixtures","status":"loaded","version":"grader-lab-perturbations-v1"},"ricechem":{"examples":"0","license_status":"pending_access_and_license_review","sha256":"not_present","source":"not supplied","status":"pending_access","version":"pending_access"},"scientsbank":{"examples":"5835","license_status":"CC BY-SA 3.0; commercial use permitted with attribution/share-alike","sha256":"sha256:5458a915f162bd52c6402ad1538d96691bc9161ca4c51e5f2c400bd6ffe554c2","source":"https://github.com/myrosia/semeval-2013-task7/tree/5157c69f914e8c581045c03e98f96398d40a91b8","status":"loaded","version":"semeval-2013-task7-5way@5157c69f914e8c581045c03e98f96398d40a91b8;Core/test"}}` |
| Baseline/model/checkpoint/classifier configuration | `{"interviv_current_scorer_guard":{"adapter":"interviv-current-v1","classifier_artifact":"sha256:2897c8cc6283cbdb4815a78182188ea60c17b39876feefa2d67919f065f16dd7","classifier_model":"LogisticRegression","classifier_version":"1.1.0","pipeline":"backend.scoring.pipeline@workspace_commit","prediction_count":"894","scoring_schema":"rubric_v1","semantic_applicable_count":"894","semantic_fallback_count":"0","semantic_fallback_reasons":"none","semantic_function_call_count":"894","semantic_model":"sentence-transformers/all-MiniLM-L6-v2","semantic_not_applicable_count":"0","semantic_revision":"1110a243fdf4706b3f48f1d95db1a4f5529b4d41","semantic_runtime":"semantic_all_applicable_predictions"},"lexical_similarity":{"algorithm":"content-token-f1-v1","checkpoint":"none"},"semantic_nli_relevance":{"embedding_model":"sentence-transformers/all-MiniLM-L6-v2","embedding_revision":"1110a243fdf4706b3f48f1d95db1a4f5529b4d41","load_error":"none","nli_component":"negation-and-antonym-heuristic-v1","runtime":"local_checkpoint"},"structured_llm_rubric_judge":{"execution":"deferred_zero_api_calls","structured_judge":"unscoped"}}` |
| Runtime versions | `{"numpy":"2.4.4","python":"3.12.4","scikit-learn":"1.8.0","sentence-transformers":"5.4.1","torch":"2.11.0"}` |

interViv scores in the CSV were recomputed through the corrected research adapter when `interviv_score_status=clean_semantic_run`; no prior fallback-only scores were reused.

## Deferred baselines

The structured LLM rubric judge is `deferred`; its interface has no client or transport and made zero API/network calls.

## Pending-access datasets

RiceChem is `pending_access`. No files were present, downloaded, or analyzed.

## Limitations

- Automatic rules detect only narrow surface forms; `OTHER` is intentionally preferred to speculative categorization.
- `deterministic_rule` is provenance, not a human gold label. Rows still need adjudication before paper claims or taxonomy-level error rates.
- The target is a pinned local embedding model plus a negation/antonym heuristic, not a trained NLI checkpoint.
- SciEntsBank and BEETLE are single-turn benchmarks; this report says nothing about follow-up resolution.
- The structured LLM rubric judge remains deferred and made zero API/network calls.
- RiceChem remains `pending_access` and was not analyzed.
