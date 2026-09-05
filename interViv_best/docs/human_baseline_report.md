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

---

<!-- Appended section below: n=50 validation study. System scores from
data/baseline_v2_system_scores.csv (research/baseline-v2). All recomputable
figures were independently re-derived from the Responses workbook plus the
system CSV and match exactly. Follow-up: near-zero-vs-Poor comparison added;
subgroups renamed extreme/middle-mean with equivalence claims removed;
historical comparison states the NLP-only vs full-pipeline distinction with
the clean-19 exclusions traced to commit 1d70fde (branch
fix/baseline-alignment-check); bootstrap CI, ordinal alpha, and the
truncation-flag row omitted (no reproducible method on record); spreadsheet
history marked unverified; length-ratio result labelled exploratory.
Recruitment method and collection dates still to be added. -->

# Human Baseline Validation Study

## Purpose

The scoring pipeline produces a number. This study asks whether that number corresponds to how people actually judge the same answers. Without it, the accuracy claims elsewhere in this report rest on the classifier's agreement with its own training labels rather than on external validity.

An earlier study established a preliminary result at n = 30 with three annotators. This study expands that to 50 items and 23 independent raters. The two studies evaluate different system outputs — the earlier study scored the three-layer NLP output alone, while this study scores the full pipeline final score — so their coefficients are reported side by side, not as a replication (see System agreement below).

## Protocol

**Sampling.** Fifty answers were drawn from `interview_dataset_v6.csv`, stratified by quality label so that raters encountered the full spectrum rather than a narrow band. The final sample contained 20 Poor, 15 Average and 15 Good items, spanning eleven skill domains with System Design (12), Machine Learning (10), DBMS (8) and Python (8) most represented.

Before distribution, every sampled `(question, answer)` pair was verified against the source dataset by exact text match. This check was introduced because the earlier study was later found to contain nine items where the question and answer did not correspond, a defect that went unnoticed until after analysis. The check passed 50/50.

Sampling drew only from unambiguous rows — pairs whose label is consistent everywhere they appear in the source. The v6 dataset contains 506 `(question, answer)` groups carrying conflicting labels, and including them would mean validating against ground truth that disagrees with itself.

**Instrument.** Scoring was collected through a web form rather than a spreadsheet, presenting one item at a time with the rubric fixed above. The change of instrument was motivated by an earlier spreadsheet round: the investigator reports its returns showed inter-rater correlations averaging 0.934 and that raters, on enquiry, said they had used AI assistance. That account is unverified — no discarded sheets or correspondence are on record in this repository. The form was chosen to discourage delegation; no instrument prevents AI assistance, and none is claimed to.

**Rubric.** Raters scored each answer from 0 to 100: Poor 0–30, Average 31–60, Good 61–100. Any integer was permitted. Instructions emphasised three points: use your own judgment without AI assistance; do not discuss individual answers with other raters; there is no correct score, and disagreement between raters is precisely what the study measures.

A reference answer accompanied each item as context, with the explicit note that candidate answers need not match its wording.

**Raters.** Twenty-three responses were collected. [TODO: add one-sentence annotator recruitment method.] [TODO: add date range of collection.] Rater identity was not recorded, at the raters' request. Two consequences follow and are stated as limitations: duplicate submissions cannot be excluded, and independence cannot be evidenced externally. The statistical profile is the only available evidence on that point and is reported below.

## Rater behaviour

Individual rater means ranged from 44.5 to 52.9, with standard deviations from 31.7 to 38.6. The proportion of scores that were multiples of five varied from 10% to 76%, indicating that raters differed in how coarsely they scored. Per-item standard deviation across raters averaged 9.9 points. No two response rows were identical.

## Results

### Inter-rater reliability

| Measure | Value |
|---|---|
| Krippendorff's α (interval) | **0.894** |
| Mean pairwise Pearson r | 0.898 |
| Mean pairwise Cohen's κ | **0.734** |
| Range of pairwise κ | 0.463 – 0.938 |

