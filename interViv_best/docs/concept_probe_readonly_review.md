# Read-only concept review — 4 November 2026

Open [the unlabeled 20-pair worksheet](../data/audits/concept_review/blind_20_pairs.md) first if you want to label without seeing the assistant judgments. [JSON export](../data/audits/concept_review/blind_20_pairs.json) contains only pair ID, question, concept, tier, full answer excerpt and similarity. The answer is kept whole so evidence is not removed. Neither file contains the assistant labels.

This review changes no thresholds, keyword scoring, bank answers, bundles, sessions, or frozen snapshots. PROBE_CONCEPT remains unimplemented and disabled. New judgments below are Codex assistant manual labels, not independent human annotation.

## Part I merge checks and storage

`codex/part-i-concept-diagnostics` was checked out in a clean worktree at `dc5fdfe`; `git status --short` was empty before merge. `37e9e95` adds only the frozen JSON; `dc5fdfe` contains only the 15 intended implementation/report files listed in the plan. `current` was fast-forwarded to `dc5fdfe`. The original checkout’s unrelated README, coding-language, Adzuna, workbook, runtime-manifest and coding-test edits were preserved and not committed. Stage (a) is on a separate branch.

Consumer audit: no production decision, mastery update, score calculation or dashboard reads the new fields by name. Tests and offline audit scripts read them. The API, frontend state and snapshot code transport/freeze whole concept dictionaries; they already carry the additive fields. Live learning and UI still use legacy `covered`/`missing`. SQL stores the breakdown twice: `RoundRow.scoring_breakdown_json` and `attempt_snapshot_json.scoring_breakdown`.

Compact UTF-8 JSON marginal bytes for `concept_match_trace`, including its key/separator:

| Population | Copies per stored round | Mean bytes | Median | p95 | Max |
|---|---|---|---|---|---|
| 50 validation answers | 1 | 541.5 | 513 | 1531 | 1562 |
| 50 validation answers | 2 | 1083.0 | 1026 | 3062 | 3124 |
| All 2,319 rows | 1 | 284.52 | 25 | 1249 | 2092 |
| All 2,319 rows | 2 | 569.04 | 50 | 2498 | 4184 |

These are serialized payload deltas, not measured database page usage; exclude indexes/compression. Empty trace costs 25 bytes per copy. All additive concept fields together cost a mean 1,369.06 bytes per stored round over the full replay (two copies; median 826, p95 3,528, max 5,364).

Frozen snapshot SHA-256 remains `b8d482e27040e1164700cb3a006867573c86114f9cd87de5e06d52a3c8240915`; the test reads it and asserts its hash again after execution. The two extra captures are `repeated_characters` (OOP) and `entity_swap` (CN), beyond the eight original named fixtures. Loaded model revision in the replay is `1110a243fdf4706b3f48f1d95db1a4f5529b4d41`.

## Original 20 pairs: assistant labels and similarity

Purposive sample of binary misses: 8 false misses (6 Tier 2, 2 Tier 3), 9 true misses, 2 rubric-overreach cases, 1 partial-support case. No matched cases were selected, so this sample cannot estimate false-match rate. Labels and reasoning are preserved unchanged from the Part I hand check.

| Pair | Concept | Tier | Similarity | Assistant label |
|---|---|---|---|---|
| R01 | classification | 3 | 0.5674 | true_miss |
| R02 | regression | 3 | 0.5202 | true_miss |
| R03 | overfitting | 3 | 0.5606 | true_miss |
| R04 | cross-validation | 3 | 0.4114 | true_miss |
| R05 | STAR | 3 | 0.2313 | rubric_overreach |
| R06 | action | 3 | 0.3783 | false_miss |
| R07 | communication | 3 | 0.6107 | false_miss |
| R08 | key distribution | 2 | 0.5921 | false_miss |
| R09 | caching | 3 | 0.3481 | true_miss |
| R10 | caching | 3 | 0.3248 | true_miss |
| R11 | bagging | 3 | 0.3009 | partial_support |
| R12 | regression | 3 | 0.43 | true_miss |
| R13 | unstructured | 2 | 0.3015 | false_miss |
| R14 | asynchronous | 2 | 0.4139 | true_miss |
| R15 | random forest | 3 | 0.5564 | rubric_overreach |
| R16 | function | 3 | 0.3259 | true_miss |
| R17 | encapsulation | 2 | 0.3983 | false_miss |
| R18 | inheritance | 2 | 0.5684 | false_miss |
| R19 | polymorphism | 2 | 0.4095 | false_miss |
| R20 | abstraction | 2 | 0.4561 | false_miss |

