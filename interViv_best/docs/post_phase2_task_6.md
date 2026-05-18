# Phase 2 — Task 6 Evidence: Dashboard Updates

Date: 2026-05-18
Branch: `phase2-task6-dashboard`
Mode: in-memory DB shim (`INTERVIV_USE_MEMORY_DB=true`).

## What landed

- `backend/routes/dashboard.py`
  - New pure helper `compute_confidence_band([l1, l2, l3])` —
    `stdev / 2`, capped at 10, `None` when fewer than 2 layer
    scores are present. Spec 6b verbatim.
  - `_sanitize_rounds` attaches `confidence_band` to every round in
    the response (no change to the stored documents).
- `frontend/src/components/dashboard/Phase2InsightsPanel.tsx` —
  new component that fetches `/gap-analysis`, `/skill-graph`, and
  `/mastery` for the session's user + target role, then renders:
    - **Readiness banner** with the percentage vs. company role,
      top-3 weak areas mini, and CTAs to the Gap Analysis screen
      and the Roadmap.
    - **Skill graph rows** — one bar per skill with `current_score`
      + Elo + attempts.
    - **Concept mastery heatmap** — per skill, a grid of concept
      pills colored by `MasteryLevel`
      (`Mastered`/`Strong`/`Weak`/`Untested`).
    - Empty states for "no user", "no target", and "no data yet".
- `frontend/src/pages/Dashboard.tsx`
  - Mounts `Phase2InsightsPanel` directly under `ScoreHero`.
  - Plumbs `confidence_band` through to the round timeline rows.
  - Header pill renamed to "Readiness vs. target" + made
    `flex-wrap` so it sits cleanly at 375px.
- `frontend/src/components/dashboard/RoundTimeline.tsx`
  - `Round` type extended with optional `confidenceBand` and the
    score row renders `73 ± 5` when present
    (`data-testid="round-confidence-band"`).
- `frontend/src/lib/api.js` — `fetchSkillGraph`, `fetchMastery`.
- `tests/test_dashboard_phase2.py` — 6 new tests.

## What was NOT changed

- `backend/scoring/pipeline.py` — untouched.
- `modules/nlp_scorer.py`, `answer_guard.py`, `semantic_scorer.py`,
  `knowledge_graph.py`, `ner_scorer.py`, `c4_feedback.py`,
  `question_bank.py` — untouched.
- Classifier weights and `modules/model_metadata.json` — untouched.
- The existing per-round breakdown panels are intact; this task
  is purely additive.

## Confidence band formula (Task 6b, spec verbatim)

```python
variance        = stdev([layer1_score, layer2_score, layer3_score])
confidence_band = variance / 2     # capped at 10
                                     # None when fewer than 2 layer
                                     # scores are present
```

The cap matters in practice — a degenerate `[0, 100]` layer pair
would otherwise produce a ±35 band that's wider than the score
itself. Saturating at ±10 keeps the band a useful visual cue.

## Evidence

### Confidence band on each round (live dashboard payload)

Three-round synthetic session, then `GET /dashboard/<session_id>`:

```
round 1  final_score= 72.0  band=±5.0  layers=[60, 70, 80]
round 2  final_score= 76.0  band=±4.5  layers=[65, 74, 83]
round 3  final_score= 80.0  band=±4.0  layers=[70, 78, 86]
```

Math check:
- Round 1: `stdev([60,70,80]) = 10.0`; `10/2 = 5.0` ✓
- Round 2: `stdev([65,74,83]) = 9.0`;  `9/2 = 4.5`  ✓
- Round 3: `stdev([70,78,86]) = 8.0`;  `8/2 = 4.0`  ✓

The `RoundTimeline` component renders this as `72% ± 5` next to
each score (`data-testid="round-confidence-band"`).

### Skill graph + concept mastery render with real data

After a 3-round session:

```
GET /skill-graph/u-task6-evidence
  DBMS            score=75.0 elo=1219 attempts=1
  DSA             score=50.0 elo=1211 attempts=1
  System Design   score=40.0 elo=1207 attempts=1

GET /mastery/u-task6-evidence
  DSA: {'Strong': 2, 'Weak': 2}
```

The dashboard `Phase2InsightsPanel`:
- Reads `raw.user_id` and `raw.target_role_id` from the session
  document (already persisted by the session route since Task 1).
- Calls `fetchSkillGraph(userId)` → renders one bar per skill.
- Calls `fetchMastery(userId)` → renders the heatmap grid; each
  pill has a tooltip of the form `concept · level · demonstrated/attempts`.

### Readiness banner

`GET /gap-analysis/u-task6-evidence/amazon_sde_intern` (after
seeding the user weak in DSA and System Design):

```
readiness=68.0%  tested=3/5
weak areas: ['HR', 'DSA', 'OOP']
```

The banner surfaces `68%` as a large italic number, lists the top
3 weak areas as colored severity dots, and exposes both
`Readiness vs. target ↗ /gap-analysis/...` and
`Build my study plan ↗ /roadmap/...?days=30` as inline CTAs.

### Test suite

```
$ INTERVIV_USE_MEMORY_DB=true python3 -m pytest tests/ --timeout=120 -q
... 87 passed, 8 warnings in 13.18s
```

6 new tests in `tests/test_dashboard_phase2.py`:

- `test_confidence_band_matches_stdev_over_two`
- `test_confidence_band_capped_at_ten`
- `test_confidence_band_none_when_only_one_layer_scored`
- `test_confidence_band_handles_two_layers`
- `test_dashboard_attaches_confidence_band_to_every_round`
- `test_skill_graph_and_mastery_endpoints_serve_dashboard`

### Frontend build

```
✓ 2840 modules transformed.
dist/assets/index-DUjvUw_4.css     38.90 kB │ gzip:   7.58 kB
dist/assets/index-CpIJmDuW.js   1,453.66 kB │ gzip: 387.44 kB
✓ built in 5.71s
```

### Mobile responsiveness (375px)

Static audit — every container in the new path is either flex-wrap
or grid-collapsing on small screens:

| Surface | Mobile behavior |
|---------|------------------|
| Dashboard top nav | `flex-wrap items-center justify-between gap-3` — pill drops to a second row at 375px |
| "Readiness vs. target" pill | reduces to `text-xs` and `px-3 py-1.5` on small screens via `sm:` modifiers |
| `ScoreHero` stat pills | `grid gap-3 sm:grid-cols-2 xl:grid-cols-4` — single column at 375px |
| Readiness banner | percentage uses `clamp(48px, 9vw, 96px)` — min 48px guarantees readability; supporting text uses `flex-wrap items-baseline gap-3 min-w-0 break-words` so long role labels wrap |
| Skill graph / mastery row | `grid gap-6 md:grid-cols-2` — single column under `md` |
| Mastery concept pills | `flex flex-wrap gap-1.5 text-[10px]` |
| RoundTimeline header | `flex flex-wrap items-center justify-between gap-3` — score + band stay on the same line, difficulty pill wraps if needed |

The dashboard surface uses `mx-auto max-w-7xl px-4 sm:px-6 lg:px-8`,
so the page padding shrinks to 16px on mobile.

### UI screenshot — not captured

Same constraint as Tasks 3–5: the preview MCP fails with
EPERM/uv_cwd in this workspace, and per your prior instruction I
do not launch your installed Chrome. Static evidence (the JSON
payloads above, the build output, the mobile audit, and 6 new
automated tests) is provided. The page is reachable at
`/dashboard/<session_id>` for any seeded session.

## What's next

Task 7 (Adaptive question selector driven by gap analysis) — will
hook into `backend/routes/session.py` / `backend/routes/answer.py`
to re-run the gap analysis after each round and route the next
LLM prompt toward the weakest concept.
