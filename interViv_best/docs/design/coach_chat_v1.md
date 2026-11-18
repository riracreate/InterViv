# Coach chat v1

Status: design only. Do not build this until it is approved.

Branch context: the bug fixes on `feat/coach-fixes` are separate. This document does not change the scorer, auth, `local_runner`, or `assistance_policy`. New chat behaviour stays behind flags that default off. The real database is not part of the tests. The local demo on ports 8000 and 5173 is not part of this work.

## What v1 is

One coach thread per signed-in user, the thread `get_or_create_conversation` already keeps. Each user message is answered from a bounded context block. The model may only *propose* a tool. The server runs the tool after the user confirms an action card. If the model is off, over budget, or wrong, the reply is the deterministic coach that already exists.

## Context block

About 3,000 tokens per message, hard stop 3,200. Estimate tokens as characters divided by 4. Trim in this order until the block fits: rolling summary, then debrief items beyond the newest, then plan tasks beyond the next four. Never drop the role line or the refusal rules.

The block is plain text with labelled sections. Numbers the model is allowed to say must appear here as the same digit sequence.

| Section | What goes in | Existing source |
| --- | --- | --- |
| Role and level | Company and role slugs, the role title, and each role skill's current score and attempt count | `get_user_target` in `backend/db/user_target.py`. Role title from the company graph `find_role` path already used by `collect_planning_evidence`. Levels from `StudentSkillGraph.get_current_state`. |
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
| `explain_last_interview` | Shows which completed session will be explained | Read that session's stored `scoring_breakdown` and concept lists. No scorer call and no new narration job. |

A proposal whose arguments are not in the context block is dropped before the card is shown.

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

`gemini-2.5-flash` is deprecated. From 1 December 2026 Google routes it to `gemini-3.5-flash-lite` and bills the 3.5 Flash-Lite rates. Gemini 3 cannot turn thinking off. If `gemini-2.5-flash-lite` stops accepting `reasoning_effort: "none"`, stop and re-read the docs. Do not move personal text onto a Gemini 3 or Gemini 4 model without a new approval.

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

Add one rule: every number in the assistant message must appear in the context block. A number is a maximal digit sequence, with an optional decimal point (`42`, `3.5`). It matches only the same sequence with boundaries, so `3` does not match inside `30`. Percent signs stay attached to the number (`66.7%` must appear that way). Words for numbers are not numbers. If any number fails, drop the provider reply, set `provider_rejected`, and show `_deterministic_reply`.

## Refusals

Refuse before any provider call, with a fixed deterministic sentence and no tool proposal:

- The user has an assessment session whose round status is in `OPEN_STATUSES` (`ready` or `in_progress`) from `backend/round_lifecycle.py`.
- The message contains the question text of an open round, after whitespace and case are folded, when that question is at least 40 characters. The question text is not copied into the provider prompt.

Coding hints during assessment stay on the path already shipped: the confirm dialog, then the submit lock. This chat does not offer hints.

## Cap and journal

Per user, per UTC day, stop at 40 chat turns or an estimated $0.50, whichever comes first. Counts live in the existing file journal used by `RequestBudget` (`artifacts/interview_llm_limits.json`), under a `coach_chat` section keyed by user id. Store turn count, prompt tokens, completion tokens, estimated USD, provider, and model. Do not store message text. When the cap is hit, serve the deterministic reply and do not call a provider.

Also call `log_llm_usage` with purpose `coach_chat` so the existing usage list shows the turn. `error` is a short code (`privacy`, `cap`, `provider`), not the response body.

## UI

Streaming uses SSE on a new `POST /coach/conversations/{id}/messages/stream`. Events are `context_ready`, `token`, `tool_proposal`, `fallback`, and `done`. The deterministic path sends one `token` event with the full sentence, so the client has one renderer. Flag off does not open a provider stream.

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

Eval set: 40 fixtures in `tests/fixtures/coach_chat_eval.json`. Each case has a context block, a user message, a fake provider reply, and the expected outcome. A case passes when:

- every number in the shown reply appears in the context block
- the tool proposal is exactly the expected tool, or there is no proposal
- assessment-open and pasted-question cases are refusals and record no provider call

The harness fails if any of the 40 miss a rule. It does not score writing quality.

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
