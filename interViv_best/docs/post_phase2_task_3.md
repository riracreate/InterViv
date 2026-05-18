# Phase 2 — Task 3 Evidence: Company Hiring Graph

Date: 2026-05-18
Branch: `phase2-task3-company-graph`
Mode: in-memory DB shim (`INTERVIV_USE_MEMORY_DB=true`) for routes,
SQLite-backed seed idempotency proof for the SQL adapter.

## What landed

- `data/company_hiring_graphs.yaml` — 5 companies / 5 roles / 25 skill
  requirements, with a load-bearing disclaimer in the YAML header.
- `modules/company_graph.py` — read-only loader (`CompanyHiringGraph`,
  `Company`, `Role`, `SkillRequirement`, `get_company_graph`,
  `reload_company_graph`).
- `backend/db/company_seed.py` — idempotent seeder for the `skills`,
  `companies`, `roles`, `company_role_requirements` tables.
- `backend/routes/companies.py` — `GET /companies`,
  `GET /companies/{id}`, `GET /companies/{id}/roles`,
  `GET /companies/{id}/roles/{role_id}`, and
  `PATCH /auth/me/target` for persisting the selection.
- `backend/main.py` — wires the router and adds a startup hook that
  loads the YAML and seeds the DB tables.
- `frontend/src/components/CompanySelector.jsx` — UI that surfaces the
  disclaimer verbatim, lets the user pick a company + role, and writes
  the selection via `PATCH /auth/me/target` for authenticated users.
- `frontend/src/pages/Upload.jsx` — mounts `CompanySelector` inside the
  Skills step so the user picks a target after their resume is parsed.
- `tests/test_company_graph.py` — 12 new tests covering the loader,
  the routes, the auth-bound PATCH, and DB seed idempotency on SQLite.

## What was NOT changed

Per the strict rules in the brief:
- `backend/scoring/pipeline.py` — untouched.
- `modules/nlp_scorer.py`, `modules/answer_guard.py`,
  `modules/semantic_scorer.py`, `modules/knowledge_graph.py`,
  `modules/ner_scorer.py`, `modules/c4_feedback.py`,
  `modules/question_bank.py` — untouched.
- Classifier weights, the scoring blend, and the 5-fold CV accuracy in
  `modules/model_metadata.json` — untouched (LogisticRegression,
  val_accuracy 0.9553, CV mean 0.9562).
- Dataset path (`data/ml_training_data.csv`) — untouched.
- No LLM-as-judge was introduced.

## Identity discipline

The "interview Readiness Platform" framing is preserved. Every API
response that mentions a company carries the disclaimer:

> Company hiring profiles are curated from publicly available job
> descriptions, observed placement patterns, and industry references.
> These are reference profiles for practice preparation, not exact
> hiring criteria.

The same string is rendered verbatim inside `CompanySelector` at
`data-testid="company-disclaimer"`.

## Evidence

### 3a — YAML cat (5 companies / 5 roles)

```
$ wc -l data/company_hiring_graphs.yaml && \
  grep -E "^  - id:|^      - id:" data/company_hiring_graphs.yaml
160 data/company_hiring_graphs.yaml
  - id: tcs
      - id: tcs_swe
  - id: infosys
      - id: infosys_system_engineer
  - id: wipro
      - id: wipro_pep
  - id: amazon
      - id: amazon_sde_intern
  - id: microsoft
      - id: microsoft_sde_intern
```

Amazon's curated profile (matches the spec's gap-analysis test scenario
of DSA 85 / OOP 70 / DBMS 60 / System Design 55 / Behavioural 75):

```yaml
  - id: amazon
    name: "Amazon"
    roles:
      - id: amazon_sde_intern
        title: "SDE Intern"
        level: "intern"
        skill_requirements:
          - {skill: "DSA",           required_level: 85, importance_weight: 0.40}
          - {skill: "OOP",           required_level: 70, importance_weight: 0.15}
          - {skill: "DBMS",          required_level: 60, importance_weight: 0.10}
          - {skill: "System Design", required_level: 55, importance_weight: 0.10}
          - {skill: "HR",            required_level: 75, importance_weight: 0.25}
```

