# Phase U — execution-service spike (investigation only)

**Branch:** `codex/phase-b-block-practice` · **Base HEAD:** `e062e0d` (Phase T) · **Date:** 2026-09-07
**Scope:** answer one question — what code-execution infrastructure, if any, can
actually run on this machine. No implementation. No application changes.
**Result:** nothing demonstrated. The Docker daemon was unreachable for two
independent reasons (Desktop Linux VM stopped; sandboxed session cannot reach
the socket), so Steps 1–2 are evidence plus static description, and **C.2
stays blocked**. See Step 3 for the recommendation and the owner's decisions.

Authorization: the owner permitted Docker image pulls and release-archive
downloads for this investigation only. **Nothing was downloaded** (no images,
no archives) because no daemon was reachable to pull through; the only network
probe was an HTTPS HEAD/GET header check against `registry-1.docker.io`
(headers only, nothing stored). Application offline defaults
(`HF_HUB_OFFLINE`, `JOBS_LIVE_FETCH`, `LLM_LIVE_FETCH`, no fonts) untouched —
no application file was modified in this phase.

---

## Step 0 — Docker reality check

### 0.1 Docker CLI vs daemon

```text
$ docker version
Client:
 Version:           29.1.3
 API version:       1.52
 Go version:        go1.25.5
 Git commit:        f52814d
 Built:             Fri Dec 12 14:48:46 2025
 OS/Arch:           darwin/arm64
 Context:           desktop-linux
permission denied while trying to connect to the docker API at unix:///Users/praneetsharma/.docker/run/docker.sock
```

```text
$ docker context ls
NAME              DESCRIPTION           DOCKER ENDPOINT                                      ERROR
default           Current ...           unix:///var/run/docker.sock
desktop-linux *   Docker Desktop        unix:///Users/praneetsharma/.docker/run/docker.sock
```

`/var/run/docker.sock` does not exist. The Desktop socket file exists:

```text
$ stat -f '%N size=%z mtime=%Sm uid=%u mode=%Mp%Lp' ~/.docker/run/docker.sock; date
/Users/praneetsharma/.docker/run/docker.sock size=0 mtime=Sep  7 23:29:38 2026 uid=501 mode=0755
Mon Sep  7 23:43:16 IST 2026
```

Direct connect probe (proves the failure mode is the sandbox, not file ACLs —
the socket is owned by our own uid 501 with mode 0755, yet connect raises
EPERM errno 1, the macOS sandbox signature, not EACCES errno 13):

```text
--- /Users/praneetsharma/.docker/run/docker.sock exists= True
CONNECT FAIL: PermissionError [Errno 1] Operation not permitted
--- /var/run/docker.sock exists= False
CONNECT FAIL: FileNotFoundError [Errno 2] No such file or directory
```

Unsandboxed execution was requested once for diagnostics and is not available
in this session: `escalated execution requires an unrestricted permission
profile`. `ps`/`pgrep` are likewise blocked (`Operation not permitted`).

### 0.2 Ground truth from Desktop logs: the Linux VM is stopped

Docker Desktop 4.55.0 (build 213807) is installed at `/Applications/Docker.app`.
Its host-side backend is alive (API-cache polls as recent as 23:42:55 IST),
but the Linux VM that hosts `dockerd` **stopped gracefully at 23:39:42 IST**
(18:09:42Z), ~10 minutes after booting at ~23:29:

```text
$ tail vm/init.log / host/com.docker.virtualization.log
{"component":"poweroff",...,"msg":"power the vm off","time":"2026-09-07T18:09:42.777465722Z"}
[2026-09-07T18:09:42.819525000Z][com.docker.virtualization] VM has stopped gracefully
```

So the daemon is unreachable for **two independent reasons**, either of which
alone blocks the spike:

1. **VM stopped** — even an unrestricted terminal would find no live `dockerd`
   right now (the owner must start/resume the Desktop engine; no sudo and no
   system-setting changes are needed for that).
2. **Sandboxed session** — this session cannot connect to the Desktop socket
   (EPERM) and cannot escalate, so hands-on steps could not run here regardless.

`docker desktop status` also fails from this session (`Could not retrieve
status. Is Docker Desktop running?`), consistent with both causes.

### 0.3 Host, resources, cgroup, flags

```text
$ sw_vers; uname -m; sysctl hw.memsize; df -h /
macOS 26.6.2 (Build 25G83) · arm64 · Apple M3 · hw.memsize: 8589934592 (8 GiB)
Filesystem  Size  Used  Avail Capacity  Mounted on
/dev/disk3s1s1  228Gi  12Gi  39Gi  24%  /
```