Within the **<0.30 bucket**, only R05 (STAR, 0.2313) qualifies. Strict false-miss count is **0/1 (0%)**; however, **1/1 is rubric overreach**: requiring the named STAR framework for that answer is questionable. Thus a concept probe on that sole low-similarity example would still be unjustified. The denominator of one provides no useful validation of the confidence cutoff. If “false miss” includes erroneous rubric requiredness, the broader error rate is 1/1 (100%).

The six Tier-2 false misses are key distribution, unstructured, encapsulation, inheritance, polymorphism and abstraction. **Tier-2 keyword matching under-credits some paraphrases (6/8 false misses), and this also affects `final_score`.** Keyword coverage enters the final-score formula directly (weight 0.20), enters classifier features, and contributes to the lexical fallback. The additive uncertainty fields do not repair those existing score effects. No Tier-2 behavior or threshold is changed in this project.

## Twenty binary matches: stratified sample and false matches

The sample was fixed by SHA-256 ordering with seed `review-seed-20261104` before labeling, without replacement within strata. A supported label requires a meaningful correct concept, paraphrase or example; a bare fragment or topical similarity is insufficient. Overall answer quality is separate. Exact/alias traces have null cosine because the model was not invoked for that term.

| Stratum | Population matches | Sample | False matches | Sample rate |
|---|---|---|---|---|
| tier2_exact_alias | 185 | 6 | 1 | 16.7% |
| tier2_semantic_ge072 | 27 | 4 | 2 | 50.0% |
| tier3_exact_alias | 1105 | 4 | 0 | 0.0% |
| tier3_semantic_062_072 | 53 | 3 | 1 | 33.3% |
| tier3_semantic_ge072 | 83 | 3 | 2 | 66.7% |

**6/20 (30%)** sampled binary matches are false under the assistant labels: Tier 2 **3/10**, Tier 3 **3/10**. This is an unweighted sample rate with unequal stratum allocation, not a bank-wide error estimate. Of the 17 sampled additive-status `matched` cases, 5 are false (29.4%); the other false match is uncertain in the additive field. Raising confidence to ≥0.72 therefore does not eliminate false matches. The 0.62 binary threshold is unchanged.

| Pair | Tier / method | Concept | Cosine | Label | Reason |
|---|---|---|---|---|---|
| M01 | 2 / exact | Single Responsibility | not computed | false_match | The fragment names Single Responsibility but stops at “a class”; it supplies no meaning or application of the principle. |
| M02 | 2 / exact | availability | not computed | supported | The Cassandra AP answer explicitly explains availability and tunable consistency. |
| M03 | 2 / exact | approval | not computed | supported | Manual approval distinguishes Continuous Delivery from Deployment. |
| M04 | 2 / exact | stopPropagation | not computed | supported | The answer correctly explains stopping propagation through the DOM. |
| M05 | 2 / exact | final | not computed | supported | The answer states that final methods cannot be overridden. |
| M06 | 2 / exact | @Autowired | not computed | supported | Spring supplies dependencies via @Autowired; the concept is explained. |
| M07 | 2 / semantic | automated | 0.7855 | supported | Deploying automatically supports automated at concept level; the answer still confuses the two meanings of CD. |
| M08 | 2 / semantic | input validation | 0.9228 | supported | Validating input is a direct paraphrase of input validation. |
| M09 | 2 / semantic | javac | 0.7349 | false_match | Development tools is too general: no Java compiler or javac is identified. |
| M10 | 2 / semantic | genuine weakness | 0.8697 | false_match | No specific technical weakness is identified. This does not assess the candidate’s honesty. |
| M11 | 3 / exact | array | not computed | supported | Array access is supplied as the constant-time example. |
| M12 | 3 / exact | elasticsearch | not computed | supported | Elasticsearch is correctly identified within ELK logging. |
| M13 | 3 / exact | elasticsearch | not computed | supported | The answer explains Elasticsearch shards, replicas and Lucene segments. |
| M14 | 3 / exact | HTTP | not computed | supported | HTTP routes and verbs are explicitly connected to the API. |
| M15 | 3 / semantic | IPv4 | 0.7081 | supported | The IPv4 private-address example supplies the concept, although the overall answer is truncated. |
| M16 | 3 / semantic | parent class | 0.6764 | supported | Subclass/parent coupling and contained objects express the parent-class relationship. |
| M17 | 3 / semantic | DNS | 0.6311 | false_match | The fragment repeats CNAME without demonstrating DNS resolution or authoritative-server behavior. |
| M18 | 3 / semantic | hash function | 0.779 | false_match | The fragment does not mention or explain a hash function; topic similarity is insufficient. |
| M19 | 3 / semantic | parent class | 0.7219 | false_match | The fragment stops at “subclass provides its”; it does not demonstrate a parent-class method relationship. |
| M20 | 3 / semantic | read model | 0.9501 | supported | Read models, denormalization and synchronization are explained. |

