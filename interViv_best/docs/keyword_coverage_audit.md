# Keyword coverage audit

**Status:** measurement only — data files, scoring code, and classifier unchanged.

## Dataset keyword presence

Keyword count = number of comma-separated (or `|`-separated) non-empty phrases
in `ideal_keywords`.

| Dataset | total rows | with non-empty `ideal_keywords` | % | mean keyword count (where present) |
|---------|----------:|--------------------------------:|--:|-----------------------------------:|
| `interview_dataset_v6.csv` | 2319 | 81 | 3.5% | 7.26 |
| `ml_training_data.csv` | 891 | 96 | 10.8% | 7.16 |
| `fallback_question_bank.csv` | 53 | 53 | 100.0% | 5.00 |

### Per skill (`interview_dataset_v6.csv`)

| skill | n | with keywords | % | mean kw (where present) |
|-------|--:|--------------:|--:|------------------------:|
| DBMS | 543 | 9 | 1.7% | 7.67 |
| System Design | 360 | 36 | 10.0% | 7.58 |
| ML | 360 | 0 | 0.0% | 0.00 |
| CN | 285 | 0 | 0.0% | 0.00 |
| DSA | 231 | 0 | 0.0% | 0.00 |
| Python | 180 | 0 | 0.0% | 0.00 |
| OOP | 120 | 3 | 2.5% | 6.00 |
| OS | 120 | 0 | 0.0% | 0.00 |
| HR | 93 | 6 | 6.5% | 7.00 |
| Java | 15 | 15 | 100.0% | 6.80 |
| JavaScript | 12 | 12 | 100.0% | 7.00 |

## CSV bank vs LLM-generated metadata

`source` values containing `llm` are treated as **LLM-generated** metadata;
all others as **CSV / curated bank** (including empty `source` on the fallback bank).

| Dataset | origin | n | with keywords | % | mean kw |
|---------|--------|--:|--------------:|--:|--------:|
| v6 | csv_bank | 2238 | 0 | 0.0% | — |
| v6 | llm_generated | 81 | 81 | 100.0% | 7.26 |
| ml_training (891) | csv_bank | 795 | 0 | 0.0% | — |
| ml_training (891) | llm_generated | 96 | 96 | 100.0% | 7.16 |
| fallback_question_bank | csv_bank (source empty) | 53 | 53 | 100.0% | 5.00 |
| fallback_question_bank | llm_generated | 0 | 0 | — | — |

### By raw `source` (v6)

| source | n | with keywords | % | mean kw |
|--------|--:|--------------:|--:|--------:|
| `archive3` | 1500 | 0 | 0.0% | 0.00 |
| `curated_v3` | 381 | 0 | 0.0% | 0.00 |
| `handcrafted_v4` | 243 | 0 | 0.0% | 0.00 |
| `reference_jsonl` | 102 | 0 | 0.0% | 0.00 |
| `llm-reference` | 78 | 78 | 100.0% | 7.31 |
| `archive3|reclassified` | 9 | 0 | 0.0% | 0.00 |
| `handcrafted_v4|reclassified` | 3 | 0 | 0.0% | 0.00 |
| `llm-reference|reclassified` | 3 | 3 | 100.0% | 6.00 |

### By raw `source` (ml_training_data)

| source | n | with keywords | % | mean kw |
|--------|--:|--------------:|--:|--------:|
| `handcrafted_v4` | 414 | 0 | 0.0% | 0.00 |
| `curated_v3` | 381 | 0 | 0.0% | 0.00 |
| `llm-reference` | 96 | 96 | 100.0% | 7.16 |

**Verdict:** on v6 and the 891 training rows, keyword presence **correlates
perfectly with question origin**. Every `llm-reference` row has keywords; every
curated/archive/handcrafted CSV-bank row has none. The fallback bank is the
exception: curated rows with keywords but blank `source`.

Therefore the same answer can score differently depending on where its question
came from: LLM-backed questions exercise the real keyword_coverage / stuffing
paths; CSV-bank questions hit the empty-keyword defaults (coverage → 0.5;
stuffing skipped). That is a production scoring asymmetry.

## Training feature: `keyword_coverage` on 891 rows

Computed with `NLPScorer.get_feature_scores` (same path as
`retrain_ml_model.build_features`). When `ideal_keywords` is empty,
`_keyword_coverage_details` returns **score 0.5** (not 0).

| Statistic | value |
|-----------|------:|
| n | 891 |
| exactly **0** | **2** |
| exactly **0.5** (empty-keyword default) | **805** (90.3%) |
| min / max / mean | 0.0 / 1.0 / 0.5053 |

Bucket histogram:

| bucket | n |
|--------|--:|
| 0 | 2 |
| (0, 0.25) | 12 |
| [0.25, 0.5) | 29 |
| 0.5 default | 805 |
| (0.5, 0.75) | 15 |
| [0.75, 1] | 28 |

Split:

- rows **without** keywords: 795/891 — all coverage **0.5**
- rows **with** keywords: 96/891 (all `llm-reference`) — mean 0.549; only **2** exact zeros

**Verdict:** almost no training mass is at zero; **805/891 (90.3%) are pinned at
the empty-keyword default 0.5**. For those rows the feature is constant and
carried **no discriminative signal** during training. The classifier is
effectively a **four-feature** model on ~90% of the training set (cosine,
clarity/length proxy, word count, concept coverage), with keyword_coverage
informative only on the 96 LLM-sourced rows.