Krippendorff's α is reported as the primary reliability statistic because it accommodates more than two raters directly, where Cohen's κ is defined pairwise. Both indicate substantial agreement. A banded ordinal alpha computed during drafting is omitted because no reproducible method is on record.

### System agreement with human judgment

| Measure | Value |
|---|---|
| Pearson r (system vs human mean) | **0.730** |
| 95% CI, Fisher z | **[0.567, 0.838]** |
| Spearman ρ | 0.764 |
| p | < 0.001 |

The Fisher interval is the only uncertainty interval reported; a bootstrap interval computed during drafting is omitted because no seed or resampling specification is on record.

The earlier n = 30 study obtained r = 0.739, but on a different system output: its `system_score` column is the three-layer NLP `overall_score` alone (`scripts/human_baseline.py`, confirmed by the notes in sections 1–5 above), while the r = 0.730 here is the full pipeline final score, which additionally applies guard caps and blends classifier, KG, and NER terms. The samples, raters, and instruments also differ, so the numerical closeness of the two coefficients is not a replication. A clean n = 19 re-analysis of the earlier study (commit `1d70fde` on branch `fix/baseline-alignment-check`, `docs/human_baseline_clean19_report.md`) excludes the 9 cross-paired rows (row_ids 2, 5, 6, 10, 11, 13, 17, 26, 30) and holds aside 2 near-variant rows (4, 28), obtaining r = 0.821 on the same NLP-only scores; the same non-comparability applies. The two item sets share no (question, answer) pairs (checked by exact text match against `data/human_baseline_real_combined.xlsx`); rater overlap cannot be checked because the present raters are anonymous.

### Agreement by human-mean group

Items are split by human mean score only: the extreme-mean group (human mean below 15 or above 85, n = 26) and the middle-mean group (human mean within [15, 85], n = 24). This split does not measure disagreement, ambiguity, or difficulty.

| | Inter-rater r | System vs human r |
|---|---|---|
| Extreme-mean items (n = 26) | 0.971 | 0.732 |
| Middle-mean items (n = 24) | 0.503 | 0.505 |

Correlations are higher in the extreme-mean group and lower in the middle-mean group for both comparisons. No claim about human disagreement, item difficulty, or equivalence between system error and rater disagreement is inferred from these subgroup correlations.

### Band-level agreement

|  | System: Poor | Average | Good |
|---|---|---|---|
| **Human: Poor** | 7 | 4 | 5 |
| **Human: Average** | 0 | 2 | 11 |
| **Human: Good** | 0 | 2 | 19 |

Band agreement: 28/50 (56%), κ = 0.290.

Band-level agreement is substantially weaker than the correlation implies. The system orders answers similarly to human raters but places its category boundaries differently, and the errors are not distributed evenly.

### Near-zero ratings vs Poor labels

Fifteen of the 50 items received a rating of exactly 0 from at least 20 of the 23 respondents (the response grid is complete — no missing cells, and blanks would not count as zeros). Form positions were mapped to dataset labels by exact (question, answer) text match, not by row_id. All 15 qualifying items are Poor-labelled (positions 2, 4, 10, 14, 18, 20, 21, 26, 31, 33, 34, 35, 42, 48, 49); no Average or Good item qualifies. Five Poor-labelled items fall short of the threshold (positions 1, 6, 27, 28, 39), so near-zero rating implies a Poor label here but the converse does not hold.

## The completeness gap

Disaggregating by dataset label locates the failure precisely.

| Label | Human mean | System mean | Gap |
|---|---|---|---|
| Good (n = 15) | 85.5 | 75.0 | +10.5 |
| Average (n = 15) | 59.1 | 67.1 | −8.0 |
| **Poor (n = 20)** | **10.9** | **46.0** | **−35.1** |

Good and Average items agree within roughly ten points. Poor items diverge by thirty-five.

