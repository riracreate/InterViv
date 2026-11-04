# Part II stage (a) — pure policy delivery

Implemented only the authorized pure core, typed graph, configured bands and offline/invariant checks. No session route, existing selector, follow-up formatter, live skill graph, dashboard or persistence schema is wired to it. `PROBE_CONCEPT` has no implementation; its separate `ADAPTIVE_CONCEPT_PROBING_ENABLED=False` guard raises `NotImplementedError` if enabled. Stage (b) and (c) remain proposals.

## Behavior and invariants

`next_adaptive_move` takes immutable policy state and a validated question bank and returns COVER, PROBE_HARDER, BRIDGE or END. The caller supplies outcomes via `record_outcome`. It performs no I/O or global-RNG mutation. Stable seed/question hashing makes ties repeatable. All role/evidence fields belong to canonical buckets; aliases collapse to maximum role weight and strongest evidence before must-cover selection. No taxonomy evidence tags are produced.

The policy admits budgets 8–12 only and caps must-cover at floor(0.6*N). It starts with a claimed/evidenced strength, then role-weighted keyword claims and other evidenced buckets, with at most one role gap. A feasibility witness protects every selected move against exhausting the remaining budget or distinct questions before covering must-cover. When remaining equals uncovered, COVER wins. Impossible banks raise `BankExhausted`; repeats or budget overruns are not fallback options. The later adapter must use baseline on explicit admission failure.

At most three observations per bucket; role gaps get one Easy observation and no probe. A harder probe requires a strong first observation and a strictly higher difficulty. Prefer the next level; Easy may jump to Hard if necessary and records difficulty relaxation. If no higher question exists, record `no_unseen_harder_question` or `already_at_max_difficulty`, try upward/across bridge, then COVER. A wrong/nonanswer may bridge only down actual prerequisites; no concept-miss branch exists. DSA, DBMS, OS and Python have no prerequisites, so their wrong/nonanswer branch records `no_eligible_prerequisite` and uses COVER.

At a requested difficulty, source order is reviewed/eligible bundle, primary CSV, fallback CSV. Unreviewed bundles are ineligible even if present. Relax to nearest difficulty only within the target bucket, preferring the lower level on ties. A same/lower question is never labeled PROBE_HARDER. All decisions expose requested/actual difficulty, source, reason and fallback list.

Dedup rejects repeated IDs, exact normalized text across sources/skills, and within-skill cosine ≥0.85 under the pinned model. A complete within-skill similarity table is required; missing values do not quietly count as distinct. Explicit offline lexical fallback uses content-token Jaccard ≥0.65. The 75% demonstrated-concept filter is soft: feasibility can relax it with a reason; duplicate exclusion is never relaxed. Empty concept lists are not treated as fully demonstrated.

## Bands and Elo

Band numeric thresholds live in `backend/config.py`, with `BAND_CALIBRATION_STATUS=in_sample_n50`. The historical read-only audit now delegates to the same classifier. Precedence: nonanswer, wrong, strong, vague, adequate. Vague uses the unchanged binary missed list; confidence/filter/alternate-question availability are separate audit measures. The 52 threshold sits in the observed 49.99–54.63 gap. The 50-row calibration has 10 guard-based and 1 content-only wrong; the full replay has 274 guard-based and 63 content-only wrong. These are in-sample classifications, not new human judgments.

Pure observed Elo starts at 1200, with Easy/Medium/Hard anchors 1000/1200/1400 and K=32. A neutral Medium observation has expected score **0.5**, replacing the misanchored 0.151 expectation in the proposed core. Easy expectation is 0.7597, Hard 0.2403. Only actual supplied observations update the rating; resume evidence does not change it. It is a heuristic rating, never labeled percentile. The existing live Elo code is untouched. No ability validity or latent-theta RMSE is claimed.

## Graph coverage by direction

Each prerequisite is stored once, prerequisite → dependent. Used-with and alternative-language relations have explicit distinct types; alternative-language edges are never downward prerequisites.

