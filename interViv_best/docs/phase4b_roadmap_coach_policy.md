# Phase 4B roadmap and coach policy

Authoritative product rules for deterministic study plans and the multi-turn
planning coach. Implementation: `modules/planning_evidence.py`,
`modules/roadmap_plans.py`, `modules/coach_conversation.py`,
`backend/routes/roadmap.py`, `backend/routes/coach.py`.

## Policy versions

| Artifact | Version |
| --- | --- |
| Planning evidence | `planning_evidence_v1` |
| Study plan schema | `study_plan_v1` |
| Coach conversation | `coach_conversation_v1` |
| Planning provider task | `plan_explanation_v1` |
| Assistance (inherited) | `assistance_v1` |

## Evidence populations

Plans distinguish:

| Population | Meaning | May drive |
| --- | --- | --- |
| `eligible` | Independently assessed | Weakness ranking, readiness mean |
| `assisted_practice` | Practiced with help / follow-up | Practice + “assess independently” only |
| `legacy_unknown` | Pre-policy or incomplete history | Not independent mastery |
| `unassessed` | Role-required / goal skill, no attempts | Starter recommendations |
| `planning_context` | Resume / JD / Adzuna-confirmed interests | Context only — never proficiency |

No eligible assessment → starter plan from confirmed goal / role requirements.
**No fabricated readiness percentage or weakness ranking.**

## Deterministic plan selection

Server selects structure, priorities, skill IDs, catalog resources, and
schedule. Default study budget is **6 h/week**, visible and editable.
Stable `task_id`s; regenerating creates a new `version` and preserves
completion for matching IDs. Historical versions remain listed.

Completing a roadmap task updates **task progress only**. It cannot award
score, Elo, readiness, or assessed mastery.

Catalog resources are optional enrichment, never a required deficiency.

## Coach conversation

- Bounded multi-turn dialogue; clarifying questions only when needed.
- Structured goals (`confirmed_goal`, `hours_per_week`, `role_id`,
  `planning_context_skills`, `adzuna_context`) are separate from transcript.
- Ownership on create/read/message/update/clear. Guests: session-scoped key
  if used; owned accounts: `user:{id}`.
- SQL conversations survive DB reopen. Memory storage is process-local.
- Message size ≤ 2000 chars; retained history ≤ 40 messages.
- Normal path with live generation **off** is deterministic templates
  end-to-end (not an empty spinner).

## Provider boundaries

A typed planning task may rewrite approved wording through a fake/gated
provider. Reject and retain deterministic reply when output invents gaps,
scores, readiness, Elo, unsupported resources, plan mutations, or completion.
Schema/provenance checks are structural, not semantic proof.
The LLM has **no tools** and cannot write learning state.

## Planning vs teaching

Planning clarification is **not** automatic teaching exposure. Classification
is application-trusted (`classify_action_kind`). If a permitted action ever
delivers answer-revealing help, Phase 4A release + exposure rules apply.
Coding coach remains separate and must keep accounting correct.

## Jobs / Adzuna handoff

Candidate-confirmed role/skills may enter coach goals. Listing snippets stay
`snippet_is_incomplete`. Optional full JD is user-provided paste. Adzuna
snippets never become assessed evidence.

## Concurrency (honest scope)

- Per-session threading lock: single-process submit / follow-up serialization.
- SQL conditional round claim (`backend/db/round_claim.py`) for multi-worker
  submit races.
- Follow-up caps remain application-level; partial unique index on
  `(session_id, follow_up_parent_round)` when a follow-up round row exists.
- Memory atomic() also snapshots skill-graph / mastery / learning-signal /
  plan / conversation module globals.

## Rollback

Migration `20260918_0015`. Downgrade target: `20260917_0014` (drops
`study_plans`, `coach_conversations`, follow-up unique index). Phase 4A
exposures remain.
