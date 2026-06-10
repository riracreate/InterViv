# interViv Phase 2 Status

Date: 2026-05-18

interViv is now documented as an Interview Readiness Platform. The product is
positioned around readiness, not legacy mock-interview-app framing. LLM usage
is limited to interview question generation through OpenRouter/Anthropic Claude
Haiku 4.5. Scoring, feedback, readiness, gap analysis, concept mastery,
roadmaps, and dashboard decisions are deterministic Python.

## Current State

- Authentication: JWT signup/login/me endpoints are implemented.
- Persistence: PostgreSQL via SQLAlchemy/Alembic when `DATABASE_URL` is set;
  in-memory fallback remains for local demos and CI.
- Student Skill Graph: persistent per-user skill nodes with current score,
  Elo, attempts, last practice timestamp, and KG-derived sub-concepts.
- Concept Mastery: concept-level attempts and demonstration rates.
- Company Hiring Graph: 5 supported company-role profiles:
  - TCS Software Engineer
  - Infosys System Engineer
  - Wipro PEP
  - Amazon SDE Intern
  - Microsoft SDE Intern
- Company profile disclaimer is load-bearing:
  "Company hiring profiles are curated from publicly available job
  descriptions, observed placement patterns, and industry references. These
  are reference profiles for practice preparation, not exact hiring criteria."
- Gap Analysis: readiness formula implemented from deterministic skill graph
  and company-role requirements.
- Concept Mastery Map: surfaced through API and dashboard.
- Personalized Roadmap: 7, 14, and 30 day deterministic plans.
- Dashboard: readiness, gap summary, skill graph, concept mastery, confidence
  bands, and roadmap links.
- Adaptive Question Selection: after each round, the next question targets the
  weakest skill/concept when enough deterministic state exists.
- Production Hardening: Sentry hooks, Redis question cache/rate limiting,
  LLM retry/fallback, startup warm-up, Docker/Compose/Render/Vercel config,
  and local load smoke.

## Model Accuracy Wording

The current `modules/model_metadata.json` reports:

- `model_type`: `LogisticRegression`
- `val_accuracy`: `0.9553`
- `cv_5fold_accuracy_mean`: `0.9562`
- `cv_5fold_accuracy_std`: `0.0148`
- dataset: `data/ml_training_data.csv`
- rows: `891`, balanced across `Average`, `Good`, and `Poor`

These numbers are classifier validation metrics on the balanced labelled
answer-quality dataset. They are not whole-system accuracy, interview
readiness accuracy, or hiring prediction accuracy.

Older quality-pass notes mention `94.61%`. That number refers to a
classifier-only 5-fold cross-validation accuracy on a balanced training set,
not the full platform's accuracy.

## Protected Scoring Identity

The Phase 2 platform keeps:

- the 3-layer scoring pipeline
- anti-gaming guard
- classifier-based answer-quality label
- NER scorer
- knowledge graph scorer
- deterministic C4 feedback
- human baseline validation framing

No LLM-as-judge path has been introduced.

## Evidence Packets

- `docs/post_phase2_task_1.md`
- `docs/post_phase2_task_2.md`
- `docs/post_phase2_task_3.md`
- `docs/post_phase2_task_4.md`
- `docs/post_phase2_task_5.md`
- `docs/post_phase2_task_6.md`
- `docs/post_phase2_task_7.md`
- `docs/post_phase2_task_8.md`

## Remaining External Work

The code and config for deployment are present, but production URLs and Sentry
dashboard screenshots require external account credentials. Fill the final
values in `docs/deployment.md` after deploying backend, frontend, PostgreSQL,
Redis, and Sentry projects.
