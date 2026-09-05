# interViv grader-lab report

> **Comparison status: INCOMPLETE.** The structured LLM rubric judge is explicitly `deferred`; no API or network call was made.

## Run manifest

| Field | Value |
| --- | --- |
| Run ID | `grader-lab-20260826T121933Z` |
| Generated at (UTC) | `2026-08-26T12:19:33.940397+00:00` |
| Git commit hash | `8758ecfed5171176add2d1905173aeac58ee914a` |
| Dirty worktree | `true` |
| Dataset versions | `{"beetle":{"examples":"1258","license_status":"CC BY-SA 3.0; commercial use permitted with attribution/share-alike","sha256":"sha256:4ae5156dbbcb9a9afe25d050cc5ab37c341461bc342739c4de1bac4bddd831d9","source":"https://github.com/myrosia/semeval-2013-task7/tree/5157c69f914e8c581045c03e98f96398d40a91b8","status":"loaded","version":"semeval-2013-task7-5way@5157c69f914e8c581045c03e98f96398d40a91b8;Core/test"},"internal_perturbation":{"examples":"17","license_status":"interViv project material","sha256":"sha256:6a28c698b5e1d413c3be1074e4ee3b39eca7f6fafd938d758475e75d4e52eaed","source":"repository-local synthetic fixtures","status":"loaded","version":"grader-lab-perturbations-v1"},"ricechem":{"examples":"0","license_status":"pending_access_and_license_review","sha256":"not_present","source":"not supplied","status":"pending_access","version":"pending_access"},"scientsbank":{"examples":"5835","license_status":"CC BY-SA 3.0; commercial use permitted with attribution/share-alike","sha256":"sha256:5458a915f162bd52c6402ad1538d96691bc9161ca4c51e5f2c400bd6ffe554c2","source":"https://github.com/myrosia/semeval-2013-task7/tree/5157c69f914e8c581045c03e98f96398d40a91b8","status":"loaded","version":"semeval-2013-task7-5way@5157c69f914e8c581045c03e98f96398d40a91b8;Core/test"}}` |
| Baseline model/checkpoint versions | `{"interviv_current_scorer_guard":{"adapter":"interviv-current-v1","classifier_artifact":"sha256:2897c8cc6283cbdb4815a78182188ea60c17b39876feefa2d67919f065f16dd7","classifier_model":"LogisticRegression","classifier_version":"1.1.0","pipeline":"backend.scoring.pipeline@workspace_commit","prediction_count":"7110","scoring_schema":"rubric_v1","semantic_applicable_count":"7110","semantic_fallback_count":"0","semantic_fallback_reasons":"none","semantic_function_call_count":"7110","semantic_model":"sentence-transformers/all-MiniLM-L6-v2","semantic_not_applicable_count":"0","semantic_revision":"1110a243fdf4706b3f48f1d95db1a4f5529b4d41","semantic_runtime":"semantic_all_applicable_predictions"},"lexical_similarity":{"algorithm":"content-token-f1-v1","checkpoint":"none"},"semantic_nli_relevance":{"embedding_model":"sentence-transformers/all-MiniLM-L6-v2","embedding_revision":"1110a243fdf4706b3f48f1d95db1a4f5529b4d41","load_error":"none","nli_component":"negation-and-antonym-heuristic-v1","runtime":"local_checkpoint"},"structured_llm_rubric_judge":{"execution":"deferred_zero_api_calls","structured_judge":"unscoped"}}` |
| Runtime versions | `{"numpy":"1.26.4","python":"3.12.4","scikit-learn":"1.8.0","sentence-transformers":"5.3.0","torch":"2.11.0"}` |

No number in this report should be cited externally without retaining this manifest.

## Benchmark-validated metrics

