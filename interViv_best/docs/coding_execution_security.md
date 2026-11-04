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

## Trusted local runner (Docker-free demo mode)

Added 2026-11-03. Started only by
`.venv/bin/python scripts/run_local.py --trusted-local-execution`, which sets
`INTERVIV_TRUSTED_LOCAL_EXECUTION=1` and `INTERVIV_BIND_HOST=127.0.0.1`. The
backend honours the flag only when `ENVIRONMENT=development` and the bind host
is loopback (`backend/local_runner.py:trusted_local_execution_enabled`); every
other deployment keeps the Piston-only requirement above.

**This is a trusted local runner, not a security sandbox.** Use it only with
your own code on your own machine. Restricted builtins and import hooks can be
bypassed by determined code; nothing here isolates the filesystem or network
the way the Piston container does.

| Control | Implementation |
|---------|----------------|
| Selection | Piston first when configured and its runtime exists; else Python only through the local runner. JavaScript, Java and C++ stay unavailable. |
| Process | Fresh `sys.executable -I` worker per job, temporary working directory (deleted afterwards), minimal environment, own process group killed on exit. |
| Concurrency | Shares `BoundedSemaphore(2)` with Piston jobs: at most two workers. |
| Time | 2.5 s wall budget for candidate code, measured after a separate startup handshake (8 s). `RLIMIT_CPU` backstop. |
| Memory | RSS watchdog (psutil) on every platform: 256 MiB Python, 512 MiB NumPy. Linux also gets `RLIMIT_AS` (limit + 1 GiB headroom for NumPy reservations); macOS does not enforce `RLIMIT_AS`. |
| Output | 256 KB stdout cap; `RLIMIT_FSIZE` 1 MB. |
| Imports | Candidate module (`solution` / `candidate`) may import a small stdlib allowlist (+ `numpy` for ML). `open`, `input`, `breakpoint` are replaced. |
| Quota | Per-round run quota is reserved before execution and released when the executor never ran; candidate syntax/runtime errors and timeouts count. |
| Data | Expected outputs and hidden tests stay in the API process; hidden outcomes are aggregate only. ML arrays cross the boundary as JSON with explicit dtype/shape, never pickle. |

ML primitives (`backend/ml_primitives/evaluate.py`, scorer `v1-ml-primitives`)
run only through this runner: score = 100 × cases passing every numerical
check ÷ cases. Imports outside the pack allowlist and syntax errors are
candidate errors and are not executed. Static/vectorization findings are
reported separately and do not change the score. Tests:
`tests/test_local_runner.py`, `tests/test_ml_execution.py`.
