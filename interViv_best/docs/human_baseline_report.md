# Human Baseline Report — interViv Scoring System

**Generated from:** `human_baseline_sheet.csv`  
**Rows analysed:** 10  
**Annotators with data:** annotator_1, annotator_2, annotator_3, annotator_4

---

## 1. Inter-Rater Agreement (Cohen's κ)

| Pair | κ | Interpretation |
|------|---|----------------|
| annotator_1 vs annotator_2 | 0.844 | Almost perfect |
| annotator_1 vs annotator_3 | 0.697 | Substantial |
| annotator_1 vs annotator_4 | 0.688 | Substantial |
| annotator_2 vs annotator_3 | 0.841 | Almost perfect |
| annotator_2 vs annotator_4 | 0.844 | Almost perfect |
| annotator_3 vs annotator_4 | 0.697 | Substantial |
| **Average** | **0.768** | **Substantial** |

> κ interpretation: <0.20 Slight, 0.20–0.40 Fair, 0.40–0.60 Moderate, 0.60–0.80 Substantial, >0.80 Almost perfect

---

## 2. System vs Human Correlation (Pearson r)

| Metric | Value |
|--------|-------|
| Pearson r | 0.9870 |
| p-value   | 0.0000 |
| n         | 10 |

> The system-human correlation is **0.987**, statistically significant (p < 0.05).

---

## 3. Confusion Matrix (Good / Average / Poor bands)

Rows = Human mean band  ·  Columns = System predicted band

| Human \ System | Good | Average | Poor |
|-----------------|------|---------|------|
| **Good** | 4 | 0 | 0 |
| **Average** | 0 | 4 | 0 |
| **Poor** | 0 | 0 | 2 |

---

## 4. Top-5 System-Human Disagreements

| # | Question (truncated) | Answer (truncated) | System | Human | Delta |
|---|----------------------|--------------------|--------|-------|-------|
| 1 | What is the difference between horizontal and vertical scali... | Vertical is making one server bigger. Horizontal i... | 30 | 20 | 10 |
| 2 | Develop an autonomous vehicle's path planning algorithm.... | Implement algorithms considering real-time obstacl... | 80 | 86 | 6 |
| 3 | What is the difference between horizontal and vertical scali... | Vertical scaling adds resources to one server (big... | 65 | 72 | 6 |
| 4 | Develop an autonomous vehicle's path planning algorithm.... | Utilize stream processing frameworks (like Apache ... | 35 | 41 | 6 |
| 5 | Develop an autonomous vehicle's path planning algorithm.... | Implement algorithms considering real-time obstacl... | 80 | 86 | 6 |

---

## 5. Notes

- **System score** is the NLP score from the 3-layer hybrid scorer (v11) without KG blending.
- **Annotator scale**: 0–30 = Poor, 31–60 = Average, 61–100 = Good.
- Band boundaries: score < 31 → Poor, 31–60 → Average, > 60 → Good.