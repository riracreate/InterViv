"""Adzuna HTTPS search client (extends Ticket D jobs explorer).

Credentials stay server-side. Log messages never include app_key or
credential-bearing URLs. Supported country codes are validated; unsupported
countries fail loudly (no silent substitute).
"""
from __future__ import annotations

import logging
import re
import time
from typing import Any
from urllib.parse import urlparse

import httpx

from backend.config import get_settings

LOGGER = logging.getLogger(__name__)


class _AdzunaCredentialFilter(logging.Filter):
    """Keep httpx INFO request logs from exposing credentials in query strings."""

    _secrets = re.compile(r"(?i)([?&](?:app_id|app_key)=)[^&\s\"']*")

    def filter(self, record: logging.LogRecord) -> bool:
        try:
            message = record.getMessage()
            if "api.adzuna.com" in message.lower():
                safe = self._secrets.sub(r"\1[redacted]", message)
                if safe != message:
                    record.msg, record.args = safe, ()
        except Exception:
            # Logging must never reveal the request when it cannot be sanitized.
            record.msg, record.args = "HTTP request details unavailable", ()
        return True


_HTTPX_LOGGER = logging.getLogger("httpx")
if not any(isinstance(item, _AdzunaCredentialFilter) for item in _HTTPX_LOGGER.filters):
    _HTTPX_LOGGER.addFilter(_AdzunaCredentialFilter())

# Adzuna public country path segments (search endpoint). Reject unknowns.
SUPPORTED_COUNTRIES = frozenset({
    "at", "au", "be", "br", "ca", "ch", "de", "es", "fr", "gb", "in", "it",
    "mx", "nl", "nz", "pl", "ru", "sg", "us", "za",
})
DEFAULT_COUNTRY = "in"
MAX_RESULTS = 20
MAX_RETRIES = 2
TIMEOUT_SECONDS = 12.0

ADZUNA_HOST_SUFFIXES = (".adzuna.com", ".adzuna.co.uk", ".adzuna.co.in", ".adzuna.com.au")


class AdzunaClientError(Exception):
    """Provider/config failure distinct from an empty result set."""

    def __init__(self, kind: str, message: str):
        super().__init__(message)
        self.kind = kind  # config|auth|rate_limit|timeout|provider|unsupported_country
        self.message = message


def normalize_country(country: str | None) -> str:
    code = (country or DEFAULT_COUNTRY).strip().lower()
    if code not in SUPPORTED_COUNTRIES:
        raise AdzunaClientError(
            "unsupported_country",
            f"Country '{country}' is not supported by the Adzuna search API. "
            f"Choose one of: {', '.join(sorted(SUPPORTED_COUNTRIES))}.",
        )
    return code


def safe_redirect_url(url: str | None) -> str | None:
    """Allow only http(s) Adzuna redirect hosts; drop javascript/data/etc."""
    raw = (url or "").strip()
    if not raw:
        return None
    try:
        parsed = urlparse(raw)
    except Exception:
        return None
    if parsed.scheme not in ("http", "https"):
        return None
    host = (parsed.hostname or "").lower()
    if not host:
        return None
    if host == "adzuna.com" or any(host.endswith(suf) for suf in ADZUNA_HOST_SUFFIXES):
        return raw
    # Some markets use www.adzuna.<tld>
    if "adzuna." in host:
        return raw
    return None


def _sanitize_text(value: Any, *, limit: int = 2000) -> str:
    text = str(value or "")
    # Strip obvious script tags from snippets before display.
    lowered = text.lower()
    if "<script" in lowered or "javascript:" in lowered:
        text = text.replace("<", "&lt;").replace(">", "&gt;")
    return text[:limit]


def credentials_configured() -> bool:
    settings = get_settings()
    return bool(settings.adzuna_app_id and settings.adzuna_app_key)


def fetch_search(
    *,
    q: str,
    where: str,
    page: int,
    country: str | None = None,
    results_per_page: int = MAX_RESULTS,
) -> dict[str, Any]:
    """Live Adzuna search. Raises AdzunaClientError on failure.

    Returns ``{jobs: list[raw_api_dicts], count, country, page}`` without
    normalizing — callers map through jobs_explorer.
    """
    settings = get_settings()
    if not settings.jobs_live_fetch:
        raise AdzunaClientError(
            "config",
            "Live job search is turned off (JOBS_LIVE_FETCH).",
        )
    app_id = settings.adzuna_app_id
    app_key = settings.adzuna_app_key
    if not app_id or not app_key:
        raise AdzunaClientError(
            "config",
            "Live job search is not configured (ADZUNA_APP_ID / ADZUNA_APP_KEY).",
        )

    country_code = normalize_country(country)
    page = max(1, min(20, int(page or 1)))
    per_page = min(MAX_RESULTS, max(1, int(results_per_page or MAX_RESULTS)))
    # Path only in logs — never append credentials to logged URLs.
    path = f"/v1/api/jobs/{country_code}/search/{page}"
    params = {
        "app_id": app_id,
        "app_key": app_key,
        "results_per_page": per_page,
        "what": (q or "software intern").strip() or "software intern",
        "content-type": "application/json",
    }
    if where and where.strip():
        params["where"] = where.strip()

    last_exc: Exception | None = None
    for attempt in range(MAX_RETRIES + 1):
        try:
            with httpx.Client(timeout=TIMEOUT_SECONDS) as client:
                resp = client.get(
                    f"https://api.adzuna.com{path}",
                    params=params,
                )
            if resp.status_code in (401, 403):
                LOGGER.warning("Adzuna auth rejected for %s (status %s)", path, resp.status_code)
                raise AdzunaClientError(
                    "auth",
                    "Adzuna rejected the API credentials.",
                )
            if resp.status_code == 429:
                LOGGER.warning("Adzuna rate/quota limit for %s", path)
                raise AdzunaClientError(
                    "rate_limit",
                    "Adzuna rate or account quota limit reached. Try again later.",
                )
            if resp.status_code >= 500:
                last_exc = AdzunaClientError(
                    "provider",
                    "Adzuna is temporarily unavailable.",
                )
                if attempt < MAX_RETRIES:
                    time.sleep(0.4 * (attempt + 1))
                    continue
                raise last_exc
            if resp.status_code != 200:
                LOGGER.warning("Adzuna unexpected status %s for %s", resp.status_code, path)
                raise AdzunaClientError(
                    "provider",
                    "Adzuna returned an unexpected response.",
                )
            data = resp.json()
            results = data.get("results") or []
            return {
                "jobs": list(results)[:per_page],
                "count": int(data.get("count") or len(results)),
                "country": country_code,
                "page": page,
            }
        except AdzunaClientError:
            raise
        except httpx.TimeoutException as exc:
            last_exc = AdzunaClientError("timeout", "Adzuna request timed out.")
            LOGGER.warning("Adzuna timeout for %s (attempt %s)", path, attempt + 1)
            if attempt < MAX_RETRIES:
                time.sleep(0.4 * (attempt + 1))
                continue
            raise last_exc from exc
        except httpx.HTTPError as exc:
            last_exc = AdzunaClientError("provider", "Adzuna network error.")
            LOGGER.warning("Adzuna HTTP error for %s: %s", path, type(exc).__name__)
            if attempt < MAX_RETRIES:
                time.sleep(0.4 * (attempt + 1))
                continue
            raise last_exc from exc
        except Exception as exc:
            LOGGER.warning("Adzuna unexpected error for %s: %s", path, type(exc).__name__)
            raise AdzunaClientError("provider", "Adzuna request failed.") from exc

    raise last_exc or AdzunaClientError("provider", "Adzuna request failed.")
