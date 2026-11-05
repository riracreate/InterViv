# Slice 1 — follow-up compatibility (B1 + B2)

Branch `codex/step0-slice1`. System follow-ups are default-off
(`SYSTEM_FOLLOW_UPS_ENABLED=false`) and, even when enabled, the shipped trigger
proposes nothing. Evidence: `tests/test_slice1_system_follow_ups.py`,
`tests/test_slice1_b2_isolation.py`; before/after transcripts were captured on
the pre-change tree `9c9b5f2` with `tests/slice1_harness.py`.

## Candidate-requested follow-ups: before / after

| Aspect | Before Slice 1 | After B2 | Kind |
|---|---|---|---|
| Consent (`accept_eligibility_consequence`) | required, 422 without | unchanged | unchanged |
| Placement | appended after every assigned round | unchanged | unchanged |
| Prompt text and plan entry | `followups[0]` or default text | byte-identical (transcript test) | unchanged |
| `follow_up_prompt` teaching exposure | recorded on allocation | unchanged | unchanged |
| Eligibility of the follow-up round | excluded (`follow_up` [+ `unreviewed_follow_up`]) | unchanged; evaluated against full history as before | unchanged |
| Elo / mastery / readiness / gap | none (ineligible) | unchanged | unchanged |
| Capacity near the 50-round cap | pending follow-ups were counted as mandatory | pending and materialized follow-ups excluded once (`mandatory_remaining`) | **intended** |
| New attempt snapshot | `rules_replayable=true` | `rules_replayable=false`; `regenerate_rules_feedback` returns `None` (no production caller) | **intended (B2 spec)** |
| Stored snapshots / digests | — | never rewritten; read-time guard only | unchanged |
| Report reveal exposure, reviewed + scored | recorded | recorded | unchanged |
| Report reveal exposure, unreviewed | skipped (score is `None`) | skipped, now even with a numeric score | **intended** |
| Session report and account Progress bodies | — | identical (account transcript test) | unchanged |
| Progress uses mandatory totals; system follow-ups in a separate report section | — | lands in Checkpoint C | pending (C) |
| Legacy (plan-less / index-less) progress and rotation | — | unchanged; never receive system insertion | unchanged |
| Asked-question list for later selection | included follow-up prompts | excludes follow-ups. Only differs with ≥ 2 candidate follow-ups in one session; reviewed (bank-question) follow-ups are never built by the route | intended (B2 spec) |
| Stored session document | specs had no index | every new mandatory spec stores `mandatory_index` (server-only; stripped from `GET /dashboard/{id}`) | **stored-document change** |
| `/continue` building a pending candidate follow-up | built as an ordinary question | unchanged — **known issue, independent of system insertion** (reproduces with the flag off; strict xfail) | known issue |

## System-initiated follow-ups (new)

Inserted at `parent.round + 1` inside the parent's attempt commit; built from a
validated prompt (no bank selector); unscored, assessment-ineligible,
exposure-free; no Elo, mastery, readiness or gap effects; never after the final
mandatory round; never for legacy plans. `follow_up_initiator` and
`follow_up_kind` are private round metadata (`ROUND_PRIVATE_META_KEYS`).

Selector isolation: the next mandatory target (skill, difficulty, targeting
context, Elo input) is resolved at the parent's commit, before the parent's
learning updates, and preserved on that spec (`resolved_next_target`,
server-only). It is reused when the follow-up is submitted or `/continue`
resumes; bank selection happens then. Mandatory rounds are evaluated for
eligibility without follow-ups in their history.

## Known issues (documented, not fixed)

1. **`/continue` and pending candidate follow-ups** (pre-existing). A
   `content_blocked` session whose next round is a pending candidate follow-up
   is continued with an ordinary bank question: no follow-up flags, no
   clarification prompt, and the round would be scored as mandatory.
   Reproduced by the strict xfail
   `test_continue_materializes_pending_candidate_follow_up`. Proposed separate
   fix: extract the submit path's candidate follow-up materialization (bank
   payload, follow-up flags, clarification override for unreviewed entries)
   into one helper used by both `answer.py` and `session_continue.py`, so the
   continued round is byte-identical to what submission would have built.
2. **Reviewed candidate follow-up in report series.** With 80 / 60 plus a
   reviewed candidate follow-up scored 100, the assessed mean and the session
   readiness are 70, but the scored series includes the 100: chart
   (`frontend/src/lib/dashboardMapping.js:249`), best score 100 (`:362`),
   range 40 (`:154-168`), "3 of 3 rounds scored" (`:376`), Elo series of 3.
   Pinned by `test_known_issue_reviewed_candidate_follow_up_in_report_series`.
3. **Pre-existing private-key exposure in `GET /dashboard/{id}`.** Technical
   rounds in the report keep `wpm`, `pause_count`, `follow_up_scoring` and
   `purpose` (the report strips `attempt_snapshot` only). Slice 1 strips its
   own new keys there; the older keys are left as they were.
4. **Scoring input `candidate_baseline`** still averages every prior scored
   round, including scored candidate follow-ups. Changing it would change
   scores, so it is left as is; system follow-ups are unscored and never
   enter it.
