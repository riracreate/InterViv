# Revised implementation plan — Part I merged; stage (a) isolated

Part I was merged by fast-forward at `dc5fdfe` after the requested clean-branch, consumer and storage checks. The latest approval authorizes Part II stage (a) **except PROBE_CONCEPT**. The pure policy, typed graph and band classifier are implemented on `codex/policy-stage-a`, with no session wiring. Concept probing is unimplemented with no flag or state field (removed in Step 0); review audit items 1–4 before designing it. Stage (b), live routing and dashboard changes remain unapproved and unimplemented.

Read the unlabeled worksheet (`data/audits/concept_review/blind_20_pairs.md`), then the read-only concept review (`docs/concept_probe_readonly_review.md`), [stage-(a) results](policy_stage_a_report.md), and [proposed go-live criteria](adaptive_policy_go_live_criteria.md). The criteria require approval before stage (b), before viewing shadow logs. Neither the Tier-3 0.62 threshold nor Tier-2 keyword scoring is changed.

> **Branch note (Step 0, `codex/step0-slice1`):** only the pure modules, their tests and three docs were brought over from `codex/policy-stage-a` @ `307a6a5`. The audit artifacts under `data/audits/concept_review/` and `data/audits/policy_stage_a/`, the scripts `replay_concept_review.py`, `export_concept_review_samples.py`, `audit_concept_availability.py` and `evaluate_policy_stage_a.py`, the stage-(a) edit to `scripts/audit_question_concepts.py`, and `docs/concept_probe_readonly_review.md` exist only on `307a6a5`. References to them below point at that commit, not at this branch.

## Part I: implemented scope and guarantees

The pre-change JSON was captured and committed as **`37e9e95` before any code edits** (source parent `8ab1fc4`). It contains all 50 validation inputs joined to exact bank question/answer pairs and all **10** current regression fixtures, exceeding the eight named in the old plan. The current script has nine OOP cases and one CN entity-swap case. Compared with the eight names in the v1 snapshot, the extras are `repeated_characters` (OOP) and `entity_swap` (TCP/UDP). `git show` confirms `37e9e95` changes only the frozen JSON. The capture uses the unmodified scoring implementation with offline cache `refs/main` verified at `1110a243fdf4706b3f48f1d95db1a4f5529b4d41`, records model-file hashes, package versions, flags, input hashes and full outputs. Tests compare to that immutable file; they never generate a replacement baseline.

Every pre-existing output field is compared recursively to four decimal places, including full rubric, KG nodes/edges/missing keys, keyword coverage, classifier output, scores, feedback and metadata. Only the explicitly added concept and keyword-trace keys are removed for comparison. No score weight, threshold, cap, classifier feature or legacy KG field is changed.

The new runtime model loader explicitly pins the same revision. Legacy keyword credit is **0.72**, not the old plan's assumed 0.62. The already computed keyword cosine is exposed as `similarity`, with `method`; null means no cosine was computed (exact/alias match, empty answer or unavailable model). It would be misleading to fabricate a numeric cosine in those cases. Tier 3 alone uses **0.62**, and the trace records its threshold and model revision. The implementation point is `modules/nlp_scorer.py`, where the cosine already exists; `nlp_scorer_patch.py` does not compute it and remains untouched.

`data/question_concepts_v1.json` is the reviewable offline artifact: question ID → source, ordered concepts, aliases, original question, rubric hash, prompt exclusions and source-file hashes. It covers 773 primary questions, 53 fallback questions and both versions in 12 YAML files (24 bundle records). There is no runtime NER/KG extraction from ideal answers. Unindexed or changed rubrics use explicit keywords only and expose `concept_index_status=unindexed_or_stale`; they do not invent a fallback rubric. Supplied bundle concepts use the existing evaluator's four evidence states, with contradicted misses first. CSV order is preserved; augmentation occurs only below two non-prompt keywords and follows first token offset in the ideal answer.

Prompt exclusion matches whole normalized token sequences, including registered aliases, across displayed question text and separately supplied prompt concepts. It cannot remove IP because of “shipping,” or class because of “classification.” It does not join unrelated prompt fragments into an artificial phrase. Existing `covered`/`missing` fields retain their legacy meanings; the five requested new fields are additive and mirrored at both result levels.

The YAML source files explicitly describe v2 concepts as drafts with review status maintained externally in the database. No file is assumed reviewed merely because it exists. Part I does not promote drafts into production selection.

### Additive three-state diagnostics (Part I amendment)

The **0.62 binary threshold is unchanged**, as are all existing binary concept lists, scores and rubric outputs. New `concept_statuses` contains disjoint ordered `matched` / `uncertain` / `missed` lists; each trace adds `status` and `status_reason`, with versioned cutoff metadata. These fields do not affect the reported score.

