# Staged Interview Flow — Design Note (`D1`)

## 1. Current Flow as Built

- **Launch & Planning (React + Backend)**: `frontend/src/pages/Practice.jsx:620-642` configures `practiceMode` (`coached_practice` vs `assessment`) and `allowOptionalFollowUps`. Selecting *Full interview* (`Practice.jsx:788-824`) calls `mapFullInterviewToStartPayload` (`frontend/src/lib/practiceBuilder.js:486-503`), sending `{skills, rounds_per_skill, round_type: 'technical_short_answer'}`. On `POST /session/start` (`backend/routes/session.py:1650-1790`), `StartSessionRequest` (`session.py:78-100`) converts legacy or custom `blocks` payloads via `legacy_to_blocks` / `normalize_blocks` and `expand_blocks` (`backend/models/blocks.py:250-613`), validates inventory up front (`_validate_block_content`, `session.py:1241-1400`), prepares round 1 (`_maybe_prepare_opening_bundle`, `session.py:1425-1452`) as `in_progress`, and optionally enqueues background bundles (`_enqueue_remaining_session_bundles`, `session.py:1455-1492`).
- **Turn Lifecycle**: `frontend/src/components/InterviewRoute.jsx:9-40` loads the session and mounts `frontend/src/pages/Interview.jsx`. `Interview.jsx:1258-1415` drives `interviewLifecycle.js` (`answering -> submitting -> reviewing -> activating -> answering | completed | blocked`). `POST /session/answer` (`backend/routes/answer.py:755-1739`) scores the active round, prepares round `n+1` in `ready` status via `prepare_round` (`backend/round_lifecycle.py:63-77`, `answer.py:1451`), and commits round results, `elo_after`, `narration_jobs` (`modules/narration_jobs.py:49-95`), and learning state inside one atomic write. Opening round `n+1` calls `POST /session/{id}/rounds/{n}/activate` (`backend/routes/round_activation.py:45-96`) -> `activate_round` (`round_lifecycle.py:80-96`) to start `started_at` / `expires_at` once. `GET /session/{id}/rounds/{n}/feedback` (`backend/routes/feedback.py:128-200`) returns allowlisted rules feedback and narration status.
- **Follow-Ups Today (3 Structural Gaps)**: Candidates click an optional follow-up button guarded by `window.confirm` (`Interview.jsx:1509-1540`), calling `POST /session/{id}/follow-ups` (`backend/routes/follow_ups.py:45-100`) -> `modules/follow_ups.py`. Today: (1) `backend/routes/follow_ups.py:75` hardcodes `reviewed = None`, forcing every follow-up through the unscored clarification branch (`answer.py:759-780,1087-1098`) instead of using bundle `followups[].targets_concept`; (2) `schedule_follow_up_in_session` (`modules/follow_ups.py:366-372`) appends the follow-up to the **end** of `expanded_plan` (after remaining blocks) rather than inline after the parent turn; and (3) `answer.py:1600-1609` clears `followups: []`, while *Full interview* has no warm-up, practical, behavioural, or in-thread debrief stages. Completed sessions redirect (`InterviewRoute.jsx:21-23`) to `frontend/src/pages/Dashboard.tsx:88-165`.

## 2. Target Staged Flow (6 Stages)

| Stage | Purpose & Content Source | Budget (Q / Time) | Exit Condition |
| :--- | :--- | :--- | :--- |
| **1. Warm-up** | Confidence-building conceptual opener on first selected skill. Source: `easy` bundle (`question_bundle_versions`) or `interview_dataset_v6.csv` / `fallback_question_bank.csv` easy row. | `1` Q · `~120s` advisory (untimed server-side) | Answer submitted (or skipped if configured); transitions to Stage 2. |
| **2. Core** | Adaptive skill rotation across target/selected skills. Source: `bundle_selector` (`reviewed -> auto_checked -> generated` when gate off; `reviewed` only when `REVIEWED_BUNDLES_ONLY=true`) -> CSV/templates (`question_bank.py:485-558`). | `2–4` Q (configurable) · `120s` advisory/turn (`TECHNICAL_ADVISORY_SECONDS`) | All scheduled core rounds + any inline follow-ups complete. |
| **3. Answer-Aware Follow-ups** | Targeted probe on one missed/contradicted concept immediately after a Core turn (`parent_round + 1`). Source: parent bundle `followups[]` matched deterministically against Scorer `v3` concept gaps (`modules/follow_ups.py`). | `0–1` per parent, `<= 2` per block (`MAX_FOLLOWUPS_PER_PARENT=1`, `MAX_FOLLOWUPS_PER_INTERVIEW_BLOCK=2`) · `~90s` advisory | Follow-up answered or candidate skips/advances (or no targeted gap matches). |
| **4. Practical** | Hands-on execution block (`sql`, `coding`, or `system_design`) matched to role track via existing `blocks` validation (`session.py:1266-1335`). | `1–2` problems · `25m` SQL/System Design, `30m` Coding (`blocks.py:260-267`) | Problems submitted or server `expires_at` (`activate_round`) expires. |
| **5. Behavioural** | Role/HR & collaboration reflection using `StarComposer.jsx`. Source: `HR` rows in `data/interview_dataset_v6.csv` (`93` rows) & `data/fallback_question_bank.csv` (`6` rows), or future HR YAML bundles. | `1–2` Q · `~150s` advisory (untimed) | All behavioural questions submitted; unscored (`final_score = None`). |
| **6. Debrief** | In-thread closing summary: per-stage highlights, covered vs missed concepts, allowlisted feedback/narration, and handoff CTA to `/dashboard/{sessionId}`. | `0` Q · Read-only turn | User clicks through to `/dashboard/{sessionId}` (`Dashboard.tsx`). |

