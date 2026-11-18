# Coach chat v1

Status: approved to build later, after Phase 2 of the role-content work lands. Do not build it before that. The changes below are part of that approval.

Branch context: the bug fixes on `feat/coach-fixes` are separate. This document does not change the scorer, auth, `local_runner`, or `assistance_policy`. New chat behaviour stays behind flags that default off. The real database is not part of the tests. The local demo on ports 8000 and 5173 is not part of this work.

## What v1 is

One coach thread per signed-in user, the thread `get_or_create_conversation` already keeps. Each user message is answered from a bounded context block. The model may only *propose* a tool. The server runs the tool after the user confirms an action card. If the model is off, over budget, or wrong, the reply is the deterministic coach that already exists.

## Context block

About 3,000 tokens per message, hard stop 3,200. Estimate tokens as characters divided by 4. Trim in this order until the block fits: rolling summary, then the oldest of the last six messages, then debrief items beyond the newest, then plan tasks beyond the next four. Never drop the current user message, the role line, or the refusal rules.

The block is plain text with labelled sections. Numbers the model is allowed to say must appear here, or in the user's current message, as the same digit sequence.

| Section | What goes in | Existing source |
| --- | --- | --- |
| Role and level | The role-only target: blueprint id, title, and the chosen level (`intern`, `junior`, or `mid`) | After Phase 2, `get_blueprint` in `modules/role_blueprints.py` for the user's role-only target, plus the level stored on that target. Not the company graph and not `find_role`. |
| Recent messages | The last 6 messages, user and assistant, trimmed to fit | `get_conversation` messages. The current user message is included. |
| Resume skills | The stored skill list, capped at 12 names | `candidates.resume_skills` on the candidate row. Do not call the resume parser again. |
| App scores | Overall readiness and the conservative figure, plus per-skill student level and attempts already on the gap report | `GapAnalysis.compute_gap` in `modules/gap_analysis.py` (`overall_readiness_percentage`, `overall_readiness_conservative`, per-skill `student_level`). Also the last completed session's stored `overall_readiness_score` when that field is present. No new score is computed. |
| Last 3 debriefs | For the three newest completed sessions, the missed concept names only | Read `rounds[].scoring_breakdown.concepts`. `missing` and `concept_statuses.missed` were written by `question_concepts_summary` and `build_concepts_summary`. Read the stored fields. Do not call the scorer. |
| Plan | Plan id, version, `plan_kind`, and up to four pending tasks (skill, title, rationale, population) | `get_active_plan` in `modules/roadmap_plans.py`. |
| Due reviews | Up to eight due rows: item id, skill, `due_at` | Same selection as `list_due_reviews`: `review_schedules` for the user, kept when `backend.review_schedule.is_due` is true. |
| Rolling summary | At most ~400 tokens of earlier coach turns | No function does this today. v1 stores `rolling_summary` on the conversation document and appends one clipped sentence from the last *validated* assistant message. A rejected model reply never updates it. The first turn sends an empty summary. |

## Tools

The model returns a proposal. The UI shows an action card. Confirm calls the existing function. Cancel drops the proposal. The model does not receive a tool result until the user has confirmed.

| Tool | Confirm copy | Existing function |
| --- | --- | --- |
| `update_plan` | Shows the goal, hours, and skills that will be saved | `ensure_plan(..., regenerate=True)` in `modules/roadmap_plans.py`, using the conversation goals. |
| `start_practice` | Shows skills, `practice_mode`, and `flow_preset` | `coach_start_practice` (`POST /coach/start-practice`). Default `coached_practice` and `legacy` unless the card says `assessment`, `quick`, or `full`. |
| `explain_last_interview` | Shows which completed session will be explained | Read that session's stored `scoring_breakdown` and concept lists. No scorer call and no new narration job. Then record a teaching exposure the same way Learning Hub does. |

A proposal whose arguments are not in the context block is dropped before the card is shown.

### explain_last_interview and assistance_v1

This rule already applies, so the tool follows it. Do not change `assistance_policy`.

`POLICY_VERSION` is `assistance_v1`. `explanation` is in `TEACHING_KINDS`. Learning Hub `GET /learning/explanation` (`get_explanation` in `backend/routes/learning_hub.py`) records that kind only after the user has a submitted attempt and the item is not still open in an active session. The write is `_record_assistance(..., kind="explanation")`, which calls `record_teaching_exposure(..., kind="explanation", also_legacy_assistance=True)`.