Tier-1 supported maps to matched; contradicted/not_demonstrated to missed; uncertain remains uncertain. Tier-2/3 whole-token exact/alias evidence maps to matched. Otherwise cosine <0.30 is missed, [0.30,0.72) uncertain, and ≥0.72 matched provided the original binary decision also matched. Nonempty answers without a computed cosine are uncertain; empty answers are missed but remain protected from probes by the nonanswer rule. Legacy substring-only hits are uncertain.

The cutoffs are in-sample operational bands: 0.30 falls just below reviewed partial support at 0.3009 and a false miss at 0.3015; 0.72 places unsupported matches at 0.6212–0.7048 into uncertainty. All eight false misses and the three separately discussed unsupported matches move to uncertain; this is abstention, not proof of correct classification. The existing 20-pair sample contains only binary misses: 8 false misses (6 Tier 2, 2 Tier 3), 9 real omissions, 2 rubric-overreach cases and 1 partial-support case, labeled by Codex. False-match frequency cannot be estimated from it. Tier 1 was not sampled.

### Exact file scope

All paths below are relative to `interViv_best/`:

| File | Purpose |
|---|---|
| `tests/fixtures/step1_golden_prechange.json` | Frozen pre-change capture; already committed separately |
| `backend/config.py` | Model name/revision constants |
| `modules/semantic_scorer.py` | Explicit pinned model loading |
| `modules/nlp_scorer.py` | Add existing cosine/method to keyword traces |
| `modules/scoring_schema.py` | Add optional scoped diagnostics while preserving legacy fields |
| `backend/scoring/pipeline.py` | Attach diagnostics after existing score calculations |
| `modules/question_concepts.py` | Boundary matching, indexed lookup, precedence, traces and additive three-state status |
| `scripts/build_question_concepts.py` | Offline deterministic index build and `--check` |
| `data/question_concepts_v1.json` | Reviewable generated expected-concept index |
| `scripts/audit_question_concepts.py` | Read-only metric computation; no policy implementation |
| `data/audits/step1_concept_quality.json` | Recomputed metrics and trace examples |
| `data/audits/step1_concept_handcheck.json` | Twenty manually inspected pairs with full text and judgments |
| `tests/test_step1_golden_regression.py` | Frozen regression, three-state boundaries, precedence, ordering and live loaded-revision checks |
| `tests/test_scorer_v3_baseline_hashes.py` | Keep v3 historical hashes frozen; compare approved changed source hashes to pre-Step-1 snapshot and unchanged assets to working tree |
| `docs/step1_concept_quality_report.md` | Quality report and limits |
| `docs/adaptive_interview_implementation_plan.md` | This revised plan |

The external copy at `~/.gemini/antigravity/brain/bcff423f-5a75-466b-9224-94e8fc17edab/implementation_plan.md` is updated to the same text. Existing unrelated working-tree changes and the pre-existing untracked runtime manifest/workbook are excluded from this scope. No Part II selector, follow-up, skill graph, frontend, report, persistence or feature flag code is changed.

### Data and concept quality findings

See [the complete report](step1_concept_quality_report.md) and its JSON evidence. The report includes top 30 concepts per skill, explicit generic-term definitions, generic-dominated/empty-list shares, filtered availability, twenty hand-checked pairs and Tier-3 threshold behavior.

There is one validation-source mismatch: form position 27 / row ID 54 is DBMS in the historical score CSV but HR in both the exact key/dataset pair. It is recorded rather than silently corrected. Current replay yields 6 nonanswer, 11 wrong, 13 vague, 11 adequate, 9 strong; historical tables are not substituted for current results.

The strict index leaves 402/773 primary questions empty after prompt exclusion; frequency filtering raises this to 451/773. These questions still have ideal answers and retain existing scores, but extracted concepts cannot establish complete coverage. The hand-check finds 8 false misses, 9 real omissions, 2 questionable required concepts and 1 partially supported concept in a purposive 20-pair sample. This is assistant manual inspection, not independent human validation or a population error rate.

At 0.62, Tier 3 accepts topical neighbors such as random forest for a single-tree explanation (0.6665) and MongoDB for a generic SQL/NoSQL answer (0.6212), yet misses communication expressed through listening/private conversation (0.6107). The 76 Tier-3 traces include 32 exact/alias hits, 44 cosine checks, 14 semantic hits and 30 misses. Six hits lie in [0.62,0.72). This threshold is diagnostic and unvalidated; it is not proof of mastery.

## Part II: stage (a) delivered; stages (b)/(c) held

Each stage remains a separate reviewable change. Stage (a) is authorized and implemented without session integration. Its concept-probe exception takes precedence over all earlier proposal language below. The outcome and prefix contracts are retained as constraints for a later reviewed design, not implemented concept-probe behavior.

