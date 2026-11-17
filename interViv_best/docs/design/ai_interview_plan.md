# AI-run job interview — owner review applied, 17 November 2026

This replaces N1–N3. The owner accepted `3384dd0` and build-step-1 base `6ebfac8`; the offline step-1b corrections are recorded in [the review-fix report](../ai_interview_step1b_report.md). Session integration and build steps 2–6 remain unauthorized; Slices 3b–3e stay paused. The [historical verification record](ai_interview_verification.md) preserves findings a–h and the original branch/test evidence.

## 1. Question path and preparation

The future staged path gives every core question a pinned OpenRouter-generated bundle. `generate_question` will select a servable cached bundle or call `generate_and_check_bundle`, without thin prompts, CSV or templates. Paid setup already returns generic skills/topics/weights; that projection plus deterministic slot allocation supplies the blueprint. **Drop the separate content-plan call: it adds no necessary information.** At start, enqueue all core slots while the unscored warm-up is answered. Check confirmed skill, hash, trust and duplicate identities; later steering selects only compatible prepared inventory.

An incomplete slot shows **Preparing questions**, saves progress and pauses the clock, with retry/cancel/resume. Serve only `reviewed`/`auto_checked`, never generated/rejected content. **Only reviewed bundles feed Elo/readiness**, subject to existing eligibility. Finding f shows this rule is currently missing: add an orchestration check using null-score/practice handling for auto-checked content, retaining private v3 diagnostics. Scorer, evaluator, guard, assistance policy, eligibility, auth and local runner stay unchanged.

## 2. Two model lanes, limits and privacy

The default-off `AI_INTERVIEW_ROUTING_ENABLED` boundary uses two separate settings, independent of legacy model variables:

| Lane | Calls and permitted input | Model selection |
|---|---|---|
| Content | Bundle generation, blind check and audit: generic role/skill/topic metadata, references and synthetic blind answers; **no personal text** | Real dispatch requires the owner's ordered `INTERVIEW_CONTENT_MODELS`, unless `INTERVIEW_ALLOW_CONTENT_DISCOVERY=true` is explicitly set. Validate every ID: zero prompt/completion/request price, text-in/text-out chat, effective context ≥ `INTERVIEW_CONTENT_MIN_CONTEXT` (16,384 default), and `structured_outputs`, `response_format`, `max_tokens` support. Exclude `openrouter/*`, rerankers and embeddings. No hardcoded free IDs. |
| Conversation | Raw JD/role extraction, optional resume, interviewer turn and evidence debrief | `INTERVIEW_CONVERSATION_MODEL`: **`anthropic/claude-haiku-4.5` only**, paid, through OpenRouter. Validate its catalog entry; reject other IDs. |

At the outbound boundary, reject personal text to IDs ending `:free` and conversation calls to any other model. Enforce this before transport/overrides and on retries/fallbacks. Raw JD/role/resume uses the paid lane; content receives only an allowlisted generic projection. Test distinctive answer/resume markers never reach content and free-model conversation overrides dispatch nothing.

