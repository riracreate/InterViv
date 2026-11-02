# interViv - Interview Readiness Platform

interViv is an **Interview Readiness Platform**. Core scoring, readiness calculations, roadmaps, and gap analysis run in Python. Optional LLM integrations provide question generation and coaching; offline practice works without provider credentials.

Start with the persistent local launcher below. See the [current maintenance results](docs/maintenance_2026-11-02.md) and [improvement roadmap](docs/IMPROVEMENT_ROADMAP.md) for verified behavior, remaining limitations, and next priorities. The winner map below records the project's assembly history rather than the current setup contract.

This folder is a curated assembly of the **best files** from all versions of the project.
Every file was chosen by reading and comparing its equivalent across all four codebases:
`AI-Driven-Adaptive-Mock-Interview-Platform`, `interview-platform`, `interviv_fixpack`, and `velorah`.

---

## Winner Map — Why Each File Was Chosen

| File | Source | Reason |
|------|--------|--------|
| `modules/nlp_scorer.py` | AI-Driven v11 | 619 lines, full 3-layer with bigram/trigram, get_feature_scores(), docstring |
| `modules/nlp_scorer_patch.py` | interviv_fixpack | Only version with empty-ideal-answer fallback heuristic |
| `modules/question_bank.py` | interview-platform | LLM-first live generation, CSV/reference fallback, SKILL_ALIASES with sub_domain tuples |
| `modules/knowledge_graph.py` | AI-Driven | Most recent, 171 edges, 9 skills |
| `modules/ner_scorer.py` | AI-Driven | Most recent, 70 entity patterns |
| `modules/c4_feedback.py` | AI-Driven | Most recent |
| `modules/resume_parser.py` | AI-Driven | Most recent |
| `modules/answer_quality_lr.joblib` | interViv retrain | Logistic Regression classifier trained on v11 answer-quality features |
| `backend/scoring/pipeline.py` | interview-platform | Cleanest import paths, identical logic |
| `backend/routes/session.py` | interview-platform | Multi-skill v2: skills[], rounds_per_skill, _skill_for_round() |
| `backend/routes/answer.py` | interview-platform | Per-skill Elo update, total_rounds, difficulty_delta |
| `backend/routes/dashboard.py` | interview-platform | topic_scores, performance_band, sanitized rounds |
| `backend/routes/resume.py` | interview-platform | Proper error handling, map_skills_to_domains |
| `backend/db/memory.py` | interview-platform | Full $set/$addToSet/$push/$inc with dotted paths, thread-safe |
| `backend/integrations.py` | interview-platform | Most complete module loader |
| `backend/config.py` | interview-platform | Env-based settings with INTERVIV_USE_MEMORY_DB flag |
| `backend/models/session.py` | interview-platform | skills[], rounds_per_skill, total_rounds fields |
| `backend/models/candidate.py` | interview-platform | Most recent |
| `data/interview_dataset_v6.csv` | interview-platform | Most recent dataset — v6 only exists here |
| `data/ml_training_data.csv` | interview-platform | Proper labelled training data |
| `frontend/src/index.css` | **velorah** | Glass-panel dark premium aesthetic |
| `frontend/src/styles/theme.css` | **velorah** | fade-rise animations |
| `frontend/src/pages/Landing.jsx` | **velorah** | Video bg, fade-in/out loop, full landing |
| `frontend/src/pages/Upload.jsx` | **velorah** | DOMAINS grid, drag-drop, step flow |
| `frontend/src/pages/Interview.jsx` | **velorah** | 741 lines, video panel, speech recognition, scoring |
| `frontend/src/pages/Dashboard.tsx` | **velorah** | TypeScript, motion.react, 415 lines, full data model |
| `frontend/src/components/dashboard/*` | **velorah** | All 9 components — only exist in velorah |
| `frontend/src/lib/api.js` | interview-platform | buildAnswerMetrics, session storage, clean request wrapper |

---

## Setup

For this checkout, with dependencies already installed:

```bash
# From interViv_best/
.venv/bin/python scripts/run_local.py
```

Open <http://127.0.0.1:5173>. This starts both services, applies migrations,
and persists accounts and progress in `local-data/interviv-local.sqlite3`.
The launcher selects this local database even if a different `DATABASE_URL`
is present in your shell. It disables live LLM and job fetching, requires no
downloads at startup, and leaves logs in `local-data/local-run/`.
Cached semantic models are used when available; a fresh machine may use the
existing lexical fallback until the model has been provisioned.

For a fresh checkout, install dependencies first (network access required):

```bash
python3.12 -m venv .venv
.venv/bin/python -m pip install -r requirements-dev.txt
(cd frontend && npm ci)
cp .env.example .env
.venv/bin/python scripts/run_local.py
```