[All selected questions, complete answers, references and judgments](../data/audits/concept_review/matched_20_adjudication.json). [Unlabeled selection/provenance](../data/audits/concept_review/matched_20_sample.json).

## All Tier-1 bundles

Checked **12 bundles × 6 answers = 72 answers**, including every reference and all 60 authored calibration examples. There are **204 raw required-concept decisions**, with **11 raw supported** decisions. All 11 are removed by prompt exclusion. There are **zero post-prompt matched Tier-1 decisions**, so the Tier-1 matched-sample stratum and false-match denominator are empty, not 0% error. All 17 retained reference concepts are uncertain. Four bundles lose every concept after prompt exclusion.

The raw supported decisions are consistent with their narrow concept definitions on manual reading, but that does not establish useful scoped matching. Draft bundles are not promoted; author labels are not substituted for independent review.

| Bundle | Raw supported / required decisions | Post-prompt matched / retained decisions | Review note |
|---|---|---|---|
| dbms.acid-properties | 0/30 | 0/24 | Reference/strong/concise answers explain the properties, but all retained properties stay uncertain; rigid phrase evidence under-credits paraphrases. |
| dbms.deadlocks | 1/12 | 0/6 | Circular-wait explanations remain uncertain. The sole raw supported deadlock in the strong answer is removed because the question names deadlocks. |
| dbms.isolation-levels | 0/12 | 0/0 | Both required concepts are in the question; all six scoped lists are empty. No operational match/miss evidence survives. |
| dbms.join-types | 0/18 | 0/12 | Reference and correct examples explain inner/left row retention, but the retained concepts stay uncertain. |
| dbms.normalisation-1nf-3nf | 0/24 | 0/0 | Every required concept is prompt-supplied; all scoped lists are empty. Raw evaluator also under-credits spelling/paraphrase variants. |
| dbms.oltp-vs-olap | 1/12 | 0/0 | Both targets are prompt-supplied. The reference has one raw supported OLAP decision, removed in every scoped result. |
| python.generators | 2/18 | 0/12 | Raw generator support in reference and concise examples is excluded. Yield/lazy-evaluation explanations remain uncertain. |
| python.gil | 0/18 | 0/12 | Reference/strong answers remain uncertain. The concise correct answer receives a missed threading status despite expressing the thread limitation. |
| python.is-vs-equals | 0/12 | 0/12 | Identity/equality explanations in reference/strong/concise examples remain uncertain; no supported state survives. |
| python.lists-vs-tuples | 6/24 | 0/12 | Six raw list/tuple supports are prompt-excluded. Mutable/immutable remain uncertain. Reference also overstates tuple hashability; elements must be hashable, as the strong example correctly qualifies. |
| python.memory-management | 0/12 | 0/12 | Reference/strong answers remain uncertain. Concise cyclic-GC paraphrase is marked not_demonstrated for garbage collection. |
| python.shallow-vs-deep-copy | 1/12 | 0/0 | Both targets are prompt-supplied; all scoped lists are empty. One raw supported shallow-copy decision in the strong answer is removed. |

[Full 72-answer evidence](../data/audits/concept_review/tier1_all_bundles.json) and [review summary](../data/audits/concept_review/tier1_review_summary.json). These examples reveal abstention/under-credit and prompt-exclusion limitations; no bundle or scorer correction is included.

## Generic-concept filter and per-skill shares

Proposed routing-only filter: normalize concept names to case-folded whole tokens; count the number of distinct primary-bank questions containing each concept after prompt exclusion. A concept is generic-filtered only if it is in the explicit vocabulary AND its within-skill document frequency is ≥ `max(3, ceil(0.05 * question_count))`. This is exact canonical-term membership, not substring matching. The vocabulary is:

`function python java javascript ml oop interface list string array node root edge index unique right left inner transaction query object state process thread priority lightweight situation task action result learning feedback communication static`

The generic occurrence share divides filtered concept/question occurrences by all retained occurrences. “Dominated” means a nonempty question concept list has ≥50% filtered concepts; its denominator is all questions, including empty lists. This heuristic is not an intrinsic quality label: broad concepts can be legitimate. Filtering applies to Tier-3 probe eligibility only, never Tier-1/2 explicit rubric requirements or final scores.

