# Slice 1 — follow-up compatibility (B1 + B2 + C, closure)

Branch `codex/step0-slice1`. System follow-ups are default-off
(`SYSTEM_FOLLOW_UPS_ENABLED=false`) and, even when enabled, the shipped trigger
proposes nothing. Evidence: `tests/test_slice1_system_follow_ups.py`,
`tests/test_slice1_b2_isolation.py`, `tests/test_slice1_c_payloads.py`,
`tests/test_slice1_closure.py`, `frontend/tests/slice1FollowUps.test.js`;
before/after transcripts were captured on the pre-change tree `9c9b5f2` with
`tests/slice1_harness.py`.

## Shared predicate

`modules.follow_ups.is_system_or_unreviewed_follow_up(round)`: a follow-up that
is system-initiated or unreviewed (unscored), regardless of any stored numeric
score. Every candidate-visible Slice 1 behaviour keys on it (report reveal
exposures, rules-replay eligibility, the report-section field). Reviewed,
scored candidate follow-ups are never matched and keep today's behaviour.
Selector isolation (asked list, eligibility history) keys on system follow-ups
only (`non_system_follow_up_rounds`).

## Candidate-requested follow-ups: before / after

| Aspect | Before Slice 1 | After | Kind |
|---|---|---|---|
| Consent (`accept_eligibility_consequence`) | required, 422 without | unchanged | unchanged |
| Placement | appended after every assigned round | unchanged | unchanged |
| Prompt text and plan entry | `followups[0]` or default text | byte-identical (transcript test) | unchanged |
| `follow_up_prompt` teaching exposure | recorded on allocation | unchanged | unchanged |
| Eligibility of the follow-up round | excluded (`follow_up` [+ `unreviewed_follow_up`]) | unchanged; full history as before | unchanged |
| Elo / mastery / readiness / gap | none (ineligible) | unchanged | unchanged |
| Capacity near the 50-round cap | pending follow-ups were counted as mandatory | pending and materialized follow-ups excluded once (`mandatory_remaining`) | **intended** |
| Attempt snapshot, reviewed + scored | `rules_replayable=true` | unchanged, byte-identical digest; replay still works | unchanged |
| Attempt snapshot, unreviewed (new rows) | `rules_replayable=true` | `rules_replayable=false`; `regenerate_rules_feedback` returns `None` (no production caller) | **intended** |
| Stored snapshots / digests | — | never rewritten; read-time guard on unreviewed markers only | unchanged |
| Report reveal exposure, reviewed + scored | recorded | recorded | unchanged |
| Report reveal exposure, unreviewed | skipped (score is `None`) | skipped, now even with a numeric score | **intended (confirmed)** |
| Asked-question list | all prior rounds | unchanged for candidate follow-ups; only system follow-ups are excluded | unchanged |
| Eligibility history of mandatory rounds | all prior rounds | only system follow-ups excluded; candidate follow-ups are never before a mandatory round | unchanged |
| Session report and account Progress bodies | — | identical (account transcript test) | unchanged |
| In-interview progress (indexed plans) | `round/total_rounds`; bar from round position | mandatory rounds: label `mandatory_index/mandatory_total`; bar from server `mandatory_completed`, so it never advances on or moves back for a follow-up | **intended (C)** |
| In-interview progress, candidate follow-up | counted as round `N+1` of `N+1`; the bar moved back | header and question label read **Optional follow-up** (server `progress_label`); mandatory progress stays at 100% (`mandatory_completed == mandatory_total`; index-less plans: 100%) | **intended (closure)** |
| Report section, unreviewed candidate follow-up | listed with unscored rounds; counted in "X of N rounds scored" | separate "Follow-up questions" section (server `report_section`); left out of the unscored list and of N | **intended (C)** |
| Report, reviewed + scored candidate follow-up | in timeline, chart, best score, range, count | unchanged (pinned by `slice1FollowUps.test.js`) | unchanged |
| Labels | "Follow-up · Practiced with help" (interview), "Follow-up" (report) | unchanged; only system follow-ups get the server label "Follow-up (not scored)". The progress position above is a separate field and replaces no existing label | unchanged |
| Additive API fields | — | `mandatory_index` (delivered rounds and start), `mandatory_total` / `mandatory_completed` (start, GET, activate, continue, submit), `current_mandatory_index` / `next_mandatory_index` (submit), `system_follow_up_scheduled` (submit and round history of non-follow-up rounds), `follow_up_label` (system follow-ups), `progress_label` (candidate follow-ups: delivered rounds, round history, submit), `report_section` (report rounds). Mandatory fields are omitted for plans without complete indices; `progress_label` does not depend on them. | additive |
| Legacy (plan-less / index-less) progress and rotation | — | unchanged; never receive system insertion | unchanged |
| Stored session document | specs had no index | every new mandatory spec stores `mandatory_index` (server-only; stripped from `GET /dashboard/{id}`) | **stored-document change** |
| `/continue` building a pending candidate follow-up | built as an ordinary question | unchanged — **known issue, independent of system insertion** (reproduces with the flag off; strict xfail) | known issue |

