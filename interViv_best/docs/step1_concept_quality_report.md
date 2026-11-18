# Part I concept-quality report

Read-only audit of bank contents and additive diagnostics. No bank, reference answer, legacy score, or policy behavior was changed for this report.

## Provenance and scope

- Frozen pre-change capture: commit `37e9e95`, `tests/fixtures/step1_golden_prechange.json`; parent `8ab1fc4`. 50 validation inputs plus all 10 current regression cases (9 OOP, 1 CN). The original plan said 8.
- Model: `sentence-transformers/all-MiniLM-L6-v2`, revision `1110a243fdf4706b3f48f1d95db1a4f5529b4d41`. Capture used the unmodified loader offline after verifying the cached main reference and hashing model files. Runtime now passes the same explicit revision.
- Validation is joined by score-row ID to key, then exact stripped question AND answer to dataset. Form position 27 / row 54 has a DBMS historical score label but HR labels in the key and dataset. The input uses the exact key/dataset pair and records the mismatch; sources were not relabeled.
- The index covers 773 unique primary questions, 53 fallback questions and 24 versioned YAML records in 12 files. v2 YAML metadata calls its concepts drafts; repository files cannot establish DB review approval. YAML records are not auto-promoted over CSV questions.
- Extraction now requires whole normalized token/alias spans and augments only when fewer than two explicit non-prompt keywords remain. Therefore the original 1,606 occurrences / 81.4% availability cannot be carried forward.
- The combined CSV audit maps FastAPI to Python and React/Node.js to JavaScript. These are explicit proposed canonical projections, not new runtime routing. Actual fallback source labels differ from the original plan: there are no additional Java or ML rows.

## Frequency filter and empty rubrics

The proposed selector filter removes only terms in the explicit generic-candidate vocabulary whose within-skill document frequency is at least `max(3, ceil(0.05 * questions_in_skill))`. Counts use each distinct post-prompt concept once per question. This is a review heuristic, not a learned quality score. It can remove useful concepts such as `transaction`; low-frequency generic terms can survive. The full candidate vocabulary and retained/removed counts are in `data/audits/step1_concept_quality.json`. Raw Step-1 diagnostics retain these concepts; no production probe policy exists yet.

A question is “generic-dominated” when at least 50% of its nonempty concept list meets that filter. The denominator below is all primary questions, with empty lists reported separately.

| Canonical skill | Questions | Generic-dominated | Empty before → after | Filtered terms |
|---|---:|---:|---:|---|
| CN | 95 | 0/95 (0.0%) | 50 → 50 | — |
| DBMS | 181 | 16/181 (8.8%) | 131 → 145 | transaction |
| DSA | 77 | 18/77 (23.4%) | 24 → 31 | array, index, node, root |
| HR | 31 | 2/31 (6.5%) | 19 → 21 | result, situation |
| Java | 5 | 0/5 (0.0%) | 0 → 0 | — |
| JavaScript | 4 | 0/4 (0.0%) | 0 → 0 | — |
| ML | 120 | 0/120 (0.0%) | 72 → 72 | — |
| OOP | 40 | 7/40 (17.5%) | 13 → 19 | interface, python |
| OS | 40 | 13/40 (32.5%) | 19 → 28 | process, thread |
| Python | 60 | 17/60 (28.3%) | 24 → 35 | function, list, python, string |
| System Design | 120 | 0/120 (0.0%) | 50 → 50 | — |

Overall: 73/773 (9.4%) generic-dominated. Empty lists: 402/773 (52.0%) before filtering, 451/773 (58.3%) after. An empty list means extraction lacks a useful rubric; it is not evidence of a correct or complete answer.

## Generic-term incidence per skill

This is the share of post-prompt **question/concept occurrences** meeting the frequency-qualified generic filter, not the share of questions. A distinct concept counts once within a question. The final column below supplies the previously reported question-level measure for comparison. Zero means no term met this explicit vocabulary/frequency rule; it does not certify the absence of generic language.