| Skill | Questions | Minimum DF | Filtered terms | Generic occurrences / total | Generic share | Dominated questions / all | Dominated share |
|---|---|---|---|---|---|---|---|
| CN | 95 | 5 | none | 0/76 | 0.0% | 0/95 | 0.0% |
| DBMS | 181 | 10 | transaction | 17/92 | 18.5% | 16/181 | 8.8% |
| DSA | 77 | 4 | array, index, node, root | 31/109 | 28.4% | 18/77 | 23.4% |
| HR | 31 | 3 | result, situation | 6/31 | 19.4% | 2/31 | 6.5% |
| Java | 5 | 3 | none | 0/25 | 0.0% | 0/5 | 0.0% |
| JavaScript | 4 | 3 | none | 0/21 | 0.0% | 0/4 | 0.0% |
| ML | 120 | 6 | none | 0/85 | 0.0% | 0/120 | 0.0% |
| OOP | 40 | 3 | interface, python | 13/64 | 20.3% | 7/40 | 17.5% |
| OS | 40 | 3 | process, thread | 16/40 | 40.0% | 13/40 | 32.5% |
| Python | 60 | 3 | function, list, python, string | 25/79 | 31.6% | 17/60 | 28.3% |
| System Design | 120 | 6 | none | 0/196 | 0.0% | 0/120 | 0.0% |

Why zero: ML’s classification (15), overfitting (13) and regression (7) are outside the generic vocabulary; `ml` occurs only 3 times against a cutoff of 6. CN’s HTTP (16) and IP (10) are outside it; JavaScript occurs twice, below 5. System Design’s consistency (13), availability (11) and caching (8) are outside it; JavaScript occurs twice, below 6. Zero therefore means no vocabulary-and-frequency intersection, not no generic language.

Java has only five questions and cutoff 3: `static` occurs twice and all other concepts once. JavaScript has four questions and cutoff 3, with each concept once. Those zeros are driven by the minimum-count floor and tiny banks; they are not evidence of better concept quality.

The following are the top 30 retained concepts by question frequency (alphabetical tie-break). OS has only 16 distinct retained concepts, so all 16 are shown.

### ML

| Concept | Question frequency |
|---|---|
| classification | 15 |
| overfitting | 13 |
| regression | 7 |
| cross validation | 4 |
| loss function | 4 |
| neural network | 4 |
| activation function | 3 |
| ml | 3 |
| random forest | 3 |
| bagging | 2 |
| dropout | 2 |
| f1 | 2 |
| high variance | 2 |
| hyperplane | 2 |
| kernel trick | 2 |
| regularization | 2 |
| underfitting | 2 |
| backpropagation | 1 |
| cnn | 1 |
| gradient descent | 1 |
| learning rate | 1 |
| lstm | 1 |
| precision | 1 |
| recall | 1 |
| reinforcement | 1 |
| resnet | 1 |
| svm | 1 |
| true positive | 1 |
| unsupervised | 1 |
| xgboost | 1 |

### CN

| Concept | Question frequency |
|---|---|
| http | 16 |
| ip | 10 |
| encryption | 5 |
| tls | 5 |
| https | 4 |
| tcp | 4 |
| dns | 3 |
| ipv4 | 3 |
| stateless | 3 |
| udp | 3 |
| application layer | 2 |
| caching | 2 |
| javascript | 2 |
| reliable | 2 |
| router | 2 |
| three way handshake | 2 |
| transport layer | 2 |
| connectionless | 1 |
| faster | 1 |
| ipv6 | 1 |
| packet filtering | 1 |
| rest | 1 |
| subnet | 1 |

### OS

| Concept | Question frequency |
|---|---|
| process | 12 |
| thread | 4 |
| mutual exclusion | 3 |
| circular wait | 2 |
| fcfs | 2 |
| hold and wait | 2 |
| memory space | 2 |
| no preemption | 2 |
| paging | 2 |
| priority | 2 |
| round robin | 2 |
| lightweight | 1 |
| page fault | 1 |
| scheduling | 1 |
| shared memory | 1 |
| virtual memory | 1 |

## All 2,319 CSV rows: vague-band opportunity audit

Every CSV row was scored by the pinned pipeline and then passed through the pure band classifier. Counts: **392 nonanswer, 337 wrong, 207 vague, 148 adequate, 1,235 strong**. Of wrong rows, **274 are guard-based** (truncated_fragment) and **63 content-signal-only**. The disjoint rule counts any active guard first; it does not infer uncapped counterfactual scores. The n=50 calibration retains 10 guard-based versus 1 content-only wrong.