- **cgroup version: UNKNOWN.** Only the daemon can report it; the daemon was
  unreachable. Docker Desktop for macOS is documented to default to cgroup v2
  with no supported switch back (per the phase brief), but that was **not
  verified on this machine**.
- **Container flag tests (`--network=none`, `-m`, `--pids-limit`,
  `--read-only`): DID NOT RUN.** No daemon, no containers.
- **Configured VM CPUs/memory/disk: UNKNOWN.** Desktop's settings store under
  `~/Library/Group Containers/group.com.docker/` is unreadable from this
  session (`Operation not permitted`).
- **Image architecture / emulation: NOT ASSESSED.** No daemon to query; no
  images pulled. Host needs `arm64` images (or Rosetta/QEMU emulation, which
  would need explicit verification later).
- **Registry network path: WORKS.** `curl -sI https://registry-1.docker.io/v2/`
  returned `HTTP/2 401` (expected for an unauthenticated probe), so pulls are
  network-feasible once a daemon exists.

### 0.4 Exactly what is needed to unblock a re-spike

1. Owner starts the Desktop engine (open Docker Desktop, or
   `docker desktop start` in an unrestricted terminal). No sudo. No settings.
2. Re-run the hands-on spike from an **unrestricted** terminal or session:
   `docker info` (record `CgroupVersion`, `MemTotal`, `Architecture`),
   pull one minimal image, run the four flag tests, then candidates
   (a)→(b)→(c) in order with the five demonstrations from Step 1.
3. Nothing in this phase changed Docker state — this session had no channel
   capable of changing it (all socket/process/settings writes blocked or
   absent; only reads were performed).

---

## Step 1 — Candidate evaluation

