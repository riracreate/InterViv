# Phase 2 — Task 5 Evidence: Personalized Roadmap

Date: 2026-05-18
Branch: `phase2-task5-roadmap`
Mode: in-memory DB shim (`INTERVIV_USE_MEMORY_DB=true`).

## What landed

- `modules/roadmap_generator.py` — `RoadmapGenerator`, `Roadmap`,
  `WeeklyBlock`, `FocusTopic` dataclasses. Reuses `GapAnalyzer`
  (Task 4) and `ConceptMastery` (Task 2). Snaps `days` to 7/14/30.
- `backend/routes/roadmap.py` —
  `GET /roadmap/{user_id}/{role_id}?days=30` and the auth-bound
  `GET /roadmap/me/{role_id}`. Literal `/me/` registered first.
- `backend/main.py` — includes the roadmap router.
- `frontend/src/pages/Roadmap.jsx` — full page with timeline of
  weekly cards, 7/14/30-day toggle, concept pills, daily-practice
  guidance, and the "not a binding schedule" copy.
- `frontend/src/pages/GapAnalysis.jsx` — "Build my study plan →"
  CTA navigates to `/roadmap/:userId/:roleId?days=30`.
- `frontend/src/App.jsx` — route `/roadmap/:userId/:roleId`.
- `frontend/src/lib/api.js` — `fetchRoadmap`, `fetchMyRoadmap`.
- `tests/test_roadmap.py` — 11 new tests.

## What was NOT changed

- `backend/scoring/pipeline.py` — untouched.
- `modules/nlp_scorer.py`, `answer_guard.py`, `semantic_scorer.py`,
  `knowledge_graph.py`, `ner_scorer.py`, `c4_feedback.py`,
  `question_bank.py` — untouched.
- Classifier weights, `modules/model_metadata.json` — untouched
  (LogisticRegression, val_accuracy 0.9553).
- No LLM-as-judge.

## Design

The generator pulls the user's gap analysis report (Task 4) and
applies a roadmap-specific re-prioritization: **tested weak skills
go before untested ones**. This intentionally differs from the gap
analysis dashboard ranking (purely importance × gap) because a
study plan should let the user work on proven weaknesses first;
untested skills are surfaced in later weeks for breadth.

Weekly allocation:

```
30-day:                                    7-day:           14-day:
  Week 1 Days  1- 7  Foundations             Days 1-2         Days  1- 4
  Week 2 Days  8-14  Intermediate depth      Days 3-4         Days  5- 8
  Week 3 Days 15-21  Application & build     Days 5-6         Days  9-12
  Week 4 Days 22-30  Mock interviews         Day  7           Days 13-14
```

Skill allocation per week:

```
Week 1: top-1 weak skill                  (foundations)
Week 2: top-2 weak skills                 (intermediate depth)
Week 3: top-3 weak skills                 (application & build)
Week 4: all focus skills + HR if missing  (mock interviews)
```

Concepts per skill come from the user's `ConceptMastery` rows
(Weak + Untested levels). If the user has no concept-level history
yet, the generator falls back to the curated KG concept list for
that skill — `array`, `linked_list`, `pointer` for DSA;
`load_balancer`, `caching`, `CAP` for System Design; etc.

`days` is snapped to the nearest supported value (7, 14, 30); a
request for `days=10` returns a 7-day plan.

## Evidence

### Spec scenario — user weak in DSA and System Design

```
$ # seed: DSA=40, System Design=35, DBMS=75 (DBMS meets the role target)
$ curl 'http://127.0.0.1:8765/roadmap/u-evidence/amazon_sde_intern?days=30'
```

```json
{
  "user_id": "u-evidence",
  "role_id": "amazon_sde_intern",
  "role_title": "SDE Intern",
  "company_id": "amazon",
  "company_name": "Amazon",
  "days": 30,
  "overall_readiness_percentage": 58.65,
  "focus_skills": ["DSA", "System Design", "HR", "OOP"],
  "focus_concepts": [
    "array", "index", "O1 access", "linked list", "node", "pointer",
    "CAP", "consistency", "availability", "partition tolerance",
    "load balancer", "horizontal scaling",
    "STAR", "situation", "task", "action", "result", "teamwork",
    "OOP", "encapsulation", "inheritance", "polymorphism", "abstraction", "method overriding"
  ],
  "weekly_blocks": [
    {
      "index": 1, "label": "Foundations", "day_range": "Days 1-7",
      "focus_skills": ["DSA"],
      "focus_topics": [
        {"skill": "DSA", "concept": "array",       "severity": "High"},
        {"skill": "DSA", "concept": "index",       "severity": "High"},
        {"skill": "DSA", "concept": "O1 access",   "severity": "High"},
        {"skill": "DSA", "concept": "linked list", "severity": "High"},
        {"skill": "DSA", "concept": "node",        "severity": "High"},
        {"skill": "DSA", "concept": "pointer",     "severity": "High"}
      ],
      "daily_practice_suggestions": [
        "Read the foundational concepts for each focus topic.",
        "Solve 2-3 warm-up problems per topic.",
        "Practice explaining one concept aloud in plain English."
      ]
    },
    {
      "index": 2, "label": "Intermediate depth", "day_range": "Days 8-14",
      "focus_skills": ["DSA", "System Design"],
      "focus_topics": ["…12 topics across DSA + System Design"]
    },
    {
      "index": 3, "label": "Application & build", "day_range": "Days 15-21",
      "focus_skills": ["DSA", "System Design", "HR"],
      "focus_topics": ["…18 topics"]
    },
    {
      "index": 4, "label": "Mock interviews", "day_range": "Days 22-30",
      "focus_skills": ["DSA", "System Design", "HR", "OOP"],
      "focus_topics": ["…24 topics"]
    }
  ],
  "plan_note": "This roadmap is a recommended plan based on your current readiness against the target role. Treat it as guidance — adjust pacing to suit your schedule. It is not a binding schedule.",
  "disclaimer": "Company hiring profiles are curated from publicly available job descriptions, observed placement patterns, and industry references. These are reference profiles for practice preparation, not exact hiring criteria."
}
```