Limit global routing concurrency to **2**, starting content requests **4 seconds apart** account-wide (15/min). Reserve durable daily/sliding-minute and interview counters before every attempt, including failures/retries. Step 1 uses a locked single-host metadata journal outside the protected DB, shared across account keys/processes; restart preserves counts and reclaims dead/expired owners. Leases record their start and expire after the greater of 120 seconds or the request timeout plus 60 seconds. `finish_interview` prunes finished counters after leases end, retaining a compact closed-ID marker to prevent a fresh allowance. Future session integration must call it; routes are not wired now. A corrupt/unavailable journal stops dispatch. Limits are [20/min, 50/day, or 1,000/day after $10 lifetime purchase](https://openrouter.ai/collections/free-models); the higher limit requires explicit owner confirmation. Daily reset is UTC midnight (05:30 India time).

For N core slots, cap **6N+1 content** and **N+2 conversation** requests including retries/fallbacks: **17 Quick / 31 Full** total. Cache hits cost no dispatch; exhaustion leaves preparing. Conversation allows one combined setup/extraction, N turns and one debrief; no turn retry.

Pre-generation has a separate content-only `batch_scope` with an explicit immutable `max_requests`, still sharing all account limits. The CLI requires `--max-requests`, supports a stable `--batch-id`, and uses already cached generic role profiles; it cannot perform paid extraction inside the batch. This is infrastructure, not authorization to run pre-generation or a pilot.

Classify **402 and 429** using error metadata/body/reset headers: daily quota stops free routing until reset; credits/key exhaustion stops until corrected; known transient RPM/in-flight limits return a retry deadline. Unknown quota errors stop. Content 400/422 backs off that model for five minutes; the next admission selects the next validated candidate. 401/403 persists an operator access block across days/restarts. 408/all 5xx means model unavailable; URL/network errors become one logged typed deferral. Step 1 returns without sleeping or hidden transport retries. Future queued retry/fallback must re-enter admission; generation/check timeouts remain 45/30 s. Account caps never cycle free models. Paid content requires `ALLOW_PAID_CONTENT_FALLBACK=true`, default **false**.

Accept returned IDs only for the exact requested vendor/model family, allowing valid trailing `YYYYMMDD` or `YYYY-MM-DD` date snapshots. A free request may return its base family without `:free`; a paid request may never return a free ID. Other vendors, versions, sizes or aliases fail. Log requested/returned IDs on every admitted attempt; usage records keep returned IDs and billed tokens even on a rejected family. Confirm this ID rule first in any separately authorized controlled live check. A later pilot reports rejection by model and checker pairing, failures and denominators; no pilot now.

`scripts/list_interview_content_models.py` lists eligible catalog metadata after the live/questions gate, with no completion or journal; it has not been run live. `scripts/interview_llm_status.py` inspects counters/blocks/backoffs/leases offline without writes. After fixing credits, the operator must explicitly use `--clear-credit-block`; correcting 401/403 access requires `--clear-access-block`. Neither clears the other block or refunds counters. Commands and the planning-only two-call live check are in the step-1b report.

Before Start, show: **“Your job description, optional resume, answers and debrief evidence go through OpenRouter to paid Anthropic Claude Haiku 4.5. Generic content may use the listed free models; answers and resumes never do. Answers and feedback are saved locally. Continue only with text you want processed by these services.”** List configured content IDs. Logs contain metadata, not personal text; promise no unverified retention guarantees.

## 3. First card and lengths

**Practice for a job is the first card**, visible without scrolling/settings on mobile and desktop, through every mode, skill selection, loading/error and completed-session state. Existing sign-in rules still gate Start. The old hiding condition was `mode === 'full'` (`10b81fa:frontend/src/pages/Practice.jsx:813`); return to `/practice` cleared that query, with no completion check. Step 0 mounts unconditionally at `Practice.jsx:763`; the new label/above-fold layout remain planned.

Collect JD **or** role, optional resume, confirmed skill chips and length. Chips show **ready / will be generated / unavailable** from inventory/quota health. Allow any technical/non-technical skill without silently remapping it; non-technical roles skip Practical. Preselect the top-weighted skills for the 2/4 core slots, show uncovered skills and allow swaps. No larger budget.

| Displayed estimate (owner-approved mapping) | Preset | Scheduled questions; optional follow-ups |
|---|---|---|
| ~15 min | `quick` | 1 warm-up + 2 core + 0 practical + 0–1 behavioural = **3–4**, plus 0–2 follow-ups |
| ~22 min (the former “30” option) | `full`, explicit practical omission | 1 + 4 + 0 + 0–2 = **5–7**, plus 0–2 |
| ~48 min (the former “45” option), **only for a supported practical track** | `full` with Practical | 1 + 4 + 1 + 0–2 = **6–8**, plus 0–2 |

Read display estimates from `modules/staged_flow.py`, rather than advertising “30”. Hide the practical/full-length option when no role track exists. These UI/omission changes remain future work. Behavioural contributes zero while its reviewed CSV is absent; do not manufacture a bank.

## 4. One interviewer call per core answer

Send question, bundle required concepts/misconceptions and the candidate answer to the paid conversation model. Strict JSON contains one `{concept_id, status, quote}` per required concept, where status is `supported | contradicted | missing | uncertain`, and exactly one `{action: probe | clarify | advance, targets_concept, follow_up_text}`. Missing evidence uses `quote:null`; any supplied quote must be a nonempty, verbatim substring of that answer. Null is never displayed as evidence.

Validate exact concept IDs/quotes and one action. Probe/clarify targets a bundle concept and passes the prompt/reference checks in item 10; advance has no follow-up. Keep coached opt-in, **1/parent, 2/block**, no recursion and existing capacity/preparation checks. Model-written follow-ups stay unscored. On invalid output, veto, refusal, 402/429 or **6 s total timeout**, run the existing deterministic follow-up decision, including its no-follow-up outcome.

Add `interviewer` to `LLM_CONSUMERS`; honor global/consumer gates for both lanes. Store model and deterministic verdicts side by side in private JSON. Cache by accepted submission identity across retries; reuse atomic splicing and log every committed decision once to the follow-up audit file, with model/version, quote validation and fallback reason. Model verdicts never alter scores/Elo/readiness. Follow-up answers use P1 without another model call.

## 5. Evidence debrief

After completion, group by job skill: shown/missed concepts, validated quotes, one fix, revealed reference and **Drill this skill**. Enable Drill only where content exists; otherwise disable it with a reason. Missing quotes say “No supporting quote”; null for missing evidence is approved. Reuse the `(1, 3, 7, 16, 35)` day ladder (`backend/review_schedule.py:24`, `backend/routes/learning_hub.py:1683`). Export per-concept model/evaluator states, model IDs, quote validity and agreement with abstentions/denominators. Debrief failure uses deterministic feedback and verified evidence; drills/model opinions never change measured readiness.

## 6. Estimated requests, tokens, cost and latency

Repo Haiku price fixture: **$1/M input + $5/M output**, not a fresh price quote. Logged generation mean: **803/1,616.25 tokens, 22.79 s**, n=4; blind check **132/201, 3.95 s**, n=1. That is **$0.010021 per generation+check** if paid. Free content has $0 token cost; these paid observations are only a workload proxy for free models, whose latency/quality are unmeasured.

There is **no content-plan request**. Paid setup uses logged 749.33/349.33 tokens (2.75 s); interviewer 1,200/350 ($0.00295, estimated 2–5 s, cutoff 6 s); debrief 2,500/700 ($0.006, estimated 6–12 s). Happy path, no cache/repair:

| Interview | Content requests; input/output tokens | Conversation requests; input/output tokens | Free content + paid conversation | Explicit all-paid content alternative |
|---|---|---|---|---|
| Quick, N=2 | 4; 1,870/3,634.5 | 4; 5,649.33/1,749.33 | **~$0.0144** | **~$0.0344** |
| Full variants, N=4 | 8; 3,740/7,269 | 6; 8,049.33/2,449.33 | **~$0.0203** | **~$0.0604** |

An optional 1,500-token resume adds ~$0.0015 once; repairs, longer answers and debriefs add cost. Fees/taxes excluded. Paid-reference preparation estimates at concurrency 2 are roughly 30–90 s Quick / 60–180 s Full, overlapping warm-up; free-provider waits may be much longer. Record per-request and per-interview tokens, cost, attempts, queue time and p50/p95 latency by lane/model. Full arithmetic and retry allowance are in the verification record.

## 7. Build order — future sessions, each separately reviewable

1. **Routing/privacy:** test model separation, answer/resume-to-free refusal, counters/restarts/concurrency, caps, 402/429/reset and default-off paid fallback.
2. **Bundles/preparing — approval gate first:** list every affected existing assertion with test file:line and old/new expectation, then stop for approval. Only after that review may implementation/tests enforce auto-checked practice-only behavior. Prefetch/preparing/session changes are not authorized now.
3. **First card/setup:** render real Practice content across every mode, account/history/error/skill state, post-completion `/practice` and refresh; check initial viewport placement with existing tools.
4. **Interviewer:** test strict JSON/quotes, band veto, leaks, fallback, 6 s deadline, caps, idempotency and transaction conflicts.
5. **Debrief/export/review:** test reveal gating, quoted skill evidence, CSV abstentions/agreement, drills and unchanged eligible aggregates.
6. **Acceptance:** flag-off transcripts and full offline suites; preregister item 10 before any separately authorized human pilot.

Use `set_bundle_llm_override`, `set_role_skills_llm_override`, `set_narration_provider`, HTTP monkeypatches and conftest network blocking; reset hooks per test. Existing JSON columns/test tools only: **no schema change, migration or new dependency**.

## 8. Existing work retained

Reuse Slice 1's concept-priority fallback, caps, atomic splice and audit; S1b's null follow-up score/masks and deferred feedback; P1's prompt-echo resistance and three-state follow-up outcome; S2's stage tags, unscored warm-up/behavioural loading and practical-track rules; 3a's dispatch, server activation, drafts/resume and retry controller. Reuse coverage distribution/scope disclosure, confirmed-skill relevance and reference checks unchanged. Existing legacy/offline practice remains available through its current entry points. All user-facing scores stay deferred to completion. New orchestration replaces the staged template escape, prefetch scheduling and trust gap; those are not claimed unchanged.

## 9. Older-line supersession

The ws2 line supplies the intended staged follow-up product path, **not a behavioral superset** of the eight older commits. Generic trigger registration, B2 next-target freezing, legacy snapshot guards and separate follow-up report accounting differ or are absent. Preserve both old branches; merge neither. See finding h and the eight-commit comparison for exact evidence.

## 10. Planned reuse from older branches

Copy pure pieces from `codex/step0-slice1`, with provenance and focused tests: `answer_bands.py` as a **veto only** on action/escalation (nonanswer forbids probing; wrong/vague forbid harder escalation; no band authorizes a probe); its n=50 thresholds are in-sample steering, never scoring. Copy `validate_system_prompt` for every model-written follow-up: max 300 chars, one question, no feedback, no unstated rubric aliases; add an explicit reference-language/overlap wrapper because the old helper alone does not guarantee that rule. Restore only required `BAND_*`/`POLICY_*` constants if those pieces are copied; do not activate the old trigger or copy config wholesale.

Adapt `adaptive_policy.py`/`adaptive_skill_graph.py` for 2/4-core budgets and arbitrary job skills before use: begin with COVER; later restrict PROBE_HARDER to justified, in-scope, already prepared questions. BRIDGE stays off. Never persist its observed-Elo calculation as candidate Elo/readiness. Adapt the presentational `FollowUpSection.tsx` and flag-off transcript harness; recapture/review a ws2 baseline rather than treating old fixtures as current truth.

Use `adaptive_policy_go_live_criteria.md` as a protocol model, **not as already matching these numbers**: before results, freeze a representative **100-turn**, two-independent-reviewer sample; require ≥90% sensible turns, ≤5% false probes among probe actions, **zero invented quotes and zero leaked references**. Preserve raw labels, agreement, counts/confidence intervals and adjudication; unresolved cases fail. Include nonanswers, weak/strong answers, non-technical skills and fallback/error turns. Extend review for inadequately represented probe/skill strata; passing is not automatic activation. Nothing is copied in this task.

## 11. Reviewer questions

Resolved by the owner: practical omission with real estimates, track-only longer option, top-weighted skill preselection/swaps, dynamic validated models, caps/default-off paid content, the band veto and 100-turn gate, null missing quotes, and content-dependent Drill. Model-written follow-ups and paid personal-text processing with the notice are approved rules. Auto-checked practice-only behavior still requires the assertion inventory/approval before build step 2. No implementation beyond step 1 is authorized.
