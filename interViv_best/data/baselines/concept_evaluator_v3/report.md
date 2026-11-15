# Concept Evaluator v3 Measurement Report

- **Evaluator v3 version**: `concept_evaluator_v3.0`
- **Frozen Semantic Threshold**: `0.62` (calibrated on Calibration Split prior to Held-Out evaluation)

## 1. Stored Bundle Inventory (YAML + Read-Only SQLite)

- Total bundles with `required_concepts`: **13** (YAML: `12`, SQLite `interviv.db`: `1`, `local-data/interviv-local.sqlite3`: `0`)
- Required concepts: **38**, Optional concepts: **12**
- Authored concept `positive_examples`: **4**, `negative_cases`: **4** (populated only in 2 bundles: `python.generators, python.gil`; remaining 11 bundles have `[]`)
- Bundle Split (sorted `bundle_id`, alternating index): Calibration (`idx % 2 == 0`, n=7) = `dbms.acid-properties, dbms.isolation-levels, dbms.normalisation-1nf-3nf, python.generators, python.is-vs-equals, python.memory-management, system-design.scalability-and-load-balanci-easy@db_v1`; Held-Out (`idx % 2 == 1`, n=6) = `dbms.deadlocks, dbms.join-types, dbms.oltp-vs-olap, python.gil, python.lists-vs-tuples, python.shallow-vs-deep-copy`

### Benchmark Sample Provenance & Vocabulary Coupling

- **Authored concept examples (`Benchmark A`)**: Only **2** stored bundles (`python.generators, python.gil`) define concept-level `positive_examples` (`4`) and `negative_cases` (`4`), yielding **4 pos / 4 neg** (`8` samples evaluated leave-one-out via `exclude_examples`).
- **Split benchmarks (`Benchmark B`: Calibration `47 pos / 47 neg`, Held-Out `33 pos / 37 neg`)**: Because the remaining stored bundles lack concept-level examples, `build_split_benchmark` pairs every bundle's `required_concepts` against: `REF` (the bundle's own `reference_answer`, positive), `CAL_L3` (`calibration_examples` with `author_level == 3`, positive), `POS_EX` (authored `positive_examples` leave-one-out, positive), `CAL_L0` (`calibration_examples` with `author_level == 0`, negative), `NEG_EX` (authored `negative_cases`, negative), and `XDOM_REF` (cross-domain `reference_answer` from another bundle in the same split with a different `bundle_id` domain prefix, negative).
- **Vocabulary coupling disclosure**: `REF`, `CAL_L3`, and `CAL_L0` answers are drawn from the same bundle documents that define each concept's `expected_propositions` and `aliases`. Consequently, Tier 1 (`proposition`) and Tier 2 (`alias`) recall on `REF`/`CAL_L3` reflects same-document vocabulary coupling rather than independent candidate phrasing; use `XDOM_REF`/`CAL_L0` for cross-domain false-positive control, `v3 isolated semantic` for Tier 3 generalization, and Benchmark A + independent human-rated answers for uncoupled recall/precision.

### Sample-Kind Breakdown by Split

| Split | Positives | Negatives | Total | Sample-Kind Counts |
|---|---:|---:|---:|---|
| Benchmark A (All Stored Authored) | 4 | 4 | 8 | `NEG_EX`=4, `POS_EX`=4 |
| Benchmark B — Calibration Split | 47 | 47 | 94 | `CAL_L0`=22, `CAL_L3`=22, `NEG_EX`=3, `POS_EX`=3, `REF`=22, `XDOM_REF`=22 |
| Benchmark B — Held-Out Split | 33 | 37 | 70 | `CAL_L0`=20, `CAL_L3`=16, `NEG_EX`=1, `POS_EX`=1, `REF`=16, `XDOM_REF`=16 |

## 2. Benchmark A: Authored `positive_examples` (Leave-One-Out) vs `negative_cases` (All Stored Bundles)