| Skill | Generic occurrences / all concept occurrences | Questions at least 50% generic |
|---|---:|---:|
| CN | 0/76 (0.0%) | 0/95 (0.0%) |
| DBMS | 17/92 (18.5%) | 16/181 (8.8%) |
| DSA | 31/109 (28.4%) | 18/77 (23.4%) |
| HR | 6/31 (19.4%) | 2/31 (6.5%) |
| Java | 0/25 (0.0%) | 0/5 (0.0%) |
| JavaScript | 0/21 (0.0%) | 0/4 (0.0%) |
| ML | 0/85 (0.0%) | 0/120 (0.0%) |
| OOP | 13/64 (20.3%) | 7/40 (17.5%) |
| OS | 16/40 (40.0%) | 13/40 (32.5%) |
| Python | 25/79 (31.6%) | 17/60 (28.3%) |
| System Design | 0/196 (0.0%) | 0/120 (0.0%) |

## Probe availability after filtering

A strict occurrence is probeable when another distinct question in the same canonical skill has that concept in its post-prompt expected list. This cold-bank statistic ignores prior asks, near-duplicates, difficulty restrictions and answer-aware deduplication; it is an upper bound on session availability. HR concept probes are disabled in the proposed policy regardless of these counts.

| Skill | Primary before | Primary after | Questions with ≥1 target after | Combined CSV after |
|---|---:|---:|---:|---:|
| CN | 70/76 (92.1%) | 70/76 (92.1%) | 44/95 (46.3%) | 74/100 (74.0%) |
| DBMS | 70/92 (76.1%) | 53/75 (70.7%) | 32/181 (17.7%) | 59/98 (60.2%) |
| DSA | 101/109 (92.7%) | 70/78 (89.7%) | 45/77 (58.4%) | 90/108 (83.3%) |
| HR | 18/31 (58.1%) | 12/25 (48.0%) | 7/31 (22.6%) | 13/36 (36.1%) |
| Java | 2/25 (8.0%) | 2/25 (8.0%) | 2/5 (40.0%) | 2/25 (8.0%) |
| JavaScript | 0/21 (0.0%) | 0/21 (0.0%) | 0/4 (0.0%) | 0/46 (0.0%) |
| ML | 72/85 (84.7%) | 72/85 (84.7%) | 45/120 (37.5%) | 72/85 (84.7%) |
| OOP | 58/64 (90.6%) | 45/51 (88.2%) | 20/40 (50.0%) | 51/73 (69.9%) |
| OS | 35/40 (87.5%) | 19/24 (79.2%) | 9/40 (22.5%) | 32/44 (72.7%) |
| Python | 72/79 (91.1%) | 47/54 (87.0%) | 22/60 (36.7%) | 53/82 (64.6%) |
| System Design | 116/196 (59.2%) | 116/196 (59.2%) | 61/120 (50.8%) | 118/217 (54.4%) |

Primary totals: 614/818 (75.1%) before; 506/710 (71.3%) after. Excluding HR: 596/787 (75.7%) before; 494/685 (72.1%) after, spread across only 280/742 (37.7%) technical questions. Shared skill/concept pairs after filtering: 138/329 (41.9%) technical pairs.
Combined CSV totals excluding HR: 650/977 (66.5%) before; 551/878 (62.8%) after, across 305/789 (38.7%) technical questions. Extra fallback rubrics add many one-off concepts, so the occurrence-weighted rate can fall while question coverage rises.
For a future probe whose own prompt names the target, raw indexed target membership can identify the question but cannot establish candidate credit. The JSON separately provides prompt-target-inclusive counts; the stricter post-prompt rates above are the headline audit. No availability figure is a live firing rate.

## Top 30 concepts per canonical skill

Primary bank, after prompt exclusion, before the generic filter. Normalized aliases are merged; frequency is number of distinct questions. Ties sort alphabetically; fewer than 30 are shown when fewer distinct concepts exist.

