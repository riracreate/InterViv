# Keyword stuffing false-positive diagnosis

**Status:** diagnosis only — `modules/answer_guard.py` not modified.

## Production impact

**The reported 36% on-topic FPR is a sweep-harness artifact, not a measured
production false-positive rate.**

The diagnosis found that the sweep loader synthesizes keywords from the ideal
answer when the evaluation row has none. Production does not. No harness or
production code is changed in this diagnosis-only task.

Production does **not** derive keywords from ideal-answer tokens when
`ideal_keywords` is empty.

- `backend/scoring/pipeline.py` (`run_scoring_pipeline`) passes
  `question_context.get("ideal_keywords", "")` straight into
  `_run_answer_guard` — no substitution from `ideal_answer`.
- `modules/answer_guard.py` skips the stuffing branch when
  `ideal_keywords` is missing or whitespace-only
  (`if ideal_keywords and ideal_keywords.strip() and tokens:`).
- Session normalization (`backend/routes/session.py`
  `_normalize_question_payload`) only joins/list-coerces whatever the
  question bank already provided; it does not invent keywords from the ideal.

The ideal-token fallback (`", ".join(sorted(word_tokens(ideal_answer))[:12])`)
exists only in the research sweep loader
(`research/grader_lab/threshold_sweep.py` /
`load_offtopic_eval_examples`).

**Empirical check** (3 of the 18 diagnosis FPs: `on_194`, `on_174`, `on_169`)
through `_run_answer_guard` and `run_scoring_pipeline` with production-shaped
`question_context` (`ideal_keywords=""` as in the eval CSV):

| eval_id | production `keyword_stuffing`? | with harness-derived keywords? |
|---------|--------------------------------|--------------------------------|
| on_194 | no (`cap_required=False`) | yes (cap 35) |
| on_174 | no | yes |
| on_169 | no | yes |

Pipeline `guard.applied` was False on all three; final scores 83.75 / 77.5 /
77.5 (uncapped by stuffing).

Context: `docs/offtopic_indomain_sweep.md` reports outcome_FPR **0.36** on the
50 on-topic rows of `data/offtopic_eval_set.csv`, floored by `keyword_stuffing`.
`AGENTS.md` is not present on this branch; workspace engineering standards apply.
Protected path `modules/answer_guard.py` was read only.

## PART 1 — Characterise the false positives

Method: run the 50 `on_topic` rows through `check_answer_quality_v2` with the
**same keyword resolution as the in-domain sweep**
(`research/grader_lab/threshold_sweep.py` / `load_offtopic_eval_examples`):

- use `ideal_keywords` when non-empty
- otherwise derive `", ".join(sorted(word_tokens(ideal_answer))[:12])`

In this eval set **46/50** on-topic rows have empty `ideal_keywords`, so the
derived-from-ideal path dominates.

Guard attribution on 50 on-topic: `{'keyword_stuffing': 18, 'none': 32}`
Keyword source: `{'derived_from_ideal': 46, 'provided': 4}`

**keyword_stuffing fired on 18/50 (0.36).**
All 18 fires used **derived_from_ideal** keywords; 0/4 rows with provided
keywords were capped by stuffing.

### Fired rows

| eval_id | skill | word_count | kw matched (token occ.) | density | non_kw tokens (rule) | non_kw content | answer |
|---------|-------|----------:|------------------------:|--------:|---------------------:|---------------:|--------|
| on_194 | DBMS | 16 | 12 | 0.750 | 4 | 3 | KEGG is a database resource for understanding high-level functions and utilities of the biological system. |
| on_180 | OS | 17 | 12 | 0.706 | 5 | 3 | Spinlocks busy-wait (consume CPU) while waiting; Mutexes put the thread to sleep (context switch) while waiting. |
| on_164 | ML | 14 | 12 | 0.857 | 2 | 1 | Precision is the ratio of correctly predicted positive observations to the total predicted positives. |
| on_193 | CN | 14 | 12 | 0.857 | 2 | 0 | Users lend or stake crypto assets in DeFi protocols to earn rewards or interest. |
| on_157 | ML | 19 | 12 | 0.632 | 7 | 4 | A method that builds a hierarchy of clusters either by merging smaller clusters (agglomerative) or splitting larger ones (divisive). |
| on_162 | DBMS | 16 | 12 | 0.750 | 4 | 3 | Focus on system architecture, push vs. pull models, handling peak loads, database optimization, and message queuing. |
| on_174 | Python | 13 | 13 | 1.000 | 0 | 0 | Context managers handle resource setup and teardown, typically used with the 'with' statement. |
| on_187 | DSA | 14 | 12 | 0.857 | 2 | 2 | Implement advanced AI techniques like Monte Carlo Tree Search, deep learning, and reinforcement learning. |
| on_166 | DSA | 13 | 12 | 0.923 | 1 | 1 | Message queues decouple producers and consumers, enabling asynchronous communication, load leveling, and reliability. |
| on_182 | HR | 19 | 12 | 0.632 | 7 | 6 | Chaos engineering proactively tests system resilience by injecting failures in controlled experiments to identify weaknesses before they cause outages. |
| on_179 | OS | 17 | 13 | 0.765 | 4 | 2 | Monolithic kernels run all services in kernel space; Microkernels run most services in user space for stability. |
| on_171 | DBMS | 15 | 12 | 0.800 | 3 | 3 | First Normal Form requires atomic values in each column and unique rows, eliminating repeating groups. |
| on_169 | CN | 10 | 10 | 1.000 | 0 | 0 | HSTS forces browsers to use HTTPS, preventing protocol downgrade attacks. |
| on_155 | DBMS | 16 | 12 | 0.750 | 4 | 4 | Sharding partitions data across multiple databases/servers, distributing load and enabling horizontal scaling for large datasets. |
| on_192 | System Design | 18 | 12 | 0.667 | 6 | 3 | Data is written to cache first and marked dirty; it is written to disk later, improving write performance. |
| on_181 | HR | 14 | 12 | 0.857 | 2 | 1 | CRDTs are data structures designed to replicate across nodes without coordination, guaranteeing eventual consistency. |
| on_186 | CN | 14 | 13 | 0.929 | 1 | 0 | Software that implements the blockchain protocol, allowing a computer to participate in the network. |
| on_197 | CN | 15 | 12 | 0.800 | 3 | 3 | LocalStorage is accessible via JavaScript, making it vulnerable to XSS attacks; use HttpOnly cookies instead. |