| Dataset | Baseline | Status | Metric | Value | n/N | pilot_synthetic | Notes |
| --- | --- | --- | --- | ---: | ---: | --- | --- |
| scientsbank | lexical_similarity | ready | grading_accuracy | 0.357669 | 2087/5835 | false |  |
| scientsbank | lexical_similarity | ready | macro_f1 | 0.245030 | — | false | Macro-average across labels present in gold data. |
| scientsbank | lexical_similarity | ready | off_topic_false_positive_rate | 0.140713 | 600/4264 | false | rule_FPR: reason==off_topic among gold on-topic answers. |
| scientsbank | lexical_similarity | ready | off_topic_detection_rate | 0.406747 | 639/1571 | false | rule_recall: reason==off_topic over gold irrelevant/non_domain. |
| scientsbank | lexical_similarity | ready | off_topic_precision | 0.515738 | 639/1239 | false | rule_precision: among reason==off_topic, share gold off-topic. |
| scientsbank | lexical_similarity | ready | outcome_recall | 0.406747 | 639/1571 | false | Primary: any guard cap among gold off-topic answers. |
| scientsbank | lexical_similarity | ready | outcome_false_positive_rate | 0.140713 | 600/4264 | false | Any guard cap among gold on-topic answers. |
| scientsbank | lexical_similarity | ready | outcome_precision | 0.515738 | 639/1239 | false | Among any-cap predictions, share that are gold off-topic. |
| scientsbank | lexical_similarity | ready | rule_recall | 0.406747 | 639/1571 | false | Alias of off_topic_detection_rate (diagnostic). |
| scientsbank | lexical_similarity | ready | rule_false_positive_rate | 0.140713 | 600/4264 | false | Alias of off_topic_false_positive_rate (diagnostic). |
| scientsbank | lexical_similarity | ready | rule_precision | 0.515738 | 639/1239 | false | Alias of off_topic_precision (diagnostic). |
| scientsbank | lexical_similarity | ready | contradiction_detection_rate | 0.000000 | 0/539 | false | Recall on gold contradictory answers. |
| scientsbank | lexical_similarity | ready | feedback_claim_count | 5835.000000 | — | false | Number of emitted feedback statements evaluated as claims. |
| scientsbank | lexical_similarity | ready | unsupported_feedback_claim_count | 0.000000 | — | false | Number of feedback claims without a backing scorer signal or adjudicated source. |
| scientsbank | lexical_similarity | ready | unsupported_feedback_rate | 0.000000 | 0/5835 | false | N/A when feedback_claim_count is zero; otherwise unsupported claims divided by all feedback claims. |
| scientsbank | lexical_similarity | ready | evidence_citation_completeness | 0.000000 | 0/5835 | false | Statements citing an explicit rubric.* or concept.* ID. |
| scientsbank | semantic_nli_relevance | ready | grading_accuracy | 0.399486 | 2331/5835 | false |  |
| scientsbank | semantic_nli_relevance | ready | macro_f1 | 0.335371 | — | false | Macro-average across labels present in gold data. |
| scientsbank | semantic_nli_relevance | ready | off_topic_false_positive_rate | 0.011961 | 51/4264 | false | rule_FPR: reason==off_topic among gold on-topic answers. |
| scientsbank | semantic_nli_relevance | ready | off_topic_detection_rate | 0.133673 | 210/1571 | false | rule_recall: reason==off_topic over gold irrelevant/non_domain. |
| scientsbank | semantic_nli_relevance | ready | off_topic_precision | 0.804598 | 210/261 | false | rule_precision: among reason==off_topic, share gold off-topic. |
| scientsbank | semantic_nli_relevance | ready | outcome_recall | 0.133673 | 210/1571 | false | Primary: any guard cap among gold off-topic answers. |
| scientsbank | semantic_nli_relevance | ready | outcome_false_positive_rate | 0.011961 | 51/4264 | false | Any guard cap among gold on-topic answers. |
| scientsbank | semantic_nli_relevance | ready | outcome_precision | 0.804598 | 210/261 | false | Among any-cap predictions, share that are gold off-topic. |
| scientsbank | semantic_nli_relevance | ready | rule_recall | 0.133673 | 210/1571 | false | Alias of off_topic_detection_rate (diagnostic). |
| scientsbank | semantic_nli_relevance | ready | rule_false_positive_rate | 0.011961 | 51/4264 | false | Alias of off_topic_false_positive_rate (diagnostic). |
| scientsbank | semantic_nli_relevance | ready | rule_precision | 0.804598 | 210/261 | false | Alias of off_topic_precision (diagnostic). |
| scientsbank | semantic_nli_relevance | ready | contradiction_detection_rate | 0.315399 | 170/539 | false | Recall on gold contradictory answers. |
| scientsbank | semantic_nli_relevance | ready | feedback_claim_count | 11670.000000 | — | false | Number of emitted feedback statements evaluated as claims. |
| scientsbank | semantic_nli_relevance | ready | unsupported_feedback_claim_count | 0.000000 | — | false | Number of feedback claims without a backing scorer signal or adjudicated source. |
| scientsbank | semantic_nli_relevance | ready | unsupported_feedback_rate | 0.000000 | 0/11670 | false | N/A when feedback_claim_count is zero; otherwise unsupported claims divided by all feedback claims. |
| scientsbank | semantic_nli_relevance | ready | evidence_citation_completeness | 1.000000 | 11670/11670 | false | Statements citing an explicit rubric.* or concept.* ID. |
| scientsbank | interviv_current_scorer_guard | ready | grading_accuracy | 0.373093 | 2177/5835 | false |  |
| scientsbank | interviv_current_scorer_guard | ready | macro_f1 | 0.245943 | — | false | Macro-average across labels present in gold data. |
| scientsbank | interviv_current_scorer_guard | ready | off_topic_false_positive_rate | 0.026735 | 114/4264 | false | rule_FPR: reason==off_topic among gold on-topic answers. |
| scientsbank | interviv_current_scorer_guard | ready | off_topic_detection_rate | 0.119032 | 187/1571 | false | rule_recall: reason==off_topic over gold irrelevant/non_domain. |
| scientsbank | interviv_current_scorer_guard | ready | off_topic_precision | 0.621262 | 187/301 | false | rule_precision: among reason==off_topic, share gold off-topic. |
| scientsbank | interviv_current_scorer_guard | ready | outcome_recall | 0.119032 | 187/1571 | false | Primary: any guard cap among gold off-topic answers. |
| scientsbank | interviv_current_scorer_guard | ready | outcome_false_positive_rate | 0.026735 | 114/4264 | false | Any guard cap among gold on-topic answers. |
| scientsbank | interviv_current_scorer_guard | ready | outcome_precision | 0.621262 | 187/301 | false | Among any-cap predictions, share that are gold off-topic. |
| scientsbank | interviv_current_scorer_guard | ready | rule_recall | 0.119032 | 187/1571 | false | Alias of off_topic_detection_rate (diagnostic). |
| scientsbank | interviv_current_scorer_guard | ready | rule_false_positive_rate | 0.026735 | 114/4264 | false | Alias of off_topic_false_positive_rate (diagnostic). |
| scientsbank | interviv_current_scorer_guard | ready | rule_precision | 0.621262 | 187/301 | false | Alias of off_topic_precision (diagnostic). |
| scientsbank | interviv_current_scorer_guard | ready | contradiction_detection_rate | 0.000000 | 0/539 | false | Recall on gold contradictory answers. |
| scientsbank | interviv_current_scorer_guard | ready | feedback_claim_count | 19453.000000 | — | false | Number of emitted feedback statements evaluated as claims. |
| scientsbank | interviv_current_scorer_guard | ready | unsupported_feedback_claim_count | 0.000000 | — | false | Number of feedback claims without a backing scorer signal or adjudicated source. |
| scientsbank | interviv_current_scorer_guard | ready | unsupported_feedback_rate | 0.000000 | 0/19453 | false | N/A when feedback_claim_count is zero; otherwise unsupported claims divided by all feedback claims. |
| scientsbank | interviv_current_scorer_guard | ready | evidence_citation_completeness | 1.000000 | 19453/19453 | false | Statements citing an explicit rubric.* or concept.* ID. |
| beetle | lexical_similarity | ready | grading_accuracy | 0.337838 | 425/1258 | false |  |
| beetle | lexical_similarity | ready | macro_f1 | 0.273984 | — | false | Macro-average across labels present in gold data. |
| beetle | lexical_similarity | ready | off_topic_false_positive_rate | 0.085418 | 99/1159 | false | rule_FPR: reason==off_topic among gold on-topic answers. |
| beetle | lexical_similarity | ready | off_topic_detection_rate | 0.727273 | 72/99 | false | rule_recall: reason==off_topic over gold irrelevant/non_domain. |
| beetle | lexical_similarity | ready | off_topic_precision | 0.421053 | 72/171 | false | rule_precision: among reason==off_topic, share gold off-topic. |
| beetle | lexical_similarity | ready | outcome_recall | 0.727273 | 72/99 | false | Primary: any guard cap among gold off-topic answers. |
| beetle | lexical_similarity | ready | outcome_false_positive_rate | 0.085418 | 99/1159 | false | Any guard cap among gold on-topic answers. |
| beetle | lexical_similarity | ready | outcome_precision | 0.421053 | 72/171 | false | Among any-cap predictions, share that are gold off-topic. |
| beetle | lexical_similarity | ready | rule_recall | 0.727273 | 72/99 | false | Alias of off_topic_detection_rate (diagnostic). |
| beetle | lexical_similarity | ready | rule_false_positive_rate | 0.085418 | 99/1159 | false | Alias of off_topic_false_positive_rate (diagnostic). |
| beetle | lexical_similarity | ready | rule_precision | 0.421053 | 72/171 | false | Alias of off_topic_precision (diagnostic). |
| beetle | lexical_similarity | ready | contradiction_detection_rate | 0.000000 | 0/355 | false | Recall on gold contradictory answers. |
| beetle | lexical_similarity | ready | feedback_claim_count | 1258.000000 | — | false | Number of emitted feedback statements evaluated as claims. |
| beetle | lexical_similarity | ready | unsupported_feedback_claim_count | 0.000000 | — | false | Number of feedback claims without a backing scorer signal or adjudicated source. |
| beetle | lexical_similarity | ready | unsupported_feedback_rate | 0.000000 | 0/1258 | false | N/A when feedback_claim_count is zero; otherwise unsupported claims divided by all feedback claims. |
| beetle | lexical_similarity | ready | evidence_citation_completeness | 0.000000 | 0/1258 | false | Statements citing an explicit rubric.* or concept.* ID. |
| beetle | semantic_nli_relevance | ready | grading_accuracy | 0.303657 | 382/1258 | false |  |
| beetle | semantic_nli_relevance | ready | macro_f1 | 0.277442 | — | false | Macro-average across labels present in gold data. |
| beetle | semantic_nli_relevance | ready | off_topic_false_positive_rate | 0.020708 | 24/1159 | false | rule_FPR: reason==off_topic among gold on-topic answers. |
| beetle | semantic_nli_relevance | ready | off_topic_detection_rate | 0.626263 | 62/99 | false | rule_recall: reason==off_topic over gold irrelevant/non_domain. |
| beetle | semantic_nli_relevance | ready | off_topic_precision | 0.720930 | 62/86 | false | rule_precision: among reason==off_topic, share gold off-topic. |
| beetle | semantic_nli_relevance | ready | outcome_recall | 0.626263 | 62/99 | false | Primary: any guard cap among gold off-topic answers. |
| beetle | semantic_nli_relevance | ready | outcome_false_positive_rate | 0.020708 | 24/1159 | false | Any guard cap among gold on-topic answers. |
| beetle | semantic_nli_relevance | ready | outcome_precision | 0.720930 | 62/86 | false | Among any-cap predictions, share that are gold off-topic. |
| beetle | semantic_nli_relevance | ready | rule_recall | 0.626263 | 62/99 | false | Alias of off_topic_detection_rate (diagnostic). |
| beetle | semantic_nli_relevance | ready | rule_false_positive_rate | 0.020708 | 24/1159 | false | Alias of off_topic_false_positive_rate (diagnostic). |
| beetle | semantic_nli_relevance | ready | rule_precision | 0.720930 | 62/86 | false | Alias of off_topic_precision (diagnostic). |
| beetle | semantic_nli_relevance | ready | contradiction_detection_rate | 0.416901 | 148/355 | false | Recall on gold contradictory answers. |
| beetle | semantic_nli_relevance | ready | feedback_claim_count | 2516.000000 | — | false | Number of emitted feedback statements evaluated as claims. |
| beetle | semantic_nli_relevance | ready | unsupported_feedback_claim_count | 0.000000 | — | false | Number of feedback claims without a backing scorer signal or adjudicated source. |
| beetle | semantic_nli_relevance | ready | unsupported_feedback_rate | 0.000000 | 0/2516 | false | N/A when feedback_claim_count is zero; otherwise unsupported claims divided by all feedback claims. |
| beetle | semantic_nli_relevance | ready | evidence_citation_completeness | 1.000000 | 2516/2516 | false | Statements citing an explicit rubric.* or concept.* ID. |
| beetle | interviv_current_scorer_guard | ready | grading_accuracy | 0.170111 | 214/1258 | false |  |
| beetle | interviv_current_scorer_guard | ready | macro_f1 | 0.161054 | — | false | Macro-average across labels present in gold data. |
| beetle | interviv_current_scorer_guard | ready | off_topic_false_positive_rate | 0.017256 | 20/1159 | false | rule_FPR: reason==off_topic among gold on-topic answers. |
| beetle | interviv_current_scorer_guard | ready | off_topic_detection_rate | 0.030303 | 3/99 | false | rule_recall: reason==off_topic over gold irrelevant/non_domain. |
| beetle | interviv_current_scorer_guard | ready | off_topic_precision | 0.130435 | 3/23 | false | rule_precision: among reason==off_topic, share gold off-topic. |
| beetle | interviv_current_scorer_guard | ready | outcome_recall | 0.030303 | 3/99 | false | Primary: any guard cap among gold off-topic answers. |
| beetle | interviv_current_scorer_guard | ready | outcome_false_positive_rate | 0.017256 | 20/1159 | false | Any guard cap among gold on-topic answers. |
| beetle | interviv_current_scorer_guard | ready | outcome_precision | 0.130435 | 3/23 | false | Among any-cap predictions, share that are gold off-topic. |
| beetle | interviv_current_scorer_guard | ready | rule_recall | 0.030303 | 3/99 | false | Alias of off_topic_detection_rate (diagnostic). |
| beetle | interviv_current_scorer_guard | ready | rule_false_positive_rate | 0.017256 | 20/1159 | false | Alias of off_topic_false_positive_rate (diagnostic). |
| beetle | interviv_current_scorer_guard | ready | rule_precision | 0.130435 | 3/23 | false | Alias of off_topic_precision (diagnostic). |
| beetle | interviv_current_scorer_guard | ready | contradiction_detection_rate | 0.000000 | 0/355 | false | Recall on gold contradictory answers. |
| beetle | interviv_current_scorer_guard | ready | feedback_claim_count | 4313.000000 | — | false | Number of emitted feedback statements evaluated as claims. |
| beetle | interviv_current_scorer_guard | ready | unsupported_feedback_claim_count | 0.000000 | — | false | Number of feedback claims without a backing scorer signal or adjudicated source. |
| beetle | interviv_current_scorer_guard | ready | unsupported_feedback_rate | 0.000000 | 0/4313 | false | N/A when feedback_claim_count is zero; otherwise unsupported claims divided by all feedback claims. |
| beetle | interviv_current_scorer_guard | ready | evidence_citation_completeness | 1.000000 | 4313/4313 | false | Statements citing an explicit rubric.* or concept.* ID. |