| Skill | Concept: question frequency (descending) |
|---|---|
| CN | http: 16; ip: 10; encryption: 5; tls: 5; https: 4; tcp: 4; dns: 3; ipv4: 3; stateless: 3; udp: 3; application layer: 2; caching: 2; javascript: 2; reliable: 2; router: 2; three way handshake: 2; transport layer: 2; connectionless: 1; faster: 1; ipv6: 1; packet filtering: 1; rest: 1; subnet: 1 |
| DBMS | transaction: 17; isolation: 5; acid: 4; primary key: 4; sharding: 4; unique: 4; consistency: 3; durability: 3; referential integrity: 3; right: 3; 1nf: 2; 2nf: 2; 3nf: 2; atomicity: 2; index: 2; inner: 2; join: 2; left: 2; redis: 2; timeout: 2; atomic: 1; availability: 1; caching: 1; circular wait: 1; collection: 1; dataloader: 1; denormalization: 1; eager loading: 1; eventual: 1; graphql: 1 |
| DSA | tree: 15; array: 12; node: 11; stack: 8; lifo: 5; bfs: 4; index: 4; queue: 4; root: 4; dfs: 3; edge: 3; hash function: 3; linked list: 3; recursion: 3; space complexity: 3; binary tree: 2; elasticsearch: 2; fifo: 2; graph: 2; hash table: 2; pointer: 2; python: 2; time complexity: 2; binary search tree: 1; go: 1; java: 1; javascript: 1; overlapping subproblems: 1; pop: 1; push: 1 |
| HR | result: 3; situation: 3; action: 2; conflict resolution: 2; growth mindset: 2; learning: 2; star: 2; task: 2; active improvement: 1; collaboration: 1; communication: 1; feedback: 1; genuine weakness: 1; honest: 1; leadership: 1; progress: 1; quantifiable: 1; self awareness: 1; specific: 1; specific actions: 1; technical challenge: 1 |
| Java | static: 2; @ autowired: 1; @ override: 1; access modifier: 1; bean: 1; bytecode: 1; cache: 1; compiler: 1; constructor: 1; container: 1; contention: 1; covariant: 1; critical section: 1; doubly linked: 1; dynamic array: 1; final: 1; ioc: 1; javac: 1; lock: 1; o 1: 1; object: 1; random access: 1; setter: 1; subclass: 1 |
| JavaScript | addeventlistener: 1; boilerplate: 1; cleanup: 1; componentdidmount: 1; delegation: 1; devtools: 1; encapsulation: 1; inner function: 1; lexical scope: 1; middleware: 1; mount: 1; outer function: 1; propagation: 1; render: 1; saga: 1; stale closure: 1; state: 1; stoppropagation: 1; target: 1; thunk: 1; unidirectional: 1 |
| ML | classification: 15; overfitting: 13; regression: 7; cross validation: 4; loss function: 4; neural network: 4; activation function: 3; ml: 3; random forest: 3; bagging: 2; dropout: 2; f1: 2; high variance: 2; hyperplane: 2; kernel trick: 2; regularization: 2; underfitting: 2; backpropagation: 1; cnn: 1; gradient descent: 1; learning rate: 1; lstm: 1; precision: 1; recall: 1; reinforcement: 1; resnet: 1; svm: 1; true positive: 1; unsupervised: 1; xgboost: 1 |
| OOP | interface: 10; abstraction: 5; liskov substitution: 4; polymorphism: 4; dependency inversion: 3; inheritance: 3; interface segregation: 3; method overriding: 3; parent class: 3; python: 3; single responsibility: 3; code reuse: 2; design pattern: 2; encapsulation: 2; factory: 2; java: 2; observer: 2; singleton: 2; child class: 1; composition: 1; method overloading: 1; oop: 1; open closed: 1; solid: 1 |
| OS | process: 12; thread: 4; mutual exclusion: 3; circular wait: 2; fcfs: 2; hold and wait: 2; memory space: 2; no preemption: 2; paging: 2; priority: 2; round robin: 2; lightweight: 1; page fault: 1; scheduling: 1; shared memory: 1; virtual memory: 1 |
| Python | function: 9; python: 7; decorator: 5; list: 5; tuple: 5; await: 4; generator: 4; immutable: 4; string: 4; dict: 3; event loop: 3; multiprocessing: 3; mutable: 3; yield: 3; caching: 2; context manager: 2; coroutine: 2; threading: 2; with statement: 2; asyncio: 1; ci cd: 1; enclosing scope: 1; gil: 1; inner function: 1; list comprehension: 1; resource cleanup: 1 |
| System Design | consistency: 13; availability: 11; redis: 9; caching: 8; async: 7; fault tolerance: 6; kafka: 6; cache invalidation: 5; cassandra: 5; stateless: 5; dynamodb: 4; microservices: 4; ttl: 4; aws: 3; cdn: 3; message queue: 3; partition tolerance: 3; rabbitmq: 3; elasticsearch: 2; horizontal scaling: 2; javascript: 2; microservice: 2; monolith: 2; service discovery: 2; typescript: 2; aes: 1; angular: 1; api gateway: 1; approval: 1; asynchronous: 1 |

