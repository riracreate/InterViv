# Coding execution security — local Piston

Branch: `codex/coding-practice`. Executor compose: `compose.coding.yml`.
App client: `backend/execution.py` (`CODING_EXECUTOR_URL`).

## Threat mitigations

### 1. No public Piston / emkc

| Control | Status |
|---------|--------|
| Tree grep for `emkc.org` / public piston execute URLs | **None found** in app code |
| Client accepts only `http://127.0.0.1:19000` | **Enforced** via `executor_url_is_allowed` / `_configured_executor_url` |
| Unset, `localhost`, `0.0.0.0`, other ports, https, userinfo, query | **Rejected** → `ExecutionUnavailableError` |
| Tests | `tests/test_coding_executor_security.py` |

Setup script downloads **package archives** from GitHub releases into a local cache (install-time only). Runtime jobs never call GitHub or emkc; Piston installs from `http://runtime-cache` on the compose network.

### 2. Host / network isolation

| Control | Evidence |
|---------|----------|
| Host bind | `lsof`: `TCP 127.0.0.1:19000 (LISTEN)` — not `0.0.0.0` |
| PortBindings | `HostIp=127.0.0.1`, `HostPort=19000` |
| Volumes | Only Docker named volume `runtimes` → `/piston/packages`. **No** Docker socket, project path, or DB mount |
| `PISTON_DISABLE_NETWORKING` | `true` in container env |
| Candidate network probe | Python `urllib.request.urlopen("http://1.1.1.1")` → stdout `NET_BLOCKED URLError` |
| Compose project | Separate `interviv-coding` project from the web app |

**Production note (documented in compose header):** run Piston on a separate VM from web/DB; keep edge rate limits on the app; never publish Piston on a public interface.

**Remaining gap:** executor runs `privileged: true` (required by Piston isolate/cgroups). Acceptable only for this local sandbox; production should harden on a dedicated VM with no app secrets mounted.

### 3. DoS / rate limiting

| Control | Status |
|---------|--------|
| In-process concurrency | `BoundedSemaphore(2)` + `PISTON_MAX_CONCURRENT_JOBS=2` |
| Per-round cap | `max_requests_per_round=50` via `consume_round_exec_slot` on `/session/coding/run` and coding `/session/answer` |
| Per-user sliding window | `coding_user_rate_ok` default 30/min (`CODING_RATE_LIMIT_PER_MINUTE`); HTTP **429** |
| Piston not exposed beyond loopback | Binding evidence above |
| Production edge limits | Documented requirement (Nginx/Cloudflare); not implemented in this local stack |

## Restriction probe evidence (2026-09-10, local Docker)

Happy path: `print(40+2)` → stdout `42\n`, code `0`.

Timeout: `time.sleep(30)` with `run_timeout=1000` → `status=TO`, `signal=SIGKILL`, empty stdout.

Network: outbound HTTP → `NET_BLOCKED URLError` with networking disabled.

Memory: allocate ~200 MiB under `run_memory_limit=67108864` → process killed, `code=137`, reported `memory≈67108000`.

## App wiring

- `POST /session/coding/run` and coding submit call `assert_coding_exec_allowed` before `execute_python_tests`.
- Local coach: `backend/coding_coach.py` + `POST /problems/coach/hint`; default Ollama model `gemma2:2b` on `127.0.0.1:11434`, curated fallback if unavailable. Hints record `assistance_events` and never affect scores.

## Remaining gaps

- Privileged container (above).
- No distributed rate limit (in-process only; fine for single local API worker).
- Fine-tuning deferred: ship stock Gemma + curated fallback; collect Socratic pairs before QLoRA/DPO.
- Full browser Monaco verification not re-run in this security interrupt.