## Synthetic-only pilot metrics

All rows below are labeled `pilot_synthetic=true`. Resolved-evidence rate is computed only here; single-turn benchmarks cannot validate it.

| Dataset | Baseline | Status | Metric | Value | n/N | pilot_synthetic | Notes |
| --- | --- | --- | --- | ---: | ---: | --- | --- |
| internal_perturbation | lexical_similarity | ready | grading_accuracy | 0.411765 | 7/17 | true |  |
| internal_perturbation | lexical_similarity | ready | macro_f1 | 0.379221 | — | true | Macro-average across labels present in gold data. |
| internal_perturbation | lexical_similarity | ready | off_topic_false_positive_rate | 0.000000 | 0/11 | true | rule_FPR: reason==off_topic among gold on-topic answers. |
| internal_perturbation | lexical_similarity | ready | off_topic_detection_rate | 0.666667 | 4/6 | true | rule_recall: reason==off_topic over gold irrelevant/non_domain. |
| internal_perturbation | lexical_similarity | ready | off_topic_precision | 1.000000 | 4/4 | true | rule_precision: among reason==off_topic, share gold off-topic. |
| internal_perturbation | lexical_similarity | ready | outcome_recall | 0.666667 | 4/6 | true | Primary: any guard cap among gold off-topic answers. |
| internal_perturbation | lexical_similarity | ready | outcome_false_positive_rate | 0.000000 | 0/11 | true | Any guard cap among gold on-topic answers. |
| internal_perturbation | lexical_similarity | ready | outcome_precision | 1.000000 | 4/4 | true | Among any-cap predictions, share that are gold off-topic. |
| internal_perturbation | lexical_similarity | ready | rule_recall | 0.666667 | 4/6 | true | Alias of off_topic_detection_rate (diagnostic). |
| internal_perturbation | lexical_similarity | ready | rule_false_positive_rate | 0.000000 | 0/11 | true | Alias of off_topic_false_positive_rate (diagnostic). |
| internal_perturbation | lexical_similarity | ready | rule_precision | 1.000000 | 4/4 | true | Alias of off_topic_precision (diagnostic). |
| internal_perturbation | lexical_similarity | ready | contradiction_detection_rate | 0.000000 | 0/3 | true | Recall on gold contradictory answers. |
| internal_perturbation | lexical_similarity | ready | feedback_claim_count | 17.000000 | — | true | Number of emitted feedback statements evaluated as claims. |
| internal_perturbation | lexical_similarity | ready | unsupported_feedback_claim_count | 0.000000 | — | true | Number of feedback claims without a backing scorer signal or adjudicated source. |
| internal_perturbation | lexical_similarity | ready | unsupported_feedback_rate | 0.000000 | 0/17 | true | N/A when feedback_claim_count is zero; otherwise unsupported claims divided by all feedback claims. |
| internal_perturbation | lexical_similarity | ready | evidence_citation_completeness | 0.000000 | 0/17 | true | Statements citing an explicit rubric.* or concept.* ID. |
| internal_perturbation | lexical_similarity | ready | resolved_evidence_rate | 0.750000 | 3/4 | true | Exact-trigger-gap resolution judgment accuracy; synthetic pilot only. |
| internal_perturbation | semantic_nli_relevance | ready | grading_accuracy | 0.529412 | 9/17 | true |  |
| internal_perturbation | semantic_nli_relevance | ready | macro_f1 | 0.592424 | — | true | Macro-average across labels present in gold data. |
| internal_perturbation | semantic_nli_relevance | ready | off_topic_false_positive_rate | 0.000000 | 0/11 | true | rule_FPR: reason==off_topic among gold on-topic answers. |
| internal_perturbation | semantic_nli_relevance | ready | off_topic_detection_rate | 0.333333 | 2/6 | true | rule_recall: reason==off_topic over gold irrelevant/non_domain. |
| internal_perturbation | semantic_nli_relevance | ready | off_topic_precision | 1.000000 | 2/2 | true | rule_precision: among reason==off_topic, share gold off-topic. |
| internal_perturbation | semantic_nli_relevance | ready | outcome_recall | 0.333333 | 2/6 | true | Primary: any guard cap among gold off-topic answers. |
| internal_perturbation | semantic_nli_relevance | ready | outcome_false_positive_rate | 0.000000 | 0/11 | true | Any guard cap among gold on-topic answers. |
| internal_perturbation | semantic_nli_relevance | ready | outcome_precision | 1.000000 | 2/2 | true | Among any-cap predictions, share that are gold off-topic. |
| internal_perturbation | semantic_nli_relevance | ready | rule_recall | 0.333333 | 2/6 | true | Alias of off_topic_detection_rate (diagnostic). |
| internal_perturbation | semantic_nli_relevance | ready | rule_false_positive_rate | 0.000000 | 0/11 | true | Alias of off_topic_false_positive_rate (diagnostic). |
| internal_perturbation | semantic_nli_relevance | ready | rule_precision | 1.000000 | 2/2 | true | Alias of off_topic_precision (diagnostic). |
| internal_perturbation | semantic_nli_relevance | ready | contradiction_detection_rate | 0.666667 | 2/3 | true | Recall on gold contradictory answers. |
| internal_perturbation | semantic_nli_relevance | ready | feedback_claim_count | 34.000000 | — | true | Number of emitted feedback statements evaluated as claims. |
| internal_perturbation | semantic_nli_relevance | ready | unsupported_feedback_claim_count | 0.000000 | — | true | Number of feedback claims without a backing scorer signal or adjudicated source. |
| internal_perturbation | semantic_nli_relevance | ready | unsupported_feedback_rate | 0.000000 | 0/34 | true | N/A when feedback_claim_count is zero; otherwise unsupported claims divided by all feedback claims. |
| internal_perturbation | semantic_nli_relevance | ready | evidence_citation_completeness | 1.000000 | 34/34 | true | Statements citing an explicit rubric.* or concept.* ID. |
| internal_perturbation | semantic_nli_relevance | ready | resolved_evidence_rate | 1.000000 | 4/4 | true | Exact-trigger-gap resolution judgment accuracy; synthetic pilot only. |
| internal_perturbation | interviv_current_scorer_guard | ready | grading_accuracy | 0.647059 | 11/17 | true |  |
| internal_perturbation | interviv_current_scorer_guard | ready | macro_f1 | 0.577839 | — | true | Macro-average across labels present in gold data. |
| internal_perturbation | interviv_current_scorer_guard | ready | off_topic_false_positive_rate | 0.000000 | 0/11 | true | rule_FPR: reason==off_topic among gold on-topic answers. |
| internal_perturbation | interviv_current_scorer_guard | ready | off_topic_detection_rate | 0.166667 | 1/6 | true | rule_recall: reason==off_topic over gold irrelevant/non_domain. |
| internal_perturbation | interviv_current_scorer_guard | ready | off_topic_precision | 1.000000 | 1/1 | true | rule_precision: among reason==off_topic, share gold off-topic. |
| internal_perturbation | interviv_current_scorer_guard | ready | outcome_recall | 0.166667 | 1/6 | true | Primary: any guard cap among gold off-topic answers. |
| internal_perturbation | interviv_current_scorer_guard | ready | outcome_false_positive_rate | 0.000000 | 0/11 | true | Any guard cap among gold on-topic answers. |
| internal_perturbation | interviv_current_scorer_guard | ready | outcome_precision | 1.000000 | 1/1 | true | Among any-cap predictions, share that are gold off-topic. |
| internal_perturbation | interviv_current_scorer_guard | ready | rule_recall | 0.166667 | 1/6 | true | Alias of off_topic_detection_rate (diagnostic). |
| internal_perturbation | interviv_current_scorer_guard | ready | rule_false_positive_rate | 0.000000 | 0/11 | true | Alias of off_topic_false_positive_rate (diagnostic). |
| internal_perturbation | interviv_current_scorer_guard | ready | rule_precision | 1.000000 | 1/1 | true | Alias of off_topic_precision (diagnostic). |
| internal_perturbation | interviv_current_scorer_guard | ready | contradiction_detection_rate | 0.000000 | 0/3 | true | Recall on gold contradictory answers. |
| internal_perturbation | interviv_current_scorer_guard | ready | feedback_claim_count | 54.000000 | — | true | Number of emitted feedback statements evaluated as claims. |
| internal_perturbation | interviv_current_scorer_guard | ready | unsupported_feedback_claim_count | 0.000000 | — | true | Number of feedback claims without a backing scorer signal or adjudicated source. |
| internal_perturbation | interviv_current_scorer_guard | ready | unsupported_feedback_rate | 0.000000 | 0/54 | true | N/A when feedback_claim_count is zero; otherwise unsupported claims divided by all feedback claims. |
| internal_perturbation | interviv_current_scorer_guard | ready | evidence_citation_completeness | 1.000000 | 54/54 | true | Statements citing an explicit rubric.* or concept.* ID. |
| internal_perturbation | interviv_current_scorer_guard | ready | resolved_evidence_rate | 1.000000 | 4/4 | true | Exact-trigger-gap resolution judgment accuracy; synthetic pilot only. |

