# interViv Deployment

interViv is an Interview Readiness Platform. LLM usage is limited to question
generation through OpenRouter/Anthropic Claude Haiku 4.5. Scoring, feedback,
readiness, gap analysis, and recommendations are deterministic Python.

## Services

- Backend: Render web service from `backend/Dockerfile`
- Frontend: Vercel static/Vite deployment from `frontend/`
- Database: managed PostgreSQL through Render, Supabase, or Neon
- Cache/rate limit: Redis, required for shared production question cache
- Error monitoring: Sentry for backend and frontend

## Required Backend Env Vars

- `DATABASE_URL`: PostgreSQL SQLAlchemy connection string
- `JWT_SECRET_KEY`: 32+ byte secret for auth tokens
- `CORS_ORIGINS`: comma-separated frontend origins
- `QUESTION_LLM_PROVIDER`: `openrouter`
- `OPENROUTER_API_KEY`: OpenRouter key
- `OPENROUTER_MODEL`: `anthropic/claude-haiku-4.5`
- `REDIS_URL`: Redis connection string for question cache/rate limiting
- `SENTRY_DSN`: backend Sentry DSN

## Hardening Env Vars

- `QUESTION_CACHE_TTL_SECONDS`: defaults to `86400`
- `QUESTION_LLM_MAX_RETRIES`: defaults to `3`
- `QUESTION_LLM_RETRY_BASE_SECONDS`: defaults to `0.25`
- `QUESTION_LLM_TIMEOUT_SECONDS`: defaults to `20`
- `QUESTION_LLM_RATE_LIMIT_PER_MINUTE`: defaults to `60`; set `0` to disable
- `SENTRY_ENVIRONMENT`: `production`, `staging`, or `development`
- `SENTRY_RELEASE`: optional release identifier
- `SENTRY_TRACES_SAMPLE_RATE`: defaults to `0.0`
- `SENTRY_PROFILES_SAMPLE_RATE`: defaults to `0.0`

## Required Frontend Env Vars

- `VITE_API_BASE_URL`: backend HTTPS URL
- `VITE_SENTRY_DSN`: frontend Sentry DSN
- `VITE_SENTRY_ENVIRONMENT`: `production`
- `VITE_SENTRY_RELEASE`: optional release identifier

## Current Deployment URLs

No production deployment has been performed from this workspace yet because
platform credentials are required. Fill these once deployed:

- Backend HTTPS URL: `TBD`
- Frontend HTTPS URL: `TBD`
- PostgreSQL provider/project: `TBD`
- Redis provider/project: `TBD`
- Sentry project URL: `TBD`

## Verification

Run migrations before serving the backend:

```bash
alembic upgrade head
```

Run local smoke tests:

```bash
.venv/bin/pytest tests/ -q
```

Run the local 10-user/3-round load smoke:

```bash
.venv/bin/python scripts/task8_load_test.py
```

The load smoke uses the in-memory DB and deterministic CSV question path so it
can run without paid production credentials. A real production load test should
target the deployed HTTPS backend with `DATABASE_URL`, `REDIS_URL`, and
`OPENROUTER_API_KEY` configured.

