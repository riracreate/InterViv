# Phase 3B SQL persistence note

Migration `20260915_0013` adds nullable `sessions.progression_blocked_reason`.

Verify on a disposable database:

```bash
export INTERVIV_DATABASE_URL=sqlite:////tmp/phase3b-continue.db
alembic upgrade head
# create content_blocked session via API, set reason, reopen process
alembic downgrade 20260914_0012   # drops column only
```

Memory mode needs no migration; the document field is stored as-is.