`explain_last_interview` uses that same call, with `item_identity_for_round` for each explained round, and only when those two Learning Hub gates pass. The exposure is why a later attempt in the existing 24-hour window is `excluded` with `REASON_TEACHING_EXPOSURE`. Rounds that are already scored are not rescored.

## Model routing

Conversation lane only. Content and check lanes are unchanged.

`COACH_CHAT_LLM_ENABLED` defaults to `0`. While it is `0`, the reply is `_deterministic_reply` in `modules/coach_conversation.py`. The same fallback is used when the daily cap is spent or the provider call fails. The fallback does not include a provider message.

`INTERVIEW_CONVERSATION_PROVIDER`:

| Value | Where personal text goes | Model |
| --- | --- | --- |
| `openrouter` (default) | OpenRouter, the lane that exists today | `anthropic/claude-haiku-4.5` only (`PAID_CONVERSATION_MODEL`). `enforce_outbound_policy` still rejects every other id and every `:free` model. |
| `gemini_paid` | Gemini Developer API, paid tier only | `gemini-2.5-flash-lite`, with thinking off (see below). |

`GEMINI_API_KEY` lives in the backend `.env` only. It is not sent to the browser, not written to logs, and not put in the budget journal.

Personal text may be sent to Gemini only when `GEMINI_PAID_TIER_CONFIRMED=true`. That flag means the user has billing enabled on the Cloud project that owns the key. If the provider is `gemini_paid` and the flag is not exactly `true`, raise `PrivacyViolation` from `modules/interview_llm.py` and serve `_deterministic_reply`. The Gemini transport is not called.

Free-tier Gemini keys are never used on the conversation lane. A free key is treated as unconfirmed and refused the same way.

Gemini free is not built. If a later change wants it, the only legal place is a third id on the existing content/check allowlist (`INTERVIEW_CONTENT_MODELS` / `INTERVIEW_CHECK_MODELS`), for generic bundle text, never for resumes, answers, goals, or this chat. Suggested id, not wired: `gemini-2.5-flash-lite` on the free tier. v1 does not add that id and does not add a Gemini content transport.

`enforce_outbound_policy` today rejects every conversation model except Claude Haiku 4.5. An approved build may allow `gemini-2.5-flash-lite` on the conversation lane only when the provider is `gemini_paid` and the paid-tier flag is set. It must still reject any model id ending in `:free` for personal text.

### What Google documents (checked 2026-11-18)

