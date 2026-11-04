"""Bound authentication attempts by client and account, before password work.

Redis counters are shared across workers. Local development uses bounded,
thread-safe memory counters. A configured Redis outage fails closed instead
of silently removing the shared protection. Forwarded headers are handled by
the server's trusted-proxy configuration, never parsed here.
"""
from __future__ import annotations

import hashlib
import hmac
import logging
import math
import os
from time import monotonic
from functools import lru_cache
from threading import Lock

from fastapi import HTTPException, Request

from backend.config import get_settings

logger = logging.getLogger(__name__)
WINDOW_SECONDS = 300
MAX_LOCAL_KEYS = 10_000
_windows: dict[str, tuple[int, float]] = {}
_lock = Lock()
_INCREMENT = """
local n = redis.call('INCR', KEYS[1])
if n == 1 then redis.call('EXPIRE', KEYS[1], ARGV[1]) end
return {n, redis.call('TTL', KEYS[1])}
"""


@lru_cache(maxsize=4)
def redis_client(url: str):
    from redis import Redis

    return Redis.from_url(url, socket_connect_timeout=2, socket_timeout=2)


def _increment(key: str) -> tuple[int, int]:
    url = (os.getenv("REDIS_URL") or "").strip()
    if url:
        try:
            count, ttl = redis_client(url).eval(_INCREMENT, 1, key, WINDOW_SECONDS)
            return int(count), max(1, int(ttl))
        except Exception as exc:
            logger.warning("Authentication rate limiter unavailable (%s).", type(exc).__name__)
            raise HTTPException(503, "Sign-in is temporarily unavailable. Please try again shortly.") from exc

    now = monotonic()
    with _lock:
        expired = [k for k, (_, until) in _windows.items() if until <= now]
        for old in expired:
            del _windows[old]
        if key not in _windows and len(_windows) >= MAX_LOCAL_KEYS:
            raise HTTPException(503, "Sign-in is temporarily busy. Please try again shortly.")
        count, until = _windows.get(key, (0, now + WINDOW_SECONDS))
        _windows[key] = (count + 1, until)
        return count + 1, max(1, math.ceil(until - now))


def check_auth_rate_limit(request: Request, email: str, *, action: str) -> None:
    client = request.client.host if request.client else "unknown"
    limits = (30, 10) if action == "login" else (10, 5)
    secret = get_settings().jwt_secret_key.encode()
    for dimension, identity, limit in zip(("client", "account"), (client, email), limits):
        digest = hmac.new(secret, identity.encode(), hashlib.sha256).hexdigest()
        count, retry_after = _increment(f"interviv:auth:{action}:{dimension}:{digest}")
        if count > limit:
            raise HTTPException(
                429,
                "Too many attempts. Please wait a few minutes and try again.",
                headers={"Retry-After": str(retry_after)},
            )
