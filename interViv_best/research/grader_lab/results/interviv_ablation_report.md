# interViv research-only ablation report

> The structured LLM rubric judge remains `deferred`; comparison coverage is incomplete and zero API/network calls were made.

## Run manifest

| Field | Value |
| --- | --- |
| Run ID | `grader-lab-20260815T161227Z` |
| Generated at (UTC) | `2026-08-15T16:12:27.165259+00:00` |
| Git commit hash | `8758ecfed5171176add2d1905173aeac58ee914a` |
| Dirty worktree | `true` |
| Dataset versions/checksums/sources/licenses | `{"beetle":{"examples":"1258","license_status":"CC BY-SA 3.0; commercial use permitted with attribution/share-alike","sha256":"sha256:4ae5156dbbcb9a9afe25d050cc5ab37c341461bc342739c4de1bac4bddd831d9","source":"https://github.com/myrosia/semeval-2013-task7/tree/5157c69f914e8c581045c03e98f96398d40a91b8","status":"loaded","version":"semeval-2013-task7-5way@5157c69f914e8c581045c03e98f96398d40a91b8;Core/test"},"internal_perturbation":{"examples":"17","license_status":"interViv project material","sha256":"sha256:6a28c698b5e1d413c3be1074e4ee3b39eca7f6fafd938d758475e75d4e52eaed","source":"repository-local synthetic fixtures","status":"loaded","version":"grader-lab-perturbations-v1"},"ricechem":{"examples":"0","license_status":"pending_access_and_license_review","sha256":"not_present","source":"not supplied","status":"pending_access","version":"pending_access"},"scientsbank":{"examples":"5835","license_status":"CC BY-SA 3.0; commercial use permitted with attribution/share-alike","sha256":"sha256:5458a915f162bd52c6402ad1538d96691bc9161ca4c51e5f2c400bd6ffe554c2","source":"https://github.com/myrosia/semeval-2013-task7/tree/5157c69f914e8c581045c03e98f96398d40a91b8","status":"loaded","version":"semeval-2013-task7-5way@5157c69f914e8c581045c03e98f96398d40a91b8;Core/test"}}` |
| Model/checkpoint/classifier/configuration | `{"interviv_ablation":{"adapter":"interviv-ablation-v1","classifier_artifact":"sha256:2897c8cc6283cbdb4815a78182188ea60c17b39876feefa2d67919f065f16dd7","classifier_model":"LogisticRegression","classifier_version":"1.1.0","full_semantic_applicable_count":"7110","full_semantic_fallback_count":"0","full_semantic_function_call_count":"7110","pipeline":"backend.scoring.pipeline@workspace_commit","semantic_model":"sentence-transformers/all-MiniLM-L6-v2","semantic_revision":"1110a243fdf4706b3f48f1d95db1a4f5529b4d41","term_ablation_policy":"remove named final-score term; renormalize remaining base weights; retain bonuses and guard cap","without_guards_policy":"use pre-cap production score and suppress guard label","without_semantic_lexical_fallback_count":"7110"},"structured_llm_rubric_judge":{"execution":"deferred_zero_api_calls","structured_judge":"unscoped"}}` |
| Runtime versions | `{"numpy":"2.4.4","python":"3.12.4","scikit-learn":"1.8.0","sentence-transformers":"5.4.1","torch":"2.11.0"}` |

## Benchmark-validated metrics