## 3. Answer-Aware Follow-Up Selection (Zero Live LLM Calls)

- **Bundle Contract & Gap Signals**: Question bundles already require `>= 2` structured `followups` entries (`modules/question_bundles.py:277-290`), each `{prompt, targets_concept}` where `targets_concept` must appear in `required_concepts[].id`. Candidate scoring (Scorer `v3`, keeping `concept_evaluator_v3` restricted strictly to `bundle_generator.py:1541` checks) records covered/missing/uncertain/contradicted concepts in `scoring_breakdown`.
- **Deterministic Offline Selection**: `modules/follow_ups.py:253-285` (`_extract_gap_concepts`) already prioritizes gaps in order **`contradicted > missing > uncertain`**, and `select_follow_up_spec` selects the first follow-up whose `targets_concept` matches the highest-priority gap (else `followups[0]`). **Zero LLM calls** are needed at runtime:
  1. Look up `followups` from `bundle_store.get_version(bundle_id, version)["content_json"]["followups"]` when `bundle_id` is pinned on the parent round (fixing `backend/routes/follow_ups.py:75`, which currently forces `reviewed = None`), or from `question_context["followups"]` (pipe-split CSV strings in `modules/question_runtime.py:662`).
  2. Fix `schedule_follow_up_in_session` (`modules/follow_ups.py:366-372`) to **splice the follow-up into `expanded_plan_json` at `parent_round_index + 1`**, renumbering only unstarted future `round` entries and never altering committed round numbers.
  3. Keep non-bundle/string follow-ups explicitly unscored (`follow_up_scoring = "unreviewed"`, `final_score = None`); bundle-backed follow-ups keep current exclusion from primary assessment mean/Elo (`answer.py:1308-1310`) while still showing concept-level feedback.

## 4. One Conversational Screen (Reused vs New UI)

- **Stack**: Existing React + Vite + Tailwind only (`InterviewRoute.jsx` -> `Interview.jsx`); **no new frontend frameworks**.
- **Reused**: `interviewLifecycle.js` (`PHASES`), `StarComposer.jsx` (`Interview.jsx:1410`, highlighted in Behavioural stage), existing SQL/Coding/MCQ/SystemDesign panels, `practiceBuilder.js` validation helpers, and `Dashboard.tsx` at Debrief exit.
- **New Lightweight Components**:
  - `StageRail`: replaces flat `Question 01 / 06` (`Interview.jsx:1264`) with clickable/read-only progress across `Warm-up · Core · Practical · Behavioural · Debrief`.
  - `ConversationThread`: scrollable timeline rendering interviewer prompts, candidate answers, non-leaky allowlisted feedback chips (`feedback.py:38-45`), and inline follow-up turns inside `Interview.jsx` (replacing `window.confirm` + full-card swap at `Interview.jsx:1509-1540`).
  - `StagedDebriefCard`: renders final stage summary inline before redirecting/linking to `/dashboard/{sessionId}`.
  - One `"Staged interview"` card in `Practice.jsx:675-699` alongside `Full interview` and the block Builder.

## 5. Data Model & Real-DB Migration Safety

Reuse `SessionRow.block_plan_json`, `SessionRow.expanded_plan_json`, `RoundRow.private_meta_json`, and `RoundRow.scoring_breakdown_json` (`backend/db/sqlalchemy_models.py:127-235`) for `stage`, `parent_round`, and `targeted_concept`. Add one small nullable Alembic migration extending `20261115_0018`:
- `sessions.interview_flow_version VARCHAR(24) NULL` (`NULL` = existing flat/block sessions; `'staged_v1'` = staged flow).
- `rounds.stage VARCHAR(24) NULL` (`'warm_up' | 'core' | 'follow_up' | 'practical' | 'behavioural'`).
- `rounds.scorer_version VARCHAR(16) NULL` (denormalized mirror of `scoring_breakdown["scorer_version"]` already written by `backend/db/sqlalchemy_store.py:696-699`).