## Twenty-pair manual check

Assistant manual reading of 20 purposively selected answer/concept pairs. Not independent human annotation; not a random sample or an accuracy estimate.

**Labeler: Codex assistant (manual text inspection), with no independent human annotator.** All 20 pairs were sampled from binary misses. There were **8 false misses; false-match count/rate is unmeasured**, because zero matched pairs were included. Of the 8 false misses, **6 are Tier 2** (`ideal_keywords`) and **2 are Tier 3** (`ideal_answer_kg`). No Tier-1 bundle pair was sampled. The separate random-forest, MongoDB and HTTP unsupported-match examples below are all Tier 3 and are **not** part of the twenty-pair sample.

Pairs were chosen to include suspicious misses, honest omissions, HR framework effects, and the OOP paraphrase fixture. “False miss” means the answer expresses that concept; “rubric overreach” means the reference-derived term need not be required by the question. Partial support is kept separate. These counts must not be generalized to the bank.

| Case | Concept / tier | Cosine | Judgment | Reason |
|---|---|---:|---|---|
| validation:1 | classification / ideal_answer_kg | 0.5674 | true_miss | Final predictions do not distinguish classification from regression; no class/label evidence. |
| validation:3 | regression / ideal_answer_kg | 0.5202 | true_miss | Classes and leaves are explained, but continuous regression targets are not. |
| validation:7 | overfitting / ideal_answer_kg | 0.5606 | true_miss | The answer describes sensitivity/underfitting; it does not explain overfitting. |
| validation:7 | cross-validation / ideal_answer_kg | 0.4114 | true_miss | No resampling, folds, or validation procedure is described. |
| validation:8 | STAR / ideal_answer_kg | 0.2313 | rubric_overreach | A sound conflict-handling strategy need not name STAR; the extracted reference framework is not necessarily required. |
| validation:8 | action / ideal_answer_kg | 0.3783 | false_miss | The answer describes concrete actions: listen, hold a private conversation, write approaches and compare criteria. |
| validation:8 | communication / ideal_answer_kg | 0.6107 | false_miss | Private conversation and listening explicitly demonstrate communication; cosine 0.6107 falls below 0.62. |
| validation:9 | key distribution / ideal_keywords | 0.5921 | false_miss | Sharing keys conveys the key-distribution concept at a high level, although the mechanism is incomplete. |
| validation:22 | caching / ideal_answer_kg | 0.3481 | true_miss | Crawler/index/ranking/sharding are described; caching is absent. Its requiredness needs rubric review. |
| validation:24 | caching / ideal_answer_kg | 0.3248 | true_miss | The detailed search design omits caching. This is a real omission, not proof that the otherwise strong answer is wrong. |
| validation:32 | bagging / ideal_answer_kg | 0.3009 | partial_support | Random subsets and aggregation describe the central bagging idea; bootstrap sampling with replacement is not explicit. A binary full miss loses partial evidence. |
| validation:32 | regression / ideal_answer_kg | 0.43 | true_miss | Forest aggregation is explained without describing regression targets or averaged continuous output. |
| validation:36 | unstructured / ideal_keywords | 0.3015 | false_miss | Images are a concrete example of unstructured blob content; a literal label is not needed for this aspect. |
| validation:36 | asynchronous / ideal_keywords | 0.4139 | true_miss | Messages between services do not by themselves establish asynchronous delivery. |
| validation:38 | random forest / ideal_answer_kg | 0.5564 | rubric_overreach | A correct detailed single-tree explanation need not mention random forests; an example/comparison in the ideal became a required concept. |
| validation:41 | function / ideal_answer_kg | 0.3259 | true_miss | The cut-off MRO answer does not address the super function represented in the reference. |
| oop_fixture:paraphrase | encapsulation / ideal_keywords | 0.3983 | false_miss | Hiding internal data behind public methods demonstrates encapsulation. |
| oop_fixture:paraphrase | inheritance / ideal_keywords | 0.5684 | false_miss | A child class reusing parent behavior demonstrates inheritance. |
| oop_fixture:paraphrase | polymorphism / ideal_keywords | 0.4095 | false_miss | One interface taking many forms by overriding derived methods demonstrates polymorphism. |
| oop_fixture:paraphrase | abstraction / ideal_keywords | 0.4561 | false_miss | Exposing essential operations while keeping implementation private demonstrates abstraction. |