| Dataset | Configuration | Metric | Value | n/N | pilot_synthetic |
| --- | --- | --- | ---: | ---: | --- |
| scientsbank | full_interviv | grading_accuracy | 0.373093 | 2177/5835 | false |
| scientsbank | full_interviv | macro_f1 | 0.245943 | — | false |
| scientsbank | full_interviv | off_topic_detection_rate | 0.061744 | 97/1571 | false |
| scientsbank | full_interviv | off_topic_false_positive_rate | 0.008677 | 37/4264 | false |
| scientsbank | full_interviv | contradiction_detection_rate | 0.000000 | 0/539 | false |
| scientsbank | without_semantic | grading_accuracy | 0.361611 | 2110/5835 | false |
| scientsbank | without_semantic | macro_f1 | 0.231423 | — | false |
| scientsbank | without_semantic | off_topic_detection_rate | 0.000000 | 0/1571 | false |
| scientsbank | without_semantic | off_topic_false_positive_rate | 0.000000 | 0/4264 | false |
| scientsbank | without_semantic | contradiction_detection_rate | 0.000000 | 0/539 | false |
| scientsbank | without_classifier_term | grading_accuracy | 0.381662 | 2227/5835 | false |
| scientsbank | without_classifier_term | macro_f1 | 0.251393 | — | false |
| scientsbank | without_classifier_term | off_topic_detection_rate | 0.061744 | 97/1571 | false |
| scientsbank | without_classifier_term | off_topic_false_positive_rate | 0.008677 | 37/4264 | false |
| scientsbank | without_classifier_term | contradiction_detection_rate | 0.000000 | 0/539 | false |
| scientsbank | without_keyword_term | grading_accuracy | 0.369152 | 2154/5835 | false |
| scientsbank | without_keyword_term | macro_f1 | 0.245751 | — | false |
| scientsbank | without_keyword_term | off_topic_detection_rate | 0.061744 | 97/1571 | false |
| scientsbank | without_keyword_term | off_topic_false_positive_rate | 0.008677 | 37/4264 | false |
| scientsbank | without_keyword_term | contradiction_detection_rate | 0.000000 | 0/539 | false |
| scientsbank | without_tfidf_term | grading_accuracy | 0.377892 | 2205/5835 | false |
| scientsbank | without_tfidf_term | macro_f1 | 0.249750 | — | false |
| scientsbank | without_tfidf_term | off_topic_detection_rate | 0.061744 | 97/1571 | false |
| scientsbank | without_tfidf_term | off_topic_false_positive_rate | 0.008677 | 37/4264 | false |
| scientsbank | without_tfidf_term | contradiction_detection_rate | 0.000000 | 0/539 | false |
| scientsbank | without_guards | grading_accuracy | 0.404113 | 2358/5835 | false |
| scientsbank | without_guards | macro_f1 | 0.257667 | — | false |
| scientsbank | without_guards | off_topic_detection_rate | 0.000000 | 0/1571 | false |
| scientsbank | without_guards | off_topic_false_positive_rate | 0.000000 | 0/4264 | false |
| scientsbank | without_guards | contradiction_detection_rate | 0.000000 | 0/539 | false |
| beetle | full_interviv | grading_accuracy | 0.170111 | 214/1258 | false |
| beetle | full_interviv | macro_f1 | 0.161054 | — | false |
| beetle | full_interviv | off_topic_detection_rate | 0.010101 | 1/99 | false |
| beetle | full_interviv | off_topic_false_positive_rate | 0.006903 | 8/1159 | false |
| beetle | full_interviv | contradiction_detection_rate | 0.000000 | 0/355 | false |
| beetle | without_semantic | grading_accuracy | 0.190779 | 240/1258 | false |
| beetle | without_semantic | macro_f1 | 0.178597 | — | false |
| beetle | without_semantic | off_topic_detection_rate | 0.000000 | 0/99 | false |
| beetle | without_semantic | off_topic_false_positive_rate | 0.000000 | 0/1159 | false |
| beetle | without_semantic | contradiction_detection_rate | 0.000000 | 0/355 | false |
| beetle | without_classifier_term | grading_accuracy | 0.232114 | 292/1258 | false |
| beetle | without_classifier_term | macro_f1 | 0.204725 | — | false |
| beetle | without_classifier_term | off_topic_detection_rate | 0.010101 | 1/99 | false |
| beetle | without_classifier_term | off_topic_false_positive_rate | 0.006903 | 8/1159 | false |
| beetle | without_classifier_term | contradiction_detection_rate | 0.000000 | 0/355 | false |
| beetle | without_keyword_term | grading_accuracy | 0.169316 | 213/1258 | false |
| beetle | without_keyword_term | macro_f1 | 0.159287 | — | false |
| beetle | without_keyword_term | off_topic_detection_rate | 0.010101 | 1/99 | false |
| beetle | without_keyword_term | off_topic_false_positive_rate | 0.006903 | 8/1159 | false |
| beetle | without_keyword_term | contradiction_detection_rate | 0.000000 | 0/355 | false |
| beetle | without_tfidf_term | grading_accuracy | 0.166932 | 210/1258 | false |
| beetle | without_tfidf_term | macro_f1 | 0.158679 | — | false |
| beetle | without_tfidf_term | off_topic_detection_rate | 0.010101 | 1/99 | false |
| beetle | without_tfidf_term | off_topic_false_positive_rate | 0.006903 | 8/1159 | false |
| beetle | without_tfidf_term | contradiction_detection_rate | 0.000000 | 0/355 | false |
| beetle | without_guards | grading_accuracy | 0.197933 | 249/1258 | false |
| beetle | without_guards | macro_f1 | 0.127784 | — | false |
| beetle | without_guards | off_topic_detection_rate | 0.000000 | 0/99 | false |
| beetle | without_guards | off_topic_false_positive_rate | 0.000000 | 0/1159 | false |
| beetle | without_guards | contradiction_detection_rate | 0.000000 | 0/355 | false |