### Stage (a): pure policy, typed graph and bands

Implemented `modules/adaptive_policy.py`, `modules/adaptive_skill_graph.py`, and `modules/answer_bands.py` plus config constants. The core accepts immutable canonical state, supplied observations, precomputed bank features and a seed, returning a decision without database/session/network/UI/global-RNG effects. It supports COVER / PROBE_HARDER / BRIDGE / END, directional graph queries, feasibility-protected budgets, dedup, source/difficulty fallback, canonical evidence inputs and observed Elo re-anchoring. The existing selector does not import it. No concept-probing flag, state field or `NotImplementedError` branch exists (Step 0). No concept-probe selection, outcome-state tracking or prefix formatter is implemented.

**Future PROBE_CONCEPT constraint, pending audit review (not implementation/design approval):** eligibility requires new trace `status == "missed"` and either source Tier 1/2, or source Tier 3 that also survives the frequency-qualified generic filter. Do not use legacy `missed_concepts` as the gate. Uncertain targets are never probed; HR concept probes, nonanswer probes and role-gap probes remain forbidden. Enforce legal bank availability, duplicate checks and per-skill/session caps. PROBE_HARDER retains its separate strong-answer rule; it is not a concept-miss probe. The future prefix contract rejects semantic-only matches even when status is matched; no prefix helper is implemented in this stage.

Delivered deterministic invariant/boundary tests, static bank diagnostics and the in-sample 100-session/1,000-move simulation. Focused validation: 160 passed. The full 2,319-row scoring replay and all 12 bundle checks are read-only audit outputs. Review these results and approve written go-live criteria before stage (b). Production selection remains unchanged.

### Stage (b): shadow-mode logging behind a default-off flag

Wire only the shadow observer into the existing session flow under `ADAPTIVE_POLICY_SHADOW=0`. The existing selector chooses every displayed question. Advance shadow state from actual questions/answers and log one proposed decision per actual round, with idempotency and separate versioned trace storage. Do not apply proposed choices, count hypothetical attempts, synthesize probe outcomes, or consume live RNG. The new `ADAPTIVE_POLICY_ENABLED` go-live path does not exist at this stage; setting a flag cannot activate it prematurely.

Measure proposed choices, applicability, fallbacks and disagreements by canonical bucket, concept tier/status and bridge direction. Specifically report PROBE_HARDER trigger/selection/fallback rates; difficulty relaxation; generic/uncertain-target rejection; HR/nonanswer/role-gap violations; near-duplicates; and extraction-empty cases. Prove shadow non-interference with session outputs and disable/rollback tests. A one-step shadow proposal is not a full counterfactual session or an outcome for an unasked probe.

### Stage (c): go-live and dashboard changes after shadow review

Only after approval of the preregistered go-live criteria, evaluation against those criteria, and explicit review of representative shadow logs, implement the live adapter in the existing `AdaptiveQuestionSelector` and `follow_ups.py`, gated by default-off `ADAPTIVE_POLICY_ENABLED`. Shadow wins if both flags are set. Approve go-live separately; disabling the flag restores baseline selection. Review unresolved confident-miss errors and rubric requiredness, actual fallback/exhaustion rates, coverage, and zero forbidden-probe/repeat violations before activation. No cutoff is silently retuned based on shadow observations.

Then implement canonical-bucket observed-score/evidence/confidence reporting, the revised probe-outcome display, resume skill preselection and General role profile UI. Any display of the pure re-anchored Elo must say heuristic rating, never percentile, and requires stage-(c) review. Show evidence uncertainty honestly; never credit a target just because the probe succeeded after its prompt supplied that target.

### Coverage of the ten prior revisions

| Prior revision | Current disposition | Stage |
|---|---|---|
| 1. Re-anchor/defer Elo; remove percentile | Pure core re-anchors neutral/Medium at 1200; no percentile label; live Elo untouched | (a) delivered; UI (c) |
| 2. Harder/difficulty fallback behavior and rates | Strictly higher only, explicit fallback; static and simulated rates with per-skill denominators | (a) delivered; actual shadow rates (b) |
| 3. Directional bridges and wrong-answer fallback | Down 3/11, up 5/11, across 8/11; wrong DSA/DBMS/OS/Python → COVER | (a) delivered |
| 4. Frequency filter; no HR concept probes | Read-only filter/opportunity audit delivered; HR disabled in counts; PROBE_CONCEPT entirely unimplemented | Separate review gate |
| 5. Config bands, in-sample label, guard/content counts | One configured classifier; n=50 wrong 10 guard/1 content; n=2319 wrong 274 guard/63 content | (a) delivered |
| 6. Probed-concepts set; outcome is probe band | Written contract retained; target excluded from credit never implies failure/mastery; no implementation | After concept audit review |
| 7. Exact/alias-only “You touched on X” | Written constraint retained; semantic-only uses neutral wording; formatter unimplemented | Later reviewed phrasing change |
| 8. Canonical-bucket evidence tags | Pure profiles collapse aliases; no taxonomy tags; dashboard deferred | (a) inputs, (c) reporting |
| 9. Feature flag and shadow mode | No concept-probing flag (removed in Step 0); default-off shadow/live flags specified, no session wiring | (b), (c) pending |
| 10. Shared simulation/calibration data/model | Explicit in simulation protocol and both reports; mechanics only, no independent validity claim | (a) delivered |

