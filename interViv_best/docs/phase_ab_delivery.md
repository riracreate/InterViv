# Phase AB — fix Z-F03, Z-F02, Z-F01

> Ported onto unify-shell (`phase0/cursor-ai-design`) from
> `cc905cfc7eb6da7b43b022ece213fc16be141b92`. Interview/Practice/api.js were
> merged so Piston coding, Gemma coach helpers, `limit_per_level`, the coding
> media gate, coding submit language, and `CodingRound` remount keys stay.
> Original branch `codex/phase-b-block-practice`, base `7498cdb` (Phase AA).

Branch `codex/phase-b-block-practice`, base `7498cdb` (Phase AA). No new features, no execution infrastructure, no migration (head stays `20260908_0009`). No protected file, scorer, guard or bank changed. `evaluation_unavailable()` and the Phase Y expiry write are untouched.

## Root cause of Z-F01, in one paragraph

**SQLite drops tzinfo on read.** Every round deadline was written correctly, as UTC. SQLite returned it as a naive datetime, and `GET /session/{id}` served it as an ISO string with no offset. The browser's `new Date(...)` parses an offset-less string as **local time**. At +05:30 that placed every fresh round 5h30m in the past, so it showed `00:00`.

This quirk was known and deliberately left alone. The earliest recorded note I could find is `phase_d_delivery.md:179`, from commit `daa18b4`: "SQLite datetime reads are tz-naive. Pre-existing." Phase O (`43ac864`) patched the same quirk locally for the jobs cache. I searched the Phase B.1 commit message and `phase_b_delivery.md` and found no such note, so I don't attribute it to B.1. It was not harmless: it stayed latent until a client parsed the value.

Any other naive timestamp crossing the API boundary is suspect. I checked with an API scan, below; this phase fixes only the round and session timestamps.

## Z-F03 — cross-account builder draft (highest priority)

**Cause.** Practice wrote the builder draft to one browser key, `interviv-builder-draft-v1`, for every account. The draft loads from the server first, then falls back to that key. A second account has no server draft, so it fell back to the first account's local copy, and autosave then wrote those blocks to its own server draft. That is why it showed "Saving" and survived reload. Server ownership was correct and is unchanged.

**Fix (both parts).**
- The local draft key is per account: `interviv-builder-draft-v1:<userId>` (`builderDraftKey`, `loadLocalBuilderDraft`, `saveLocalBuilderDraft` in `frontend/src/lib/practiceBuilder.js`). Practice reads and writes only through these helpers, and never without an account id.
- The unnamespaced legacy key is never read. `saveAuthToken` (signin, signup) and `clearAuthToken` (signout) in `frontend/src/lib/api.js` remove it, along with the other unkeyed account state. Per-account drafts survive, so each user recovers their own.