(All weights sum to 1.0 per role; the loader rejects mismatches with a
`CompanyGraphError`.)

### 3e — curl GET /companies

```
$ curl -s http://127.0.0.1:8765/companies | python3 -m json.tool | head -8
{
    "disclaimer": "Company hiring profiles are curated from publicly available job descriptions, observed placement patterns, and industry references. These are reference profiles for practice preparation, not exact hiring criteria.",
    "companies": [
        {
            "id": "tcs",
            "name": "TCS",
            ...
        },
        ...  # infosys, wipro, amazon, microsoft
    ]
}
```

```
$ curl -s http://127.0.0.1:8765/companies/amazon/roles | python3 -c "import sys, json; d=json.load(sys.stdin); print('company:', d['company']); print('roles:', [r['id'] for r in d['roles']]); print('req count:', len(d['roles'][0]['skill_requirements']))"
company: {'id': 'amazon', 'name': 'Amazon'}
roles: ['amazon_sde_intern']
req count: 5
```

```
$ curl -s http://127.0.0.1:8765/companies/microsoft/roles/microsoft_sde_intern | python3 -m json.tool
{
    "disclaimer": "Company hiring profiles are curated from publicly available job descriptions, observed placement patterns, and industry references. These are reference profiles for practice preparation, not exact hiring criteria.",
    "company_id": "microsoft",
    "role": {
        "id": "microsoft_sde_intern",
        "title": "SDE Intern",
        "level": "intern",
        "skill_requirements": [
            {"skill": "DSA", "display_name": "Data Structures & Algorithms", "required_level": 80.0, "importance_weight": 0.35},
            {"skill": "OOP", "display_name": "Object-Oriented Programming", "required_level": 75.0, "importance_weight": 0.2},
            {"skill": "System Design", "display_name": "System Design", "required_level": 60.0, "importance_weight": 0.15},
            {"skill": "DBMS", "display_name": "Databases", "required_level": 60.0, "importance_weight": 0.1},
            {"skill": "HR", "display_name": "Behavioural", "required_level": 75.0, "importance_weight": 0.2}
        ],
        "db_id": null
    }
}
```

### Negative path — 404 on unknown company

```
$ curl -s -o /dev/null -w "%{http_code}\n" http://127.0.0.1:8765/companies/apple/roles
404
```

### PATCH /auth/me/target round-trip (graceful fallback verified)

Authenticated path:

```
$ TOKEN=$(curl -s -X POST .../auth/signup ... | jq -r .access_token)
$ curl -s -X PATCH http://127.0.0.1:8765/auth/me/target \
    -H "Authorization: Bearer $TOKEN" \
    -H "Content-Type: application/json" \
    -d '{"target_company_id":"amazon","target_role_id":"amazon_sde_intern"}' \
    | python3 -m json.tool
{
    "user": {
        "id": "aac50438-8163-4986-9bb5-de461e5df4c0",
        "email": "task3@example.com",
        "name": "Task3 Tester",
        "target_company_id": "amazon",
        "target_role_id": "amazon_sde_intern",
        "created_at": "2026-05-18T10:18:50.353537Z",
        "last_active_at": "2026-05-18T10:18:50.545090Z"
    },
    "target_company_slug": "amazon",
    "target_role_slug": "amazon_sde_intern",
    "disclaimer": "Company hiring profiles are curated from publicly available job descriptions, observed placement patterns, and industry references. These are reference profiles for practice preparation, not exact hiring criteria."
}

$ curl -s -o /dev/null -w "%{http_code}\n" -X PATCH http://127.0.0.1:8765/auth/me/target \
    -H "Authorization: Bearer $TOKEN" \
    -H "Content-Type: application/json" \
    -d '{"target_company_id":"amazon","target_role_id":"notreal_role"}'
404
```