## Part II: detailed requirements retained for those stages

### 1. Re-anchor the pure observed Elo

The old neutral 1200 versus Medium 1500 gives `1/(1+10**(300/400)) ≈ 0.151`. The authorized pure core instead uses neutral 1200 and Easy/Medium/Hard anchors 1000/1200/1400, with K=32. Neutral Medium expected score is 0.5. Only observed score/difficulty updates it; resume priors affect routing, not observed ratings. No percentile mapping/label is present. This is a heuristic, not empirically calibrated ability. Existing live Elo and reporting are untouched; any later dashboard rating needs separate stage-(c) review.

### 2. PROBE_HARDER and difficulty relaxation

A higher-difficulty probe requires a real unseen question strictly above the preceding difficulty, within the same canonical skill and passing every duplicate/eligibility filter. Prefer the next level; Easy may jump to Hard only if Medium is unavailable, logging `difficulty_relaxed` with requested and actual levels. Never label a same/lower-difficulty question PROBE_HARDER. On no higher question, log `no_unseen_harder_question` (or `already_at_max_difficulty`), then try the normal upward/across bridge for a strong answer, then COVER. Terminal-hard failures count in the attempted-harder denominator separately.

For COVER/BRIDGE, search all eligible sources at the requested difficulty first: DB-reviewed eligible YAML, primary CSV, then curated fallback CSV. If none exists, relax to the nearest difficulty within the same skill; ties prefer lower. Log requested and actual difficulty, source, reason, candidate counts before/after exclusions and relaxation distance. For PROBE_CONCEPT, a difficulty relaxation may preserve the target and real rubric; never relax away the target. Role-gap questions remain strictly Easy and capped at one: choose another eligible gap/coverage skill if unavailable. No fallback relaxes repeats, semantic near-duplicates or assessment eligibility. Admission/preflight must verify enough distinct bank questions for the budget and must-cover set; infeasible or exhausted banks yield an explicit availability error, not synthetic unscorable questions.

**Measured cold-bank diagnostic rates, not live firing rates:**

| Skill | Primary E/M/H | No strictly harder question / all starts | Missing next level / non-Hard starts | Combined CSV E/M/H |
|---|---|---:|---:|---|
| CN | 3/92/0 | 92/95 (96.8%) | 92/95 (96.8%) | 5/95/1 |
| DBMS | 3/173/5 | 5/181 (2.8%) | 0/176 (0.0%) | 6/175/6 |
| DSA | 4/71/2 | 2/77 (2.6%) | 0/75 (0.0%) | 7/73/3 |
| HR | 12/19/0 | 19/31 (61.3%) | 19/31 (61.3%) | 14/22/1 |
| Java | 2/2/1 | 1/5 (20.0%) | 0/4 (0.0%) | 2/2/1 |
| JavaScript | 2/1/1 | 1/4 (25.0%) | 0/3 (0.0%) | 3/4/2 |
| ML | 1/116/3 | 3/120 (2.5%) | 0/117 (0.0%) | 1/116/3 |
| OOP | 7/32/1 | 1/40 (2.5%) | 0/39 (0.0%) | 9/35/2 |
| OS | 4/35/1 | 1/40 (2.5%) | 0/39 (0.0%) | 6/38/2 |
| Python | 9/44/7 | 7/60 (11.7%) | 0/53 (0.0%) | 11/48/8 |
| System Design | 5/100/15 | 15/120 (12.5%) | 0/105 (0.0%) | 5/103/17 |

Primary bank: 36 Hard questions, none for CN/HR. No-higher fallback occurs for 147/773 (19.0%) enumerated starts: 36 terminal Hard starts plus 111 Medium CN/HR starts. Among non-Hard starts, 111/737 (15.1%) cannot reach the next level. All 111 are Medium CN/HR. The actual fallback bank contains one Hard CN and one Hard HR item; combined canonical CSV counts are 46 Hard across 826 questions. It reduces cold no-higher failures to 46/826 (5.6%), all terminal Hard starts, but one Hard question is easily exhausted and may not pass duplicate filters.

