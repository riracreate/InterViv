# Phase I — spaced repetition over the mistakes notebook

**Branch tip (this commit):** see `git log -1`
**Base:** `9e91e08` (H.1)
**One feature.** No scoring-formula changes. Reviews are practice, not measured mastery.

## Scheduling rule

Fixed ladder **`INTERVAL_LADDER = (1, 3, 7, 16, 35)`** days (`backend/review_schedule.py`).

| Event | Effect |
|-------|--------|
| New schedule row (first sync of a recorded miss) | `interval_index=0`, `interval_days=1`, **`due_at = now`** (due immediately) |
| Review outcome `correct` | `interval_index = min(index+1, last)`; `due_at = now + ladder[index]` |
| Review outcome `incorrect` | Reset to index 0 / 1 day; `due_at = now + 1 day` |

Reproducible from stored fields alone. No SM-2 ease factor; no opaque model.

### Pre-feature notebook history

Items whose misses predate this feature are **not** backfilled onto a guessed timeline. On first sync they enter as **due now** (honest: we do not invent prior review dates).

Interview-style notebook entries without a stable `item_id` are not scheduled.

## What shipped

- Alembic **`20260907_0008`** → `review_schedules` (revises `0007`; single head).
- SQLAlchemy ORM + `_ReviewScheduleCollection` registered on `SQLAlchemyDatabase` (B.1 lesson: full field round-trip).
- Routes: `POST /learning/reviews/sync`, `GET /learning/reviews/due`, `GET /learning/reviews/me`, `POST /learning/reviews/start`.
- Start reuses block `StartSessionRequest` / retry-set shape; tags `round_config.purpose = spaced_review` + `review_map`.
- Answer path: spaced-review skips Elo, learning-state, measured readiness mean; sets `evidence_kind=practice_review`; advances schedule only.
- Coding attempts sync as **`due_but_unavailable`** (`review_available=False`); cannot start an outcome review.
- Learn UI: due count/list, empty as absence, scheduled-not-due intervals, start review session.

## Explicit non-goals (unchanged)

No mastery model from schedules. Schedules do not feed gap analysis, readiness, or measured aggregates. No LLM judge. Protected scoring modules and banks untouched. C.2 / E.2 / phase21 integrate not started.

## Test pins

- New: `tests/test_phaseI_review_schedule.py`, `tests/test_phaseI_persistence.py`.
- Alembic downgrade uses `parent_revision("20260907_0008")` → `20260907_0007` (G.0 convention).
- `RetrySetRequest.skills` restored (was used by create path / Learn suggestions; field was missing).

## Browser verification (disposable DB)

Environment: `/tmp/interviv_phasei_disposable.db`, signup `contributors@example.invalid` / `PhaseI123`, backend `127.0.0.1:8000`, frontend `127.0.0.1:5173`. Real signup; measured misses via authenticated session API + one browser review session. **No fabricated mastery rows.**

| Claim | Result | Method |
|-------|--------|--------|
| Empty due for fresh account | **VERIFIED** | Browser Learn after signup: “No review schedule yet…” (absence, not zeros) |
| Due count + list with real items / dates | **VERIFIED** | Browser: “2 due (1 reviewable, 1 coding unavailable)”; MCQ + due date + interval 1 day |
| Coding due-but-unavailable | **VERIFIED** | Browser Learn: Two Sum “Due but unavailable”; note not a score/zero |
| Review session starts/runs/completes via existing engine | **VERIFIED** | Browser Start review → `/interview/…` → submit correct → Session Complete 100% |
| Correct lengthens interval (visible) | **VERIFIED** | Browser scheduled list: MCQ “interval 3 days · last correct” |
| Incorrect shortens/resets (visible) | **VERIFIED** | Browser scheduled list: second MCQ “interval 1 day · last incorrect” (after forced prior interval 7 via disposable SQLite for the demo) |
| Progress/mastery unchanged by review | VERIFIED | Z #46: isolated correct review followed by browser Progress comparison retained measured session/skill counts, scores, rounds and Elo; Learn interval increased to three days. See Z before/after values |
| Second account sees none of first schedule | **VERIFIED** | Browser signup `contributors@example.invalid` → Learn empty due / no user-1 items |

## Commands (evidence)

```text
pytest tests/ -q  →  477 passed, 1 skipped
frontend npm test →  49 pass
frontend npm run build → success
alembic heads → 20260907_0008 (head)
HF_HUB_OFFLINE=1 scoring_regression → 2/8 fail (full SemanticScorer; gibberish 6.06/repetition; keyword_stuffing 10.00/gibberish)
DISABLE_SEMANTIC_SCORING=1 scoring_regression → 4/8 fail (degraded)
human_baseline_report.md → 230 lines, MD5 5421f9f0fd6efad395666c545e5cf76a (restored)
```

## Deferred / not started

C.2, E.2, phase21 Verbal Upload integration. No push/merge.