`requirements-tested.txt` captures versions from the tested Python 3.12
environment. It is a constraints file, not a complete cross-platform hash
lock; fresh Linux/container installation still needs verification in CI.

### Local services

| Port | Process | Start | Required |
|------|---------|-------|----------|
| `8000` | FastAPI backend (uvicorn) | local launcher | yes |
| `5173` | Vite frontend | local launcher | yes |
| `19000` | Piston coding executor (Docker, loopback only) | `docker compose -f compose.coding.yml up executor` | only for Run/Submit on `/problems` |
| `11434` | Ollama (`gemma2:2b`) for coding hints | system Ollama | no; curated hints are the fallback |

Create an account via `/signup`. There is no built-in demo account.
The local launcher keeps accounts across restarts. Starting uvicorn directly
without a `DATABASE_URL` instead uses disposable in-memory storage in
development; production configuration now rejects a missing database.

Press Ctrl+C in the launcher's terminal to stop its backend and frontend.
If you separately started the coding executor, stop it with
`docker compose -f compose.coding.yml stop`.

### Coding practice executor (Piston)

Candidate code runs only in a local Piston container bound to
`127.0.0.1:19000`. `backend/execution.py` rejects every other URL (public
emkc.org included). Scoring is a deterministic visible + hidden test
comparison; no model judges code.

```bash
# one-time: fetch and checksum the four approved runtimes into a local mirror
python scripts/setup_coding_runtimes.py --download ~/piston-cache
CODING_RUNTIME_CACHE=~/piston-cache docker compose -f compose.coding.yml up -d
python scripts/setup_coding_runtimes.py --install     # python 3.12, node 20, java 15, gcc 10
docker stop interviv-coding-runtime-cache-1           # setup-only container

# then, for the backend:
export CODING_EXECUTOR_URL=http://127.0.0.1:19000
```

If the editor shows **"<Language> execution is unavailable. Your draft can
still be saved."** for every language, the backend cannot reach Piston (or the
runtime is not installed). `GET /problems/execution/status` reports
per-language availability; the UI reads that endpoint, so the warning follows
the selected language but the cause is shared. Drafts still autosave.

Optional env: `CODING_RATE_LIMIT_PER_MINUTE` (default 30), `CODING_COACH_URL`
(default `http://127.0.0.1:11434`), `CODING_COACH_MODEL` (default `gemma2:2b`).
Security evidence: `docs/coding_execution_security.md`.

### PostgreSQL and Auth

For a separately configured PostgreSQL backend, set `DATABASE_URL` in `.env`
and apply migrations before starting uvicorn. Start the frontend separately
with `npm run dev -- --host 127.0.0.1 --port 5173` from `frontend/`.
The convenience local launcher always selects its local SQLite database.

```bash
docker compose up postgres
DATABASE_URL=postgresql+psycopg://interviv:interviv@localhost:5432/interviv alembic upgrade head
uvicorn backend.main:app --reload --port 8000
```

Auth endpoints:

- `POST /auth/signup`
- `POST /auth/login`
- `GET /auth/me`

If `DATABASE_URL` is missing, the backend keeps the in-memory fallback only
for local demos and tests. Production also requires an explicit JWT secret
and allowed CORS origins. `/health` checks liveness; `/ready` checks database
connectivity, migration state, practice packs, and configured Redis access.
Use Redis for authentication limits shared across multiple backend workers;
without Redis, counters are local to each process.

The SQLAlchemy path is exercised end-to-end (signup → login → session →
answer → dashboard, plus company seeding and the skill graph) by
`tests/test_sqlalchemy_store.py`, which points `DATABASE_URL` at a throwaway
SQLite database.

### Phase 2 Readiness Platform

Phase 2 adds the durable readiness layer on top of the deterministic scoring
pipeline:

- persistent users, sessions, rounds, skill graph, and concept mastery
- curated company-role hiring profiles for TCS, Infosys, Wipro, Amazon, and Microsoft
- gap analysis against a selected target role
- concept mastery map
- personalized roadmap
- dashboard readiness, gap, mastery, and confidence-band surfaces
- adaptive question selection toward weak skills/concepts
- Sentry/Redis/deployment hardening

Evidence is tracked in `docs/post_phase2_task_1.md` through
`docs/post_phase2_task_8.md`, with the final status in
`docs/phase2_status.md`.

### Question Generation

The example configuration defaults to offline CSV questions. To opt into live
generation when starting a separately configured backend:

```bash
QUESTION_GENERATION_MODE=llm
QUESTION_REQUIRE_LLM=true
LLM_LIVE_FETCH=1
QUESTION_LLM_PROVIDER=auto
OPENAI_API_KEY=...
# or
OPENROUTER_API_KEY=...
OPENROUTER_MODEL=anthropic/claude-haiku-4.5
```

