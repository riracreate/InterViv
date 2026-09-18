# Phase 4A assistance and eligibility policy

Authoritative product rules for teaching exposures, assessment eligibility,
and optional follow-ups. Implementation: `modules/assistance_policy.py`,
`modules/teaching_exposures.py`, `modules/follow_ups.py`.

## Policy version

`assistance_v1`. Persisted on every newly submitted attempt with the
eligibility decision. Historical rows without a decision are
`legacy_unknown` — never silently treated as independently assessed.

## Teaching exposures

Durable records in `teaching_exposures` (memory + SQL). Each row identifies:

- owner (`user:{id}` or `guest:{session_id}`)
- session / block / round
- item type + id
- content kind (`hint`, `explanation`, `solution`, `editorial`, `reference`,
  `answer_sketch`, `named_gap`, `follow_up_prompt`, `feedback_reveal`)
- server `delivered_at` + `delivery_order`
- policy version
- concept/topic scope (conservative; may be coarse)
- stable `content_id` and logical `delivery_id` (idempotent retries)

Generation or status-only polls are **not** deliveries. GET feedback may
log an idempotent `feedback_reveal` without advancing session progression.
Phase D `assistance_events` continue to dual-write for owned accounts.

## Eligibility (freeze at submission acceptance)

Evaluated under the session submit lock using exposures with
`delivered_at <= submission cutoff`. Feedback after that cutoff cannot
retroactively mark the committed attempt assisted; it can affect later
attempts.

| Case | Decision |
| --- | --- |
| Follow-up round | `excluded` (`follow_up`) |
| Same-item retry | `excluded` (`same_item_retry`) — window does not help |
| Teaching exposure on exact item (same session, or owned ≤24h cross-session) | `excluded` |
| Related item via shared concepts, or coarse same skill/topic fallback | `excluded` (+ `coarse_topic_scope` when uncertain) |
| Incomplete relevant history | `unknown` — not clean |
| No excluding evidence | `eligible` |
| Pre-4A row | `legacy_unknown` |

Guests: session-scoped only; no device fingerprinting. Owned accounts:
24h cross-session window. The window is a product rule, not proof that
memory resets or that no outside help occurred.

## Primary metric consumers (shared gate)

Assisted / repeated / follow-up / unknown / legacy-unknown attempts do
**not** change:

- block score numerator/denominator (`assessment_eligible_rounds`)
- session overall readiness (population `assessment_eligible`)
- candidate Elo (atomic commit)
- skill-graph rolling mean + graph Elo (post-commit; SQL mean filters
  eligible + legacy unassisted)
- concept mastery updates
- assessed counts in reports

They remain visible as practice (“Practiced with help”, “Follow-up”,
“Repeated practice”, “Unscored practice”). Numeric scoring formulas,
thresholds, guards, and frozen scorer assets are unchanged — gating is
at commit/aggregate boundaries only.

## Optional follow-ups

- Opt-in Interview-block `allow_optional_follow_ups`; assessment mode
  defaults off.
- Max 1 per parent, 2 per Interview block; never recursive.
- Reserve remaining mandatory rounds under `MAX_TOTAL_ROUNDS` (50); skip
  optional when no spare capacity; do not renumber completed rounds.
- Concurrent requests serialize on the submit lock.
- Reviewed follow-ups would score as practice but stay excluded from
  primary metrics. Unreviewed follow-ups always get a **null** score even
  when `REVIEWED_BUNDLES_ONLY=false`. No production draft approvals; live
  generation stays off. Current inventory: 0 reviewed bundles →
  clarification / unscored path only.

## Labels

Assessment · Coached practice · Practiced with help · Follow-up ·
Repeated practice · Unscored practice.

## Rollback

`alembic downgrade 20260915_0013` drops `teaching_exposures` and
eligibility/follow-up columns on rounds/sessions (4A-only data loss).
Phase D `assistance_events` remain.