| System / Mode | TP | FP | FN | TN | Precision | Recall | F1 |
|---|---:|---:|---:|---:|---:|---:|---:|
| v2 (overall) | 0 | 0 | 4 | 4 | 0.0000 | 0.0000 | 0.0000 |
| v3 @ 0.62 (overall) | 3 | 3 | 1 | 1 | 0.5000 | 0.7500 | 0.6000 |
| v3 isolated `proposition` | 0 | 0 | 4 | 4 | 0.0000 | 0.0000 | 0.0000 |
| v3 isolated `alias` | 3 | 3 | 1 | 1 | 0.5000 | 0.7500 | 0.6000 |
| v3 isolated `semantic` | 1 | 1 | 3 | 3 | 0.5000 | 0.2500 | 0.3333 |

### Benchmark A Waterfall `match_type` Attribution (v3)

| match_type | TP | FP | Precision | Recall Contribution |
|---|---:|---:|---:|---:|
| `proposition` | 0 | 0 | 0.0000 | 0.0000 |
| `alias` | 3 | 3 | 0.5000 | 0.7500 |
| `semantic` | 0 | 0 | 0.0000 | 0.0000 |

### Benchmark A Waterfall `match_type` Attribution (v2)

| match_type | TP | FP | Precision | Recall Contribution |
|---|---:|---:|---:|---:|
| `proposition` | 0 | 0 | 0.0000 | 0.0000 |
| `alias` | 0 | 0 | 0.0000 | 0.0000 |

### Benchmark A Per-Sample Audit (4 `POS_EX` Leave-One-Out + 4 `NEG_EX`)

| Kind | Polarity | Bundle | Concept | v2 (state) | v3 (state / match_type / score) |
|---|---:|---|---|---|---|
| POS_EX | 1 | `python.generators` | `generator` | `uncertain` | `supported / alias` |
| NEG_EX | 0 | `python.generators` | `generator` | `uncertain` | `supported / alias` |
| POS_EX | 1 | `python.generators` | `yield` | `uncertain` | `supported / alias` |
| NEG_EX | 0 | `python.generators` | `yield` | `uncertain` | `supported / alias` |
| POS_EX | 1 | `python.generators` | `lazy_evaluation` | `not_demonstrated` | `not_demonstrated / None` |
| NEG_EX | 0 | `python.generators` | `lazy_evaluation` | `not_demonstrated` | `not_demonstrated / None` |
| POS_EX | 1 | `python.gil` | `GIL` | `uncertain` | `supported / alias` |
| NEG_EX | 0 | `python.gil` | `GIL` | `uncertain` | `supported / alias` |

## 3. Benchmark B — Calibration Split Threshold Sweep (Calibration Split Only; `47 pos / 47 neg`)

| System / Mode | TP | FP | FN | TN | Precision | Recall | F1 |
|---|---:|---:|---:|---:|---:|---:|---:|
| v2 (calibration baseline) | 8 | 1 | 39 | 46 | 0.8889 | 0.1702 | 0.2857 |
| v3 @ 0.62 (calibration frozen) | 44 | 8 | 3 | 39 | 0.8462 | 0.9362 | 0.8889 |
| v3 isolated `proposition` | 9 | 1 | 38 | 46 | 0.9000 | 0.1915 | 0.3158 |
| v3 isolated `alias` | 38 | 6 | 9 | 41 | 0.8636 | 0.8085 | 0.8352 |
| v3 isolated `semantic` | 16 | 2 | 31 | 45 | 0.8889 | 0.3404 | 0.4923 |

### Calibration Split Waterfall `match_type` Attribution (v3)

| match_type | TP | FP | Precision | Recall Contribution |
|---|---:|---:|---:|---:|
| `proposition` | 9 | 1 | 0.9000 | 0.1915 |
| `alias` | 35 | 6 | 0.8537 | 0.7447 |
| `semantic` | 0 | 1 | 0.0000 | 0.0000 |

### Calibration Split Waterfall `match_type` Attribution (v2)

| match_type | TP | FP | Precision | Recall Contribution |
|---|---:|---:|---:|---:|
| `proposition` | 8 | 1 | 0.8889 | 0.1702 |
| `alias` | 0 | 0 | 0.0000 | 0.0000 |

### Full 3-Tier v3 Sweep (Calibration Split)

