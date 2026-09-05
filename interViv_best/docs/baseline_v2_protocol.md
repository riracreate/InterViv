# Baseline v2 annotation protocol

Expanded human baseline study: 100 answers, five annotators. This replaces the
n=19 matched-pairs baseline (three annotators, Pearson r = 0.821, 95% CI
[0.585, 0.929]), whose interval is too wide to support the report's claims.

## Sampling

- Source: `data/interview_dataset_v6.csv` (2,319 rows, 11 skills; labels Good /
  Average / Poor, 773 rows each).
- Method: stratified random sample by label — 34 Good, 33 Average, 33 Poor —
  so annotators see the full quality range rather than 100 similar answers.
  Drawn only from the unambiguous pool (see "Exclusion of label-ambiguous
  pairs" below); the pool (Good 260 / Average 260 / Poor 773) supports the
  full 34/33/33 split with no rebalancing needed.
- Seed: **24**, fixed in `scripts/build_baseline_v2.py` (`SEED = 24`). The
  sample is shuffled with the same seed so quality bands are not grouped in
  row order (grouping would hint at scores).
- Skill coverage is checked and printed by the script. Seed 24 covers all 11
  skills with no skill above 21% of the sheet. If a future re-sample leaves
  any skill at zero rows, the script prints a warning rather than silently
  producing a lopsided sheet.
- Builder: `python scripts/build_baseline_v2.py`. It reads only the source
  CSV and writes only the two files below; existing data files are untouched.

## Alignment check (why it exists)

The previous study had an undocumented distractor mechanism in
`scripts/human_baseline.py`: for each question it injected an answer taken
from a *different* question, shuffled the four candidates, and wrote one row
per candidate. 9 of its 30 distributed rows therefore paired a question with
an answer belonging to a different question, and the defect went unnoticed
for weeks because nothing verified the pairs.

`build_baseline_v2.py` verifies alignment **before writing anything**: for
every sampled row it confirms the exact (question, answer) pair exists
together in the source CSV. On any failure it raises `AlignmentError` and
writes nothing. The run summary prints the confirmation
(`Alignment check: PASSED (100/100 ...)`).

## Annotator rubric

Score each candidate answer 0–100 against the reference answer:

| Band    | Range  |
|---------|--------|
| Poor    | 0–30   |
| Average | 31–60  |
| Good    | 61–100 |

The reference answer is provided for calibration only and must not be copied
into the score justification. Annotators work **independently** and are
briefed **separately**; they must not discuss ratings until all sheets are
returned.

## Analysis plan

Five annotators are recruited so that inter-rater reliability can be reported
as **Krippendorff's alpha** (all five raters jointly) alongside **pairwise
Cohen's kappa** (per annotator pair). Do not modify
`scripts/baseline_analysis.py` until the annotated sheets are returned.

## Output files

| File | Contents | Distribution |
|------|----------|--------------|
| `data/baseline_v2_blank.xlsx` | `row_id`, `question`, `reference_answer` (header notes it is for reference only and must not be copied), `candidate_answer`, empty `your_score (0-100)`, empty `notes (optional)`. No label, no system score, no skill, no sub_domain. | Goes to annotators |
| `data/baseline_v2_key.csv` | `row_id`, `question`, `answer`, `label`, `skill`, `sub_domain`. | **Confidential — internal only. Annotators never receive this.** |

## Exclusion of label-ambiguous pairs

The source CSV contains identical (question, answer) pairs under contradictory
labels — e.g. rows 708/709: a byte-identical answer labelled Good and
Average. This is a known v6 defect (flagged during the v6-to-v7 cleaning
work). Grouping the source by (question, answer) finds **506 ambiguous
groups covering 1,026 rows**; the unambiguous pool is **1,293 rows**
(Good 260 / Average 260 / Poor 773).

The builder (`filter_unambiguous`) samples only from the unambiguous pool.
Exclusion was chosen over a sensitivity analysis because ground truth that
disagrees with itself on 43% of the study set is not a sound basis for a
validation study: keeping ambiguous pairs would force every agreement metric
to be reported twice (with/without them) while the headline numbers still
rested on self-contradictory labels. The builder prints the excluded-set size
and the ambiguous-pair count (0/100) on every run as confirmation.

Note: the cleaning work cites 513 duplicated answers; this builder measures
506 ambiguous (question, answer) groups. The small gap is a counting
definition difference (this count groups by exact question+answer pair after
whitespace normalisation); the exclusion itself is unaffected.
