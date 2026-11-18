"""Pure HTTP quota classification. No retries, network, scoring or session writes."""
from __future__ import annotations

import json
import math
import re
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


_DURATION_TOKEN_RE = re.compile(r"(\d+(?:\.\d+)?)\s*(ms|h|m|s)")
_DURATION_MULTIPLIER = {"ms": 0.001, "s": 1.0, "m": 60.0, "h": 3600.0}


def _parse_duration_seconds(raw: str | None) -> float | None:
    text = str(raw or "").strip().lower()
    if not text:
        return None
    try:
        value = float(text)
        return value if math.isfinite(value) and value >= 0 else None
    except ValueError:
        pass
    pos = 0
    total = 0.0
    matched = False
    for m in _DURATION_TOKEN_RE.finditer(text):
        if text[pos:m.start()].strip():
            return None
        total += float(m.group(1)) * _DURATION_MULTIPLIER[m.group(2)]
        pos = m.end()
        matched = True
    if not matched or text[pos:].strip():
        return None
    return total if math.isfinite(total) and total >= 0 else None


def _opt_int(raw: str | None) -> int | None:
    if raw is None:
        return None
    text = str(raw).strip()
    if not text or not text.isascii() or not text.isdigit():
        return None
    return int(text)


def _groq_reset_at(
    *,
    now: float,
    remaining_requests: int | None,
    remaining_tokens: int | None,
    reset_req_s: float | None,
    reset_tok_s: float | None,
) -> float | None:
    candidates: list[float] = []
    if remaining_requests == 0 and reset_req_s is not None:
        candidates.append(reset_req_s)
    if remaining_tokens == 0 and reset_tok_s is not None:
        candidates.append(reset_tok_s)
    if not candidates:
        candidates = [s for s in (reset_req_s, reset_tok_s) if s is not None]
    return max(now, now + max(candidates)) if candidates else None


def parse_ratelimit_headers(headers: Mapping[str, str], now: float) -> dict[str, object]:
    """Parse OpenRouter/Groq rate-limit response headers into numeric limits and reset timestamp."""
    lowered = {str(key).lower(): str(value) for key, value in (headers or {}).items()}
    limit_requests = _opt_int(lowered.get("x-ratelimit-limit-requests"))
    limit_tokens = _opt_int(lowered.get("x-ratelimit-limit-tokens"))
    remaining_requests = _opt_int(lowered.get("x-ratelimit-remaining-requests"))
    remaining_tokens = _opt_int(lowered.get("x-ratelimit-remaining-tokens"))
    reset_req_s = _parse_duration_seconds(lowered.get("x-ratelimit-reset-requests"))
    reset_tok_s = _parse_duration_seconds(lowered.get("x-ratelimit-reset-tokens"))

    reset_at = _reset_time(headers, now)
    if reset_at is None:
        reset_at = _groq_reset_at(
            now=now,
            remaining_requests=remaining_requests,
            remaining_tokens=remaining_tokens,
            reset_req_s=reset_req_s,
            reset_tok_s=reset_tok_s,
        )

    return {
        "limit_requests": limit_requests,
        "limit_tokens": limit_tokens,
        "remaining_requests": remaining_requests,
        "remaining_tokens": remaining_tokens,
        "reset_requests_s": reset_req_s,
        "reset_tokens_s": reset_tok_s,
        "reset_at": reset_at,
    }


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
        if math.isfinite(value):
            return max(now, value)
    except ValueError:
        pass
    return _groq_reset_at(
        now=now,
        remaining_requests=_opt_int(lowered.get("x-ratelimit-remaining-requests")),
        remaining_tokens=_opt_int(lowered.get("x-ratelimit-remaining-tokens")),
        reset_req_s=_parse_duration_seconds(lowered.get("x-ratelimit-reset-requests")),
        reset_tok_s=_parse_duration_seconds(lowered.get("x-ratelimit-reset-tokens")),
    )


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