For an equal-weight requested-difficulty audit (11 skills × 3 levels), primary-only difficulty relaxation is needed in 2/33 cells (6.1%, Hard CN/HR). Combined CSV has a question in every cell (0/33), before any session filtering. For the nine strong n=50 answers treated as independent first-attempt triggers with no other exclusions, 8/9 have a higher-level option; 1/9 (11.1%) is already Hard and falls back. These are not session rollout results. Stage-(a) primary-only simulation measures 35/295 harder fallbacks (11.9%) and 17/1,000 difficulty relaxations (1.7%). Actual live/shadow rates remain **unmeasured** because no session wiring exists; shadow mode must report numerators and denominators by canonical skill, source, requested difficulty and exclusion reason, including exhaustion.

### 3. Bridge coverage by direction

Keep one stored prerequisite edge `prerequisite → dependent`. Do not invent reverse prerequisite edges. The proposed six prerequisite edges and eight symmetric used-with edges from the original plan remain; OOP is not a prerequisite for DSA.

| Canonical bucket | Down: prerequisites | Up: dependents | Across: used with |
|---|---|---|---|
| Python | — | ML | OOP, DBMS |
| ML | Python | — | DSA, DBMS |
| DSA | — | System Design | OOP, ML |
| DBMS | — | System Design | Python, Java, ML |
| OS | — | CN, System Design | — |
| CN | OS | System Design | JavaScript |
| System Design | DSA, DBMS, CN, OS | — | — |
| OOP | — | — | Java, Python, DSA |
| Java | — | — | OOP, DBMS |
| JavaScript | — | — | CN |
| HR | — | — | — |

Downward availability is **3/11 (27.3%)**: ML, CN and System Design only. Upward dependent availability is **5/11 (45.5%)**. Used-with availability is **8/11 (72.7%)**; upward-or-across union is **9/11 (81.8%)**. Any technical direction covers 10/11, which is not a downward-coverage claim. Resume/role membership, question availability, role-gap caps, repeats and budget constraints can reduce every rate.

Wrong or nonanswer outcomes in **DSA, DBMS, OS and Python go to COVER** with `no_eligible_prerequisite`; they cannot bridge downward. Wrong answers in Java, JavaScript and OOP behave the same. Wrong/nonanswer ML/CN/System Design may bridge to an eligible prerequisite, otherwise COVER. Strong System Design has no up/across neighbor under these edges and falls back to COVER. Prefer uncovered must-cover neighbors, then role weight, then a deterministic canonical-name tie-break. HR is isolated. Alternative-language edges are not fault-isolation prerequisites. The former 70/71 taxonomy claim remains unverified until a full projection table is reviewed; canonical coverage above is the supported statement.

### 4. Frequency-filtered concept-probe constraints; implementation held

The selector proposal uses the explicit generic-candidate vocabulary and frequency threshold in `scripts/audit_question_concepts.py`: remove generic candidates present in at least `max(3, ceil(0.05*N_skill))` bank questions. This is an auditable heuristic and can remove useful broad concepts. Do not change scoring diagnostics or their order to hide filtered concepts.

Strict primary-bank technical occurrence availability falls from **596/787 (75.7%)** to **494/685 (72.1%)** after filtering; only **280/742 (37.7%)** technical questions have at least one shared remaining target. Combined CSV technical availability is **551/878 (62.8%)**, across **305/789 (38.7%)** questions. The lower combined occurrence rate reflects new singleton concepts, not fewer candidate questions. Exact per-skill rates and denominators are in the quality report; these replace the old 81.4% claim. They measure cold-bank concept availability, not firing rates after the new confident-miss gate; that gate can only reduce observed opportunities.

Disable **concept probes for HR** unconditionally. An HR strong answer may still try a real higher-difficulty bank question if the session includes HR and the other caps permit it; HR never bridges into technical skills. For technical skills, only unprobed, non-prompt targets with additive `status == missed` enter the candidate search: Tier-1/2 concepts qualify on that status, while Tier-3 concepts must also survive the frequency-qualified generic filter. Tier-1/2 explicit rubric requirements are not silently removed merely because a term is frequent. Uncertain targets never trigger a concept probe. The legacy binary missed list is retained for compatibility and is not the routing gate. If none remains, or there is no unseen eligible real-bank probe, log `no_usable_missed_concept` / `no_unseen_concept_probe_in_bank` and continue BRIDGE/COVER. No template follow-up is assessed as an eligible adaptive probe. Because automatic concept quality is weak, these rules first run in shadow mode; applying them requires independent review of false hits/misses and requiredness.

### 5. Band constants and in-sample status

Stage (a) places thresholds in `backend/config.py` with an explicit calibration version. The older offline audit delegates to this classifier:

