# Proposed go-live criteria — approval required before stage (b)

These are proposed acceptance thresholds for stage (c), written before any shadow logs are collected or reviewed. They are not approved by this change. Stage (b), live routing, dashboard work and concept probing remain unimplemented. Do not tune the criteria after seeing shadow results; a changed criterion requires a dated rationale and explicit approval before a new evaluation window.

## Evaluation window and review protocol

Use at least 200 completed shadow sessions and 1,000 eligible one-step proposals, covering intended roles and budgets 8–12. Each bucket considered for live rollout needs at least 30 proposals from at least 10 sessions. Report excluded, failed and incomplete sessions as well as the analysis denominator. Keep ordinary traffic proportions in aggregate metrics; separately oversample sparse buckets/move types for review and report those strata without presenting the unweighted oversample as a population rate.

Before logs are opened, fix a seed and select 200 proposals for two independent human reviewers. Include at least 20 examples of each available move type (COVER, BRIDGE, PROBE_HARDER), at least 10 per intended canonical bucket, and all error/forbidden-move cases outside the random review sample. Sample at least 100 harder-probe proposals separately for the false-probe check. If a stratum is too small, extend the window or omit that bucket/move from the proposed live rollout; do not silently lower its minimum. Reviewers see the actual preceding question/answer, proposed bank question and declared role/evidence, but not each other’s labels. Preserve each original label and an adjudication by a third human for disagreements. Assistant labels in the concept report do not count as these reviews.

“Sensible” means the move follows the observed evidence, tests a useful role-relevant skill, respects the candidate’s declared scope and available budget, and asks a coherent nonredundant question. “False harder probe” means escalation was unjustified by the preceding answer, the selected question is not meaningfully harder, or it repeats the assessment already made. Source difficulty labels alone do not establish that a question is harder.

## Proposed gates

| Gate | Proposed pass criterion | Denominator / interpretation |
|---|---|---|
| Must-cover and budget | 100% full-session completion of admitted offline scenarios; 100% shadow proposals preserve a feasible completion witness and `remaining >= uncovered` after selection | All tested feasible sessions/proposals; report infeasible admission separately. A one-step shadow observation cannot establish full counterfactual session coverage. |
| Human sensible choices | At least 90% adjudicated sensible overall; at least 80% in every reviewed bucket and move type | Preregistered human sample, with raw reviewer agreement and counts; count unresolved cases as failures. |
| False harder probes | At most 5% adjudicated false; Wilson 95% upper bound at most 10% | At least 100 reviewed PROBE_HARDER proposals; conservative treatment of unresolved cases. |
| Harder fallback | At most 20% overall; at most 30% in each intended live bucket with at least 20 trigger opportunities | Failed strictly-higher search / all eligible harder attempts, including terminal-hard starts. Show trigger and selected-move rates separately. |
| Difficulty relaxation | At most 10% overall; at most 20% in each intended live bucket with at least 30 selections | Selected question differs from requested difficulty / all selected proposals. Report source, requested/actual difficulty and reason. |
| Bridge fallback | At most 20% failed searches when an in-scope graph neighbor exists | Failed question search / eligible graph-neighbor bridge searches, by up/down/across direction. No-prerequisite cases are reported separately and must follow COVER. |
| Repeats and forbidden routing | Zero same-ID or near-duplicate questions, role-gap probes, probes after nonanswers, role-gap cap violations, or out-of-role bridge targets | Every proposal, not only the reviewed sample; preserve source IDs and dedup evidence. |
| Concept probing | Zero proposals or live concept probes | The separate concept flag stays off. Audit items 1–4 require review before design/implementation. A future concept pilot needs its own approved human false-probe gate (proposed ≤5% with 95% upper bound ≤10%, n≥100) before activation. |
| Canonical accounting | Zero duplicate-counted alias attempts/weights; no taxonomy-level evidence tags | All shadow records and later dashboard acceptance tests. |
| Shadow integrity | Zero changed live question/score/session state, zero synthesized outcomes, zero duplicate log records | Idempotency, replay, actual-session observation and flag-off tests. Shadow uses no production RNG. |
| Errors and rollback | Zero unhandled policy exceptions; all infeasible/exhausted inputs fail explicitly to baseline; flag-off restoration verified | All shadow runs plus fault injection. Live enablement remains separate from shadow. |

The primary bank’s CN and HR have zero Hard questions. The stage-(a) simulation already shows harder fallback of 18/23 and 17/23 in those buckets. They would fail the proposed per-bucket gate; there is no automatic exemption for a known bank gap. Stage (c) would require separately reviewed bank availability or a narrower approved rollout that leaves the affected buckets on baseline routing. Curated fallback adds one Hard question to each, but actual post-dedup/post-history availability still has to pass the gate. Report both all-attempt and nonterminal rates so terminal-Hard attempts cannot obscure exhaustion.

## Approval and activation sequence

1. Approve these criteria and the intended role/bucket population before stage (b).
2. Implement stage (b) behind default-off `ADAPTIVE_POLICY_SHADOW`; collect actual-session one-step proposals without applying them. Freeze the evaluation window and publish every numerator/denominator, source version and human review result.
3. Review pass/fail and unresolved cases. Explicitly approve the scope of stage (c); passing metrics is not permission to activate automatically.
4. Implement the live adapter and canonical dashboard under a separate default-off `ADAPTIVE_POLICY_ENABLED`. Shadow takes precedence if both flags are enabled. Verify rollback and begin a limited reviewed rollout. Concept probing stays off throughout unless separately approved and implemented.

The same-bank simulation verifies mechanics only. Its answer data and Easy/Medium/Hard model overlap calibration; it cannot satisfy human-sensibility or false-probe gates, establish independent ability validity, or replace representative shadow review.
