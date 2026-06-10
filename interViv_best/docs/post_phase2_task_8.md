# Phase 2 Task 8 Evidence

Task 8 production hardening added:

- Backend Sentry initialization via `SENTRY_DSN`
- Frontend Sentry envelope reporting via `VITE_SENTRY_DSN`
- Redis-backed 24h question cache keyed by
  `(skill, sub_domain, difficulty, target_concepts)`
- LLM rate limiting and 3-attempt exponential-backoff retry
- Deterministic CSV/domain/template question fallback after final LLM failure
- Startup warm-up for classifier model, sentence-transformer, knowledge graph,
  company graph, and question runtime
- Local 10-user/3-round load smoke

## Health/Warm-Up Smoke

```text
$ INTERVIV_USE_MEMORY_DB=true QUESTION_GENERATION_MODE=csv QUESTION_REQUIRE_LLM=false DISABLE_SEMANTIC_SCORING=true .venv/bin/python - <<'PY'
from fastapi.testclient import TestClient
from backend.main import app

with TestClient(app) as client:
    response = client.get('/health')
    print(response.status_code)
    print(response.json())
PY
SemanticScorer unavailable; semantic scoring disabled by env.
200
{'status': 'ok', 'sentry_enabled': False, 'warmup': {'classifier_model': {'loaded': True, 'model_type': 'LogisticRegression', 'metadata_accuracy': 0.9553}, 'sentence_transformer': {'loaded': False, 'fallback_reason': 'disabled_by_env'}, 'knowledge_graph': {'loaded': True, 'skills': ['CN', 'DBMS', 'DSA', 'HR', 'ML', 'OOP', 'OS', 'Python', 'System Design'], 'stats': {'OOP': {'nodes': 25, 'edges': 22}, 'Python': {'nodes': 29, 'edges': 20}, 'ML': {'nodes': 30, 'edges': 23}, 'DSA': {'nodes': 31, 'edges': 21}, 'DBMS': {'nodes': 26, 'edges': 19}, 'CN': {'nodes': 28, 'edges': 18}, 'OS': {'nodes': 21, 'edges': 15}, 'System Design': {'nodes': 31, 'edges': 21}, 'HR': {'nodes': 17, 'edges': 12}}}, 'question_runtime': {'csv_questions_loaded': 773, 'redis_enabled': False, 'redis_ready': False, 'cache_ttl_seconds': 86400, 'llm_rate_limit_per_minute': 60}}}
```

## Task 8 Unit Smoke

```text
$ .venv/bin/pytest tests/test_task8_hardening.py tests/test_adaptive_selector.py -q
...............                                                          [100%]
15 passed in 0.30s
```

## Frontend Build

```text
$ npm run build

> interviv-frontend@1.0.0 build
> tsc && vite build

vite v5.4.21 building for production...
transforming...
✓ 2841 modules transformed.
rendering chunks...
computing gzip size...
dist/index.html                     0.59 kB │ gzip:   0.37 kB
dist/assets/index-BGqmZKHa.css     39.14 kB │ gzip:   7.62 kB
dist/assets/index-DfVuLpHx.js   1,455.22 kB │ gzip: 388.25 kB

(!) Some chunks are larger than 500 kB after minification. Consider:
- Using dynamic import() to code-split the application
- Use build.rollupOptions.output.manualChunks to improve chunking: https://rollupjs.org/configuration-options/#output-manualchunks
- Adjust chunk size limit for this warning via build.chunkSizeWarningLimit.
✓ built in 11.19s
```

## Local Load Smoke

```text
$ INTERVIV_USE_MEMORY_DB=true QUESTION_GENERATION_MODE=csv QUESTION_REQUIRE_LLM=false DISABLE_SEMANTIC_SCORING=true .venv/bin/python scripts/task8_load_test.py
SemanticScorer unavailable; semantic scoring disabled by env.
{
  "users": 10,
  "rounds_per_user": 3,
  "answer_calls": 30,
  "errors": [],
  "mean_latency_seconds": 0.6876,
  "p95_latency_seconds": 1.9789,
  "wall_time_seconds": 2.7846,
  "passed": true
}
```

## External Evidence Not Produced Locally

No Sentry dashboard screenshot or deployed HTTPS URL was produced from this
workspace, because those require external Sentry/Render/Vercel/database account
credentials. Deployment variables and URL placeholders are documented in
`docs/deployment.md`.