**Nothing was stood up; nothing ran.** Per the phase instructions ("If the
daemon is not reachable, stop"), no Judge0 setup was attempted, no Piston
(or other) service was evaluated, and no plain-Docker runner was executed.
The five demonstrations were **not performed for any candidate**. What
follows is the honest static record: what is known without running, and what
a re-spike must do.

### Pre-checks (ran; both negative)

- No alternate sandbox/container runtime installed: `nsjail`, `firejail`,
  `gvisor-runsc`, `colima`, `podman`, `lima`, `nerdctl` all absent.
- Nothing listening where the candidates would live:
  `http://127.0.0.1:2358/about` (Judge0) and
  `http://127.0.0.1:2000/api/v2/runtimes` (Piston) both → connection refused.

### (a) Judge0 — not attempted

Would-have-been failure point is **unverified**: cgroup, `isolate`,
architecture, or setup friction are all still open. Static knowns (from the
phase brief, not re-verified here — no web access was used):

- Documented as tested only on Linux; recommends Ubuntu 22.04 with cgroup v1
  via GRUB. Docker Desktop for macOS defaults to cgroup v2 with no documented
  switch; `isolate` (Judge0's sandbox) has poor cgroup v2 support.
- Security posture to carry into any future evaluation: self-hosted Judge0
  has a published sandbox escape, and `ALLOW_ENABLE_NETWORK` defaults to true
  in its configuration. A re-spike must set it false and say so.

A re-spike attempt needs: running engine → `docker info` cgroup version →
documented Judge0 quick-start → record the first hard failure (or success)
with logs. Budget-box it: a clear failure is a useful result; do not force it.

### (b) Alternative self-hosted service (Piston-class) — not evaluated

No service was pulled, started, or probed beyond the `:2000` refused check.
A re-spike should pick the most plausible cgroup-v2-tolerant,
arm64-published candidate, verify its image manifest actually ships `arm64`
(no silent QEMU), and run the five demonstrations. If none publishes arm64,
that alone is a finding.

### (c) Plain Docker runner — not run (contract question preserved)

No container was executed, so the flag matrix is entirely unverified on this
machine. A re-spike must test each flag for real
(`--network=none`, `-m`, `--pids-limit`, `--read-only`, non-root user,
host-enforced wall-clock timeout) and then run the five demonstrations.

**Contract question — flagged, not decided** (owner must rule):

- *Argument it is an "existing execution service":* the isolation would come
  from Docker's own primitives (namespaces, cgroups, seccomp, read-only root)
  plus a stock `python:slim` image — no custom ptrace jail, no hand-rolled
  syscall filter, no in-process `exec`. The application would be a thin client
  over a maintained runtime, comparable to calling Judge0 minus the HTTP API.
- *Argument it is a "homemade sandbox":* the security boundary would be a
  project-authored `docker run` invocation and its flag set; every omitted or
  misordered flag is a project bug, and the project owns timeout killing,
  output truncation, image pinning, and container lifecycle. The contract's
  "never build a homemade sandbox" clause exists precisely because that
  ownership is easy to get wrong.

This report proceeds as though the question is **unsettled**: Step 2
describes (c) only to the same depth as the other candidates, and the
recommendation does not assume (c) is permitted.

### Five demonstrations — none executed

| Demonstration | Source in repo | Result |
|---|---|---|
| Reference solution passes its tests | `backend/db/phase_c_coding_bank.py` (e.g. `coding_two_sum`) | DID NOT RUN |
| Mutant fails a hidden test | same bank, `mutant_solution` | DID NOT RUN |
| Infinite loop → timeout fires | (ad-hoc, host timeout) | DID NOT RUN |
| Network open → blocked | (ad-hoc, `--network=none`) | DID NOT RUN |
| Excess allocation → limit holds | (ad-hoc, `-m`) | DID NOT RUN |

No new problems were authored (none were needed — the bank's 15 problems with
reference/mutant pairs stand ready for a re-spike).

---

## Step 2 — What C.2 would require (described, not implemented)

All of this is derived from the current seam, scorer, routes, and schema
without executing anything. Citations are file/line facts, not proposals.

### 2.1 Where it sits

`execute_python_tests` in `backend/execution.py:60-80` is the whole seam:

```python
execute_python_tests(*, source, function, visible_tests, hidden_tests, limits=None)
    -> {"visible": [...], "hidden": [...]}
```

Each per-test outcome carries only
`{"passed": bool, "error": str | None, "stdout": str | None,
"time_ms": float | None}`, with hidden stdout already stripped. C.2 would
replace the `raise ExecutionUnavailableError()` body with a client call and
leave the signature and return shape untouched:

- Against (a)/(b): an HTTP client to the service on `127.0.0.1` (loopback
  only, per working constraints), translating the service's per-submission
  response into the per-test outcome list. Note the bank shape: each problem
  has 3 visible + 5 hidden tests, each test `{"input": {"args": [...]},
  "expected": ...}` — the client must run the candidate `function` against
  each case (8 executions per scored submit, 3 per run) or run one harness
  script that iterates cases inside the sandbox and emits JSON. The latter is
  fewer round-trips but puts the comparison harness inside untrusted-adjacent
  code; either way the comparison semantics (equality against `expected`)
  must be defined once, in the client, not per candidate.
- Against (c): a `docker run` (or Docker Engine API over the Desktop socket)
  invocation per harness execution, with the flags from Step 1(c), a pinned
  image digest, stdin/stdout JSON over a pipe (never a shared volume with
  the candidate able to write it), and a host-side timeout kill.
- `get_execution_status` (`backend/execution.py:83-90`) currently returns
  `available: False` and has no callers in `backend/` or `tests/`. C.2 would
  back it with a real health check (service ping / `docker info`) and wire
  it to an honest UI affordance; until then the frontend only learns
  unavailability from 503s.

### 2.2 Vocabulary mapping

The scorer contract (`modules/scoring/coding.py`, `CANDIDATE_ERRORS =
{"compile", "runtime"}`) fixes the mapping the client must produce:

| Service / runner signal | Outcome `error` | Scorer effect |
|---|---|---|
| `compile()` / import of candidate raises `SyntaxError` (or equivalent pre-run check) | `"compile"` | score capped at 25 |
| Non-zero exit / traceback during a test | `"runtime"` | score capped at 25 |
| Wall-clock kill (host timeout, or service `time` status) | `"timeout"` | ordinary failed test, no cap |
| Ran, returned, value `!= expected` | `"mismatch"` (`passed: False`, `error: "mismatch"`) | ordinary failed test |
| Ran, value `== expected` | `None` (`passed: True`) | pass |

Edge details C.2 must pin down (open, not decided here): whether `compile`
is judged once per submission or per test; `"timeout"` on some-but-not-all
tests (per-test timeout vs whole-harness timeout — the bank's 10^4–10^5
input constraints make whole-harness the sane default); output truncation
counting as pass-with-truncated-stdout (visible only) rather than failure;
and `time_ms` provenance (service-reported vs host-measured).

### 2.3 Where it runs, how it starts, what happens when it is down

- **Where:** on the same machine as the app for local/dev (loopback-only
  service or Desktop socket); production placement is undecided and out of
  scope for this spike.
- **How started:** (a)/(b) a Compose sidecar or a documented
  `docker run -d` with pinned digests, started before the app; (c) no
  long-lived service — the Desktop engine itself is the dependency, plus the
  pinned image present locally. In all cases C.2 needs a startup probe so a
  missing service is detected at boot, not at first submit.
- **When down:** the current behavior is correct and must survive unchanged:
  `POST /session/coding/run` answers 503 without mutating anything
  (`backend/routes/session.py:1699-1710`, visible-only, `hidden_tests=[]`);
  scored submits roll the round back to `in_progress`, record a
  `coding_submissions` row with `status="unavailable"`, and answer 503, with
  retry as a plain resubmit rather than a 409
  (`backend/routes/answer.py:562-588`). `ExecutionUnavailableError` stays
  the boundary exception; C.2 maps connection-refused/timeouts/health-fail
  onto it and never onto a candidate zero. The `/health` surface (F.0
  precedent for scoring mode) could honestly report execution availability,
  but that is additive, not required.

### 2.4 Resource limits

`CodingLimits` (`backend/execution.py:20-30`) already fixes the product
surface: `wall_seconds=5.0`, `memory_mb=256`, `output_bytes=1_000_000`,
`max_requests_per_round=50`. C.2's job is enforcement mapping, not new
numbers:

- **Time:** 5 s wall per execution, host-enforced kill (service-level `cpu`
  limits alone are insufficient — a sleeping or network-blocked candidate
  must still die; with `--network=none` the sleep case is the one that
  matters). The run route (3 tests) and scored submit (8 tests) should share
  one harness execution each where possible so 5 s covers the whole problem.
- **Memory:** 256 MB (`-m 256m` or service equivalent) with swap capped;
  the bank's largest inputs (10^5 small ints) fit comfortably, so OOM during
  tests indicates candidate pathology, which maps to `"runtime"`.
- **Output:** 1 MB cap, truncated host-side even if the service truncates
  (defense in depth; visible stdout is sliced to 4000 chars at
  `session.py:1711-1715` for the run response, but the service-facing cap
  stays 1 MB).
- **Concurrency:** `max_requests_per_round=50` bounds API abuse, not runner
  parallelism. Judge0/Piston bring their own queues; (c) needs an explicit
  host-side semaphore (sized after measuring: 8 GiB host RAM ÷ 256 MB ≈ 32
  absolute ceiling, practical value far lower — 2–4 — given the app, DB, and
  Desktop VM share the same 8 GiB). Unbounded `docker run` per submit is not
  acceptable on this hardware.

### 2.5 Persistence

`coding_submissions` (migration `20260907_0005`) already stores everything
the scorer returns: `status`, `score`, `visible_passed/total`,
`hidden_passed/total`, `error`, plus `source`/`truncated`. Likely **no new
table** is needed. Probable small additions for C.2 to decide (no migration
in this phase): a documented `status` vocabulary extension beyond today's
`"unavailable"` (scored/failed/timeout states as needed by history UI),
optional `time_ms` / `executed_at` columns, and a retention rule for stored
`source`. Hidden per-test detail must never be persisted beyond counts —
the scorer already strips defensively (`modules/scoring/coding.py:104-108`).

### 2.6 Security posture (specific, not reassuring)

- Against (a): inherits Judge0's posture wholesale — including its published
  sandbox escape (unpatched-in-evaluation here) and the
  `ALLOW_ENABLE_NETWORK=true` default, which C.2 must explicitly set false.
  `isolate`'s cgroup-v2 weakness is not just a compatibility risk but a
  containment risk: a sandbox that cannot account processes cannot reliably
  kill or confine them.
- Against (b): depends entirely on which service; Piston-class runners
  typically isolate per-job with cgroups/namespaces inside their own
  containers. The re-spike must record: network default, user (root?),
  filesystem writability, and how timeouts kill (host cgroup kill vs
  in-container signal). None of this is known here.
- Against (c): the boundary would be Docker Desktop's Linux VM plus
  per-container namespaces/cgroups/seccomp, `--network=none`, read-only
  root, non-root user, PID and memory caps, and a host timeout. Residual
  risks to name honestly: container escapes land in the Desktop VM (a
  stronger boundary than the app host, but the VM mounts host directories
  via virtiofs — mount scope must be minimal/none for runner containers);
  fork bombs are contained by the PID limit only if the limit is actually
  verified on Desktop's kernel; and every property above must be re-verified
  after each Desktop upgrade, because the VM kernel is outside the repo's
  control.
- Common to all: candidate code must never execute in the application
  process (the current guarantee — keep it); hidden tests must never reach
  the browser (run route loads visible-only; scored route strips hidden —
  keep both); images/digests must be pinned so a re-pull cannot change the
  runtime under recorded scores.

### 2.7 Effort estimate for C.2 (reasoning visible)

Assumes the engine is running and the re-spike has picked a working
candidate; the re-spike itself is estimated separately.

- **Re-spike (owner or unrestricted session):** ~0.5 day. Engine start,
  `docker info`, one pull, flag matrix, candidates in order, five demos,
  write-up. Mostly waiting on pulls and Judge0's documented setup.
- **C.2 behind (a)/(b):** ~1–2 weeks. Service packaging/pinning, HTTP client
  + harness protocol, vocabulary mapping, health/startup probes,
  `get_execution_status` wiring, concurrency bounds, persistence vocabulary,
  tests (contract tests with a fake executor exist as pattern; live-service
  tests need opt-in markers), and a security review of the chosen service's
  defaults. Judge0-on-macOS risk could consume the range without delivering.
- **C.2 behind (c):** ~2–4 days *if* the owner rules (c) contract-permitted.
  Runner module (pinned digest, flags, timeout kill, JSON protocol),
  mapping, probes, semaphore, tests with a Docker-gated marker, docs. The
  range is narrow because there is no second service to operate — but review
  burden is higher, since the project owns the flag set.
- **AKA the estimate's load-bearing assumption:** all of the above is moot
  until one candidate passes the five demonstrations. Do not schedule C.2
  off this spike's static description.

---

## Step 3 — Recommendation

**Recommend: C.2 stays blocked. Nothing here is sound to build on yet.**

Reasoning: the spike's job was evidence, and the evidence is that no
execution path was exercised at all — not the daemon handshake, not one
container flag, not one candidate, not one demonstration. Recommending (a),
(b), or (c) now would be recommending from documentation and priors, which
is exactly what the spike was meant to replace. The 503 seam, the round-open
retry semantics, and the scorer contract are all in good shape and wait
safely; there is no decay risk in staying blocked.

**Strongest argument against this recommendation:** the machine is closer
than "blocked" sounds. Docker Desktop 4.55.0 is installed, the registry is
reachable, the VM booted cleanly today (and stopped gracefully — nothing is
broken, it is simply off), and the bank's reference/mutant pairs are ready
made for the five demos. An owner at an unrestricted terminal could plausibly
start the engine and work through (a)→(b)→(c) in under an hour, and (c) has
a high prior of working on the first try. "Blocked" here means *this session
produced no evidence*, not *the machine is incapable* — the re-spike is
cheap and should happen soon rather than letting the question rot.

**Owner must decide:**

1. **Re-spike:** start the Desktop engine and re-run the hands-on spike
   (Step 0.4 list) in an unrestricted terminal, or authorize an
   unrestricted-profile session to do it.
2. **Homemade-sandbox question:** if (c) is what works, is a project-owned
   `docker run` flag set an "existing execution service" (permitted) or a
   "homemade sandbox" (forbidden)? See Step 1(c) for both arguments. Do not
   let C.2 start on (c) without a written ruling.
3. **Permanent Docker Desktop dependency:** any of (a)/(b)/(c) makes this
   product require Docker Desktop running alongside the app on every machine
   that scores coding — dev, CI, and production (or a Linux host with a real
   daemon, which re-opens Judge0/cgroup questions). Is that acceptable, or
   should coding execution remain an explicitly unavailable surface?
4. **Judge0 security posture** (if (a) ever passes functionally): accept a
   service with a published sandbox escape and network-on-by-default,
   hardened by configuration — or rule it out now and skip it in the re-spike.

---

## Downloads, disk, cleanup

- Downloaded and retained: **nothing**. No images pulled, no archives
  fetched. The single network probe (`curl -sI
  https://registry-1.docker.io/v2/`, `HTTP/2 401`) stored nothing.
- Containers/images created: **none** (no daemon channel existed).
- Docker state: left as found. This session performed reads only against
  Desktop artifacts; the VM stop at 23:39:42 IST predates and is independent
  of this investigation (first socket probe could not have caused it — EPERM
  means the connect never reached the daemon).
- Application tree: two documentation files changed (this report + a
  `review_guide.md` pointer). No code, no dependencies, no migrations.

## Verification (nothing disturbed)

- Backend: `489 passed, 1 skipped` (`pytest tests/ -q`, 94.64 s).
- Frontend: `55 pass, 0 fail` (`npm test`); `npm run build` ok (`built in 8.21s`).
- `alembic heads` → single head `20260907_0008`.
- `docs/human_baseline_report.md` rewritten by pytest run, restored:
  MD5 `5421f9f0fd6efad395666c545e5cf76a`, 230 lines.
- `git diff --check` clean; `git status --short` clean apart from the two
  intended doc files; all four `refs/rescue/*` still reachable (verified at
  commit time).
- Protected files, guard, and banks untouched (docs-only phase).
