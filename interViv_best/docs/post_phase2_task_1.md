# Phase 2 Task 1 Evidence - Authentication and Real Database

Date: 2026-05-18
Mode: PostgreSQL through SQLAlchemy/Alembic, with in-memory fallback when
`DATABASE_URL` is unset.

## What Landed

- SQLAlchemy persistence adapter and Alembic migration for the Phase 2 schema.
- JWT auth with bcrypt password hashing:
  - `POST /auth/signup`
  - `POST /auth/login`
  - `GET /auth/me`
- PostgreSQL-backed route-compatible storage for users, sessions, rounds,
  companies, roles, requirements, skills, skill graph, concept mastery, and
  rubrics.
- Local deployment config:
  - `backend/Dockerfile`
  - `docker-compose.yml`
  - `render.yaml`
- In-memory fallback preserved for local demos and CI when `DATABASE_URL` is
  unset.

## Protected Areas

No scoring formula, scoring weights, classifier model, dataset, or LLM-as-judge
path was introduced by this task.

## Alembic Upgrade

```text
$ DATABASE_URL=postgresql+psycopg://interviv:interviv@localhost:5432/interviv .venv/bin/alembic upgrade head
INFO  [alembic.runtime.migration] Context impl PostgresqlImpl.
INFO  [alembic.runtime.migration] Will assume transactional DDL.
INFO  [alembic.runtime.migration] Running upgrade  -> 20260518_0001
```

## Auth Round Trip

```text
POST /auth/signup -> 200
POST /auth/login  -> 200
GET  /auth/me     -> 200
```

The returned user payload included `id`, `email`, `name`,
`target_company_id`, `target_role_id`, `created_at`, and `last_active_at`.

## PostgreSQL Tables

```text
alembic_version
candidates
companies
company_role_requirements
question_rubrics
roles
rounds
sessions
skills
student_concept_mastery
student_skill_graph
users
```

## Existing Smoke Tests

```text
$ .venv/bin/pytest tests/ -v
46 passed, 6 warnings in 21.38s
```