The CSV dataset is still kept for evaluation, scoring references, retraining,
and dashboard history. To intentionally use dataset questions again, set
`QUESTION_GENERATION_MODE=csv`; to try LLM first and fall back to CSV, set
`QUESTION_GENERATION_MODE=llm_csv_fallback`.

---

## Project Structure

```
interViv_best/
├── backend/
│   ├── main.py               FastAPI app, registers all routers
│   ├── config.py             Settings (Elo, max_rounds, DB mode)
│   ├── integrations.py       Module loader, map_skills_to_domains
│   ├── db/
│   │   ├── __init__.py       get_database() — picks PostgreSQL or memory fallback
│   │   ├── sqlalchemy_*.py   SQLAlchemy models + route-compatible store
│   │   └── memory.py         In-memory DB for local demos and CI
│   ├── models/
│   │   ├── session.py        SessionDocument + RoundDocument (skills[], rounds_per_skill)
│   │   └── candidate.py      CandidateDocument
│   ├── routes/
│   │   ├── session.py        POST /session/start (multi-skill, rounds_per_skill)
│   │   ├── answer.py         POST /session/answer (per-skill Elo)
│   │   ├── dashboard.py      GET /dashboard/{id}
│   │   └── resume.py         POST /resume
│   └── scoring/
│       └── pipeline.py       NLP→KG→NER→Feedback→Elo orchestration
│
├── modules/                  ← loaded dynamically by integrations.py
│   ├── nlp_scorer.py         3-layer scorer (v11)
│   ├── nlp_scorer_patch.py   Empty-ideal-answer fallback
│   ├── question_bank.py      LLM question generation + CSV/reference fallback
│   ├── knowledge_graph.py    NetworkX concept graphs
│   ├── ner_scorer.py         Tech entity extraction
│   ├── c4_feedback.py        Rule-based feedback (16 rules)
│   ├── resume_parser.py      PDF skill extraction
│   ├── skill_taxonomy_v2.csv Skill→domain mapping
│   ├── answer_quality_lr.joblib Trained Logistic Regression classifier (v11 features)
│   └── svm_model.joblib      Compatibility alias → answer_quality_lr.joblib
│
├── data/
│   ├── interview_dataset_v6.csv   875+ questions, 11 skills
│   └── ml_training_data.csv       891 labelled rows for retraining
│
├── frontend/
│   ├── src/
│   │   ├── index.css              Velorah dark glass CSS
│   │   ├── styles/
│   │   │   ├── theme.css          fade-rise animations
│   │   │   └── fonts.css          CSS vars for fonts
│   │   ├── App.jsx                Routes: / /login /signup /home /practice /problems /learn /resources /ats /jobs /coach /upload /interview/:id /dashboard /gap-analysis /roadmap
│   │   ├── lib/appNav.js          Nav destinations for the hamburger panel
│   │   ├── components/AppNav.jsx  Brand + hamburger slide panel (no profile/sign-out control)
│   │   ├── main.jsx               React entry point
│   │   ├── lib/api.js             All API calls + buildAnswerMetrics
│   │   ├── pages/
│   │   │   ├── Landing.jsx        Video background landing page
│   │   │   ├── Upload.jsx         Resume upload + domain selection
│   │   │   ├── Interview.jsx      Full interview UI with speech + scoring
│   │   │   └── Dashboard.tsx      TypeScript dashboard with motion.react
│   │   └── components/dashboard/
│   │       ├── ScoreHero.tsx      Animated score ring + stat pills
│   │       ├── EloChart.tsx       Recharts dual-line Elo chart
│   │       ├── SkillRadar.tsx     Recharts radar with glow effects
│   │       ├── LayerBreakdown.tsx L1/L2/L3 progress bars
│   │       ├── PerformanceChart.tsx Score vs difficulty line chart
│   │       ├── RoundTimeline.tsx  Animated vertical timeline
│   │       ├── RoundTable.tsx     Desktop table / mobile cards
│   │       ├── FeedbackCards.tsx  Tag-coloured expandable cards
│   │       └── StrengthsWeaknesses.tsx Split glass columns
│   ├── package.json               React 18 + recharts + motion + lucide
│   ├── vite.config.ts
│   ├── tailwind.config.js
│   └── tsconfig.json              allowJs: true (JSX + TSX mix OK)
│
├── retrain_ml_model.py        Rebuild answer-quality classifier from ml_training_data.csv
├── requirements.txt
├── .env.example
└── README.md
```

---

## Rotation Logic

```
skills = ["Python", "DSA", "System Design"]
rounds_per_skill = 3
→ Round 1,2,3 → Python  (Elo adapts per round)
→ Round 4,5,6 → DSA
→ Round 7,8,9 → System Design
```

---

## Scoring Formula

