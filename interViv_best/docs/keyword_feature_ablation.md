# Keyword coverage feature ablation

**Status:** measurement only. Production `modules/answer_quality_lr.joblib`
untouched. Recommendation below is not applied.

## Question

805 of 891 training rows pin `keyword_coverage` at the empty-keyword default
0.5 (`docs/keyword_coverage_audit.md`). Does the feature carry usable signal?

## Method

Retrain LogisticRegression (`C=1`, `class_weight=balanced`, seed **42**, same
5-fold stratified CV / held-out split as `retrain_ml_model.py`) three ways on
`data/ml_training_data.csv` (891 rows):

| id | Features | Rows |
|----|----------|-----:|
| (a) | all five (cosine, clarity, **keyword_coverage**, word_count, concept) | 891 |
| (b) | four — **keyword_coverage removed** | 891 |
| (c) | all five | **86** rows with `keyword_coverage ≠ 0.5` |

Feature build matches the audit: empty / NaN `ideal_keywords` cleaned to `""`
so the scorer returns the 0.5 default (raw `retrain_ml_model.build_features`
turns CSV NaN into the string `"nan"` and mostly yields coverage **0** — that
path was not used here).

Artifacts (research only):

- `research/keyword_feature_ablation/answer_quality_lr_5feat.joblib`
- `research/keyword_feature_ablation/answer_quality_lr_4feat_no_keyword.joblib`
- `research/keyword_feature_ablation/answer_quality_lr_5feat_real_keyword_only.joblib`
- `research/keyword_feature_ablation/cv_metrics.json`
- `research/keyword_feature_ablation/ood_metrics.json`

Runner: `python research/keyword_feature_ablation.py` (optional `--ood-only`
when a `research/grader_lab` tree is present).

## In-domain 5-fold CV

| Variant | n | accuracy | macro F1 | Average F1 | Good F1 | Poor F1 |
|---------|--:|---------:|---------:|-----------:|--------:|--------:|
| (a) five features | 891 | 0.9394 | 0.9391 | 0.9066 | 0.9747 | 0.9362 |
| (b) no keyword_coverage | 891 | **0.9405** | **0.9402** | 0.9078 | 0.9765 | 0.9362 |
| (c) real-coverage rows only | **86** | 0.8605 | 0.8555 | 0.7600 | 1.0000 | 0.8065 |

Dropping the feature does **not** hurt in-domain CV; it is slightly better.
Variant (c) looks usable but **n=86 is too small for a strong conclusion**.

### Fitted importance in (a)

Standardized LR mean absolute coefficient across the three classes:

| Feature | mean \|coef\| |
|---------|-------------:|
| word_count | 2.472 |
| clarity_score | 2.312 |
| concept_coverage | 1.165 |
| cosine_similarity | 0.333 |
| **keyword_coverage** | **0.201** |

Per-class `keyword_coverage` coefs: Average −0.249, Good +0.302, Poor −0.053.
It is the **weakest** of the five features under this fit.

## Out-of-domain (SciEntsBank / Beetle)

(a) and (b) plugged into the production scoring pipeline via a research
monkeypatch of the classifier load + feature vector (four-feature path for
(b) = cos, clarity/length proxy, word_count, concept — not the stock 4-feat
layout that still includes keyword_coverage). Guards unchanged (main branch
threshold). Full corpora: SciEntsBank 5835, Beetle 1258.

| Variant | SciEntsBank macro F1 | Beetle macro F1 | SciEntsBank acc | Beetle acc |
|---------|---------------------:|----------------:|----------------:|-----------:|
| (a) five features | 0.2341 | 0.1365 | 0.3599 | 0.1407 |
| (b) no keyword_coverage | 0.2332 | 0.1357 | 0.3596 | 0.1399 |
| Δ (b − a) | **−0.0009** | **−0.0008** | −0.0003 | −0.0008 |

Off-topic rule recall / FPR / precision are **identical** for (a) and (b) on
both panels (classifier swap does not change the guard).

### Relation to whole-classifier ablation

Frozen `interviv_ablation` (`without_classifier_term` vs `full_interviv`):

| Panel | full macro F1 | without classifier | Δ |
|-------|--------------:|-------------------:|--:|
| SciEntsBank | 0.2459 | 0.2514 | **+0.0055** |
| Beetle | 0.1611 | 0.2047 | **+0.0437** |

Removing **only** `keyword_coverage` moves OOD macro F1 by ~0.001 **down**,
not up. It does **not** explain the gain from removing the classifier term.
That gain comes from the rest of the classifier (or its interaction with
other score terms), not this feature.

(Note: research (a) is a fresh retrain with cleaned keywords, so its absolute
OOD F1 is not identical to the frozen production `full_interviv` cell; the
(a) vs (b) delta is the controlled contrast.)

## Recommendation

**Gate** the feature — do not keep it as a always-on fifth input, and do not
silently drop it from production without a follow-up retrain decision.

- **Keep as-is:** weak. 805/891 rows are constant; mean \|coef\| is smallest;
  in-domain CV is flat-to-worse with it; OOD delta is noise-scale.
- **Drop:** reasonable for a classifier-only simplification, and CV/OOD do not
  argue against it, but a gated design preserves the path when real keywords
  exist (96 LLM-sourced rows; 86 non-default coverage).
- **Gate (preferred):** use keyword_coverage in the classifier vector only when
  `ideal_keywords` is non-empty (else omit or freeze a dedicated four-feature
  model). Retrain and re-measure before shipping; this report does not apply
  that change.

Do not replace `modules/answer_quality_lr.joblib` from this work.
