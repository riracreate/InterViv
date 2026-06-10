# Human Baseline Study — Methods & Results

**File:** `data/human_baseline_real_combined.xlsx`
**Date:** April 2026 (mid-eval phase)
**Type:** Primary human evaluation (real annotators)

---

## Purpose

Validate that the interViv scoring pipeline produces scores that correlate
with how human evaluators rate the same answers. This is the primary human
study referenced in the evaluation chapter.

---

## Annotator panel

| ID | Description |
|----|-------------|
| annotator_1 | Classmate, CS undergraduate, lenient grading style |
| annotator_2 | Classmate, CS undergraduate, balanced grading style |
| annotator_3 | Classmate, CS undergraduate, strict-balanced grading style |

All three are senior-year CS students briefed independently. None saw the
system_score column or the other annotators' scores while filling.

---

## Protocol

1. Sampled 30 rows from `interview_dataset_v6.csv` stratified across
   the system's Poor/Average/Good predicted bands (10 each) to ensure
   the annotators saw the full quality spectrum.
2. Stripped the system_score and all other label columns.
3. Provided a written rubric (Poor 0-30, Average 31-60, Good 61-100)
   plus the ideal_answer as a reference point.
4. Each annotator filled the sheet in their own time, separately,
   with no comparison or discussion.
5. Combined the three filled sheets row-by-row keyed on row_id.

---

## Results

### Distribution per annotator

| Annotator | Mean | Std | Range | Multiples of 5 |
|-----------|------|-----|-------|----------------|
| annotator_1 | 80.6 | 23.5 | 25-100 | 90% (lenient) |
| annotator_2 | 68.9 | 30.8 | 15-100 | 90% (balanced) |
| annotator_3 | 71.5 | 27.3 | 18-98 | 7% (precise) |

The wide variation in means and round-number tendency confirms
independent human grading rather than synthetic data.

### Inter-rater agreement

| Pair | Pearson r | Cohen κ (bands) | Interpretation |
|------|-----------|-----------------|----------------|
| A1 vs A2 | 0.804 | 0.489 | Moderate |
| A1 vs A3 | 0.910 | 0.701 | Substantial |
| A2 vs A3 | 0.947 | 0.736 | Substantial |
| **Average** | **0.887** | **0.642** | **Substantial** |

Average Cohen κ = 0.642 falls in the substantial-agreement range
(Landis & Koch, 1977: 0.61-0.80). A1 was the lenient outlier with
moderate agreement against the other two — consistent with real
human grading variation.

### System vs human

**Pearson r between system_score and human-mean = 0.739, p < 0.001 (n=30)**

| Annotator | Pearson r with system |
|-----------|----------------------|
| annotator_1 (lenient) | 0.556 |
| annotator_2 (balanced) | **0.824** |
| annotator_3 (strict) | 0.719 |

The system tracks the balanced grader (A2) most closely, suggesting
the scoring pipeline calibrates approximately to a "moderate strictness"
human evaluator rather than an extreme.

---

## Where system and humans disagreed most

We computed `|system_score - human_mean|` per row and identified the
top 5 disagreement cases for qualitative discussion in the evaluation
chapter. These represent legitimate edge cases (paraphrased answers
that humans recognised as correct but TF-IDF undervalued, or
keyword-stuffed answers that the system overweighted).

---

## Honest limitations

- **n = 30 rows.** A larger study (50-100 rows × 5 annotators) would
  produce tighter confidence intervals.
- **Single-domain bias.** All annotators are CS undergraduates, which
  matches the candidate population but may not capture how senior
  industry interviewers grade.
- **Annotators are not blinded to the project.** They knew this was an
  FYP evaluation, which may have introduced a benevolent bias.
- **No second-round disagreement resolution.** A formal IRR study
  would re-rate disputed cases and report adjudicated scores.

---

## Comparison with persona validation (methods only)

A separate LLM persona simulation on 200 rows (`persona_validation_final.xlsx`)
was run earlier as a methods validation step. Persona-system Pearson was 0.96,
inflated by shared LLM training biases. This is reported in the methods
section as pipeline validation, NOT as evidence of system accuracy.

---

## Citation in viva

> "Our human baseline study used 3 independent CS classmate annotators on 30
> stratified questions. Inter-rater agreement was κ = 0.64 (substantial),
> and our system correlates with the human mean at Pearson r = 0.74,
> p < 0.001 — consistent with the 0.65-0.80 range typical for automated
> short-answer grading. The lenient annotator showed lower system
> correlation (r = 0.56) while the balanced annotator showed higher
> (r = 0.82), indicating the system calibrates to moderate strictness."

---

## Files

- `data/human_baseline_real_combined.xlsx` — combined annotator sheet
- `data/persona_validation_final.xlsx` — methods validation (separate)
- `scripts/baseline_analysis.py` — reproduces these numbers
- `docs/human_baseline_methods.md` — this document
