"""Durable, single-host multiprocess admission for the opt-in interview lanes.

Only dispatch metadata is stored. A file lock + fsync/atomic rename protects
reservations across threads/processes. Counts are spent before sending and
never refunded. Live processes retain slots; dead owners are reaped on restart.
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


class BudgetUnavailable(RuntimeError):
    pass


class DispatchDeferred(RuntimeError):
    def __init__(self, reason: str, retry_at: float | None = None):
        super().__init__(f"Interview LLM dispatch stopped: {reason}")
        self.reason = reason
        self.retry_at = retry_at


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
                })
                # Validate persisted counters, never silently recreate a corrupt account.
                for key in ("day", "free_count", "total_count"):
                    if type(account[key]) is not int or account[key] < 0:
                        raise ValueError("invalid counter")
                for key in ("last_seen", "next_content_at", "free_until", "all_until"):
                    if not math.isfinite(account[key]) or account[key] < 0:
                        raise ValueError("invalid time")
                for key in ("leases", "interviews", "models"):
                    if not isinstance(account[key], dict):
                        raise ValueError("invalid map")
                if type(account["credit_block"]) is not bool:
                    raise ValueError("invalid credit block")
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
                    try:
                        os.kill(pid, 0)
                    except ProcessLookupError:
                        del account["leases"][token]
                    except PermissionError:
                        pass  # An uninspectable owner is live; fail closed on capacity.
                yield account, now
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

    def reserve(self, *, interview_id: str, core_count: int, lane: str, model: str, free: bool) -> str:
        if not interview_id or len(interview_id) > 160 or type(core_count) is not int or core_count not in {2, 4}:
            raise BudgetUnavailable("A stable interview identifier and 2/4 core slots are required.")
        if lane not in {"content", "conversation"}:
            raise BudgetUnavailable("Unknown model lane.")
        with self._state() as (state, now):
            interview = state["interviews"].setdefault(interview_id, {"core_count": core_count, "content": 0, "conversation": 0})
            if interview["core_count"] != core_count:
                raise BudgetUnavailable("An existing interview's budget cannot be resized.")
            for key in ("content", "conversation"):
                if type(interview[key]) is not int or interview[key] < 0:
                    raise BudgetUnavailable("Invalid persisted interview counter.")
            if state["credit_block"]:
                raise DispatchDeferred("credits")
            if state["all_until"] > now:
                raise DispatchDeferred("account_backoff", state["all_until"])
            if state["models"].get(model, 0) > now:
                raise DispatchDeferred("model_backoff", state["models"][model])
            if free and (state["free_until"] > now or state["free_count"] >= self.daily_limit):
                raise DispatchDeferred("free_daily", max(state["free_until"], next_utc_day(now)))
            if free and len(state["free_starts"]) >= 20:
                raise DispatchDeferred("free_minute", state["free_starts"][0] + 60)
            cap = 6 * core_count + 1 if lane == "content" else core_count + 2
            if interview[lane] >= cap:
                raise DispatchDeferred(f"{lane}_interview_cap")
            if len(state["leases"]) >= 2:
                raise DispatchDeferred("concurrency", now + 0.25)
            if lane == "content" and state["next_content_at"] > now:
                raise DispatchDeferred("content_pacing", state["next_content_at"])
            token = uuid.uuid4().hex
            state["leases"][token] = {"pid": os.getpid()}
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
            elif decision.kind in {"rpm", "in_flight"}:
                state["all_until"] = max(state["all_until"], decision.retry_at or now + 60)
            elif decision.kind in {"upstream", "model_unavailable"}:
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

    def snapshot(self) -> dict:
        with self._state() as (state, _):
            return json.loads(json.dumps(state))