> **Real-DB Migration Warning (`scripts/run_local.py`)**: `scripts/run_local.py:164` sets `DATABASE_URL` to `local-data/interviv-local.sqlite3` (`sha256: 93dfc4b9...f2801`) and `run_local.py:249` unconditionally runs `python -m alembic upgrade head` on startup. **Any** committed migration modifies that real DB on launcher boot. **Rule**: develop and test migrations strictly against a copy (`cp local-data/interviv-local.sqlite3 /tmp/interviv-dev.sqlite3` with explicit `DATABASE_URL`), verify `upgrade head` + `downgrade -1` round-trip, and never run `scripts/run_local.py` or `pregenerate_bundles.py` (protected by `protected_local_db_error()`, `scripts/pregenerate_bundles.py:132-151`) against the original file.

## 6. Scoring in the Flow

- **Pinned to `v3`**: `modules/scoring_schema.py` keeps Scorer `v3` default (`v4` remains OFF behind `SCORER_VERSION=v4`; `v1–v3` baselines/hash locks untouched). Bundle checker `concept_evaluator_v3` stays isolated in `bundle_generator.py:1541` and is never used in candidate scoring.
- **Single Score & Anti-Leak**: Candidate UI displays only `final_score` (and allowlisted `content/strengths/weakness/next_step`, `feedback.py:38-45`); component scores (`nlp_score`, `kg_score`, `svm_label`) and reference answers stay withheld until session completion (`feedback.py:91-99`).
- **Stamped Per Round**: `sqlalchemy_store.py:696-699` stamps `breakdown["scorer_version"] = current_scorer_version()` on every round write (mirrored to `rounds.scorer_version`).
- **Unscored Stages**: **Behavioural** (`HR`), **Warm-up**, and **unreviewed follow-ups** store `final_score = None` (`answer.py:759-780,1087-1098`) and stay excluded from `assessment_eligible_scores` and Elo updates (`answer.py:1308-1310`).

## 7. Cost per Interview (Repo Prices & Token Limits Only)

- **Model & Pricing Source**: `.env.example:52` and `docs/deployment.md:22` set default `OPENROUTER_MODEL=anthropic/claude-haiku-4.5` (`modules/question_bank.py:210` lists `google/gemini-2.5-flash` as a fallback model string without dollar rates). Production USD rates are **not hardcoded**; `modules/bundle_generator.py:666-680` fetches live OpenRouter `/api/v1/models` pricing at runtime. The repo-recorded rate for `anthropic/claude-haiku-4.5` in `tests/test_ws2_batch_robustness.py:371-372` is **`$0.000001`/prompt token (`$1.00`/1M)** and **`$0.000005`/completion token (`$5.00`/1M)**.
- **Per-Stage Token Caps in Code**:
  - Role-Skill Extraction (Prompt A): `500` in / `350` out est., `max_tokens=700` (`modules/bundle_generator.py:68`, `modules/role_skills.py:1242`, cached in `role_skill_cache`).
  - Bundle Generation (Prompt B) + Blind Check: `800`/`1300` est. (`max_tokens=2200`) + `180`/`240` est. (`max_tokens=380`); optional Audit E.3 `max_tokens=400` (`bundle_generator.py:65-67,765-773`).
  - Legacy question gen: `max_tokens=600` (`question_bank.py:384`, `question_runtime.py:425`); coding coach: `max_tokens=300` (`modules/guidance_coach.py:116`).
  - Narration: `NullNarrationProvider` default (`modules/narration_provider.py:113`) = `0` LLM tokens (`narration_jobs.py:263-319`).

| Stage | Cached / Steady-State Calls | Live Uncached Worst-Case Calls (4 Core + Role) | Estimated USD (`tests/test_ws2_batch_robustness.py:371-372`) |
| :--- | :--- | :--- | :--- |
| **Role-Skill Prefill** | `0` (hit in `role_skill_cache`) | `0–1` Prompt A (`500` in / `350` out) | `$0.0000` cached · `$0.00225` cold (`$0.0040` at `max_tokens=700`) |
| **Warm-up & Core (1 + 3 Q)** | `0` (`reviewed` / `auto_checked` / CSV) | Up to `4` × (Prompt B `800`/`1300` + Blind `180`/`240`) | `$0.0000` cached · **`$0.0347`** est. (`3,920` in / `6,160` out; Prompt B+Blind `max_tokens` ceiling `$0.0555`, `+$0.0080`+in if E.3 triggers) |
| **Follow-ups / Practical / Behavioural / Scoring v3 / Debrief** | `0` (bundle `followups[]` + local SQL/Coding/HR CSV + `v3` + rules narration) | `0` | **`$0.0000`** across both modes |
| **Total per Interview** | **`0` live calls** | **`8–9` live calls** (4 uncached bundles + cold role) | **`$0.0000`** steady state · **`~$0.037`** est. (`~$0.068` max-token ceiling incl. E.3) |