**Browser-storage audit** (every persistent write in `frontend/src`, plus the server's cookies):

| Key / mechanism | Holds | Account-specific | Leaked across signout→signin before AB | After AB |
|---|---|---|---|---|
| localStorage `interviv-auth-token` | JWT bearer token | yes | No. Removed on signout, replaced on signin. | Unchanged; the same calls now also clear the unkeyed keys. |
| localStorage `adaptive-mock-interview-state` | Last started interview: session and candidate ids, question text/context, config, deadline, calibration baseline | yes, but unkeyed | Cleared by the Account page's Sign out. It **survived a signin without a signout** (expired token → log in as someone else). It did not render there, because `/interview/:id` loads state from the server (InterviewRoute). | Cleared on signin, signup and signout. |
| localStorage `interviv-builder-draft-v1` (legacy) | Builder blocks | yes, but unkeyed | **Yes (Z-F03).** | Never read; removed on signin, signup and signout. |
| localStorage `interviv-builder-draft-v1:<userId>` | Builder blocks | yes, keyed | n/a (new) | Persists per account. |
| sessionStorage | not used | — | — | Pinned by test. |
| IndexedDB | Not written by the app. face-api.js bundles a tfjs `indexeddb://` handler, but the app only calls `loadFromUri('/models')`. | — | — | Pinned by test (no `indexedDB` in src). |
| Cookies | None: no `document.cookie` in the client, no `Set-Cookie` in the backend. | — | — | Pinned by test. |
| `history.state` (react-router `location.state`) | Interview state passed on navigate; persists per tab | yes | Not rendered under another account: InterviewRoute uses server state. | Not changed (not a storage key). Reported only. |

**Left unfixed / needs a larger change.**
- An account two whose server draft was already overwritten with account one's blocks, as in Phase Z's disposable DB, keeps that server draft. Repairing existing server rows is a data change and was not attempted.
- Per-account local drafts of a signed-out user stay in that browser's localStorage. The UI never shows them to another account, but they are readable in devtools. Wiping them on signout would contradict "each account's draft persists independently"; that is an owner choice.

## Z-F02 — expired unscored round reported as failure

**Which surfaces were wrong.** Only the session report's client side:
- `frontend/src/lib/dashboardMapping.js` computed `avg = averages.final_score || 0`, turning the API's `null` into 0. From that zero it built Overall `0`, `Needs Work`, `0% avg score`, and layer scores (`?? avg`). It filled skill values: radar `DSA 0%`, plus padded Clarity/Structure/Depth values.
- The Review Summary fell back to "priority skill = session skill at overall score". That produced "1 skill assessed" and "Rebuild DSA".
- The "You completed all rounds" copy appeared whenever there was no strength to list.

**Already right** (confirmed on the migrated SQLite store by test):
- `GET /dashboard/{id}`: averages `null`, `topic_scores` `{}`, breakdown all 0, block result `average_score`/`suggestion` `null`, and `coverage.unscored_rounds` listing the round as `execution_unavailable`.
- `/dashboard/progress`: history average `null` and `unscored_rounds`.
- `coding_coverage` is scored 0 / unscored 1. The Phase Y trace (scored 1 / unscored 0, hidden from `unscored_rounds`) **no longer holds** for rounds expired after Phase Y.
- item-status: 0 attempts. The notebook, assistance breakdown and skill graph also skip `final_score is None`.

**Changed.**
- The mapping treats a missing average as not measured: score `null`, grade "Not measured", "No scored rounds". There are no layers, radar, priority skills or strengths/weaknesses, and no `0%` in the feedback cards. "Completed all rounds" appears only when no round is unscored.
- The report lists unscored rounds from `coverage.unscored_rounds`, the list Progress renders, with Progress's wording (`unscoredReasonLabel`, now shared).
- `ReviewSummary` shows "Round N · Unscored (coding unavailable)", explains that it is excluded, and hides the skill priority and action plan when nothing was measured.
- `ScoreHero` shows `—`. `Dashboard.tsx` hides the layer/radar and strengths panels when they are empty.
- A genuinely scored zero is unchanged: `0`, "Needs Work", "0% avg score", with a block suggestion.

The existing test `empty session still yields a safe dashboard shape` asserted `overall.score === 0` for a session with no averages. That assertion pinned this defect and now asserts `null` / "Not measured".

No second unavailability notion was added. The write side is still `evaluation_unavailable()`; the read side reads what the API already reports.

**Not changed.** Coding rounds written with `0.0` before Phase Y still count as scored everywhere. Correcting them is a data repair, not presentation.

## Z-F01 — fresh rounds showing 00:00 (root cause confirmed before fixing)

Probe: a migrated disposable SQLite DB, one fresh round per category, the machine at `+0530`, and the client's own `computeSecondsRemaining`.

| Category | Duration | Start response `expires_at` | `GET /session/{id}` `expires_at` | Stored column | Client seconds (start → GET) |
|---|---|---|---|---|---|
| verbal | 10 | `…09:54:16.607669+00:00` | `…09:54:16.607669` | `2026-09-11 09:54:16.607669` | 599 → **0** |
| oa | 12 | `+00:00` | no offset | UTC wall time | 719 → **0** |
| sql | 15 | `+00:00` | no offset | UTC wall time | 899 → **0** |
| interview | 30 | `+00:00` | no offset | UTC wall time | 1799 → **0** |
| coding | 30 | `+00:00` | no offset | UTC wall time | 1799 → **0** |
| system_design | 25 | `+00:00` | no offset | UTC wall time | 1499 → **0** |
| ml_primitives | 30 | `+00:00` | no offset | UTC wall time | 1799 → **0** |

- **What is stored:** the correct deadline, `started_at + duration`, as UTC wall time for every category. The write path is correct.
- **Serialization:** `DateTime(timezone=True)` on SQLite returns a naive datetime. `sanitize_round_for_client` emits `isoformat()` with no offset. The browser's `new Date("…T09:54:16")` reads that as **local** time, 5h30m earlier, so every fresh round is already past.
- **Which path reads it:** Practice navigates to `/interview/:id`. InterviewRoute fetches `GET /session/{id}` and replaces the start response's (correct) state with the offset-less one. The SQLite tzinfo quirk is the cause here; it is not assumed. Postgres and the in-memory store return aware datetimes and were never affected.
- **Header vs round timer:** two sources. The Interview header shows `ROUND_SECONDS = 120`, the technical round's per-question timer. It ticks only for technical rounds, so on Coding it sat at `02:00`, while CodingRound showed the deadline (`00:00`).
- **Disabled Submit:** the client clock. ML Submit is disabled by `seconds <= 0`. The server never decided expiry: it compares the naive value as UTC, which is correct. MCQ/Coding/System-design Submit are not time-gated, which is why OA showed zero while accepting answers.

**Fix.**
- `backend/db/sqlalchemy_store.py` restores UTC on read (`_as_utc`) for round `created_at`/`started_at`/`expires_at`/`submitted_at` and session `started_at`/`created_at`/`completed_at`. Every consumer (GET session, next-round reuse, progress) now gets aware values; existing comparisons already accepted aware values.
- The Interview header and calibration header show the `02:00` technical timer only for technical rounds.

Durations and expiry policy are unchanged.

**Rounds already stored:** they hold correct UTC wall time. They now serve with `+00:00`, and no migration is needed. The test asserts the raw column equals the aware value's UTC wall time.

### Other naive timestamps crossing the API — checked, not fixed

I checked with a scratch scan against a migrated SQLite store:
- **Rows created through the API:** signup, 7 sessions, answer draft, builder draft, preset, bookmark, review sync, retry set, submits.
- **Scanned:** every JSON response for ISO timestamps without an offset.

After the fix, the round and session timestamps carry `+00:00`. These still cross without an offset:

| Response field | Client use |
|---|---|
| `GET /session/{id}/draft` `updated_at`; `GET /practice/builder-draft` `updated_at`; `GET /practice/presets` `created_at`/`updated_at` | not rendered as time |
| `GET /learning/bookmarks/me` `created_at`; `GET /learning/retry-sets/me` `created_at` | not rendered as time |
| `GET /auth/me` `created_at`/`last_active_at` | not rendered as time |
| `GET /dashboard/progress` and `GET /skill-graph/me` `skills[].last_practiced_at` | not rendered as time |
| `GET /av/system-design-attempts` `created_at` | not rendered as time |
| `GET /learning/reviews/me` and `/learning/reviews/due` `items[].due_at` | **Learn renders it with `new Date(...).toLocaleString()`**, so it would display shifted by the viewer's UTC offset (5h30m early at +05:30). Source/API inference; not rendered. |

**Scan gaps:**
- `PUT /target-context/me` returned 404 on the payload the scan sent, so target contexts were not checked.
- One `POST /session/answer` in the scan returned 422, so ML attempt timestamps may not have been exercised.
- Jobs and ATS were not exercised.

Server-side comparisons on these fields were not audited here; Phase O already guards the jobs cache.

These are recorded as an open finding in review guide §i. Fixing them means extending UTC restoration to the other store readers, which was outside this phase.

`modules/jobs_explorer.py` has its own `_as_utc` (Phase O). The store keeps its own helper rather than importing a feature module.

## Tests

Backend `tests/test_phaseAB_deadlines_and_report.py` (migrated SQLite, 13 tests):
- One per category, `test_fresh_round_deadline_is_served_with_utc_offset[verbal|oa|sql|interview|coding|system_design|ml_primitives]`.
- A round-trip through store reopen, including the raw column.
- Genuine expiry still expires: coding and ML unscored, verbal 0.0.
- The report and coverage for an expired unevaluated round.
- A genuinely scored zero.

Frontend `tests/phaseABReportAndTimers.test.js` renders real payloads emitted from a migrated SQLite store (`tests/helpers/emit_phase_ab_payloads.py`) through the browser's deep-link path, with `TZ=Asia/Kolkata`:
- A fresh-round test per category.
- Expired ML (ended, Submit disabled) and expired coding (`00:00`).
- The Coding header and round timer agree (one reading, no `02:00`).
- Report unavailable, still visible as unscored, and genuine zero.

Frontend `tests/accountStorage.test.js`: one test per audited key, the cross-account, legacy and own-draft cases, and an audit pin.

Limits:
- A static render does not run effects. ML Submit's time term is asserted through the ended copy, which uses the same `seconds <= 0` condition; its `loaded` term (draft recovery) needs the browser.
- The interview category's Submit waits for an answer, not for time.
- Media categories render with calibration skipped (Z-F07 unchanged).

Fail-before-fix check, with `_as_utc` temporarily a no-op:

- **First run:** 11 of 13 backend and 6 of 13 Node Phase AB tests failed.
  - Three of the backend failures were the expiry tests, failing for their own reason: the assertion compared a naive served value with an aware `now`.
- **Assertion fix:** the expiry assertion now parses the served deadline with the server's own `backend.routes.dashboard._utc_date` (naive read as UTC). Expiry is what that test covers; the offset is pinned by the fresh-round tests. No app change was needed.
- **Re-run, fix still disabled:** exactly the 8 serialization tests fail (7 fresh-round, 1 round-trip). The 3 expiry and 2 report tests pass.
- **Fix restored:** 13/13 pass.

## Suite evidence

```text
$ HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 JOBS_LIVE_FETCH=0 LLM_LIVE_FETCH=0 DATABASE_URL='' .venv/bin/python -m pytest tests/ -q -p no:cacheprovider
552 passed, 1 skipped, 67 warnings in 101.21s (0:01:41)

$ npm --offline test
# tests 77
# pass 77
# fail 0
npm --offline run build (tsc + vite, outDir in session scratch) — built; existing face-api chunk 664.20 kB warning

HF_HUB_OFFLINE=1 scripts/scoring_regression.py            → 2/8 failed (gibberish repetition 6.06; keyword_stuffing gibberish 10.00)
DISABLE_SEMANTIC_SCORING=1 scripts/scoring_regression.py   → 4/8 failed (adds paraphrase 39.75, off_topic guard None)
alembic heads → 20260908_0009 (head)
docs/human_baseline_report.md: rewritten to 68 lines by pytest, restored → 230 lines, MD5 5421f9f0fd6efad395666c545e5cf76a
```

## Browser verification

Environment:
- Fresh disposable SQLite in the session scratch directory, migrated to head.
- Backend `127.0.0.1:18001`, frontend `127.0.0.1:5174`; `:18000`/`:5173` not touched.
- Offline flags as in the review guide; API keys blank; throwaway signing secret.
- `/health`: `scoring.mode: full`, sentence-transformer loaded, no fallback reason.

| Check | Status |
|---|---|
| Z-F03 cross-account draft | **STILL BLOCKED** — no browser tool was available; nothing was rendered. |
| Z-F02 expired coding report | **STILL BLOCKED** — no browser tool was available; nothing was rendered. |
| Z-F01 fresh-round timers | **STILL BLOCKED** — no browser tool was available; nothing was rendered. |

Test and API evidence above does not close these rows.

### Manual browser steps (to run later)

Use a fresh disposable SQLite database migrated to head and the reproduction commands in the review guide §h (backend `127.0.0.1:18001`, frontend `127.0.0.1:5174`; never `:18000`/`:5173` or a personal database). Record the `/health` `scoring.mode`.

1. **Z-F03.**
   1. Sign up account one. In Practice → Custom builder, create a draft: Coding/DSA, 1 problem, 1 minute. Wait for "Draft saved".
   2. Sign out from the Account page. Sign up account two in the same browser.
   3. Open the builder: it must be empty. Reload: it must stay empty.
   4. Sign out, then sign in as account one: the Coding/DSA/1/1 draft must be present.
   5. In devtools, confirm localStorage has no `interviv-builder-draft-v1` key, only `interviv-builder-draft-v1:<id>` keys.
2. **Z-F01.** Start one fresh round each of Verbal, OA, SQL, Coding, System design, ML primitives and Interview, skipping calibration where shown. For each:
   - The timer counts down from the configured duration.
   - Submit is enabled (for Interview, once an answer is typed).
   - No time-ended copy appears.
   - On Coding, only one timer shows, with no `02:00` header.
3. **Z-F02.**
   1. Note Progress's measured values.
   2. Start the one-minute Coding round and let it expire naturally.
   3. Open `/dashboard/<session>`. It should show `—`, "Not measured", "No scored rounds" and "Round 1 · Unscored (coding unavailable)". It should show no `0%`, no "Needs Work", no skill percentage, no action plan and no "completed all rounds".
   4. Confirm Progress still shows the round unscored / coding unavailable, with the measured values unchanged.

## Preservation

- Only this worktree was used. The other checkout was never read, written or git-queried.
- No dependency was installed, upgraded or removed.
- The shared `.venv` interpreter and `node_modules` were executed as-is.
- Rescue refs (4) and the stash list match the Phase Z record.
- No push, merge, rebase, amend or history rewrite.