| Proposed constant | Value |
|---|---:|
| `BAND_NONANSWER_MIN_WORDS` | 8 |
| `BAND_NONANSWER_MAX_SCORE` (strictly below) | 40.0 |
| `BAND_WRONG_MAX_SCORE` (strictly below) | 52.0 |
| `BAND_WRONG_MAX_CORRECTNESS` (strictly below) | 5.0 |
| `BAND_STRONG_MIN_SCORE` | 72.0 |
| `BAND_STRONG_MIN_CORRECTNESS` | 7.5 |
| `BAND_VAGUE_MAX_DEPTH` (strictly below) | 4.2 |
| `BAND_CALIBRATION_STATUS` | `in_sample_n50` |

Retain the total precedence: nonanswer guards/refusals or low-scoring ultra-short answer; then wrong score/correctness/Poor-label/entity-swap/truncation; then strong; then vague if the existing binary missed list is nonempty and score/depth is low; else adequate. Ultra-short alone must not override a high score. Active nonanswer guards still take precedence: Part I has not changed or softened existing brevity guards, so the old blanket “short correct answers never become nonanswer” claim is removed. Empty concept lists cannot establish completeness and should be logged as `no_concept_evidence` even if the total partition calls an intermediate answer adequate.

The **52 cutoff is in-sample**, placed in the observed **49.99–54.63** score gap. Current diagnostic replay of all 50 is 6 nonanswer / 11 wrong / 13 vague / 11 adequate / 9 strong before applying the proposed generic routing filter. **10 wrong items are guard-based** (active `truncated_fragment`) and **1 is content-signal-only**. A capped answer may satisfy both guard and score conditions; this disjoint count labels any active guard first and does not infer what an uncapped score would have been. Record both reasons in shadow logs. No generalization claim is justified by this set.

### 6. Future probe outcome contract — unimplemented pending audit review

Maintain `probed_concepts: dict[canonical_skill, set[canonical_concept]]` plus per-probe records. Add the target only when a selected PROBE_CONCEPT is actually presented, including the originating round/question and probe question ID. A pending/skipped request is not an observed answer; aborted probes keep an explicit pending/aborted status. Once the eligible probe answer is scored, **outcome is the probe's own band**, recorded with its own score, rubric, expected concepts, exclusions and `target_excluded_from_credit` flag.

The target may be named by the bank's question and therefore excluded from matched/missed credit. The outcome still evaluates the probe against that question's own reference/rubric. Adequate/strong is a favorable probe outcome, not proof that the target was explicitly demonstrated; never insert that target into `matched_concepts` or session mastery merely because the probe succeeded. Record any independently supported remaining concepts normally. Do not probe the same canonical target twice in a session, regardless of outcome. Prefer targets whose bank probe asks for an explanation/example with an independently assessable reference.

### 7. Future prefix constraint — no formatter implementation in stage (a)

Use `You touched on {X}. Building on that: …` only if X has new status `matched` and its trace reports `method` exactly `exact` or `alias` **and** a whole-token check confirms that surface/alias in the candidate answer. Do not use it for a semantic match or a bundle-supported state without exact/alias evidence. Otherwise use `Going a step deeper on {canonical_skill}: …`. Neither prefix names a missed target. Pass the complete displayed question to the scorer and include all supplied concepts. Optional rewrite validation must reject newly introduced answer/target terms, and a failed rewrite falls back to the original bank wording.

### 8. Evidence tags belong to canonical buckets

Aggregate all eligible attempts, resume evidence, coverage and report tags once per canonical bucket. SQL/DBMS share DBMS; React/Node.js/JavaScript share JavaScript; FastAPI/Python share Python under the reviewed projection. A single question/attempt contributes once even if several taxonomy aliases mapped to the bucket. Deduplicate role weights by an explicitly chosen rule (proposed maximum constituent weight, then normalize across buckets), so aliases do not multiply influence.

Confidence remains untested n=0, low n=1, moderate n=2, established n≥3. `not_verified` requires a claimed canonical bucket, at least two eligible observations, and observed mean below 45 or both first two observed bands wrong/nonanswer. With n≥3 use the mean rule rather than stale first-two bands if later evidence improves. Never label an untested or one-attempt bucket not_verified; role gaps are not claimed skills. Taxonomy names can explain evidence provenance, not create separate tags or scores. Avoid promising that n≥3 establishes psychometric certainty; it is a count-based badge.

### 9. Feature flag and shadow mode

Proposed flags: `ADAPTIVE_POLICY_ENABLED=0`, `ADAPTIVE_POLICY_SHADOW=0` by default. With neither set, existing selection runs unchanged. With shadow set (including when both flags are set), existing selection remains authoritative and the new policy logs its proposed decision only. Applying adaptive choices requires enabled=true and shadow=false after explicit rollout approval.