### Density distribution

| Set | n | min | p25 | median | p75 | max | mean |
|-----|--:|----:|----:|-------:|----:|----:|-----:|
| Fired (keyword_stuffing) | 18 | 0.632 | 0.750 | 0.800 | 0.857 | 1.000 | 0.807 |
| Not fired | 32 | 0.016 | 0.163 | 0.200 | 0.500 | 0.600 | 0.293 |

Word count among fired: min=10, median=15, max=19 (all **< 20**).

Non-keyword token count among fired (the rule floor): min=0, median=3, max=7 (all **< 8**).

### Grouping

- Short answers (word_count < 20): **18/18**
- Keyword-dense (density > 0.60): **18/18**
- Both: **18/18**
- Derived-from-ideal keyword source: **18/18**

**Verdict:** the rule fires on **both** short and keyword-dense answers — in
practice the same 18 rows are short *and* dense. They are not keyword salad;
they are concise Good answers that reuse vocabulary from the ideal. Because
keywords were taken as the first 12 tokens of `ideal_answer`, any faithful
short paraphrase looks “stuffed.” Separately: with **empty** keywords the
stuffing branch cannot fire (0/50); the 0.36 FPR is an interaction of the
threshold pair **and** the ideal-token keyword fallback used by the sweep.

## PART 2 — Human baseline connection

The published finding: **11 of 21** human-rated Good rows have system band
≠ Good (under-scored). Workbook
`data/human_baseline_real_combined.xlsx` has **no** `ideal_keywords` column.
For the guard call we resolve keywords as: match `interview_dataset_v6.csv` by
question when present; otherwise derive from `ideal_answer` (same fallback as
Part 1). Note: `scripts/human_baseline.py` scores via `PatchedNLPScorer` and
does **not** apply `answer_guard` to `system_score`, so a firing guard here is
a counterfactual on the stored score, not the historical scoring path.

| row_id | human mean | system score | system band | guard fired | reason | under-scored? |
|-------:|-----------:|-------------:|-------------|------------:|--------|--------------:|
| 1 | 99.3 | 80.2 | Good | yes | keyword_stuffing | no |
| 3 | 99.0 | 80.2 | Good | yes | keyword_stuffing | no |
| 4 | 82.3 | 57.0 | Average | no | none | yes |
| 6 | 69.3 | 21.1 | Poor | yes | off_topic | yes |
| 7 | 98.7 | 80.2 | Good | yes | keyword_stuffing | no |
| 8 | 99.0 | 80.2 | Good | no | none | no |
| 10 | 62.3 | 20.2 | Poor | yes | off_topic | yes |
| 12 | 93.3 | 58.4 | Average | no | none | yes |
| 13 | 86.0 | 19.1 | Poor | yes | off_topic | yes |
| 14 | 81.7 | 39.2 | Average | no | none | yes |
| 15 | 75.7 | 47.3 | Average | no | none | yes |
| 16 | 99.0 | 80.2 | Good | yes | keyword_stuffing | no |
| 19 | 98.7 | 80.2 | Good | no | none | no |
| 20 | 61.0 | 34.3 | Average | yes | gibberish | yes |
| 21 | 90.7 | 65.3 | Good | no | none | no |
| 22 | 99.0 | 80.2 | Good | yes | keyword_stuffing | no |
| 24 | 99.3 | 80.2 | Good | yes | keyword_stuffing | no |
| 25 | 99.3 | 80.2 | Good | yes | keyword_stuffing | no |
| 27 | 86.3 | 48.2 | Average | no | none | yes |
| 28 | 96.3 | 53.0 | Average | no | none | yes |
| 29 | 81.3 | 48.6 | Average | no | none | yes |