Judgment counts: 9 true_miss, 2 rubric_overreach, 8 false_miss, 1 partial_support. Full question, answer, ideal answer, trace and judgment for each pair are in `data/audits/step1_concept_handcheck.json`.

## How 0.62 behaves on Tier 3

Tier 3 first accepts whole-token exact or registered-alias matches. Otherwise it computes the maximum cosine to the existing deterministically sorted answer unigram–4-gram candidates, capped at 80 by `SemanticScorer.max_similarity`. The decision uses the unrounded cosine; the trace rounds to four decimals. The candidate cap and loss of wider context can both hide evidence. Null similarity means no cosine was computed, not a zero score. Legacy Tier-2 credit remains at 0.72.

Across the 50 validation inputs plus 10 fixtures, Tier 3 emits 76 post-exclusion traces: 32 exact/alias hits, 44 cosine checks, 14 semantic hits and 30 misses. Three checked cosines are in [0.60, 0.64]; six extra hits are in [0.62, 0.72). These are diagnostics, not calibration of a new accuracy threshold.

- Useful hit: classification at 0.6442 for “separates the classes.”
- False/unsupported hit: random forest at 0.6665 for an answer that explains only a single decision tree.
- False/unsupported hit: MongoDB at 0.6212 for a generic SQL/NoSQL comparison that never demonstrates MongoDB.
- Unsupported specific detail: HTTP at 0.7048 for the fragment “WAFs protect web applications from common.”
- False miss: communication at 0.6107 for private conversation and listening.
- Partial-evidence miss: bagging at 0.3009 for random subsets and aggregated tree predictions; sampling with replacement is not explicit.
- Requiredness error: random forest at 0.5564 is missed by a strong single-tree explanation, even though the question need not require that comparator.

0.62 is permissive on topical relatedness and still misses paraphrases; it is not a validated demonstration threshold. Keeping these fields additive preserves scores, but they should not yet be treated as reliable mastery evidence. The revised Part II keeps feature flags off and requires shadow evaluation before applying routing. HR concept probes are disabled.

## In-sample answer bands

The proposed thresholds are evaluated only for this report. Current replay: {'vague': 13, 'wrong': 11, 'nonanswer': 6, 'adequate': 11, 'strong': 9}. By source label: {"Poor": {"vague": 3, "wrong": 11, "nonanswer": 6}, "Average": {"vague": 7, "strong": 1, "adequate": 7}, "Good": {"adequate": 4, "vague": 3, "strong": 8}}.
Of 11 wrong items, 10 are guard-based (`truncated_fragment`) and 1 has no active guard and meets content-signal rules. The categories are mutually exclusive by active guard status; guarded scores also meet low-score rules because they are capped, so this is not a causal attribution. Nonanswers are counted separately (6).
The historical plan reported 10 wrong / 7 nonanswer; do not reuse those counts for the current code. The 52 cutoff was chosen in the observed 49.99–54.63 gap and is in-sample. Generic-filtered routing may alter vague/adequate labels; it does not change this wrong/guard decomposition.

## Reproduction

```sh
.venv/bin/python scripts/build_question_concepts.py --check
.venv/bin/python scripts/audit_question_concepts.py --output /tmp/step1_audit.json
.venv/bin/python -m pytest tests/test_step1_golden_regression.py -q
```

The report is descriptive. The audit script reads banks/index and scores stored inputs; it writes only its selected output artifact. The committed golden JSON is never regenerated by tests or audit scripts. Manual judgments are deliberately separate from generated metrics.

## Additive three-state amendment

The binary Tier-3 match threshold stays **0.62**, and Tier-2 binary credit stays **0.72**. Existing `matched_concepts`, `missed_concepts`, trace `matched`, scores and rubric fields retain their prior values. The new trace `status`/`status_reason` and `concept_statuses = {matched, uncertain, missed}` are a separate, disjoint partition; `concept_status_version` and `concept_status_cutoffs` make the rule explicit. Consumers must not combine the old binary lists and the new status lists as if they were one partition.