Shadow state advances from actual displayed questions and actual scored answers. Never score an answer against an unasked hypothetical question, mutate production attempt/coverage counts for proposed choices, add proposed targets to the live `probed_concepts`, consume production RNG, or persist counterfactual scores. Log actual choice plus proposed `(move, canonical_skill, question_id, difficulty, reason, fallback, target, exclusions, budget, seed, calibration/index versions)` and disagreements. Protect idempotency with session/round keys. Counterfactual full-session coverage cannot be inferred from one-step shadow choices.

Rollout reports must include PROBE_HARDER trigger/selection/fallback rates, difficulty relaxations, per-direction bridge candidate/selection/fallback rates, skipped generic targets, HR probe violations (must be zero), repeat/near-duplicate rates, and policy errors. Disabling the enabled flag restores the existing selector; diagnostics remain separately inspectable. No new flags or shadow runtime are implemented in Part I. Stage (b) provides shadow observation only; the live enabled path is added in stage (c) after review.

### 10. Simulation protocol and shared-data limitation

The stage-(a) mechanics simulation uses 100 seeded candidate profiles, budgets 8–12 and existing Good/Average/Poor bank answers, with all selections and row IDs recorded. Report coverage, harder-trigger/selection/fallback counts, difficulty relaxation, bridge direction, eligible question counts and duplicates. Tests assert hard invariants, not synthetic accuracy. No concept probe or concept-outcome count is synthesized.

The simulator **shares question/answer data and the assumed Easy/Medium/Hard difficulty model with calibration**. It is not independent validation and can favor the policy’s assumptions. It does not establish better assessment accuracy than round-robin. Future comparative efficacy requires held-out questions, independently authored answers/annotations and human sessions. Re-anchored Elo is reported only in native heuristic units; no percentile or Elo-versus-latent-theta validity claim is made.

## Retained Part II architecture and verification constraints

- Stage (a) creates a pure policy module; stage (b) observes actual sessions in shadow; stage (c) delegates from the existing selector to the approved core and uses `follow_ups.py` for phrasing. Preserve current public methods and avoid a parallel production selector.
- Fixed requested length 8–12, default 10, subject to admission feasibility. `must_cover` ≤ floor(0.6*N), evidenced strength opener, then role-weighted claims and at most one role gap. All skills canonicalized before counting.
- Enforce remaining budget versus uncovered must-cover first. Never probe a nonanswer or role gap; role gaps at most one Easy attempt. Concept probes require the new confident-miss/tier gate, at most two consecutively and three total skill attempts; one harder probe on a strong first attempt. HR concept probes disabled.
- Bundle precedence applies only to DB-approved, eligible versions, then primary CSV, then fallback CSV. All scored adaptive questions have their own reference/rubric. Required target/difficulty constraints are applied across all sources before relaxing difficulty.
- Keep zero repeat IDs and within-skill cosine ≥0.85 duplicate exclusion under the pinned model. Offline content-token Jaccard ≥0.65 is only the declared semantic-disabled fallback. Deduplicate equivalent bundle/CSV question identities as well as source IDs. Answer-aware filtering at ≥75% demonstrated expected concepts uses only valid nonempty rubrics; it must not divide by zero or reject every empty-rubric question as fully covered.
- Filter bridge targets to resume/role canonical buckets, respect role-gap and exhaustion caps, and prefer uncovered must-cover. If no legal target exists, take COVER; deterministic exhaustion is explicit.
- Proposed UI work removes resume skill preselection caps, adds General role profiles, and presents observed-score/evidence fields. It is deferred to stage (c).
- Stage-(a) tests cover fixed-seed replay; must-cover feasibility/coverage over 100 seed profiles; no nonanswer/role-gap/HR-concept probes; no repeats/near-duplicates; direction-specific bridges; all fallback paths; canonical aggregation. Target outcomes, shadow non-interference and live flag rollback remain later-stage tests and are not claimed as delivered. Simulation tables are reports, not brittle accuracy assertions.

## Verification record

Part I full-suite run: **1024 passed, 6 skipped**; five local-runner/ML timeout/memory tests hit a macOS sandbox `psutil/sysctl` PermissionError. The two affected test files then passed with process-inspection permission: **51 passed**. After the final bundle-precedence edge-case fix, the focused scoring/golden suite passed **92 tests**; the offline index reproducibility check and `git diff --check` also passed. Every frozen-output case and the index/precedence/boundary/pinning tests passed in the full-suite run. The v3 manifest itself was not regenerated.

