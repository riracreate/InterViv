# Phase 2 — Task 4 Evidence: Gap Analysis Engine & Screen

Date: 2026-05-18
Branch: `phase2-task4-gap-analysis`
Mode: in-memory DB shim (`INTERVIV_USE_MEMORY_DB=true`).

## What landed

- `modules/gap_analysis.py` — `GapAnalyzer`, `GapAnalysisReport`,
  `SkillGap`, `WeakArea`, and the pure `compute_gap_for_levels` core.
  Formula documented in the module header (and below).
- `backend/routes/gap_analysis.py` — `GET /gap-analysis/{user_id}/{role_id}`
  and the auth-bound `GET /gap-analysis/me/{role_id}`. Literal `/me/`
  route registered first so FastAPI doesn't bind `user_id="me"`.
- `backend/main.py` — wires the new router.
- `frontend/src/pages/GapAnalysis.jsx` — full page: big readiness
  percentage, per-skill bar chart, ranked weak areas list, "Start
  practice on weak areas" CTA, disclaimer footer.
- `frontend/src/App.jsx` — route `/gap-analysis/:userId/:roleId`.
- `frontend/src/components/CompanySelector.jsx` — "See readiness →"
  link to the GapAnalysis page once a role is picked (post-resume-upload
  flow).
- `frontend/src/pages/Dashboard.tsx` — "View readiness vs. target →"
  pill next to the header when the session has a `target_role_id`.
- `frontend/src/lib/api.js` — `fetchGapAnalysis`, `fetchMyGapAnalysis`.
- `tests/test_gap_analysis.py` — 9 new tests covering the spec
  scenario, severity bucketing, weak-area ranking, untested handling,
  the live route, and auth on `/me/`.

## What was NOT changed

- `backend/scoring/pipeline.py` — untouched.
- `modules/nlp_scorer.py`, `answer_guard.py`, `semantic_scorer.py`,
  `knowledge_graph.py`, `ner_scorer.py`, `c4_feedback.py`,
  `question_bank.py` — untouched.
- Classifier weights and `modules/model_metadata.json` —
  untouched (LogisticRegression, val_accuracy 0.9553).
- No LLM-as-judge.
- Existing routes and the scoring formula — untouched.

## Formula (load-bearing, also in modules/gap_analysis.py)

```
per_skill_readiness = min(student_level / required_level, 1.0) * 100
overall_readiness   = sum_t(weight_t * per_skill_readiness_t) / sum_t(weight_t)
                      # t iterates over TESTED required skills only.

gap_severity = "High"   if (required - student) > 25
             = "Medium" if 10 < (required - student) <= 25
             = "Low"    if (required - student) <= 10
             = "Untested"  for skills with attempts == 0

weak-area rank_score = importance_weight * gap_for_ranking
   gap_for_ranking = max(0, required - student) when tested
                   = required_level             when untested
```

**Design call** — Untested required skills are surfaced in
`per_skill_gap` with `tested=False` and severity "Untested", but they
do **not** contribute to `overall_readiness_percentage` (neither
numerator nor denominator). This keeps the percentage honest as "how
strong is the candidate on the role skills they have actually
demonstrated." The UI then highlights untested skills in the ranked
weak areas so they don't get hidden.

## Evidence

### Spec scenario (Python 70, DSA 45, DBMS 60 → Amazon SDE Intern)

`GET /gap-analysis/u-spec/amazon_sde_intern` after seeding the student
skill graph with the spec levels:

```json
{
  "user_id": "u-spec",
  "role_id": "amazon_sde_intern",
  "role_title": "SDE Intern",
  "company_id": "amazon",
  "company_name": "Amazon",
  "overall_readiness_percentage": 62.35,
  "tested_skill_count": 2,
  "required_skill_count": 5,
  "per_skill_gap": [
    { "skill": "DSA", "display_name": "Data Structures & Algorithms",
      "student_level": 45.0, "required_level": 85.0,
      "gap_severity": "High", "importance_weight": 0.4,
      "per_skill_readiness": 52.94, "attempts": 1, "tested": true },
    { "skill": "OOP", "display_name": "Object-Oriented Programming",
      "student_level": null, "required_level": 70.0,
      "gap_severity": "Untested", "importance_weight": 0.15,
      "per_skill_readiness": 0.0, "attempts": 0, "tested": false },
    { "skill": "DBMS", "display_name": "Databases",
      "student_level": 60.0, "required_level": 60.0,
      "gap_severity": "Low", "importance_weight": 0.1,
      "per_skill_readiness": 100.0, "attempts": 1, "tested": true },
    { "skill": "System Design", "display_name": "System Design",
      "student_level": null, "required_level": 55.0,
      "gap_severity": "Untested", "importance_weight": 0.1,
      "per_skill_readiness": 0.0, "attempts": 0, "tested": false },
    { "skill": "HR", "display_name": "Behavioural",
      "student_level": null, "required_level": 75.0,
      "gap_severity": "Untested", "importance_weight": 0.25,
      "per_skill_readiness": 0.0, "attempts": 0, "tested": false }
  ],
  "ranked_weak_areas": [
    { "skill": "HR",            "rank_score": 18.75, "gap_severity": "Untested" },
    { "skill": "DSA",           "rank_score": 16.00, "gap_severity": "High"     },
    { "skill": "OOP",           "rank_score": 10.50, "gap_severity": "Untested" },
    { "skill": "System Design", "rank_score": 5.50,  "gap_severity": "Untested" }
  ],
  "disclaimer": "Company hiring profiles are curated from publicly available job descriptions, observed placement patterns, and industry references. These are reference profiles for practice preparation, not exact hiring criteria."
}
```

