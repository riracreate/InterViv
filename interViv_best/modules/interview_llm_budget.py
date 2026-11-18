"""Durable, single-host multiprocess admission for the opt-in interview lanes.

Only dispatch metadata is stored. A file lock + fsync/atomic rename protects
reservations across threads/processes. Counts are spent before sending and
never refunded. Leases outlive request timeouts; dead/expired owners are reaped.
Sharing this journal across different hosts is refused (not a distributed lock).
"""
from __future__ import annotations

import json
import math
import os
import socket
import tempfile
import time
import uuid
from contextlib import contextmanager
from pathlib import Path

from modules.llm_http_policy import LimitDecision, next_utc_day

LEASE_MIN_SECONDS = 120
LEASE_GRACE_SECONDS = 60


class BudgetUnavailable(RuntimeError):
    pass


class DispatchDeferred(RuntimeError):
    def __init__(self, reason: str, retry_at: float | None = None, *, reasoning_tokens: int | None = None):
        super().__init__(f"Interview LLM dispatch stopped: {reason}")
        self.reason = reason
        self.retry_at = retry_at
        self.reasoning_tokens = reasoning_tokens


class RequestBudget:
    def __init__(self, path: Path, *, account: str = "default", high_free_limit: bool = False, clock=time.time):
        self.path = Path(path).expanduser().resolve()
        if self.path.suffix != ".json":
            raise BudgetUnavailable("The metadata journal must be a .json file, never a database.")
        if not account or len(account) > 80:
            raise BudgetUnavailable("Use a non-secret account quota label of 1–80 characters.")
        self.account = account
        self.daily_limit = 1000 if high_free_limit else 50
        self.clock = clock

    @contextmanager
    def _state(self):
        try:
            import fcntl
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with self.path.with_suffix(".lock").open("a") as lock:
                fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
                if self.path.exists():
                    state = json.loads(self.path.read_text())
                    if state["version"] != 1 or state["host"] != socket.gethostname():
                        raise ValueError("journal version/host mismatch")
                    accounts = state["accounts"]
                    if not isinstance(accounts, dict):
                        raise ValueError("invalid accounts")
                else:
                    state = {"version": 1, "host": socket.gethostname(), "accounts": {}}
                now = float(self.clock())
                if not math.isfinite(now) or now < 0:
                    raise ValueError("invalid clock")
                account = state["accounts"].setdefault(self.account, {
                    "last_seen": now, "day": int(now // 86400), "free_count": 0,
                    "total_count": 0, "free_starts": [], "next_content_at": 0,
                    "leases": {}, "interviews": {}, "free_until": 0,
                    "all_until": 0, "credit_block": False, "models": {},
                    "operator_block": None, "batches": {}, "closed_interviews": {},
                })
                # Backward-compatible metadata additions; no counter is reset.
                account.setdefault("operator_block", None)
                account.setdefault("batches", {})
                account.setdefault("closed_interviews", {})
                # Validate persisted counters, never silently recreate a corrupt account.
                for key in ("day", "free_count", "total_count"):
                    if type(account[key]) is not int or account[key] < 0:
                        raise ValueError("invalid counter")
                for key in ("last_seen", "next_content_at", "free_until", "all_until"):
                    if not math.isfinite(account[key]) or account[key] < 0:
                        raise ValueError("invalid time")
                for key in ("leases", "interviews", "models", "batches", "closed_interviews"):
                    if not isinstance(account[key], dict):
                        raise ValueError("invalid map")
                if type(account["credit_block"]) is not bool:
                    raise ValueError("invalid credit block")
                if account["operator_block"] not in {None, "authorization"}:
                    raise ValueError("invalid operator block")
                if not isinstance(account["free_starts"], list) or any(
                    not isinstance(t, (int, float)) or not math.isfinite(t) for t in account["free_starts"]
                ):
                    raise ValueError("invalid request window")
                now = max(now, account["last_seen"])  # clock rollback cannot reset a quota
                account["last_seen"] = now
                if int(now // 86400) > account["day"]:
                    account["day"], account["free_count"] = int(now // 86400), 0
                account["free_starts"] = [t for t in account["free_starts"] if t > now - 60]
                for token, lease in list(account["leases"].items()):
                    pid = lease["pid"]
                    if type(pid) is not int or pid <= 0:
                        raise ValueError("invalid lease owner")
                    started = lease.setdefault("started_at", now)
                    expires = lease.setdefault("expires_at", started + LEASE_MIN_SECONDS)
                    if not all(isinstance(t, (int, float)) and math.isfinite(t) for t in (started, expires)) or expires <= started:
                        raise ValueError("invalid lease deadline")
                    if expires <= now:
                        del account["leases"][token]
                        continue
                    try:
                        os.kill(pid, 0)
                    except ProcessLookupError:
                        del account["leases"][token]
                    except PermissionError:
                        pass  # An uninspectable owner is live; fail closed on capacity.
                self._prune_finished_interviews(account)
                yield account, now
                self._prune_finished_interviews(account)
                with tempfile.NamedTemporaryFile(mode="w", dir=self.path.parent, delete=False) as output:
                    temporary = Path(output.name)
                    try:
                        json.dump(state, output, allow_nan=False, sort_keys=True)
                        output.flush()
                        os.fsync(output.fileno())
                        os.replace(temporary, self.path)
                    finally:
                        temporary.unlink(missing_ok=True)
                directory = os.open(self.path.parent, os.O_RDONLY)
                try:
                    os.fsync(directory)
                finally:
                    os.close(directory)
        except (OSError, ValueError, KeyError, TypeError, ImportError) as exc:
            raise BudgetUnavailable("Interview LLM journal unavailable; no dispatch permitted.") from exc

    @staticmethod
    def _prune_finished_interviews(state: dict) -> None:
        # Compact closed-ID tombstones prevent a pruned ID from getting a fresh
        # allowance. Detailed counters leave the active journal once leases end.
        leases = state["leases"].values()
        for identity, interview in list(state["interviews"].items()):
            if interview.get("finished_at") is None:
                continue
            if any(lease.get("scope_id") in {None, identity} for lease in leases):
                continue
            state["closed_interviews"][identity] = interview["finished_at"]
            del state["interviews"][identity]

    def reserve(self, *, interview_id: str, core_count: int, lane: str, model: str, free: bool,
                timeout_s: float = 45) -> str:
        if not interview_id or len(interview_id) > 160 or type(core_count) is not int or core_count not in {2, 4}:
            raise BudgetUnavailable("A stable interview identifier and 2/4 core slots are required.")
        if lane not in {"content", "conversation"}:
            raise BudgetUnavailable("Unknown model lane.")
        cap = 6 * core_count + 1 if lane == "content" else core_count + 2
        return self._reserve_scope(kind="interviews", identity=interview_id, fixed_key="core_count",
                                   fixed_value=core_count, lane=lane, cap=cap, model=model, free=free, timeout_s=timeout_s)

    def reserve_batch(self, *, batch_id: str, max_requests: int, lane: str, model: str, free: bool,
                      timeout_s: float = 45) -> str:
        if not batch_id or len(batch_id) > 160 or type(max_requests) is not int or max_requests < 1:
            raise BudgetUnavailable("A batch ID and positive explicit max_requests are required.")
        if lane != "content":
            raise BudgetUnavailable("Batch scope is content-only.")
        return self._reserve_scope(kind="batches", identity=batch_id, fixed_key="max_requests",
                                   fixed_value=max_requests, lane=lane, cap=max_requests,
                                   model=model, free=free, timeout_s=timeout_s)

    def _reserve_scope(self, *, kind, identity, fixed_key, fixed_value, lane, cap, model, free, timeout_s):
        if not isinstance(timeout_s, (int, float)) or isinstance(timeout_s, bool) or not math.isfinite(timeout_s) or timeout_s <= 0:
            raise BudgetUnavailable("A finite positive request timeout is required.")
        with self._state() as (state, now):
            if kind == "interviews" and identity in state["closed_interviews"]:
                raise DispatchDeferred("interview_finished")
            interview = state[kind].setdefault(identity, {fixed_key: fixed_value, "content": 0, "conversation": 0})
            if interview[fixed_key] != fixed_value:
                raise BudgetUnavailable("An existing interview or batch budget cannot be resized.")
            if interview.get("finished_at") is not None:
                raise DispatchDeferred("interview_finished")
            for key in ("content", "conversation"):
                if type(interview[key]) is not int or interview[key] < 0:
                    raise BudgetUnavailable("Invalid persisted interview counter.")
            if state["credit_block"]:
                raise DispatchDeferred("credits")
            if state["operator_block"]:
                raise DispatchDeferred(state["operator_block"])
            if state["all_until"] > now:
                raise DispatchDeferred("account_backoff", state["all_until"])
            if state["models"].get(model, 0) > now:
                raise DispatchDeferred("model_backoff", state["models"][model])
            if free and (state["free_until"] > now or state["free_count"] >= self.daily_limit):
                raise DispatchDeferred("free_daily", max(state["free_until"], next_utc_day(now)))
            if free and len(state["free_starts"]) >= 20:
                raise DispatchDeferred("free_minute", state["free_starts"][0] + 60)
            if interview[lane] >= cap:
                raise DispatchDeferred(f"{lane}_{'batch' if kind == 'batches' else 'interview'}_cap")
            if len(state["leases"]) >= 2:
                raise DispatchDeferred("concurrency", now + 0.25)
            if lane == "content" and state["next_content_at"] > now:
                raise DispatchDeferred("content_pacing", state["next_content_at"])
            token = uuid.uuid4().hex
            expires = now + max(LEASE_MIN_SECONDS, timeout_s + LEASE_GRACE_SECONDS)
            if not math.isfinite(expires):
                raise BudgetUnavailable("Invalid lease deadline.")
            state["leases"][token] = {"pid": os.getpid(), "started_at": now, "expires_at": expires,
                                      "scope_id": identity, "scope_kind": kind}
            interview[lane] += 1
            state["total_count"] += 1
            if free:
                state["free_count"] += 1
                state["free_starts"].append(now)
            if lane == "content":
                state["next_content_at"] = now + 4
            return token

    def release(self, token: str) -> None:
        with self._state() as (state, _):
            state["leases"].pop(token, None)

    def record_failure(self, model: str, decision: LimitDecision, *, free: bool) -> None:
        with self._state() as (state, now):
            if decision.kind == "free_daily":
                state["free_until"] = max(state["free_until"], decision.retry_at or next_utc_day(now))
            elif decision.kind == "credits":
                state["credit_block"] = True
            elif decision.kind == "authorization":
                state["operator_block"] = "authorization"
            elif decision.kind in {"rpm", "in_flight", "timeout", "network_unavailable"}:
                state["all_until"] = max(state["all_until"], decision.retry_at or now + 60)
            elif decision.kind in {"upstream", "model_unavailable", "request_rejected", "provider_error",
                                   "invalid_response", "empty_response", "truncated"}:
                state["models"][model] = decision.retry_at or now + 300
            elif decision.kind == "unknown_quota":
                if free:
                    state["free_until"] = next_utc_day(now)
                else:
                    state["credit_block"] = True

    def clear_credit_block(self) -> None:
        """Explicit operator action after fixing credits; does not refund counters."""
        with self._state() as (state, _):
            state["credit_block"] = False

    def clear_access_block(self) -> None:
        """Explicit operator action after correcting credentials/access policy."""
        with self._state() as (state, _):
            state["operator_block"] = None

    def finish_interview(self, interview_id: str) -> None:
        """Close an interview and prune its counters after outstanding leases end."""
        with self._state() as (state, now):
            if interview_id in state["interviews"]:
                state["interviews"][interview_id]["finished_at"] = now

    def inspect(self) -> dict:
        """Read-only status: no file creation, clock reset, lease pruning or write."""
        status = {"journal": str(self.path), "account": self.account, "exists": self.path.exists(),
                  "free_daily_limit": self.daily_limit, "free_per_minute_limit": 20, "concurrency_limit": 2,
                  "state": None}
        if not status["exists"]:
            return status
        try:
            state = json.loads(self.path.read_text())
            if state["version"] != 1 or state["host"] != socket.gethostname() or not isinstance(state["accounts"], dict):
                raise ValueError("invalid journal")
            status["state"] = state["accounts"].get(self.account)
            return status
        except (OSError, ValueError, KeyError, TypeError) as exc:
            raise BudgetUnavailable("Journal inspection failed; nothing was changed.") from exc

    def snapshot(self) -> dict:
        with self._state() as (state, _):
            return json.loads(json.dumps(state))