The three-state amendment is validated by the focused scoring/semantic/golden suite, including a live model check that prints `SCORING_MODEL_REVISION_LOADED=1110a243fdf4706b3f48f1d95db1a4f5529b4d41`. A separate comparison of all 60 outputs before/after the amendment confirms exact preservation after removing only the new status fields. The frozen JSON hash remains unchanged; no test regenerates it. Final amendment validation: **132 focused scoring/semantic/golden tests passed**, plus the offline index reproducibility check and `git diff --check`. The implementation commit is recorded in the delivery. Part I is committed on `codex/part-i-concept-diagnostics`; unrelated workspace edits are excluded. The latest approval allowed a clean-worktree fast-forward merge of Part I to `current`; stage (a) is now isolated on `codex/policy-stage-a`. All unrelated original-checkout edits are retained. No stage (b)/(c) or concept-probe implementation is performed.


## Latest read-only review and stage-(a) scope

The original 20-pair blind export has no assistant labels. Prior labels: 8 false misses (6 Tier 2, 2 Tier 3), 9 true misses, 2 rubric-overreach, 1 partial support. Below 0.30 there is one pair: strict false-miss 0/1, but rubric-overreach 1/1. New stratified matched sample: assistant-labeled false matches 6/20 (Tier 2 3/10, Tier 3 3/10), not a population estimate. Every Tier-1 bundle was checked: 72 answers, zero post-prompt matches. Tier-2 paraphrase under-credit also affects final_score and is explicitly out of scope for correction.

All 2,319 rows were replayed: 207 vague. With confident-miss/filter/alternate-question/near-dedup gates and HR disabled, strict post-prompt availability is 33/207 (15.9%); permitting the next question to name its rubric target gives 35/207 (16.9%). These are cold-history proxies, not live probe rates. See the report for all skill denominators, top-30 ML/CN/OS concepts, generic-filter zeros and storage deltas.

Stage (a) touches only the following files relative to `interViv_best` (Part I’s historical file scope above is unchanged). On `codex/step0-slice1`, rows marked † exist only on `307a6a5` (see the branch note at the top); Step 0 additionally touches `modules/follow_ups.py` (`non_follow_up_rounds`) and `tests/conftest.py`:

| File | Purpose |
|---|---|
| `backend/config.py` | Band and policy Elo constants only (Step 0) |
| `modules/answer_bands.py` | Pure total band classifier |
| `modules/adaptive_skill_graph.py` | Typed edges, canonical aliases and directional queries |
| `modules/adaptive_policy.py` | Pure budget/dedup/selection/Elo functions; no concept probe |
| `tests/test_adaptive_policy_stage_a.py` | Invariant and boundary tests |
| `scripts/audit_question_concepts.py` † | Delegate historic audit bands to configured classifier (stage-(a) edit not brought over; file here is the `dc5fdfe` version) |
| `scripts/replay_concept_review.py` † | Full pinned scoring replay and all-bundle audit |
| `scripts/export_concept_review_samples.py` † | Blind export and fixed matched-pair sampling |
| `scripts/audit_concept_availability.py` † | Read-only target-in-prompt availability bounds |
| `scripts/evaluate_policy_stage_a.py` † | Seeded offline mechanics simulation |
| `data/audits/concept_review/all_rows.jsonl` † | All 2,319 scored rows/traces |
| `data/audits/concept_review/full_replay_summary.json` † | Aggregates, storage and source hashes |
| `data/audits/concept_review/blind_20_pairs.json` † | Unlabeled original pairs |
| `data/audits/concept_review/blind_20_pairs.md` † | Unlabeled human worksheet |
| `data/audits/concept_review/prior_20_label_comparison.json` † | Prior labels alongside similarity |
| `data/audits/concept_review/matched_20_sample.json` † | Stratified selection without judgments |
| `data/audits/concept_review/matched_20_adjudication.json` † | Assistant labels/reasons, clearly attributed |
| `data/audits/concept_review/tier1_all_bundles.json` † | All 72 reference/calibration evaluations |
| `data/audits/concept_review/tier1_review_summary.json` † | Per-bundle manual review and limitations |
| `data/audits/concept_review/prompt_inclusive_availability.json` † | Alternate question IDs by eligible target |
| `data/audits/policy_stage_a/simulation_moves.jsonl` † | Every simulated choice/outcome row |
| `data/audits/policy_stage_a/simulation_summary.json` † | Counts, directional coverage and provenance |
| `docs/concept_probe_readonly_review.md` † | Requested read-only review |
| `docs/policy_stage_a_report.md` | Implementation behavior and test/simulation results |
| `docs/adaptive_policy_go_live_criteria.md` | Proposed criteria for approval before shadow logs |
| `docs/adaptive_interview_implementation_plan.md` | Latest approvals, exclusions and scope |

The external plan copy remains synchronized. No frozen fixture, score function, concept threshold, question bank, session integration, UI or database schema is changed by stage (a).