- Tier 1: supported → matched; contradicted/not_demonstrated → missed; uncertain → uncertain. This retains the bundle evaluator's authority.
- Tier 2/3: whole-token exact/alias evidence → matched; otherwise cosine **<0.30 → missed**, **[0.30,0.72) → uncertain**, and **≥0.72 → matched** provided the original binary decision also matched. The latter check prevents a rounded-up Tier-2 cosine from gaining credit.
- No computed cosine on a nonempty answer → uncertain. An empty answer → missed (the future nonanswer guard still prevents probes). A legacy substring hit without whole-token evidence → uncertain.

The lower cutoff is just below the lowest reviewed partial-support cosine (bagging 0.3009) and false-miss cosine (unstructured content 0.3015). The upper cutoff uses the existing 0.72 keyword standard and places the three discussed unsupported Tier-3 hits (0.6212, 0.6665, 0.7048) in uncertain. All eight manually labeled false misses become uncertain, and those three unsupported matches also become uncertain. This does **not** prove they have been correctly resolved; it defers the decision. Rubric-overreach errors remain possible, especially STAR at 0.2313. Cutoffs are conservative in-sample operational bands, not validated confidence probabilities.

For the 44 computed Tier-3 cosines: 3 are below 0.30, 33 are in [0.30,0.72), and 8 are at least 0.72. Adding 32 exact/alias hits produces **40 matched / 33 uncertain / 3 missed** Tier-3 statuses. Tier 2 yields **29 matched / 22 uncertain / 21 missed** across these 60 cases; some misses come from deliberately empty/gibberish fixtures. Tier 1 has no observations in this sample and is covered by deterministic fixtures, not an empirical quality estimate.

The future PROBE_CONCEPT gate must use `status == missed`, not the retained binary missed list: Tier-1/2 confident misses are candidates; Tier-3 confident misses additionally need the frequency filter. Uncertain concepts never trigger a concept probe. Existing role-gap, nonanswer, HR, budget, availability and repetition restrictions still apply. PROBE_HARDER remains the separate strong-answer rule. `You touched on X` requires exact/alias evidence plus a whole-token check; semantic status matched alone is insufficient. These are Part II design requirements only; no routing or prefix runtime is wired in Part I.

## Pre-merge verification details

The original eight fixture names in `tests/fixtures/scorer_v1_baseline.json` are excellent, paraphrase, partial, empty, gibberish, excessive_repetition, keyword_stuffing and off_topic. The two extra captured cases are **repeated_characters** (OOP) and **entity_swap** (CN: TCP/UDP properties swapped).

`git show --name-only 37e9e95` contains exactly `interViv_best/tests/fixtures/step1_golden_prechange.json` and no code. The golden tests read it with `read_text()`/`json.loads()`, pin its SHA-256 (`b8d482e27040e1164700cb3a006867573c86114f9cd87de5e06d52a3c8240915`), compare all outputs, and verify the hash again after the run. They never regenerate it. A separate before/after check of all 60 pre-amendment outputs also confirmed that only the new three-state fields changed.

During the real golden test run, the test inspects `auto_model.config._commit_hash` on the model actually used by the pipeline's dynamic NLP scorer (not merely a configuration constant) and prints:

```text
SCORING_MODEL_REVISION_LOADED=1110a243fdf4706b3f48f1d95db1a4f5529b4d41
```

The five sandbox-blocked cases in the earlier full-suite run were:

1. `tests/test_local_runner.py::test_worker_enforces_limits` — infinite loop / timeout.
2. The same test — `time.sleep(30)` / timeout.
3. The same test — repeated 8 MB allocations / memory limit.
4. `tests/test_local_runner.py::test_candidate_failures_are_scored_outcomes` — infinite-loop `two_sum` / timeout.
5. `tests/test_ml_execution.py::test_candidate_errors_score_zero_with_a_kind` — infinite-loop NumPy softmax / timeout.

All five failed when `psutil` enumerated child processes to monitor resource limits: macOS sandbox denied `sysctl`, raising `PermissionError: [Errno 1] Operation not permitted`. The two files passed outside that restriction: **51 passed**. These were not scoring assertion failures.

Final amendment validation: **132 focused scoring/semantic/golden tests passed**; the offline concept index reproduced exactly. `git diff --check` passed. The model revision line above was emitted during this test run.