| Canonical bucket | Down | Up | Across |
|---|---|---|---|
| CN | OS | System Design | JavaScript |
| DBMS | — | System Design | Java, ML, Python |
| DSA | — | System Design | ML, OOP |
| HR | — | — | — |
| Java | — | — | DBMS, OOP |
| JavaScript | — | — | CN |
| ML | Python | — | DBMS, DSA |
| OOP | — | — | DSA, Java, Python |
| OS | — | CN, System Design | — |
| Python | — | ML | DBMS, OOP |
| System Design | CN, DBMS, DSA, OS | — | — |

Down: **3/11 (27.3%)**; up: **5/11 (45.5%)**; across: **8/11 (72.7%)**; up-or-across union: **9/11 (81.8%)**. Only ML, CN and System Design have prerequisites. HR is isolated. These are graph availability rates; role membership, bank eligibility/dedup and budget further restrict actual bridges.

## Measured offline firing rates

100 deterministic sessions, seeds 0–99, budgets 8–12 (1,000 selected questions): 34 strong, 33 mixed and 33 weak synthetic profiles, all 11 canonical buckets in shuffled evidence/role order. This run uses **773 primary questions** with full pinned cosine dedup; bundle approval and fallback answer outcomes are unavailable in the replay, so those sources are excluded from these rollout rates. Every selected outcome is an existing scored Good/Average/Poor CSV answer, selected using the documented synthetic ability/difficulty margin and seeded noise. No fabricated score is used.

**This simulation shares question/answer data and its assumed difficulty model with calibration.** It verifies mechanics, not improved interviewing, independent accuracy or production firing rates. It does not compare assessment accuracy with the baseline selector.

| Quantity | Numerator / denominator | Rate |
|---|---:|---:|
| COVER selections | 569 / 1,000 | 56.9% |
| PROBE_HARDER selections | 260 / 1,000 | 26.0% |
| BRIDGE selections | 171 / 1,000 | 17.1% |
| Harder attempts | 295 / 1,000 decisions | 29.5% |
| Harder fallback | 35 / 295 eligible attempts | 11.9% |
| Difficulty relaxation | 17 / 1,000 selections | 1.7% |
| Complete must-cover | 100 / 100 admitted sessions | 100% |
| Same-ID / near-duplicate / concept probes | 0 / 1,000 each | 0% |

Harder-attempt denominator includes selected harder moves and searches that failed, including terminal-Hard cases if they occur; budget-forced COVER and second observations do not trigger the harder rule. In this run all 35 failures were `no_unseen_harder_question`; zero were terminal-Hard. Bridges selected 39 up, 34 down and 98 across. There were 117 no-prerequisite fallbacks, 1 no-eligible-bridge fallback and 1 all-candidates-demonstrated soft-filter fallback. These are reasons, so their denominators differ from move rates.

| Skill | Selected moves | Harder attempts | Harder selected | Harder fallback / attempts | Difficulty relaxation / selections |
|---|---:|---:|---:|---:|---:|
| CN | 79 | 23 | 5 | 18/23 (78.3%) | 0/79 (0.0%) |
| DBMS | 110 | 36 | 36 | 0/36 (0.0%) | 0/110 (0.0%) |
| DSA | 93 | 24 | 24 | 0/24 (0.0%) | 0/93 (0.0%) |
| HR | 65 | 23 | 6 | 17/23 (73.9%) | 0/65 (0.0%) |
| Java | 95 | 34 | 34 | 0/34 (0.0%) | 3/95 (3.2%) |
| JavaScript | 84 | 21 | 21 | 0/21 (0.0%) | 14/84 (16.7%) |
| ML | 74 | 13 | 13 | 0/13 (0.0%) | 0/74 (0.0%) |
| OOP | 103 | 30 | 30 | 0/30 (0.0%) | 0/103 (0.0%) |
| OS | 104 | 38 | 38 | 0/38 (0.0%) | 0/104 (0.0%) |
| Python | 85 | 18 | 18 | 0/18 (0.0%) | 0/85 (0.0%) |
| System Design | 108 | 35 | 35 | 0/35 (0.0%) | 0/108 (0.0%) |