## Deferred baselines

| Dataset | Baseline | Status | Metric | Value | n/N | pilot_synthetic | Notes |
| --- | --- | --- | --- | ---: | ---: | --- | --- |
| all | structured_llm_rubric_judge | deferred | deferred | — | — | false | Deferred by policy; zero API/network calls made. Comparison table is incomplete. |

## Pending-access datasets

| Dataset | Baseline | Status | Metric | Value | n/N | pilot_synthetic | Notes |
| --- | --- | --- | --- | ---: | ---: | --- | --- |
| ricechem | all | pending_access | pending_access | — | — | false | RiceChem files are absent; access and license review are pending. |

## Interpretation limits

- SciEntsBank, BEETLE, and RiceChem are single-turn datasets. They do not benchmark follow-up resolution.
- Evidence-citation completeness measures structural traceability to `rubric.*` or `concept.*` IDs; it does not by itself prove that feedback is pedagogically correct.
- Unsupported-feedback rate requires a backing scorer signal or adjudicated source. It is distinct from whether that support is explicitly cited; human review remains necessary for substantive support quality.
- The interViv row is produced by a research adapter around the current scorer/guard output. Production application logic is unchanged.
- The semantic baseline uses a pinned local embedding checkpoint and an inspectable negation/antonym heuristic; it is not a trained NLI classifier.
