# Semantic runtime diagnosis

## 1. Executive conclusion

Primary classification: `RESEARCH_ADAPTER_BUG`.

The prior grader-lab run did not reveal a production runtime failure. The research entrypoint defaulted `enable_interviv_semantic=False`; its adapter then set `DISABLE_SEMANTIC_SCORING=1` around every production-pipeline call. That intentionally selected the production scorer's lexical fallback while the separate semantic baseline loaded the local checkpoint normally.

The fix belongs in the `research adapter`. No production configuration or scoring code was changed.

## 2. Evidence

### Actual prior call path

1. `research/grader_lab/run.py::run_lab` defaulted `enable_interviv_semantic=False` and constructed `InterVivCurrentBaseline(enable_semantic=False)`.
2. `research/grader_lab/baselines.py::InterVivCurrentBaseline.predict` set the process environment variable `DISABLE_SEMANTIC_SCORING=1`, then called `backend.scoring.pipeline.run_scoring_pipeline`.
3. `backend/scoring/pipeline.py::_run_nlp_score` instantiated `modules.nlp_scorer_patch.PatchedNLPScorer`, which delegates ideal-backed answers to `modules.nlp_scorer.NLPScorer.get_feature_scores`.
4. `modules/nlp_scorer.py::_get_semantic_scorer` saw the environment value and returned `None` with fallback reason `disabled_by_env`; `SemanticScorer.score` was therefore never called.
5. `NLPScorer.get_feature_scores` substituted TF-IDF for the blended cosine. `backend.scoring.pipeline._semantic_or_lexical_component` recorded `semantic_component_source=lexical_fallback`.

This exactly explains the old manifest's `disabled_lexical_fallback`. There was no missing adapter argument, model-path mismatch, reduced production scorer, or skipped initialization beyond the adapter's explicit opt-out.

### Standalone versus production-model initialization

| Path | Model request | Revision behavior | Offline behavior | Observed result |
| --- | --- | --- | --- | --- |
| `SemanticRelevanceBaseline.__init__` | `sentence-transformers/all-MiniLM-L6-v2` | Explicit pinned revision `1110a243fdf4706b3f48f1d95db1a4f5529b4d41` | `local_files_only=True` plus offline environment | Local checkpoint loaded |
| `modules.semantic_scorer._get_model` | `sentence-transformers/all-MiniLM-L6-v2` | Production code requests the model name without an explicit revision | Falls back on load exception; lab process sets offline environment | Local checkpoint loaded in corrected smoke test |

Production's semantic scorer is enabled by default. `DISABLE_SEMANTIC_SCORING` is the only semantic opt-out found; it is absent from `.env.example`. `backend.main.lifespan` calls `backend.startup_warmup.warm_runtime_dependencies`, which attempts `_get_model()` and reports load/fallback state. Load or encode exceptions are intentionally swallowed into lexical fallback. Whether a particular deployed process has the model cache and environment flag is not independently established by this repository inspection.

## 3. Semantic execution trace

After changing only the research adapter default, one existing internal clean-paraphrase case (`internal:paraphrase-001`) was executed locally. This was the only scorer execution performed for Part A; the full benchmark was not rerun.

```text
requested_semantic: true
model_identifier: sentence-transformers/all-MiniLM-L6-v2
model_revision_in_local_cache: 1110a243fdf4706b3f48f1d95db1a4f5529b4d41
model_load_attempted: true
model_load_success: true
semantic_function_called: true
semantic_score: 0.8459
fallback_called: false
fallback_reason: null
runtime_mode: semantic
exception: null
device: cpu
```

`semantic_function_called=true` is derived from the returned production contract: `modules.nlp_scorer` can set `semantic_scoring_available=true` and a non-null `semantic_score` only after calling `SemanticScorer.score(...)` and receiving a value. The adapter now records those execution fields per prediction. The device was independently detected from the same local sentence-transformer checkpoint; production does not currently expose device in its scoring payload.

Smoke-test assertions required both `semantic_function_called is True` and `fallback_called is False`; they passed. Merely changing a manifest string was not used as evidence.

## 4. Correct fix location

`research adapter`.

`research/grader_lab/run.py::run_lab` and `InterVivCurrentBaseline` now default to the semantic-enabled production-intended path. The CLI provides an explicit `--disable-interviv-semantic` opt-out for controlled fallback experiments. Production scoring, guards, configuration, startup, and model code remain unchanged.

## 5. LogisticRegression feature-schema check

Conclusion: `NO_SCHEMA_MISMATCH_FOUND`.

| Check | Training | Inference | Finding |
| --- | --- | --- | --- |
| Artifact | `modules/answer_quality_lr.joblib`; metadata version `1.1.0`; SHA-256 `2897c8cc6283cbdb4815a78182188ea60c17b39876feefa2d67919f065f16dd7` | Same located artifact, checksum verified by pipeline metadata loader | Match |
| Feature order | `nlp_cosine_similarity`, `clarity_score`, `keyword_coverage`, `server_word_count`, `concept_coverage` | Same order in `backend.scoring.pipeline._classifier_features` | Match |
| Dimensionality | Saved sklearn pipeline, scaler, and classifier each report 5 input features; classifier coefficient shape is 3 x 5 | `_classifier_features` emits 5 values when `n_features_in_ >= 5` | Match |
| Preprocessing | Saved `Pipeline(StandardScaler, LogisticRegression)`; scaler fitted during training | Inference calls the saved pipeline's `predict`/`predict_proba`, so the same fitted scaler runs | Match |
| Semantic-derived input | Training's first feature is `NLPScorer`'s `cosine_similarity`, which is the 0.4 TF-IDF + 0.6 semantic blend when semantic is available | Same scorer output is supplied at runtime | Match when semantic is available |
| Fallback input | Training code permits the scorer's pure-TF-IDF fallback under model unavailability | Runtime supplies pure TF-IDF in the same first feature slot under fallback | Same type/range/position; potentially different value distribution, not a schema mismatch |

The artifact has no `feature_names_in_` because training used a NumPy matrix, so names are verified from `retrain_ml_model.py`, `modules/model_metadata.json`, and inference source rather than artifact column labels. A lexical fallback may cause distribution shift relative to semantic-enabled examples; the available repository evidence does not quantify the training-time fallback rate. That is a calibration/data-distribution risk, not evidence of incompatible dimensionality, ordering, or preprocessing.

## Reproducibility record

| Field | Value |
| --- | --- |
| Git commit hash | `8758ecfed5171176add2d1905173aeac58ee914a` |
| Worktree state | dirty (research files not committed) |
| Smoke dataset | `internal_perturbation` / `grader-lab-perturbations-v1` / SHA-256 `6a28c698b5e1d413c3be1074e4ee3b39eca7f6fafd938d758475e75d4e52eaed` / repository-local synthetic fixture |
| License status | interViv project material |
| Python | `3.12.4` |
| sentence-transformers | `5.4.1` |
| torch | `2.11.0` |
| scikit-learn | `1.8.0` |
| Network/API activity | zero; offline local checkpoint only |