| Threshold | TP | FP | FN | TN | Precision | Recall | F1 |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 0.45 | 45 | 11 | 2 | 36 | 0.8036 | 0.9574 | 0.8738 |
| 0.50 | 45 | 11 | 2 | 36 | 0.8036 | 0.9574 | 0.8738 |
| 0.52 | 45 | 10 | 2 | 37 | 0.8182 | 0.9574 | 0.8824 |
| 0.55 | 45 | 9 | 2 | 38 | 0.8333 | 0.9574 | 0.8911 |
| 0.58 | 45 | 9 | 2 | 38 | 0.8333 | 0.9574 | 0.8911 |
| 0.60 | 44 | 9 | 3 | 38 | 0.8302 | 0.9362 | 0.8800 |
| 0.62 | 44 | 8 | 3 | 39 | 0.8462 | 0.9362 | 0.8889 |
| 0.65 | 44 | 8 | 3 | 39 | 0.8462 | 0.9362 | 0.8889 |
| 0.68 | 44 | 7 | 3 | 40 | 0.8627 | 0.9362 | 0.8980 |
| 0.70 | 44 | 7 | 3 | 40 | 0.8627 | 0.9362 | 0.8980 |

### Standalone Tier-3 (`semantic` only) Sweep (Calibration Split)

| Threshold | TP | FP | FN | TN | Precision | Recall | F1 |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 0.45 | 32 | 9 | 15 | 38 | 0.7805 | 0.6809 | 0.7273 |
| 0.50 | 27 | 8 | 20 | 39 | 0.7714 | 0.5745 | 0.6585 |
| 0.52 | 26 | 7 | 21 | 40 | 0.7879 | 0.5532 | 0.6500 |
| 0.55 | 25 | 5 | 22 | 42 | 0.8333 | 0.5319 | 0.6494 |
| 0.58 | 22 | 5 | 25 | 42 | 0.8148 | 0.4681 | 0.5946 |
| 0.60 | 16 | 3 | 31 | 44 | 0.8421 | 0.3404 | 0.4848 |
| 0.62 | 16 | 2 | 31 | 45 | 0.8889 | 0.3404 | 0.4923 |
| 0.65 | 12 | 2 | 35 | 45 | 0.8571 | 0.2553 | 0.3934 |
| 0.68 | 12 | 1 | 35 | 46 | 0.9231 | 0.2553 | 0.4000 |
| 0.70 | 7 | 1 | 40 | 46 | 0.8750 | 0.1489 | 0.2545 |

## 4. Benchmark B — Held-Out Split Report (Frozen Threshold = `0.62`; `33 pos / 37 neg`)

| System / Mode | TP | FP | FN | TN | Precision | Recall | F1 |
|---|---:|---:|---:|---:|---:|---:|---:|
| v2 (overall) | 7 | 0 | 26 | 37 | 1.0000 | 0.2121 | 0.3500 |
| v3 @ 0.62 (overall) | 33 | 8 | 0 | 29 | 0.8049 | 1.0000 | 0.8919 |
| v3 isolated `proposition` | 7 | 0 | 26 | 37 | 1.0000 | 0.2121 | 0.3500 |
| v3 isolated `alias` | 33 | 8 | 0 | 29 | 0.8049 | 1.0000 | 0.8919 |
| v3 isolated `semantic` | 23 | 1 | 10 | 36 | 0.9583 | 0.6970 | 0.8070 |

### Held-Out Waterfall `match_type` Attribution (v3)

| match_type | TP | FP | Precision | Recall Contribution |
|---|---:|---:|---:|---:|
| `proposition` | 7 | 0 | 1.0000 | 0.2121 |
| `alias` | 26 | 8 | 0.7647 | 0.7879 |
| `semantic` | 0 | 0 | 0.0000 | 0.0000 |

### Held-Out Waterfall `match_type` Attribution (v2)

| match_type | TP | FP | Precision | Recall Contribution |
|---|---:|---:|---:|---:|
| `proposition` | 7 | 0 | 1.0000 | 0.2121 |
| `alias` | 0 | 0 | 0.0000 | 0.0000 |