## 8. Offline Behaviour (Live Calls Off — Default)

With `llm_live_fetch_enabled()` off (default): `_inline_bundle_generation_enabled()` and `_background_bundle_prefetch_enabled()` return `False` (`session.py:1402-1422`), and `NullNarrationProvider` is active (`narration_provider.py:113`).
- **Warm-up & Core** pull from stored DB bundles (`bundle_selector.py:106-113`), then `data/interview_dataset_v6.csv` / `data/fallback_question_bank.csv`, then `_TEMPLATES` (`question_bank.py:485-558`).
- **Follow-ups** select matching `targets_concept` prompts from stored bundle `followups[]`, skip cleanly if the fallback question lacks follow-up metadata, or offer unscored clarification on CSV pipe-separated prompts.
- **Practical** (`sql`/`coding`/`system_design`) runs deterministically against local seed tables/banks; **Behavioural** serves the `93` `HR` rows in `interview_dataset_v6.csv` (or `6` in `fallback_question_bank.csv`) with `StarComposer.jsx`.
- **Debrief** serves deterministic rules feedback (`feedback.py:195`), `"Rules feedback"` (`narration.status = "skipped"`, `feedback.py:81-84`), and full `/dashboard/{sessionId}` analytics.

## 9. Build Slices in Order & Explicit Out-of-Scope

1. **Slice 1 — Inline Bundle Follow-Ups**: Splice follow-ups at `parent_round + 1` in `modules/follow_ups.py`, look up stored bundle `followups[]` in `backend/routes/follow_ups.py` when `bundle_id` is pinned, and auto-propose follow-up specs after Core submission (`answer.py`) when enabled. *Tests*: unit tests for inline splice + round renumbering + gap priority (`contradicted > missing > uncertain`); concurrency retry (`SessionWriteConflict`) idempotency test.
2. **Slice 2 — Stage Metadata, Behavioural HR Stage & Safe DB Migration**: Add Alembic nullable columns (`sessions.interview_flow_version`, `rounds.stage`, `rounds.scorer_version`), wire unscored `HR` behavioural + warm-up stages cleanly excluded from Elo/readiness mean, and expose a `staged_v1` `blocks` preset validator. *Tests*: upgrade/downgrade test on temp SQLite copy, backward-compatibility test for legacy `NULL` sessions, and full-scoring exclusion tests.
3. **Slice 3 — Single Conversational Screen (`Interview.jsx`) & Staged Preset (`Practice.jsx`)**: Add `StageRail`, `ConversationThread`, `StagedDebriefCard`, and the `"Staged interview"` launcher card (`Practice.jsx`); remove `window.confirm` follow-up disruption. *Tests*: frontend lifecycle/component tests for all 6 stages and offline mode + end-to-end staged `TestClient` journey test.

- **Explicitly OUT of Scope**: Voice / STT / TTS features (`Interview.jsx` voice controls stay untouched), whiteboard/drawing canvas, authentication (`auth.py` / JWT), database engine changes, `scripts/local_runner.py` / `scripts/run_local.py` changes, and scorer `v1–v4` modifications.

## 10. Risks & Open Questions for Reviewer

- **Q1 (Warm-up under `REVIEWED_BUNDLES_ONLY=true`)**: Should Stage 1 Warm-up use an unscored `easy` CSV/fallback prompt even when `REVIEWED_BUNDLES_ONLY=true`, or require a reviewed bundle?
- **Q2 (Follow-up Trigger in `staged_v1`)**: In `coached_practice`, should missing a `required_concept` on a Core turn automatically insert the matching bundle follow-up inline (no `window.confirm`), while remaining strictly OFF in `assessment` mode?
- **Q3 (Follow-up Score Eligibility)**: Confirm keeping even bundle-backed inline follow-ups excluded from `assessment_eligible_scores` and Elo (`answer.py:1308-1310`) so follow-up coaching never inflates primary scores.
- **Q4 (Behavioural Source)**: `interview_dataset_v6.csv` already has `93` `HR` rows (`fallback_question_bank.csv` has `6`), with no HR YAML bundles yet. Is unscored CSV/fallback `HR` acceptable for Slice 2 until HR bundles are authored?
- **Technical Risks**: (a) Running `scripts/run_local.py` will run Alembic against `local-data/interviv-local.sqlite3` (`run_local.py:164,249`) — keep all migration tests on temp copies; (b) inline renumbering of unstarted `expanded_plan_json` items must stay idempotent across `SessionWriteConflict` retries (`answer.py:1201-1230`); (c) multi-skill topic intersection checks (`session.py:1367-1399`) must stay scoped per block so Practical/Behavioural stages never fail Core skill-topic validation.
