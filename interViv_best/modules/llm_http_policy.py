"""Pure HTTP quota classification. No retries, network, scoring or session writes."""
from __future__ import annotations

import json
import math
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from typing import Mapping


@dataclass(frozen=True)
class LimitDecision:
    kind: str
    retry_at: float | None = None


def next_utc_day(now: float) -> float:
    date = datetime.fromtimestamp(now, timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    return (date + timedelta(days=1)).timestamp()


def _reset_time(headers: Mapping[str, str], now: float) -> float | None:
    lowered = {key.lower(): str(value) for key, value in headers.items()}
    retry = lowered.get("retry-after")
    if retry:
        try:
            value = now + max(0.0, float(retry))
        except ValueError:
            try:
                date = parsedate_to_datetime(retry)
                value = date.replace(tzinfo=date.tzinfo or timezone.utc).timestamp()
            except (ValueError, TypeError, OverflowError):
                value = float("nan")
        if math.isfinite(value):
            return max(now, value)
    try:
        value = float(lowered.get("x-ratelimit-reset", "nan"))
        if value > 10_000_000_000:  # OpenRouter also returns epoch milliseconds.
            value /= 1000
        return max(now, value) if math.isfinite(value) else None
    except ValueError:
        return None


def classify_http_error(status: int, body: bytes | str, headers: Mapping[str, str], *, now: float,
                        lane: str = "content") -> LimitDecision:
    """Prefer structured limit_source; recognize older body-only responses too.

    A 402 is not always permanent, and a 429 is not always transient. Unknown
    quota responses stop dispatch; callers never infer permission from a status.
    Raw error text is used only here, never persisted in the budget journal.
    """
    text = body.decode("utf-8", errors="replace") if isinstance(body, bytes) else body
    try:
        data = json.loads(text)
    except (ValueError, TypeError):
        data = {}
    error = data.get("error", {}) if isinstance(data, dict) else {}
    metadata = error.get("metadata", {}) if isinstance(error, dict) else {}
    source = str(metadata.get("limit_source", "")) if isinstance(metadata, dict) else ""
    evidence = (source + " " + str(error) + " " + text).casefold()
    reset = _reset_time(headers, now)
    if status in {401, 403}:
        return LimitDecision("authorization")
    if status in {400, 422}:
        return LimitDecision("model_unavailable" if lane == "content" else "request_rejected", now + 300)
    if status == 408 or 500 <= status <= 599:
        return LimitDecision("model_unavailable", reset or now + 300)
    if status in {402, 429}:
        if any(word in evidence for word in ("free_tier_daily", "daily limit", "daily quota", "per day", "per-day")):
            return LimitDecision("free_daily", max(next_utc_day(now), reset or 0))
        if any(word in evidence for word in ("in_flight_budget", "in-flight budget")):
            return LimitDecision("in_flight", reset or now + 4)
        if any(word in evidence for word in ("free_tier_per_minute", "per minute", "per-minute", "requests/min")):
            return LimitDecision("rpm", reset or now + 60)
        if "upstream_provider_shared_pool" in evidence or "temporarily rate-limited upstream" in evidence:
            return LimitDecision("upstream", reset or now + 4)
        if status == 402 or any(word in evidence for word in ("openrouter_key_limit", "openrouter_credits", "insufficient credit", "out of credits")):
            return LimitDecision("credits")
        if reset is not None:
            return LimitDecision("rpm", reset)
        return LimitDecision("unknown_quota")
    if status == 404:
        return LimitDecision("model_unavailable", reset or now + 300)
    return LimitDecision("http_error")