## Synthetic-only pilot metrics

All rows in this section are `pilot_synthetic=true`; they are not benchmark evidence.

| Dataset | Configuration | Metric | Value | n/N | pilot_synthetic |
| --- | --- | --- | ---: | ---: | --- |
| internal_perturbation | full_interviv | grading_accuracy | 0.647059 | 11/17 | true |
| internal_perturbation | full_interviv | macro_f1 | 0.577839 | — | true |
| internal_perturbation | full_interviv | off_topic_detection_rate | 0.166667 | 1/6 | true |
| internal_perturbation | full_interviv | off_topic_false_positive_rate | 0.000000 | 0/11 | true |
| internal_perturbation | full_interviv | contradiction_detection_rate | 0.000000 | 0/3 | true |
| internal_perturbation | without_semantic | grading_accuracy | 0.294118 | 5/17 | true |
| internal_perturbation | without_semantic | macro_f1 | 0.266667 | — | true |
| internal_perturbation | without_semantic | off_topic_detection_rate | 0.000000 | 0/6 | true |
| internal_perturbation | without_semantic | off_topic_false_positive_rate | 0.000000 | 0/11 | true |
| internal_perturbation | without_semantic | contradiction_detection_rate | 0.000000 | 0/3 | true |
| internal_perturbation | without_classifier_term | grading_accuracy | 0.647059 | 11/17 | true |
| internal_perturbation | without_classifier_term | macro_f1 | 0.566667 | — | true |
| internal_perturbation | without_classifier_term | off_topic_detection_rate | 0.166667 | 1/6 | true |
| internal_perturbation | without_classifier_term | off_topic_false_positive_rate | 0.000000 | 0/11 | true |
| internal_perturbation | without_classifier_term | contradiction_detection_rate | 0.000000 | 0/3 | true |
| internal_perturbation | without_keyword_term | grading_accuracy | 0.588235 | 10/17 | true |
| internal_perturbation | without_keyword_term | macro_f1 | 0.523333 | — | true |
| internal_perturbation | without_keyword_term | off_topic_detection_rate | 0.166667 | 1/6 | true |
| internal_perturbation | without_keyword_term | off_topic_false_positive_rate | 0.000000 | 0/11 | true |
| internal_perturbation | without_keyword_term | contradiction_detection_rate | 0.000000 | 0/3 | true |
| internal_perturbation | without_tfidf_term | grading_accuracy | 0.647059 | 11/17 | true |
| internal_perturbation | without_tfidf_term | macro_f1 | 0.577839 | — | true |
| internal_perturbation | without_tfidf_term | off_topic_detection_rate | 0.166667 | 1/6 | true |
| internal_perturbation | without_tfidf_term | off_topic_false_positive_rate | 0.000000 | 0/11 | true |
| internal_perturbation | without_tfidf_term | contradiction_detection_rate | 0.000000 | 0/3 | true |
| internal_perturbation | without_guards | grading_accuracy | 0.647059 | 11/17 | true |
| internal_perturbation | without_guards | macro_f1 | 0.454505 | — | true |
| internal_perturbation | without_guards | off_topic_detection_rate | 0.000000 | 0/6 | true |
| internal_perturbation | without_guards | off_topic_false_positive_rate | 0.000000 | 0/11 | true |
| internal_perturbation | without_guards | contradiction_detection_rate | 0.000000 | 0/3 | true |

## Deferred baselines

The structured LLM rubric judge is `deferred` and made zero API/network calls.

## Pending-access datasets

RiceChem is `pending_access`; no files were present or downloaded.

## Interpretation limits

- `without_semantic` executes the production lexical fallback and therefore also changes the classifier's first input feature.
- Classifier, keyword, and TF-IDF variants remove only the named final aggregation term and renormalize remaining base weights. Correlated evidence retained in upstream features is not erased.
- `without_guards` removes the hard cap and explicit off-topic flag but leaves all underlying scorer components unchanged.
- All configurations inherit the current pipeline's lack of an explicit contradiction output; contradiction recall is therefore expected to remain zero.
- Ablation results measure component sensitivity on these datasets, not learner readiness or hiring outcomes.