**Verification:**

- `overall_readiness_percentage = 62.35` — inside the spec band [40, 70].
- Math check: tested-only weighted average = `(0.40 * 52.94 + 0.10 * 100) / (0.40 + 0.10) = 62.35` ✓
- DSA flagged `High` severity (gap = 40 > 25) ✓
- DBMS flagged `Low` (met exactly) ✓
- Untested OOP / System Design / HR appear with `tested=False` ✓
- Python (in user resume but not in Amazon's required set) is correctly ignored ✓
- HR (untested, weight 0.25) ranks first by `importance_weight × required_level` ✓

### Negative paths

```
GET /gap-analysis/u-spec/not_a_real_role
→ 404 {"detail": "Unknown role 'not_a_real_role'."}

GET /gap-analysis/me/amazon_sde_intern   (no Authorization header)
→ 401 {"detail": "Sign in to view your readiness against this role."}

GET /gap-analysis/fresh-user/amazon_sde_intern   (no skill graph)
→ 200 with overall_readiness_percentage = 0.0,
       tested_skill_count = 0,
       all 5 required skills surfaced as "Untested"
```

### Test suite

```
$ INTERVIV_USE_MEMORY_DB=true python3 -m pytest tests/ --timeout=120 -q
... 70 passed, 8 warnings in 15.21s
```

9 new tests in `tests/test_gap_analysis.py`:

- `test_spec_scenario_readiness_lands_in_40_to_70_band` — asserts 62.35.
- `test_dsa_is_high_severity_dbms_is_low`
- `test_untested_skills_appear_as_untested`
- `test_weak_areas_ranking_orders_by_importance_times_gap`
- `test_unknown_role_raises`
- `test_route_returns_spec_readiness_for_seeded_user` (via TestClient)
- `test_route_404_on_unknown_role`
- `test_me_route_requires_auth`
- `test_me_route_returns_my_readiness`

### Frontend — page + entry points

`npm run build` clean:

```
✓ 2838 modules transformed.
dist/assets/index-DaTU0dpj.css     38.06 kB │ gzip:   7.48 kB
dist/assets/index-BsOslLfg.js   1,436.70 kB │ gzip: 384.29 kB
✓ built in 8.97s
```

Wiring:

- `App.jsx` registers `/gap-analysis/:userId/:roleId` →
  `<GapAnalysis />`.
- `Upload.jsx` mounts `CompanySelector` in the Skills step.
  `CompanySelector` exposes a `data-testid="open-gap-analysis"` link
  to `/gap-analysis/<me|anonymous>/<role_id>` once a role is picked.
- `Dashboard.tsx` shows a `data-testid="dashboard-to-gap-analysis"`
  pill in the header when the session row has both `target_role_id`
  and `user_id`. Falls back gracefully when those are absent.

UI surfaces:

- `data-testid="overall-readiness"` — large percentage in the header.
- `data-testid="gap-skill-row"` — one per required skill.
- `data-testid="ranked-weak-areas"` — top 5 weak areas list.
- `data-testid="start-practice-cta"` — the "Start practice on weak
  areas" CTA, which navigates to `/upload` with the weak skills
  pre-filled.
- `data-testid="gap-disclaimer"` — same load-bearing disclaimer
  re-rendered from the API payload.

### UI screenshot — not captured

The preview MCP helper fails before launching the dev server in this
workspace:

```
shell-init: error retrieving current directory: getcwd: ... Operation not permitted
Error: EPERM: process.cwd failed with error operation not permitted, uv_cwd
```

Per the user's instruction in Task 3 ("dont use my chrome"), I did
not fall back to launching their installed Chrome to capture a live
screenshot. Static evidence (source snippets, build output, JSON
payloads, automated tests) is provided instead. If a visual screenshot
is required, please capture one from your browser of
`http://127.0.0.1:5173/gap-analysis/u-spec/amazon_sde_intern` after a
short seed script — happy to write a tiny helper.

## What's next

Task 5 (Personalized Roadmap) — will reuse `GapAnalyzer` to pick the
top weak areas, then pull concept-level recommendations from
`modules/concept_mastery.py` to fill weekly blocks.
