"""Public Greenhouse job-board feeds. No API key.

Each board is one company's open roles. Tokens below were checked against
https://boards-api.greenhouse.io/v1/boards/{token}/jobs and returned that
company's postings. A token that 404s, or that belongs to a different
employer, is not included.
"""
from __future__ import annotations

import html
import re
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Callable
from urllib.parse import urlparse

import httpx

# (board token, display name). Do not add a token without checking the feed.
BOARDS: tuple[tuple[str, str], ...] = (
    ("stripe", "Stripe"),
    ("airbnb", "Airbnb"),
    ("discord", "Discord"),
    ("figma", "Figma"),
    ("cloudflare", "Cloudflare"),
    ("databricks", "Databricks"),
    ("gitlab", "GitLab"),
    ("mongodb", "MongoDB"),
    ("twilio", "Twilio"),
    ("dropbox", "Dropbox"),
    ("coinbase", "Coinbase"),
    ("robinhood", "Robinhood"),
    ("instacart", "Instacart"),
    ("pinterest", "Pinterest"),
    ("reddit", "Reddit"),
    ("asana", "Asana"),
    ("brex", "Brex"),
    ("lyft", "Lyft"),
    ("datadog", "Datadog"),
    ("elastic", "Elastic"),
)

PAGE_SIZE = 20
_CACHE_SECONDS = 6 * 3600
_BOARD_CACHE: dict[str, tuple[float, list[dict[str, Any]]]] = {}
_DETAIL_CACHE: dict[tuple[str, str], tuple[float, str]] = {}
_TAG = re.compile(r"(?is)<(script|style)\b.*?>.*?</\1>")
_TAGS = re.compile(r"(?s)<[^>]+>")
_SPACE = re.compile(r"\s+")
_WORD = re.compile(r"[a-z0-9+#.]{3,}")
_STOP = frozenset({"and", "the", "for", "with"})


def safe_greenhouse_url(url: str | None) -> str | None:
    """HTTPS job links from a Greenhouse board, including company career domains."""
    raw = (url or "").strip()
    if not raw:
        return None
    try:
        parsed = urlparse(raw)
    except Exception:
        return None
    if parsed.scheme != "https" or parsed.username or parsed.password:
        return None
    host = (parsed.hostname or "").lower().rstrip(".")
    if not host or host == "localhost" or host.endswith(".local"):
        return None
    return raw


def html_to_text(value: str | None, *, limit: int = 500) -> str:
    text = html.unescape(html.unescape(value or ""))
    text = _TAG.sub(" ", text)
    text = _TAGS.sub(" ", text)
    text = _SPACE.sub(" ", text).strip()
    return text[:limit]


def keywords(query: str) -> list[str]:
    words: list[str] = []
    for part in re.split(r"\bOR\b|,", query or "", flags=re.IGNORECASE):
        for word in _WORD.findall(part.lower()):
            if word not in _STOP and word not in words:
                words.append(word)
    return words


def _matches_keywords(job: dict[str, Any], words: list[str]) -> bool:
    if not words:
        return True
    hay = " ".join(
        str(job.get(field) or "")
        for field in ("title", "company", "location", "snippet")
    ).lower()
    return any(word in hay for word in words)


def filter_jobs(
    jobs: list[dict[str, Any]], *, q: str, where: str
) -> tuple[list[dict[str, Any]], str | None]:
    """Keyword filter, then location when that city appears on a board."""
    words = keywords(q)
    matched = [job for job in jobs if _matches_keywords(job, words)]
    place = (where or "").strip()
    if not place:
        return matched, None
    located = [
        job
        for job in matched
        if place.lower() in str(job.get("location") or "").lower()
    ]
    if located:
        return located, None
    if matched:
        return matched, (
            f"No Greenhouse board listings in {place}. "
            "Showing keyword matches from the public boards."
        )
    return [], None


def listing_from_api(raw: dict[str, Any], company: str, token: str) -> dict[str, Any] | None:
    external_id = str(raw.get("id") or "").strip()
    title = str(raw.get("title") or "").strip()
    if not external_id or not title:
        return None
    location = raw.get("location")
    if isinstance(location, dict):
        location = location.get("name") or ""
    redirect = safe_greenhouse_url(str(raw.get("absolute_url") or "")) or ""
    snippet = html_to_text(raw.get("content"))
    return {
        "token": token,
        "company": company,
        "external_id": external_id,
        "title": title,
        "location": str(location or ""),
        "redirect_url": redirect,
        "snippet": snippet,
        "updated_at": raw.get("updated_at"),
    }


def _get_json(url: str) -> dict[str, Any]:
    with httpx.Client(timeout=12.0) as client:
        response = client.get(url, headers={"Accept": "application/json"})
        response.raise_for_status()
        data = response.json()
    return data if isinstance(data, dict) else {}


def _board_jobs(token: str, company: str) -> list[dict[str, Any]]:
    now = time.time()
    cached = _BOARD_CACHE.get(token)
    if cached and now - cached[0] < _CACHE_SECONDS:
        return cached[1]
    try:
        payload = _get_json(f"https://boards-api.greenhouse.io/v1/boards/{token}/jobs")
    except (httpx.HTTPError, ValueError):
        return cached[1] if cached else []
    jobs = []
    for raw in payload.get("jobs") or []:
        if isinstance(raw, dict):
            item = listing_from_api(raw, company, token)
            if item:
                jobs.append(item)
    _BOARD_CACHE[token] = (now, jobs)
    return jobs


def _detail_text(token: str, external_id: str) -> str:
    key = (token, external_id)
    now = time.time()
    cached = _DETAIL_CACHE.get(key)
    if cached and now - cached[0] < _CACHE_SECONDS:
        return cached[1]
    try:
        payload = _get_json(
            f"https://boards-api.greenhouse.io/v1/boards/{token}/jobs/{external_id}"
        )
    except (httpx.HTTPError, ValueError):
        return cached[1] if cached else ""
    text = html_to_text(payload.get("content"))
    _DETAIL_CACHE[key] = (now, text)
    return text


def load_board_jobs(
    fetch_board: Callable[[str, str], list[dict[str, Any]]] | None = None,
) -> list[dict[str, Any]]:
    loader = fetch_board or _board_jobs
    found: list[dict[str, Any]] = []
    with ThreadPoolExecutor(max_workers=8) as pool:
        for batch in pool.map(lambda board: loader(board[0], board[1]), BOARDS):
            found.extend(batch or [])
    return found


def attach_descriptions(
    jobs: list[dict[str, Any]],
    fetch_detail: Callable[[str, str], str] | None = None,
) -> list[dict[str, Any]]:
    loader = fetch_detail or _detail_text
    missing = [job for job in jobs if not job.get("snippet")]
    if not missing:
        return jobs
    texts: list[str] = []
    with ThreadPoolExecutor(max_workers=8) as pool:
        texts = list(
            pool.map(lambda job: loader(job["token"], job["external_id"]), missing)
        )
    by_id = {
        (job["token"], job["external_id"]): text
        for job, text in zip(missing, texts)
        if text
    }
    filled = []
    for job in jobs:
        if job.get("snippet"):
            filled.append(job)
            continue
        text = by_id.get((job["token"], job["external_id"])) or ""
        filled.append({**job, "snippet": text})
    return filled
