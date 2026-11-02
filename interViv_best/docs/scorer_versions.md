# Scorer versions

This file records identifiable scoring implementations. A version change is
required for algorithm, threshold, model, matching, guard, or configuration
changes. Input-bundle changes get a separate bundle version even when the
algorithm is unchanged.

`v1` is the original unify-shell baseline captured in Phase 0. It is not an
alias for whatever the current tree happens to contain. Replay uses the frozen
fixture and asset hashes. Later versions get their own fixtures and reports.
Do not overwrite `tests/fixtures/scorer_v1_baseline.json` to absorb a new
result.

| Version | Source commit | Status | Notes |
| --- | --- | --- | --- |
| v1 | `6659feda31b2f27d687f609d59e397911285a6ff` (`codex/unify-shell`) | frozen original baseline | Production path at capture. `LENGTH_RATIO_MULTIPLIER_ENABLED` off. Semantic runtime **full** (`sentence-transformers/all-MiniLM-L6-v2` revision `1110a243fdf4706b3f48f1d95db1a4f5529b4d41`). Classifier `modules/answer_quality_lr.joblib` sha256 `2897c8cc6283cbdb4815a78182188ea60c17b39876feefa2d67919f065f16dd7` (matches `modules/model_metadata.json`). |
| v2 | `071284b1f85f861898be3a19bb853cfc5d5372f1` (`upgrade/verified-blueprint`) | frozen | v1 + `entity_swap` guard in `modules/answer_guard.py` (cap 35) and its messages in `pipeline.py` / `c4_feedback.py`. No weight, threshold, model or matching change. All 8 v1 items replay identically; fixture adds one `entity_swap` item (88.2 before the guard, 35.0 after). Evaluation: `scripts/evaluate_entity_swap_guard.py`. |
| v3 | branch `upgrade/verified-blueprint` (parent `071284b`; fill in the commit once made) | current | v2 + letter-pair nonsense check built from the question bank's own text (common and never-seen pairs), an exemption for words the question's reference material uses, and a `too_short` rule for answers under 8 words and under half the reference answer. No weight, model or matching change. Of the 9 v2 items only `keyword_stuffing` changes (gibberish 10.0 → keyword_stuffing 35.0); fixture adds `real_terms_not_gibberish` and `short_fragment`. Table: `scripts/build_guard_bigrams.py`. Evaluation: `scripts/evaluate_guard_v3.py`. |

## What v2 changes

Comparison questions ("difference between TCP and UDP") let an answer that
gives each side the other's properties score like a correct one: embeddings and
keyword coverage ignore which side a property is attached to. The guard learns
each side's distinctive properties from the reference answer and caps the
answer at 35 when properties cross over in both directions. It is a no-op for
questions without a clear A/B pair, for clauses that name both sides, and for
negated clauses.

Measured with `scripts/evaluate_entity_swap_guard.py` (question-grouped split,
seed 42): 0 fires on 284 unique real comparison answers across
`interview_dataset_v6.csv` and `ml_training_data.csv` (86 applicable Good
answers; the 95% upper bound on the Good false-positive rate is about 3.5%).
Recall on synthetic swaps is 85% on the tune split and 87.5% on held-out (16
swaps). Synthetic swaps are symmetric by construction, and the rules were
tightened after inspecting two false positives in the pooled data, so the
held-out figures are not fully untouched.

v1 can only be replayed at its source commit.

## What v3 changes

The per-word nonsense check compared each word with 80 hand-picked letter pairs.
The list missed pairs English uses constantly ("ol", "ob", "ow", "ll", "ly",
"op", "ts"), so it called 30.5% of real six-letter-plus words nonsense:
"solves", "optimal", "global", "allows", "objects", "patterns", "polymorphism".
An answer made half of such words was capped at 10 as gibberish. The Good
answer "DP solves subproblems and stores results for optimal global solution;
Greedy makes locally optimal choices hoping for a global optimum." scored 10.

v3 changes three things in `modules/answer_guard.py`:

