# Human Baseline Report — interViv Scoring System

**Generated from:** `persona_validation_final.xlsx`  
**Rows analysed:** 200  
**Annotators with data:** annotator_1, annotator_2, annotator_3, annotator_4

---

## 1. Inter-Rater Agreement (Cohen's κ)

| Pair | κ | Interpretation |
|------|---|----------------|
| annotator_1 vs annotator_2 | 0.770 | Substantial |
| annotator_1 vs annotator_3 | 0.748 | Substantial |
| annotator_1 vs annotator_4 | 0.571 | Moderate |
| annotator_2 vs annotator_3 | 0.791 | Substantial |
| annotator_2 vs annotator_4 | 0.501 | Moderate |
| annotator_3 vs annotator_4 | 0.460 | Moderate |
| **Average** | **0.640** | **Substantial** |

> κ interpretation: <0.20 Slight, 0.20–0.40 Fair, 0.40–0.60 Moderate, 0.60–0.80 Substantial, >0.80 Almost perfect

---

## 2. System vs Human Correlation (Pearson r)

| Metric | Value |
|--------|-------|
| Pearson r | 0.9578 |
| p-value   | 0.0000 |
| n         | 200 |

> The system-human correlation is **0.958**, statistically significant (p < 0.05).

| Annotator | Pearson r with system | p-value |
|-----------|----------------------|---------|
| annotator_1 | 0.957 | 0.0000 |
| annotator_2 | 0.955 | 0.0000 |
| annotator_3 | 0.939 | 0.0000 |
| annotator_4 | 0.868 | 0.0000 |

---

## 3. Confusion Matrix (Good / Average / Poor bands)

Rows = Human mean band  ·  Columns = System predicted band

| Human \ System | Good | Average | Poor |
|-----------------|------|---------|------|
| **Good** | 79 | 12 | 0 |
| **Average** | 0 | 49 | 0 |
| **Poor** | 0 | 31 | 29 |

---

## 4. Top-5 System-Human Disagreements

| # | Question (truncated) | Answer (truncated) | System | Human | Delta |
|---|----------------------|--------------------|--------|-------|-------|
| 1 | What are Python's dunder (magic) methods?... | Dunder methods let custom classes hook into Python... | 49 | 96 | 47 |
| 2 | Explain the difference between SQL and NoSQL databases.... | SQL: structured schema, relational model, ACID, go... | 50 | 86 | 36 |
| 3 | What is HTTPS and how does TLS work?... | HTTPS is HTTP over TLS. TLS handshake: client send... | 61 | 90 | 28 |
| 4 | When would you choose Redux over React Context for state man... | Redux is for big applications with lots of state. ... | 40 | 66 | 26 |
| 5 | What is the difference between horizontal and vertical scali... | Vertical scaling adds resources to one server (big... | 65 | 91 | 26 |

---

## 5. Notes

- **System score** is the NLP score from the 3-layer hybrid scorer (v11) without KG blending.
- **Annotator scale**: 0–30 = Poor, 31–60 = Average, 61–100 = Good.
- Band boundaries: score < 31 → Poor, 31–60 → Average, > 60 → Good.
- `persona_validation_final.xlsx` is a separate persona simulation and is not used as the primary human baseline.