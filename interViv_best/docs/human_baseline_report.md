# Human Baseline Report — interViv Scoring System

**Generated from:** `human_baseline_real_combined.xlsx`  
**Rows analysed:** 30  
**Annotators with data:** annotator_1, annotator_2, annotator_3

---

## 1. Inter-Rater Agreement (Cohen's κ)

| Pair | κ | Interpretation |
|------|---|----------------|
| annotator_1 vs annotator_2 | 0.489 | Moderate |
| annotator_1 vs annotator_3 | 0.701 | Substantial |
| annotator_2 vs annotator_3 | 0.736 | Substantial |
| **Average** | **0.642** | **Substantial** |

> κ interpretation: <0.20 Slight, 0.20–0.40 Fair, 0.40–0.60 Moderate, 0.60–0.80 Substantial, >0.80 Almost perfect

---

## 2. System vs Human Correlation (Pearson r)

| Metric | Value |
|--------|-------|
| Pearson r | 0.7392 |
| p-value   | 0.0000 |
| n         | 30 |

> The system-human correlation is **0.739**, statistically significant (p < 0.05).

| Annotator | Pearson r with system | p-value |
|-----------|----------------------|---------|
| annotator_1 | 0.556 | 0.0014 |
| annotator_2 | 0.824 | 0.0000 |
| annotator_3 | 0.719 | 0.0000 |

---

## 3. Confusion Matrix (Good / Average / Poor bands)

Rows = Human mean band  ·  Columns = System predicted band

| Human \ System | Good | Average | Poor |
|-----------------|------|---------|------|
| **Good** | 10 | 8 | 3 |
| **Average** | 0 | 3 | 3 |
| **Poor** | 0 | 3 | 0 |

---

## 4. Top-5 System-Human Disagreements

| # | Question (truncated) | Answer (truncated) | System | Human | Delta |
|---|----------------------|--------------------|--------|-------|-------|
| 1 | What is the role of data contracts in microservices and data... | Python uses reference counting as the.... | 19 | 86 | 67 |
| 2 | What is regularisation in machine learning?... | Data contracts define schema, semantics, and SLAs ... | 21 | 69 | 48 |
| 3 | What is circuit breaker pattern?... | Circuit breaker states: Closed — calls succeed, tr... | 53 | 96 | 43 |
| 4 | What is the difference between horizontal and vertical scali... | Horizontal means adding more servers and vertical ... | 39 | 82 | 42 |
| 5 | What is the difference between primary key and foreign key?... | Use collaborative filtering, content-based filteri... | 20 | 62 | 42 |

---

## 5. Notes

- **System score** is the NLP score from the 3-layer hybrid scorer (v11) without KG blending.
- **Annotator scale**: 0–30 = Poor, 31–60 = Average, 61–100 = Good.
- Band boundaries: score < 31 → Poor, 31–60 → Average, > 60 → Good.
- `persona_validation_final.xlsx` is a separate persona simulation and is not used as the primary human baseline.