```
final_score = 100 × (
  0.45 × semantic_or_lexical_match
  + 0.25 × classifier_score
  + 0.20 × keyword_coverage
  + 0.10 × tfidf_overlap
) + KG_bonus + NER_bonus - penalties

NLP layer blend = 0.55×Layer1 + 0.25×Layer2 + 0.20×Layer3

Layer1 (Content): TF-IDF cosine(25%) + keyword coverage(15%) + bigram/trigram(15%)
Layer2 (Quality): depth signals(8%) + structure(7%) + anti-gaming(5%) + clarity(5%)
Layer3 (ML):      Logistic Regression → Good / Average / Poor

Modifiers: difficulty ×(1.00/1.05/1.12) + trade-off/example/edge-case bonus (+5 max)
Calibration: after round 2 → 85% raw + 15% session average
```

---

## Phase 2 Checklist

- ✅ PDF resume upload + skill extraction
- ✅ Multi-skill session (up to 5 skills, 3 rounds each = 15 rounds)
- ✅ Adaptive Elo per skill (separate rating per skill)
- ✅ 3-layer NLP scoring (no external API needed)
- ✅ Trained ML model (v11 features, answer_quality_lr.joblib)
- ✅ Knowledge graph scoring (9 skills, 171 edges)
- ✅ Rule-based feedback (16 C4 conditions)
- ✅ Voice input (Web Speech API, Chrome/Safari)
- ✅ PostgreSQL persistence with in-memory fallback for local demos and CI
- ✅ Dashboard: score ring, Elo chart, radar, layer breakdown, timeline
- ✅ Student Skill Graph and Concept Mastery
- ✅ Company Hiring Graphs with public-reference disclaimer
- ✅ Gap Analysis and Personalized Roadmap
- ✅ Dashboard readiness, skill graph, mastery map, and confidence bands
- ✅ Adaptive question targeting driven by deterministic weak-area state
- ✅ Deployment hardening hooks for Sentry, Redis cache/rate limits, and warm-up
- ✅ Dark glass premium UI (Velorah aesthetic)
- ✅ Landing page with video background

---

## App shell and demo path

Login and signup land on `/home`. The nav is a brand link plus a hamburger
that opens a translucent panel of destinations (`frontend/src/lib/appNav.js`):
Home, Progress, Practice, Gap, Roadmap, Problems, Learn, Resources, Resume
check, Jobs, Coach, Resume upload. Gap and Roadmap deep-link once a target
company/role is set; otherwise they point at `/home#target`. Sign out lives on
the Account page, not in the nav.

Logged-in student happy path:

1. `/home` — pick a target company/role; prepare cards for OA, Coding, SQL, Resources
2. `/practice` — Interview, **OA** (MCQ), **SQL**, or custom session builder
3. `/problems` — coding practice: Monaco editor, Python/JavaScript/Java/C++, Run (visible tests) and Submit (hidden tests) via local Piston; Coach tab gives up to 3 hints (Gemma via Ollama, curated fallback). Hints are logged as assistance and never change the score.
4. `/interview/:sessionId` — verbal rounds with deterministic NLP scoring
5. `/resources` — 32 curated links browsable by skill and category (`docs/resources_curation.md`)
6. `/coach` — paste a goal or JD → plan with skill chips + links (maps to lexicon; **does not score interviews**)
7. `/ats` — score resume vs role → Practice / Resources for a missing skill
8. `/jobs` — Apply opens Adzuna `redirect_url` in a new tab; **Practice for this role** starts a session
9. `/dashboard` — progress, last ATS total (if scored), learning signals, entry cards

### Env (optional pieces)

| Var | Notes |
|-----|--------|
| `OPENROUTER_API_KEY` / `OPENROUTER_MODEL` | Question gen + coach phrase extract; coach falls back to lexicon if unset |
| `ADZUNA_APP_ID` / `ADZUNA_APP_KEY` | Live India jobs; without keys the explorer uses fixture / documented empty state |
| `SENTRY_TRACES_SAMPLE_RATE=0.1` | Optional tracing sample rate |
| `CODING_EXECUTOR_URL=http://127.0.0.1:19000` | Enables Run/Submit on `/problems`; only this loopback URL is accepted |
| `CODING_COACH_URL` / `CODING_COACH_MODEL` | Ollama endpoint/model for coding hints; curated hints if unreachable |

Honest labels:

- OA+SQL ≠ “coding interview”; `/problems` is the test-based coding judge and needs Piston running
- ATS layout: `extract_layout_unchecked` (no invented multi-column penalties)
- Jobs need Adzuna keys for live listings; else fixture
- Paper notes: report **Krippendorff α**, not Cronbach; `LENGTH_RATIO_MULTIPLIER_ENABLED` stays **off**; **506** ambiguous annotation groups remain human-only / quarantined