Why the asked list keeps candidate follow-ups: a reviewed candidate follow-up is
materialized through the bank selector (`_get_next_question`) and served
unmodified, so its question is a real bank item; only unreviewed entries are
overridden with the clarification prompt. B2's first version excluded every
follow-up and, with two reviewed follow-ups, re-served the first one's bank
question to the second (`[DBMS] Stub question 4` twice). The narrowed filter
reproduces the pre-change transcript exactly
(`test_two_reviewed_candidate_follow_ups_unchanged`). The route itself never
builds reviewed entries today (`reviewed = None`), so the case needs storage
seeding to reach.

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
eligibility without system follow-ups in their history.

## Flag-off behaviour

| Condition | Behaviour | Evidence |
|---|---|---|
| Default configuration | `system_follow_ups_enabled` is `False` unless `SYSTEM_FOLLOW_UPS_ENABLED` is set (`backend/config.py:64,173`); `propose_system_follow_up` returns before the trigger is consulted | `test_gates_flag_off_default_trigger_opt_out_and_bad_prompts` |
| Flag on, nothing registered | The registry holds `default_trigger`, which always returns `None`. No setting or environment variable names a trigger; nothing under `backend/` or `modules/` registers one; the production image copies neither `scripts/` nor `tests/` | `test_flag_alone_never_installs_a_trigger`, `test_no_shipped_module_registers_a_trigger`, `test_production_image_and_settings_offer_no_registration_path` |
| Practice start, no follow-up | Equal to the `9c9b5f2` capture with the flag unset and with the flag `true` | `test_transcript_matches_pre_slice1_capture[no_follow_up]` |
| Practice start, candidate follow-up | Equal to the `9c9b5f2` capture, flag unset and `true` | `test_transcript_matches_pre_slice1_capture[candidate_follow_up]` |
| Non-Practice start (the Upload page's legacy body) | Equal to the `9c9b5f2` capture, flag unset and `true`. It carries no opt-in (`allow_optional_follow_ups=False`), so even with the flag on and a trigger that proposes for every parent nothing is proposed or inserted | `test_transcript_matches_pre_slice1_capture[upload_start]`, `test_non_practice_start_never_receives_system_follow_ups` |
| Legacy (index-less) plans | Never receive a system insertion; mandatory fields omitted | `test_legacy_session_without_indices_never_inserts`, `test_legacy_plans_omit_mandatory_fields` |

Differences the transcript comparison allows, and nothing else: the additive
API fields listed above (values asserted separately), the stored
`mandatory_index` on mandatory specs, and `rules_replayable=false` on new
unreviewed follow-up snapshots.

Opt-in today: a system follow-up needs the session's existing
`allow_optional_follow_ups` (`modules/system_follow_ups.py:217`,
`modules/follow_ups.py:304-311`). The Practice page disables that checkbox in
Assessment, but an Assessment session that sets it through the API passes the
same gate (`test_system_path_never_requires_consent_and_honors_api_opt_in`).

## Eligibility and counting

| Quantity | What it counts | Follow-ups |
|---|---|---|
| Scored slots N | Mandatory plan specs (`mandatory_total`). One Interview block holds 1–10 questions; N = 12 needs two blocks | never counted; N is unchanged by insertions (`test_scored_slot_budget_is_preserved_when_follow_ups_are_inserted`) |
| Mandatory progress (interview header) | Closed non-follow-up rounds over `mandatory_total` | never advance it; a candidate follow-up is shown as "Optional follow-up" at 100% |
| Raw `round` / `total_rounds` | Every materialized round / every plan entry | counted (they drive completion and next-round arithmetic) |
| Assessment-eligible population (averages, readiness, Elo, mastery, gap) | `assessment_eligible_rounds`, unchanged | every follow-up is excluded (`follow_up` [+ `unreviewed_follow_up`]); a system follow-up has no numeric score and never changes its parent's stored round or the candidate's ratings (`test_system_follow_up_never_mutates_its_parent_round`, `test_eligibility_unchanged_by_intervening_follow_up`) |
| Report header and summary ("X of N rounds scored") | Rounds outside the follow-up section | system and unreviewed follow-ups are left out of X and N |
| Report scored series (chart, best, range, Elo series) | Scored rounds outside the follow-up section | a reviewed, scored candidate follow-up is included (known issue 2) |
| Report per-block card, account Progress row | Every round in the block / session | counted, including the follow-up section (known issue 5) |
| Follow-up caps | 1 per parent; 2 per Interview block, or the block's lower `max_follow_ups`; total rounds ≤ 50 with mandatory rounds reserved first | one pool shared by both initiators; pending entries hold budget. There is no per-session follow-up cap: two Interview blocks admit four |

The hint, clarification and retry code paths (`modules/assistance_policy.py`,
`modules/teaching_exposures.py`, `backend/routes/learning_hub.py`,
`backend/learning_hints.py`, `backend/routes/follow_ups.py`,
`backend/db/follow_up_allocate.py`) and the scoring pipeline are unchanged
since `dc5fdfe`, and their suites pass unmodified. A submitted round cannot be
resubmitted or rescored (409); `regenerate_rules_feedback` only replays
feedback from a frozen snapshot and has no production caller.

## Round-number arithmetic readers (Checkpoint C)

Raw `round` / `total_rounds` keep counting every materialized round, follow-ups
included; mandatory progress comes only from server-derived fields.

| Reader | Where | Required behaviour | Status |
|---|---|---|---|
| `total_rounds` | `answer.py:202` (`_total_rounds`), GET `/session`, activation, `/continue` | Raw count including follow-ups; a system insertion increments it inside the parent's commit, before the arithmetic below | done (B1) |
| Completion | `answer.py:1566` (`request.round >= total_rounds`) | Uses the post-insertion raw total; never completes before an inserted follow-up | done (B1) |
| `request.round + 1` | `answer.py:1584-1585` | Next raw round; an inserted follow-up occupies it and is built directly from its prompt | done (B1) |
| Round-to-skill mapping | `session.py:191` (`_skill_for_round`) | Explicit spec skill, then `mandatory_index`, then raw round; follow-up specs carry the parent's skill | done (B1) |
| `session_continue` | `session_continue.py:181-182` (`last_submitted + 1`, `> total`) | Raw arithmetic; system follow-up built directly; preserved next-mandatory target reused; response carries mandatory fields | done (B1/B2/C); candidate pending follow-up = known issue 1 |
| Restore after refresh | `session.py:1873-1902` (open / pending / review round), `interviewLifecycle.js:142`, `accountOverview.js:81` | Open/pending/review detection stays raw; round history and active round carry `mandatory_index`, `follow_up_label`, `system_follow_up_scheduled`; client restores progress from them | done (C) |
| Account resume | `dashboard.py:408` (`rounds[-1]`) | Raw latest round; a ready or in-progress follow-up resumes like any round | unchanged |
| Progress (account page) | `dashboard.py:386` (`total_rounds`), `Progress.jsx` history | History counts unchanged (scored rounds / raw total) — required by the account-level regression | unchanged |
| Progress (interview header) | `Interview.jsx` header, `interviewLifecycle.mandatoryProgress` | Indexed plans: label from `mandatory_index`, bar from `mandatory_completed`; legacy plans: historical `round/total`; candidate follow-up: server `progress_label`, bar complete | done (C, closure) |
| Report counts | `dashboardMapping.js:226,412` | `total_rounds` minus follow-up-section rounds; scored series exclude that section (server `completed_rounds` too) | done (C) |
| Start adapters | `Practice.jsx:88`, `Jobs.jsx:201`, `Problems.jsx:155`, `Coach.jsx:174`, `Learn.jsx:113`, `Upload.jsx:277` | Unchanged (they map `total_rounds`); the start response adds `mandatory_*` and the interview hydrates them from GET `/session` on mount (round 1: `mandatory_total == total_rounds`) | unchanged |
| Capacity | `follow_ups.mandatory_remaining` / `spare_capacity` | Follow-ups (pending and materialized) excluded once | done (B1) |
| `last_round` | `answer.py:1901` | Raw submitted round (fallback for the client's round) | unchanged |

## Known-issues register (documented, not fixed in Slice 1)

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
2. **Chart and best score: reviewed candidate follow-up in report series.** With 80 / 60 plus a
   reviewed candidate follow-up scored 100, the assessed mean and the session
   readiness are 70, but the scored series includes the 100: chart
   (`frontend/src/lib/dashboardMapping.js:249`), best score 100 (`:362`),
   range 40 (`:154-168`), "3 of 3 rounds scored" (`:376`), Elo series of 3.
   Pinned by `test_known_issue_reviewed_candidate_follow_up_in_report_series`.
3. **Dashboard `wpm` / `pause_count`: pre-existing private-key exposure in `GET /dashboard/{id}`.** Technical
   rounds in the report keep `wpm`, `pause_count`, `follow_up_scoring` and
   `purpose` (the report strips `attempt_snapshot` only). Slice 1 strips its
   own new keys there; the older keys are left as they were.
4. **Scoring input `candidate_baseline`** still averages every prior scored
   round, including scored candidate follow-ups. Changing it would change
   scores, so it is left as is; system follow-ups are unscored and never
   enter it.
5. **Progress versus report round counts.** The report header and summary
   leave follow-up-section rounds out of "X of N rounds scored"; the report's
   per-block card (`backend/routes/dashboard.py:158`, `_block_results`) and
   the account Progress row (`backend/routes/dashboard.py:385-399`,
   `Progress.jsx:38`) still count them. Measured through the real routes:

   | Session | Report header | Report block card | Progress row |
   |---|---|---|---|
   | 10 mandatory + 1 system follow-up | 10 of 10 rounds scored | Attempted 11 · Scored 10 · Unscored 1 of 11 | 10/11 rounds scored · 1 unscored |
   | 4 mandatory + 1 unreviewed candidate follow-up (flag off) | 4 of 4 rounds scored | Attempted 5 · Scored 4 · Unscored 1 of 5 | 4/5 rounds scored · 1 unscored |

   The second row is reachable today with the flag off; before Checkpoint C
   all three said 4 of 5. Pinned by
   `test_known_issue_block_and_progress_counts_include_follow_up_section_rounds`.
   To be reconciled before system follow-ups are enabled: one server-side
   count over the shared predicate (`is_system_or_unreviewed_follow_up`) used
   by the block card and the Progress row. Other dashboard issues in this
   register are listed only and are not part of that reconciliation.