Inspection of the Poor items explains why. They are predominantly truncated fragments:

> *"ZK-Rollups use validity proofs (zero-knowledge) to."* — 6 words. Human mean 0.9. System 69.2.
>
> *"WAFs protect web applications from common."* — 6 words. Human mean 0.8. System 68.2.
>
> *"A consistent tagging schema enables automation,."* — 6 words. Human mean 0.1. System 62.9.

The surviving fragment is semantically on-topic, so semantic similarity rates it highly. A human reads an incomplete sentence and assigns near zero. The pipeline measures similarity to a correct answer; it does not measure whether the answer is finished.

The anti-gaming guard caught seven of these through its `too_short` and `question_parroting` rules, scoring them at 20.7 against a human mean of 1.0. Thirteen further Poor items passed the guard and scored around 60. The guard's coverage is therefore partial rather than absent.

### A quantified remedy

Length ratio — candidate answer length divided by reference answer length — separates the three classes without overlap at the means:

| Label | Mean length ratio |
|---|---|
| Good | 0.85 |
| Average | 0.46 |
| Poor | 0.31 |

Applying a completeness multiplier of `clip(length_ratio / 0.45, 0.3, 1.0)` to the final score was evaluated against this study's data:

| Configuration | Pearson r | Band agreement | Poor gap |
|---|---|---|---|
| Current pipeline | 0.730 | 56% | −35.1 |
| **Length-ratio scaling** | **0.788** | **66%** | **−22.4** |

A truncation-flag variant computed during drafting is omitted because its rule is not specified reproducibly. The length-ratio result is exploratory analysis on the same 50 items, not an independent validation: the multiplier was chosen and evaluated on this sample, so it requires confirmation on fresh items before any pipeline change. It has not been integrated into the production pipeline; doing so would require re-running the benchmark harness and re-validating the frozen results, which is scoped as future work.

## Limitations

The headline correlation (r = 0.730) should be read alongside band agreement (28/50, κ = 0.290) and the Poor-label gap (system mean 46.0 against human mean 10.9): the system orders answers much as raters do but places category boundaries differently and systematically over-scores truncated answers.

**Sample size.** Fifty items with 23 raters. The confidence interval on the system-human correlation spans 0.567 to 0.838, which is wide enough that the point estimate should not be quoted without it.

**Rater anonymity.** Identity was not collected, so duplicate submissions cannot be excluded and independence cannot be demonstrated through submission metadata. The statistical profile — varied rater means and standard deviations, round-number habits ranging from 10% to 76%, and no duplicate response rows — is consistent with independent judgment but is not proof of it.

**Rater population.** All raters were computer science students. This matches the intended user population but does not capture how experienced interviewers assess the same answers.

**Skill coverage.** Seven of the eleven skills contributed three or fewer items. No per-skill analysis is possible; results are aggregate only.

**No adjudication round.** Disputed items were not re-rated. A formal reliability study would resolve disagreements and report adjudicated scores.

**Prior spreadsheet round (unverified).** The investigator reports that an initial spreadsheet-based collection was discarded after AI assistance was identified; no discarded sheets or correspondence are on record in this repository, so this history is noted as given, not verified. The results reported here come entirely from the subsequent form-based collection.

## Conclusion

The full pipeline final score agrees with human mean ratings at r = 0.730 (95% CI [0.567, 0.838]). Inter-rater reliability among the 23 human raters was Krippendorff's α = 0.894. The earlier r = 0.739 figure evaluated the NLP-only score and is not a directly comparable replication.

Agreement is strongest on extreme-mean items (human mean below 15 or above 85) and weaker on middle-mean items, for both inter-rater and system-vs-human comparisons.

The principal weakness is a systematic over-scoring of truncated answers, arising because semantic similarity does not penalise incompleteness. This is measured at 35 points on Poor-labelled items, and a length-ratio completeness term is shown, in exploratory same-sample analysis requiring independent validation, to recover a substantial portion of it.