**Verification against the spec:**

- ✅ "Verify the plan emphasizes those two skills in early weeks" —
  DSA leads Week 1 (Foundations) alone; System Design joins it in
  Week 2 (Intermediate depth). Both are present through Week 3 and
  Week 4.
- ✅ DBMS (met the role target at 75 ≥ 60) is correctly excluded
  from `focus_skills`.
- ✅ HR shows up later (Week 3 onward) because it's untested — the
  roadmap prioritises proven weaknesses before guesses.
- ✅ `focus_concepts` for DSA come from the KG: `array`, `index`,
  `O1_access`, `linked_list`, `node`, `pointer`. For System Design:
  `CAP`, `consistency`, `availability`, `partition_tolerance`,
  `load_balancer`, `horizontal_scaling`.
- ✅ `plan_note` makes the "recommended, not binding" framing
  explicit (per spec 5d).
- ✅ `disclaimer` propagates from the company hiring graph.

### 7-day and 14-day variants

```
$ curl '/roadmap/u-route-multi/amazon_sde_intern?days=7'  → days=7,
   weekly_blocks[0].day_range="Days 1-2",
   weekly_blocks[-1].day_range="Day 7"

$ curl '/roadmap/u-route-multi/amazon_sde_intern?days=14' → days=14,
   weekly_blocks[0].day_range="Days 1-4",
   weekly_blocks[-1].day_range="Days 13-14"
```

### Negative paths

```
GET /roadmap/u-x/no_such_role            → 404 "Unknown role 'no_such_role'."
GET /roadmap/me/amazon_sde_intern  (no auth) → 401
GET /roadmap/u-blank/amazon_sde_intern   → 200, readiness=0.0,
                                            but a sensible 4-week plan
                                            built from untested req skills
```

### Test suite

```
$ INTERVIV_USE_MEMORY_DB=true python3 -m pytest tests/ --timeout=120 -q
... 81 passed, 8 warnings in 13.02s
```

11 new tests:

- `test_30_day_plan_puts_dsa_in_week1_and_sd_by_week2`
- `test_days_param_snaps_to_supported_values` (10 → 7)
- `test_7_day_plan_compresses_to_4_phases`
- `test_14_day_plan_uses_14_day_ranges`
- `test_focus_concepts_include_skill_specific_concepts`
- `test_unknown_role_raises`
- `test_user_with_no_skill_graph_returns_untested_plan`
- `test_route_returns_200_for_seeded_user`
- `test_route_404_on_unknown_role`
- `test_me_route_requires_auth`
- `test_route_supports_7_and_14_day_query`

### Frontend

`npm run build` clean:

```
✓ 2839 modules transformed.
dist/assets/index-eP1qR8b9.css     38.51 kB │ gzip:   7.54 kB
dist/assets/index-CZWsmS6M.js   1,444.92 kB │ gzip: 385.66 kB
✓ built in 5.68s
```

Wiring:

- `App.jsx` → route `/roadmap/:userId/:roleId` → `<Roadmap />`.
- `GapAnalysis.jsx` → "Build my study plan →" CTA
  (`data-testid="build-roadmap-cta"`) navigates to the roadmap.
- `Roadmap.jsx` renders a timeline of weekly cards (testids:
  `roadmap-page`, `roadmap-title`, `roadmap-weeks`,
  `roadmap-week-card`, `roadmap-concepts`, `roadmap-day-toggle`,
  `roadmap-disclaimer`, `roadmap-start-practice`).
- Plan-length toggle (7/14/30) updates the URL via
  `?days=` and re-fetches.
- `plan_note` is surfaced in the page subtitle making the
  "recommended plan, not binding schedule" framing explicit.

### UI screenshot — not captured

Same constraint as Tasks 3 and 4: the preview MCP fails with
EPERM/uv_cwd in this workspace and I do not launch your installed
Chrome per your prior instruction. Static evidence (source, build,
JSON, tests) is provided. If you want a screenshot, the page is
reachable at `/roadmap/:userId/:roleId` after seeding the user's
skill graph.

## What's next

Task 6 (Dashboard updates) — surface readiness percentage, gap
analysis mini, skill graph tree, concept mastery heatmap, and
confidence bands per round. The Roadmap link is already wired
into the Dashboard via the Gap Analysis pill from Task 4.