Guard reasons on 21 Good rows: `{'keyword_stuffing': 7, 'none': 10, 'off_topic': 3, 'gibberish': 1}`
Reasons on 11 under-scored: `{'none': 7, 'off_topic': 3, 'gibberish': 1}`

**keyword_stuffing among the 11 under-scored: 0/11.**
keyword_stuffing among all 21 Good (counterfactual): 7/21
(those 7 still have system band Good at 80.2 — uncapped NLP score).

With intentionally empty keywords, stuffing fires on **0/21** Good rows.

**Verdict:** overlap is **not** substantial. The 11 under-scores are dominated
by `none` (7), distractor `off_topic` (3), and `gibberish` (1).
**Band miscalibration and this keyword_stuffing FPR are not the same defect.**
Stuffing would hit a different subset of Good rows (mostly still band-Good in
the workbook) if the guard were applied with derived keywords.

## PART 3 — Threshold fault

### Exact production conditions

From `modules/answer_guard.py` in `_check_basic_rules` (before `too_short`):

```text
kw_tokens = _keyword_token_set(ideal_keywords)   # comma-split, word-tokenised
stuffed   = count of answer tokens that ∈ kw_tokens
kw_ratio  = stuffed / len(answer_tokens)
non_kw    = answer tokens ∉ kw_tokens   # includes stopwords; NOT content-token filter
fire if:  kw_ratio > 0.45  AND  len(non_kw) < 8
cap:      keyword_stuffing → score_cap 35
```

Constants: **density threshold 0.45** (strict `>`), **non-keyword token floor 8**
(strict `<`). Cap score 35. Cascade order places stuffing after empty /
gibberish / repetition / question_parroting and before too_short.

### Which condition produces the false positives?

Every FP satisfies **both** limbs (density min among FPs = 0.63 ≫ 0.45;
non_kw max = 7 < 8). Univariate sweeps on the 50 on-topic rows:

- Raise density only (floor fixed at 8): FPR stays **0.36** until density > 0.60,
  then falls to 0.08 at density > 0.90 — never ≤ 0.05.
- Tighten floor only (density fixed at 0.45): FPR falls from 0.36 (floor 8) to
  **0.20** at floor 4 — still far above 0.05.

So the binding design fault is the **combination**, with density the stronger
lever once above 0.60, but **neither lever alone** (nor any pair in the grid
below) reaches FPR ≤ 0.05 on this set while keywords are ideal-derived.
Structurally, short ideal-overlapping prose will always look dense when the
keyword set is a sample of the ideal itself.

### Genuine stuffing set

Constructed **24** cases from on-topic keyword sets:
comma-separated keyword lists, keywords repeated with no prose, and keyword
salad. Production predicate recall: **1.00** (24/24); real
`check_answer_quality_v2` also returns `keyword_stuffing` on 24/24.

### Threshold sweep

Grid: density ∈ {0.45, 0.50, …, 0.90} × content_floor ∈ {4, 5, …, 20}.
FPR = stuffing predicate on 50 on-topic (same resolved keywords); recall =
predicate on 24 genuine cases.

**Pairs with FPR ≤ 0.05 and recall ≥ 0.80: 0.**

Best under recall ≥ 0.80 (by FPR):

| dens_th | content_floor | FPR | recall |
|--------:|--------------:|----:|-------:|
| 0.9 | 4 | 0.08 | 1.00 |
| 0.9 | 5 | 0.08 | 1.00 |
| 0.9 | 6 | 0.08 | 1.00 |
| 0.9 | 7 | 0.08 | 1.00 |
| 0.9 | 8 | 0.08 | 1.00 |
| 0.9 | 9 | 0.08 | 1.00 |
| 0.9 | 10 | 0.08 | 1.00 |
| 0.9 | 11 | 0.08 | 1.00 |

Minimum FPR anywhere in the grid: **0.08** (4/50) at density > 0.90 (any floor
4–20 in this set). Genuine recall remains 1.00 across those cells because
synthetic stuffing has density 1.0 and non_kw = 0.

**Verdict: no retune meets FPR ≤ 0.05 and recall ≥ 0.80 on this evaluation.**
The rule needs **restructuring**, not threshold retuning alone.

## Recommended fix (do not apply in this task)

1. **Stop using ideal-answer tokens as a keyword fallback for stuffing.** If
   `ideal_keywords` is empty, skip the stuffing branch (current behaviour with
   empty keywords already yields 0 stuffing FPs on this set). Prefer curated
   keywords from the question bank only.
2. If a stuffing check remains: require a minimum curated keyword-set size,
   raise density well above paraphrase rates (e.g. ≥ 0.85–0.90), and/or count
   **content** non-keyword tokens (exclude stopwords) so short grammatical
   answers are not floor-starved.
3. Optionally gate stuffing behind a “no connected prose” signal (punctuation /
   function-word rate) so comma-lists and salads stay caught after (1)–(2).

Priority is to correct the evaluation harness before further off-topic
threshold work. The reported 0.36 outcome_FPR is caused by the harness-derived
keywords interacting with the 0.45/8 AND rule; it is not the production FPR.
If production begins supplying curated keywords broadly, the rule still needs
the restructuring and validation recommended above before rollout.