1. **Letter-pair table from reference text.** `_COMMON_BIGRAMS` now lists the
   262 pairs found in at least 10 distinct words (6+ letters) of every question
   and ideal answer in `interview_dataset_v6.csv` and `ml_training_data.csv`.
   Candidate answers are not used. A word is nonsense below a 0.60 share of
   common pairs, or with two or more pairs that occur in no reference word
   (`_UNSEEN_BIGRAMS`, 243 pairs; "gctcititxi" has "gc" and "tx"). Odd vowel or
   consonant shape counts only below a 0.75 share, so "branch" and
   "abstraction" pass. Keyboard patterns, repeated patterns and 4+ repeated
   characters still mark a word as nonsense on their own.
2. **Reference words are never nonsense.** A word the question, ideal answer or
   keywords use is exempt, which covers names such as "dijkstra" and "kruskal".
3. **Short fragments are capped explicitly.** Fewer than 8 words *and* fewer
   than half the ideal answer's words gives `too_short` (cap 20). Before, most
   such fragments were capped only because the old check misread their words.
   A short answer to a question whose ideal answer is short is not affected.

Measured on all 3,210 dataset answers (`interview_dataset_v6.csv` +
`ml_training_data.csv`), comparing guard decisions and full-pipeline final
scores at commit `071284b` against this tree:

| Change | Answers | Final score before → after (mean) |
| --- | --- | --- |
| Poor, uncapped → `too_short` | 307 | 58.6 → 20.0 (max before 73.4) |
| Poor, `gibberish` → `too_short` | 17 | 10.0 → 20.0 |
| Poor, `gibberish` → `truncated_fragment` | 7 | 10.0 → 25.0 |
| Poor, `off_topic` → `too_short` | 1 | 21.2 → 20.0 |
| Good / Average, `gibberish` → uncapped | 1 / 1 | 10.0 → 83.8 |
| Poor, `too_short` → uncapped | 2 | 20.0 → 67.9 |

No Good or Average answer gains a cap. Capped answers by label: Good 9 → 8,
Average 15 → 14, Poor 478 → 783. Every dataset answer under 8 words is
labelled Poor (793 answers), so the data cannot show how the length rule treats
a short *correct* answer; the half-the-reference condition is the protection.
The two Poor answers that lose their cap are machine-truncated ("…Hold and
Wait, No.", "…prefix-based searches,.") with short ideal answers.

On words alone (letter-pair table built from 80% of reference words, measured
on the other 20%): real words flagged 1.1% (was 30.5%); uniformly random
strings 91.0% (was 98.8%); keyboard-row mash 85.4% (was 98.8%). The real words
still flagged are names and identifiers ("dijkstra", "kruskal", "postgresql",
"componentdidmount"); the reference-word exemption covers them when the
question uses them. Pronounceable
made-up words mostly pass the per-word check and fall to later rules
(`off_topic` in the regression example).

Known limitation unchanged by v3: an answer made only of listed keywords
("Atomicity, Consistency, Isolation, Durability.") is still capped by
`keyword_stuffing`, even when the list is the complete answer.

Reproduce these figures with `scripts/evaluate_guard_v3.py --scores`.

Replay v3 with `--version v3`. v2 can now only be replayed at its source commit.

## How to replay v1

From `interViv_best/`:

```
.venv/bin/python scripts/replay_scorer_v1_baseline.py              # v1 (needs the v1 source commit)
.venv/bin/python scripts/replay_scorer_v1_baseline.py --version v2 # current tree
```

The replay hashes the listed source assets against `data/baselines/v1/SHA256SUMS.json`
and re-scores the pinned answers in `tests/fixtures/scorer_v1_baseline.json`.
It fails if hashes or per-item `final_score` / `guard_applied` / `nlp_score` /
`kg_score` differ. Missing MiniLM weights cannot claim v1; they are a different
runtime.

## What v1 is not

- Not permission to change the production scorer.
- Not a reproduction of the historical n=50 form study (r = 0.730 in later
  Tree 2 / protocol text). That study needs the form-response workbook, which
  is not on this branch.
- Not a rewrite of `docs/human_baseline_report.md`. That file on this commit
  is the 230-line report (n=30 r = 0.7392 plus appended n=50 r = 0.730) and
  stays unchanged. Pytest currently regenerates the n=30-only body; restore
  it from git after the suite (`git restore -- docs/human_baseline_report.md`).