Sources: [OpenAI compatibility](https://ai.google.dev/gemini-api/docs/openai), [structured outputs](https://ai.google.dev/gemini-api/docs/structured-output), [pricing](https://ai.google.dev/gemini-api/docs/pricing).

OpenAI-compatible endpoint: yes. Base URL `https://generativelanguage.googleapis.com/v1beta/openai/`. Chat completions: `POST https://generativelanguage.googleapis.com/v1beta/openai/chat/completions` with `Authorization: Bearer $GEMINI_API_KEY`.

Strict JSON schema: the compatibility page does not mention a `strict` field or the name `json_schema`. It shows structured output through `client.beta.chat.completions.parse(..., response_format=YourModel)` and `zodResponseFormat`. The native API takes `responseMimeType: "application/json"` plus a JSON schema (`responseJsonSchema`, or Interactions `response_format.schema`). Google compiles that schema into a state machine and returns `400 INVALID_ARGUMENT` when the schema is too deep or too branchy. v1 uses that documented schema path, then still runs our validator. It does not depend on an undocumented `strict: true` switch.

Thinking: on the compatible endpoint, `reasoning_effort: "none"` turns thinking off for 2.5 models. It cannot be turned off for Gemini 2.5 Pro, Gemini 3, or Gemini 4. Gemini 4 maps `minimal` to thinking level `low`. Gemini 2.5 maps effort to a thinking budget: `minimal` and `low` are 1,024 tokens, `medium` is 8,192, `high` is 24,576. v1 sends `reasoning_effort: "none"` with `gemini-2.5-flash-lite`. Output prices include thinking tokens, so leaving thinking on would bill tokens the coach does not show.

`gemini-2.5-flash` is deprecated. From 1 December 2026 Google routes it to `gemini-3.5-flash-lite` and bills the 3.5 Flash-Lite rates. Gemini 3 cannot turn thinking off.

`gemini-2.5-flash-lite` deprecation, checked 2026-11-18 on [Gemini deprecations](https://ai.google.dev/gemini-api/docs/deprecations): stable id released 22 July 2025, shutdown date **not announced**. The preview id `gemini-2.5-flash-lite-preview-09-2025` shut down on 31 March 2026. The model page (updated 29 October 2026) still lists the stable id and says thinking and structured outputs are supported. If that stable id stops accepting `reasoning_effort: "none"`, or a shutdown date is announced, stop and re-read the docs. Do not move personal text onto a Gemini 3 or Gemini 4 model without a new approval. The live eval below is what chooses between Haiku and Flash-Lite before a default change.

Paid prices below are US dollars per 1 million tokens, text, as listed on the pricing page on 2026-11-18. Output prices include thinking tokens. Free tier rows are listed so the journal can show why they are refused. On the free tier, Google says the data may be used to improve its products. On the paid tier, it says it is not.

| Model | Paid input | Paid output | Free tier | Conversation lane |
| --- | --- | --- | --- | --- |
| `gemini-2.5-flash-lite` | $0.10 (text/image/video), $0.30 audio | $0.40 | Exists. Used to improve products: yes. | v1 model, paid only, thinking off. |
| `gemini-3.5-flash-lite` | $0.30 | $2.50 | Exists. Used to improve products: yes. | Not used. Thinking cannot be turned off. |
| `gemini-3.8-flash` | $0.75 through 31 Dec 2026, then $1.50 | $3.75 through 31 Dec 2026, then $7.50 | Exists. Used to improve products: yes. | Not used. |
| `gemini-4-hydrogen` | $1.50 | $7.50 | Exists. Used to improve products: yes. | Not used. Thinking cannot be turned off. Lowest effort is `low`. |
| `gemini-4-carbon`, `gemini-4-argon` | $2.00 through 30 Nov 2026, then $4.00 | $10.00 through 30 Nov 2026, then $20.00 | Not available. | Not used. |

The budget journal stores this table as a `rates` object (model, input_usd_per_million, output_usd_per_million, thinking, source URL, checked date). Cost estimates multiply token counts by those rates. The journal stores counts and the estimate, never the prompt or the reply.

## Validator

Reuse `_validate_provider_output` in `modules/coach_conversation.py`. It already rejects invented readiness, scores, Elo, mastery, hiring promises, plan mutation, and actions that point at unknown tasks or off-site URLs.

Add one rule. Strip markdown list markers first (`1.`, `2)`, and the same forms at the start of a line). Then every remaining number in the assistant message must appear in the context block or in the user's current message. A number is a maximal digit sequence, with an optional decimal point (`42`, `3.5`). It matches only the same sequence with boundaries, so `3` does not match inside `30`. Percent signs stay attached to the number (`66.7%` must appear that way). Words for numbers are not numbers. The prompt tells the model to write counts as words. If any number fails, drop the provider reply, set `provider_rejected`, and show `_deterministic_reply`. The rejected text is not sent to the client.

## Refusals

Refuse before any provider call, with a fixed deterministic sentence and no tool proposal:

- The user has an assessment round that was opened in the last 3 hours, and that session has not expired. Opened means `started_at` is within 3 hours and the round status is `in_progress`. The session has not expired when its status is not `completed`, `closed`, or `expired`, and the round `expires_at` is absent or still in the future. A `ready` round that was never started, and an assessment round opened more than 3 hours ago, do not refuse the chat.
- The message contains the question text of an open round, after whitespace and case are folded, when that question is at least 40 characters. The question text is not copied into the provider prompt.

Coding hints during assessment stay on the path already shipped: the confirm dialog, then the submit lock. This chat does not offer hints.

## Cap and journal

Two caps, both per UTC day. Per user: 40 chat turns or an estimated $0.50, whichever comes first. Across all users: an estimated $0.50 (`COACH_CHAT_GLOBAL_DAILY_USD`, default `0.50`). Either cap stops the provider call and serves the deterministic reply.

Counts live in the existing file journal used by `RequestBudget` (`artifacts/interview_llm_limits.json`), under a `coach_chat` section. Per-user rows are keyed by user id. One global row holds the day's estimated USD. Store turn count, prompt tokens, completion tokens, estimated USD, provider, and model. Do not store message text.

Also call `log_llm_usage` with purpose `coach_chat` so the existing usage list shows the turn. `error` is a short code (`privacy`, `cap`, `provider`), not the response body.

## UI

Streaming uses SSE on a new `POST /coach/conversations/{id}/messages/stream`. The server generates the full reply, validates it, and only then streams that validated text in chunks. A rejected reply never reaches the client. Events after validation are `token` (chunks of the accepted text), `tool_proposal`, and `done`. The deterministic fallback is validated the same way and then chunked. There is no event that carries unvalidated provider text. Flag off does not open a provider stream.

Chat history is the `messages` list `get_conversation` already returns, shown oldest at the top. v1 does not add a second thread.

Suggestion chips are the validated `actions` already on a coach reply (`create_plan`, `start_task`, `assess_independently`, `update_hours`), plus "Why this task?" when a plan exists. Chips are not free text from the model.

Action cards render a `tool_proposal`. The buttons are Confirm and Cancel. Confirm is the only path into `ensure_plan`, `coach_start_practice`, or the stored debrief read.

## Tests

Provider tests use a fake transport. No test calls OpenRouter, Gemini, or Ollama.

- Flag off: the fake transport is not called, and the reply mode is `deterministic`.
- Budget spent, and a transport error: same fallback.
- `gemini_paid` with `GEMINI_PAID_TIER_CONFIRMED` unset or `false`: `PrivacyViolation`, deterministic reply, and the fake Gemini transport receives no personal text.
- `gemini_paid` with the flag `true`: the fake transport receives the context and the key header name, not a logged key. A free-tier base URL or a `:free` model id still raises `PrivacyViolation`.
- A number that is not in the context block is rejected.
- An open assessment round, and a pasted live question, do not call the transport.
- Confirming `update_plan` calls `ensure_plan`. Confirming `start_practice` calls `coach_start_practice`. Dismissing a card calls neither.

Two evals share `tests/fixtures/coach_chat_eval.json` (40 cases: context, user message, expected tool or none, expected refusal).

Safety test, in CI, fake replies only. The harness feeds each scripted reply through the validator. A case passes when:

- every number in the shown reply appears in the context block or the user's current message, after list markers are stripped
- the tool proposal is exactly the expected tool, or there is no proposal
- assessment rounds opened in the last 3 hours, and pasted-question cases, are refusals and record no provider call

The harness fails if any of the 40 miss a rule. It does not score writing quality.

Live eval, by hand only, never in CI. It sends the same 40 contexts to the real model when credits are available. It reports validator pass rate (and so the fallback rate), correct tool proposals, correct refusals, cost, and 10 replies for a person to rate. Run it once for Haiku (`anthropic/claude-haiku-4.5`, the default) and once for `gemini-2.5-flash-lite`. The write-up of those two runs is what may change the default. Until that write-up, Haiku stays the default.

## Size

Roughly these files, and no others, if this is approved:

| File | Kind | About |
| --- | --- | --- |
| `modules/coach_chat.py` | new | Context block, number rule, provider switch, cap |
| `modules/coach_conversation.py` | small edit | Call the chat helper from `post_message` when the flag is on |
| `modules/interview_llm.py` | small edit | Allow the paid Gemini id only behind the provider flag |
| `backend/routes/coach.py` | small edit | SSE route |
| `frontend/src/pages/Coach.jsx` | edit | Stream, history, chips, action cards |
| `tests/test_coach_chat.py` | new | Fake transport and privacy flag |
| `tests/fixtures/coach_chat_eval.json` | new | 40 conversations |
| `tests/test_coach_chat_eval.py` | new | The three pass rules |
| `frontend/tests/coachChat.test.js` | new | Chips, cards, and that Confirm is required |

About 1,500 lines of production code and 1,200 lines of tests and fixtures. No migration. No change to `assistance_policy`, the scorer, auth, or `local_runner`.

Build this only after Phase 2 of the role-content work has landed, so the role-only target and blueprint exist. Phase 0 and Phases 1–3 of that brief come first. The live model comparison is a manual run, not part of that build's CI.