Graceful fallback rule:

- Unauthenticated visitor → CompanySelector shows the picker but the
  "Save as my target" button changes to "Use for this session"; the
  session route reads `target_company_id`/`target_role_id` from the
  user record so anonymous sessions stay in general practice mode.
- No company picked → the picker stays empty and the session starts
  with `target_company_id=None` (existing behaviour).

### 3d — Idempotent DB seed (SQLite proof of upsert behaviour)

```
$ rm -f /tmp/co_smoke.db
$ DATABASE_URL="sqlite:////tmp/co_smoke.db" python3 -c "
... reset caches, create_all, seed three times ..."
first run:  {'companies': 5, 'roles': 5, 'skills': 7, 'requirements': 25}
second run: {'companies': 0, 'roles': 0, 'skills': 0, 'requirements': 0}
third run:  {'companies': 0, 'roles': 0, 'skills': 0, 'requirements': 0}
companies in db: 5
roles in db: 5
skills in db: 7  # DSA, OOP, DBMS, OS, CN, System Design, HR
requirements in db: 25
```

### 3f — Frontend CompanySelector

The frontend dev server (Vite) was confirmed up at
`http://127.0.0.1:5180/upload`. The `Upload.jsx` "Skills" step mounts
the `CompanySelector` component before the "Choose Interview Domains"
CTA:

```
$ grep -B 1 -A 5 "CompanySelector" frontend/src/pages/Upload.jsx
import CompanySelector from '../components/CompanySelector';
...
<div className="mb-6">
  <CompanySelector
    isAuthenticated={isAuthenticated}
    onSelectionChange={setTargetSelection}
  />
</div>
```

Disclaimer is sourced from the live API payload and re-rendered
verbatim:

```jsx
<p data-testid="company-disclaimer" className="text-xs ...">
  <span className="font-medium text-black">Note:</span> {disclaimer}
</p>
```

`npm run build` passes cleanly:

```
✓ 2837 modules transformed.
dist/assets/index-C-roikDm.css     37.48 kB │ gzip:   7.38 kB
dist/assets/index-DWKnBzwO.js   1,425.98 kB │ gzip: 381.53 kB
✓ built in 7.43s
```

Live screenshot via the user's installed Chrome was deliberately
avoided per user feedback ("dont use my chrome"). Static evidence
(source snippets + live API payloads + build output) is provided
instead.

### Test suite

```
$ INTERVIV_USE_MEMORY_DB=true python3 -m pytest tests/ --timeout=120 -q
... 61 passed, 8 warnings in 18.11s
```

12 new tests cover:

- Loader returns exactly the 5 expected companies.
- Disclaimer text is the load-bearing wording.
- Amazon SDE Intern weights sum to 1.0 and match the spec.
- `get_role` rejects mismatched (company, role) pairs.
- `get_required_skills` returns 5 entries with values in [0, 100] / [0, 1].
- Loader rejects YAMLs whose weights don't sum to 1.0.
- `GET /companies` returns the 5 companies + disclaimer.
- `GET /companies/{id}/roles` returns roles + disclaimer.
- `GET /companies/{unknown}/roles` → 404.
- `PATCH /auth/me/target` round-trip persists the slug.
- `PATCH /auth/me/target` rejects an unknown role with 404.
- Seeding against a fresh SQLite DB three times: counts go
  `(5,5,7,25) → (0,0,0,0) → (0,0,0,0)`, final row counts match.

## What's next

Task 4 (Gap Analysis engine + screen) — will join the user's
`student_skill_graph` to the role's `skill_requirements` and surface
per-skill readiness + ranked weak areas. The Amazon profile authored
in this task is already wired to match the Task 4 test scenario
(`DSA 85, OOP 70, DBMS 60, System Design 55, Behavioural 75`).