Bands are in-sample: the 52 cutoff lies in the 49.99–54.63 calibration gap. The vague classifier uses the existing binary missed list; confident-miss, generic-filter and availability tests are measured afterwards. This avoids defining vague by the outcome being audited.

An opportunity here means at least one `status=missed` target (Tier 1/2, or Tier 3 surviving the filter) AND another primary-bank same-skill question retaining that target in its post-prompt expected concepts. Only the current question is considered seen. The stricter column also excludes question cosine ≥0.85. This is a cold-history proxy, not actual session availability or a selected probe; duplicate history, skill caps and budgets will reduce it. Conversely, a probe question that explicitly names its target is excluded by this strict metric, so it understates the broader prompt-target-inclusive design space. No such probe is designed or enabled here.

| Skill | All rows | Vague | Confident miss | Filter survivor | Other question | After near-dedup | HR disabled | Share of vague |
|---|---|---|---|---|---|---|---|---|
| CN | 285 | 10 | 1 | 1 | 1 | 1 | 1 | 10.0% |
| DBMS | 543 | 17 | 6 | 6 | 3 | 3 | 3 | 17.6% |
| DSA | 231 | 23 | 3 | 3 | 2 | 2 | 2 | 8.7% |
| HR | 93 | 3 | 1 | 1 | 1 | 1 | 0 | 0.0% |
| Java | 15 | 5 | 2 | 2 | 0 | 0 | 0 | 0.0% |
| JavaScript | 12 | 5 | 1 | 1 | 0 | 0 | 0 | 0.0% |
| ML | 360 | 23 | 2 | 2 | 2 | 2 | 2 | 8.7% |
| OOP | 120 | 14 | 3 | 3 | 3 | 2 | 2 | 14.3% |
| OS | 120 | 5 | 0 | 0 | 0 | 0 | 0 | 0.0% |
| Python | 180 | 31 | 7 | 7 | 7 | 7 | 7 | 22.6% |
| System Design | 360 | 71 | 26 | 26 | 16 | 16 | 16 | 22.5% |

Totals: **52/207** vague rows have a confident miss; all 52 retain at least one qualifying concept after the filter. **35/207 (16.9%)** have another same-skill primary question; **34/207 (16.4%)** remain after near-dedup; **33/207 (15.9%)** remain with HR disabled. Technical-only denominator: **33/204 (16.2%)**. The filter removes no final opportunities in this particular vague subset, despite removing concepts across the bank.

### Availability when the other question names the target

The probe-outcome contract permits a target to be named in the next question and excluded from that answer’s concept credit. Counting those questions when the target is in their offline rubric raises availability to **36/207 (17.4%)**, or **35/207 (16.9%) with HR disabled**. This is the broader answer to “another same-skill question testing it.” System Design increases from 16 to 18; every other skill is unchanged. Technical-only rate is **35/204 (17.2%)**. Both definitions remain cold-history upper bounds with respect to session exhaustion, not actual probe firing rates.

| Skill | Vague | Prompt-inclusive, deduped, HR disabled | Share |
|---|---:|---:|---:|
| CN | 10 | 1 | 10.0% |
| DBMS | 17 | 3 | 17.6% |
| DSA | 23 | 2 | 8.7% |
| HR | 3 | 0 | 0.0% |
| Java | 5 | 0 | 0.0% |
| JavaScript | 5 | 0 | 0.0% |
| ML | 23 | 2 | 8.7% |
| OOP | 14 | 2 | 14.3% |
| OS | 5 | 0 | 0.0% |
| Python | 31 | 7 | 22.6% |
| System Design | 71 | 18 | 25.4% |

[Every eligible target and alternate question ID](../data/audits/concept_review/prompt_inclusive_availability.json). This file records availability only; it selects no question and implements no concept probe.

Similarities in traces are rounded to four decimals; status decisions use the computed value before formatting where available. A displayed 0.3000 can therefore be just below the cutoff. Reproduce eligibility from the recorded status, not a rounded-value reclassification. The <0.30 twenty-pair calculation above uses the exported similarities as requested.

[Every row and concept trace](../data/audits/concept_review/all_rows.jsonl), [aggregate counts and source hashes](../data/audits/concept_review/full_replay_summary.json), [replay script](../scripts/replay_concept_review.py). This replay shares data with calibration and contains no independent human labels. The separate stage-(a) simulation also shares the bank and difficulty model; neither establishes assessment accuracy.