## Cold bank availability and fallback sources

| Bucket | Easy / Medium / Hard | No higher after current + near-dedup |
|---|---:|---:|
| CN | 3 / 92 / 0 | 92/95 |
| DBMS | 3 / 173 / 5 | 5/181 |
| DSA | 4 / 71 / 2 | 2/77 |
| HR | 12 / 19 / 0 | 19/31 |
| Java | 2 / 2 / 1 | 1/5 |
| JavaScript | 2 / 1 / 1 | 1/4 |
| ML | 1 / 116 / 3 | 3/120 |
| OOP | 7 / 32 / 1 | 1/40 |
| OS | 4 / 35 / 1 | 1/40 |
| Python | 9 / 44 / 7 | 7/60 |
| System Design | 5 / 100 / 15 | 15/120 |

Primary bank has **36 Hard questions, zero for CN/HR**. Enumerated single-question cold starts have 147/773 (19.0%) no-higher cases, unchanged after current-question near-dedup: 36 terminal Hard and 111 Medium CN/HR. Nonterminal rate: 111/737 (15.1%). The static primary+curated fallback inventory has 826 questions and 46 Hard, including one Hard each for CN/HR; before history/dedup, no-higher cases fall to 46/826 (5.6%), all terminal Hard. Those combined-inventory counts are not the measured rollout above. One available Hard can be exhausted or deduped.

Equal-weight cold requested-difficulty cells: primary 2/33 (6.1%) missing (Hard CN/HR); combined CSV 0/33 before filters. Real fallback frequency is population/history-dependent and must be measured in stage (b). No missing source is treated as authorization to invent a question.

## Verification and reproduction

Focused run: **160 passed**, including 30 stage-(a) tests (with 100-seed replay inside the invariant test), 60 frozen output cases, band boundaries, graph directions, canonical dedup, infeasible banks, unreviewed-bundle rejection, explicit semantic fallback, three-state boundaries and score-regression checks. The golden test printed `SCORING_MODEL_REVISION_LOADED=1110a243fdf4706b3f48f1d95db1a4f5529b4d41` from the model actually loaded, not just the config constant. No test in this run was sandbox-blocked.

Historical Part I sandbox failures were five local code-runner timeout/memory cases: three `test_worker_enforces_limits` variants (loop, sleep, allocation), infinite-two_sum `test_candidate_failures_are_scored_outcomes`, and infinite-softmax `test_candidate_errors_score_zero_with_a_kind`. macOS denied process inspection through psutil/sysctl. The affected two files passed all 51 tests with that permission; this was not a score failure.

Run from `interViv_best` with the existing virtualenv and offline cached model:
```sh
python -m pytest tests/test_adaptive_policy_stage_a.py tests/test_step1_golden_regression.py tests/test_scorer_v3_baseline_hashes.py tests/test_phase1_scoring.py tests/test_semantic.py -q -s
python scripts/replay_concept_review.py --output-dir data/audits/concept_review
python scripts/export_concept_review_samples.py
python scripts/audit_concept_availability.py --embeddings /private/tmp/interviv_stage_a_embeddings.npz
python scripts/evaluate_policy_stage_a.py --embeddings /private/tmp/interviv_stage_a_embeddings.npz --output-dir data/audits/policy_stage_a
```

The replay writes the embedding cache under `/private/tmp`; subsequent scripts use that same pinned cache. Manual adjudication files are not regenerated by these commands. Source hashes and every simulation decision/answer row are in [simulation summary](../data/audits/policy_stage_a/simulation_summary.json) and [move records](../data/audits/policy_stage_a/simulation_moves.jsonl).

[Read-only concept report and blind export](concept_probe_readonly_review.md). [Proposed pre-shadow go-live criteria](adaptive_policy_go_live_criteria.md) require approval before stage (b); concept probing needs separate review and implementation.
