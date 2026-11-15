"""Job explorer — Adzuna search + cache + lexicon skill overlay.

No scrapers. No LLM JD parse. View job = validated redirect_url only.
Practice handoff proposes a builder draft; it does not invent company
questions or bypass inventory validation.
"""

from __future__ import annotations

import hashlib
import json
import logging
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable

from backend.config import get_settings
from modules.adzuna_client import (
    DEFAULT_COUNTRY,
    AdzunaClientError,
    credentials_configured,
    fetch_search,
    normalize_country,
    safe_redirect_url,
    _sanitize_text,
)
from modules.greenhouse_client import (
    PAGE_SIZE as GREENHOUSE_PAGE_SIZE,
    attach_descriptions,
    filter_jobs,
    load_board_jobs,
    safe_greenhouse_url,
)
from modules.resume_parser import extract_skills_from_text

LOGGER = logging.getLogger(__name__)

PROVIDER_ADZUNA = "adzuna"
PROVIDER_GREENHOUSE = "greenhouse"
ROOT = Path(__file__).resolve().parents[1]
FIXTURE_PATH = ROOT / "data" / "jobs_fixture_adzuna.json"
GREENHOUSE_FIXTURE_PATH = ROOT / "data" / "jobs_fixture_greenhouse.json"
GREENHOUSE_SAMPLE_DISCLAIMER = (
    "Sample listings for offline practice: fictional companies, not real openings. "
    "Start the app with --live-jobs for live Greenhouse boards."
)


def load_greenhouse_sample_jobs() -> list[dict[str, Any]]:
    """Offline Greenhouse-shaped sample listings (no network)."""
    data = json.loads(GREENHOUSE_FIXTURE_PATH.read_text(encoding="utf-8"))
    return [dict(row) for row in data.get("jobs") or []]

CACHE_TTL_DEFAULT = 6 * 3600
MAX_RESULTS = 20
MAX_PRACTICE_SKILLS = 5

MCQ_ABLE = frozenset(
    {
        "DBMS",
        "DSA",
        "OOP",
        "Operating Systems",
        "Computer Networks",
        "Python",
        "System Design",
        "Machine Learning",
        "SQL",
    }
)

# query_hash -> {fetched_at, jobs: list[dict]}
_SEARCH_MEMORY: dict[str, dict[str, Any]] = {}
# (provider, external_id) -> job card dict
_JOB_MEMORY: dict[tuple[str, str], dict[str, Any]] = {}
# user_id -> list[timestamps]
_RATE: dict[str, list[float]] = {}

# Injected for tests
_FETCH_OVERRIDE: Callable[..., list[dict[str, Any]]] | None = None
_FETCH_ERROR_OVERRIDE: AdzunaClientError | None = None


def reset_memory_store() -> None:
    _SEARCH_MEMORY.clear()
    _JOB_MEMORY.clear()
    _RATE.clear()


def set_fetch_override(fn: Callable[..., list[dict[str, Any]]] | None) -> None:
    global _FETCH_OVERRIDE, _FETCH_ERROR_OVERRIDE
    _FETCH_OVERRIDE = fn
    if fn is not None:
        _FETCH_ERROR_OVERRIDE = None


def set_fetch_error_override(err: AdzunaClientError | None) -> None:
    global _FETCH_ERROR_OVERRIDE, _FETCH_OVERRIDE
    _FETCH_ERROR_OVERRIDE = err
    if err is not None:
        _FETCH_OVERRIDE = None


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _as_utc(dt: datetime) -> datetime:
    """SQLite often returns naive datetimes; compare only in UTC-aware form."""
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _using_sql() -> bool:
    return bool(get_settings().database_url)


def query_hash(q: str, where: str, page: int, country: str = DEFAULT_COUNTRY) -> str:
    raw = (
        f"{(country or DEFAULT_COUNTRY).strip().lower()}|"
        f"{(q or '').strip().lower()}|{(where or '').strip().lower()}|{int(page)}"
    )
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def rate_limit_ok(user_id: str) -> bool:
    settings = get_settings()
    limit = max(1, int(settings.jobs_rate_limit_per_minute or 30))
    now = time.time()
    bucket = _RATE.setdefault(str(user_id), [])
    _RATE[str(user_id)] = [t for t in bucket if now - t < 60.0]
    if len(_RATE[str(user_id)]) >= limit:
        return False
    _RATE[str(user_id)].append(now)
    return True


def load_fixture_jobs() -> list[dict[str, Any]]:
    rows = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    return [_normalize_adzuna_item(r, from_fixture=True) for r in rows]


def _normalize_adzuna_item(raw: dict[str, Any], *, from_fixture: bool = False) -> dict[str, Any]:
    salary_is_predicted = raw.get("salary_is_predicted")
    if from_fixture or (
        "redirect_url" in raw and "company" in raw and isinstance(raw.get("company"), str)
    ):
        company = raw.get("company") or ""
        location = raw.get("location") or ""
        external_id = str(raw.get("id") or "")
        title = str(raw.get("title") or "")
        snippet = _sanitize_text(raw.get("description") or "")
        redirect = safe_redirect_url(str(raw.get("redirect_url") or "")) or ""
        created = raw.get("created")
        salary_min = raw.get("salary_min")
        salary_max = raw.get("salary_max")
        if salary_is_predicted is None:
            salary_is_predicted = raw.get("salary_predicted")
    else:
        # Live Adzuna shape
        external_id = str(raw.get("id") or "")
        title = str(raw.get("title") or "")
        company = str((raw.get("company") or {}).get("display_name") or "")
        location = str((raw.get("location") or {}).get("display_name") or "")
        snippet = _sanitize_text(raw.get("description") or "")
        redirect = safe_redirect_url(str(raw.get("redirect_url") or "")) or ""
        created = raw.get("created")
        salary_min = raw.get("salary_min")
        salary_max = raw.get("salary_max")

    if salary_is_predicted in (0, "0", False):
        salary_is_predicted = False
    elif salary_is_predicted in (1, "1", True):
        salary_is_predicted = True
    else:
        salary_is_predicted = None

    text_for_skills = f"{title}\n{snippet}"
    skills = extract_skills_from_text(text_for_skills)
    return {
        "id": f"{PROVIDER_ADZUNA}:{external_id}",
        "provider": PROVIDER_ADZUNA,
        "external_id": external_id,
        "title": title,
        "company": company,
        "location": location,
        "created": created,
        "salary_min": salary_min,
        "salary_max": salary_max,
        "salary_is_predicted": salary_is_predicted,
        "salary_currency": raw.get("salary_currency") or None,
        "snippet": snippet,
        "redirect_url": redirect,
        "skills": skills,
        "payload": {
            "title": title,
            "company": company,
            "location": location,
            "created": created,
            "salary_min": salary_min,
            "salary_max": salary_max,
            "salary_is_predicted": salary_is_predicted,
            "description": snippet,
            "redirect_url": redirect,
            "id": external_id,
        },
    }


def fetch_adzuna(
    *,
    q: str,
    where: str,
    page: int,
    country: str | None = None,
    results_per_page: int = MAX_RESULTS,
) -> tuple[list[dict[str, Any]], str]:
    """Return (jobs, provenance). Raises AdzunaClientError on live failures.

    Empty live results are ``([], \"live\")``, not an error. Offline default
    serves fixtures with provenance ``fixture``.
    """
    if _FETCH_ERROR_OVERRIDE is not None:
        raise _FETCH_ERROR_OVERRIDE
    if _FETCH_OVERRIDE is not None:
        raw_jobs = _FETCH_OVERRIDE(q=q, where=where, page=page, country=country)
        normalized = []
        for item in raw_jobs or []:
            if isinstance(item, dict) and item.get("provider") == PROVIDER_ADZUNA:
                normalized.append(item)
            else:
                normalized.append(_normalize_adzuna_item(item, from_fixture=True))
        return normalized, "override"

    settings = get_settings()
    country_code = normalize_country(country)

    if not settings.jobs_live_fetch:
        return load_fixture_jobs()[:results_per_page], "fixture"

    if not credentials_configured():
        raise AdzunaClientError(
            "config",
            "Live job search is not configured (ADZUNA_APP_ID / ADZUNA_APP_KEY).",
        )

    payload = fetch_search(
        q=q,
        where=where,
        page=page,
        country=country_code,
        results_per_page=results_per_page,
    )
    jobs = [_normalize_adzuna_item(item) for item in payload.get("jobs") or []]
    return jobs, "live"


def _cache_ttl() -> timedelta:
    return timedelta(seconds=max(60, int(get_settings().jobs_cache_ttl_seconds or CACHE_TTL_DEFAULT)))


def _stamp_provenance(
    jobs: list[dict[str, Any]],
    *,
    provenance: str,
    fetched_at: datetime,
) -> list[dict[str, Any]]:
    """Attach provenance + fetch time so cache hits keep honesty labels."""
    iso = fetched_at.isoformat()
    stamped: list[dict[str, Any]] = []
    for job in jobs:
        card = dict(job)
        card["provenance"] = provenance
        card["fetched_at"] = fetched_at
        card["fetched_at_iso"] = iso
        stamped.append(card)
    return stamped


def _sample_empty_reason(provenance: str) -> str | None:
    if provenance != "fixture":
        return None
    settings = get_settings()
    if not settings.jobs_live_fetch:
        LOGGER.info(
            "Jobs serving sample listings because live fetch is gated off "
            "(JOBS_LIVE_FETCH=%s)",
            "0" if not settings.jobs_live_fetch else "1",
        )
        return (
            "Live job search is turned off. The listings below are sample data "
            "for practice, not live openings."
        )
    LOGGER.info(
        "Jobs serving sample listings because Adzuna credentials are unset"
    )
    return (
        "Live job search is not configured. The listings below are sample data "
        "for practice, not live openings."
    )


def get_cached_search(
    q: str, where: str, page: int, country: str = DEFAULT_COUNTRY
) -> dict[str, Any] | None:
    """Return ``{jobs, fetched_at, provenance}`` or None on miss/expiry."""
    key = query_hash(q, where, page, country)
    if _using_sql():
        return _get_search_sql(key)
    entry = _SEARCH_MEMORY.get(key)
    if not entry:
        return None
    fetched_at = _as_utc(entry["fetched_at"])
    if _now() - fetched_at > _cache_ttl():
        return None
    return {
        "jobs": list(entry["jobs"]),
        "fetched_at": fetched_at,
        "provenance": entry.get("provenance") or _provenance_from_jobs(entry["jobs"]),
    }


def _provenance_from_jobs(jobs: list[dict[str, Any]]) -> str:
    for job in jobs or []:
        prov = job.get("provenance")
        if prov:
            return str(prov)
    # Conservative: unlabeled historical cache rows are treated as sample.
    return "fixture"


def put_cached_search(
    q: str,
    where: str,
    page: int,
    jobs: list[dict[str, Any]],
    *,
    provenance: str,
    country: str = DEFAULT_COUNTRY,
) -> None:
    key = query_hash(q, where, page, country)
    fetched = _now()
    stamped = _stamp_provenance(jobs, provenance=provenance, fetched_at=fetched)
    for job in stamped:
        _upsert_job(job, fetched_at=fetched)
    if _using_sql():
        _put_search_sql(key, page, stamped, fetched, provenance=provenance)
        return
    _SEARCH_MEMORY[key] = {
        "fetched_at": fetched,
        "jobs": list(stamped),
        "provenance": provenance,
    }

def _upsert_job(job: dict[str, Any], *, fetched_at: datetime) -> None:
    key = (job["provider"], job["external_id"])
    stored = {**job, "fetched_at": fetched_at}
    _JOB_MEMORY[key] = stored
    if _using_sql():
        _upsert_job_sql(stored)


def get_job(job_id: str) -> dict[str, Any] | None:
    # id format provider:external_id
    if ":" not in job_id:
        return None
    provider, external_id = job_id.split(":", 1)
    key = (provider, external_id)
    if key in _JOB_MEMORY:
        return dict(_JOB_MEMORY[key])
    if _using_sql():
        return _get_job_sql(provider, external_id)
    # Fall back to fixture
    for job in load_fixture_jobs():
        if job["external_id"] == external_id:
            _JOB_MEMORY[key] = job
            return dict(job)
    return None


def match_pct(job_skills: list[str], user_skills: list[str] | None) -> float | None:
    if not job_skills:
        return None
    if not user_skills:
        return None
    job_set = {s.lower() for s in job_skills}
    user_set = {s.lower() for s in user_skills}
    if not job_set:
        return None
    hit = len(job_set & user_set)
    return round(100.0 * hit / len(job_set), 1)


def user_skills_for_overlay(user_id: str) -> list[str] | None:
    """Resume skills if present; else skill-graph skills with any attempts; else None."""
    from backend.db import get_database

    db = get_database()
    candidate = db["candidates"].find_one({"user_id": user_id})
    if candidate:
        skills = list(candidate.get("resume_skills") or [])
        if skills:
            return skills
    try:
        from modules.skill_graph import StudentSkillGraph

        payload = StudentSkillGraph(str(user_id)).to_api_payload()
        nodes = payload.get("skills") or payload.get("nodes") or []
        names = []
        for node in nodes:
            if isinstance(node, dict):
                name = node.get("skill") or node.get("name") or node.get("canonical_name")
                attempts = int(node.get("attempts") or 0)
                score = float(node.get("current_score") or 0)
                if name and (attempts > 0 or score > 0):
                    names.append(str(name))
        return names or None
    except Exception:
        return None


def search_jobs(
    *,
    q: str,
    where: str,
    page: int,
    user_id: str,
    country: str | None = None,
) -> dict[str, Any]:
    page = max(1, int(page or 1))
    q = (q or "software intern OR backend OR data").strip()
    where = (where or "").strip()
    country_code = normalize_country(country)

    cached = get_cached_search(q, where, page, country_code)
    # A fixture cached in offline mode must not mask real jobs after the
    # owner enables live search (or vice versa when returning offline).
    expected_source = "live" if get_settings().jobs_live_fetch else "fixture"
    if cached and cached.get("provenance") in {"live", "fixture"}:
        if cached["provenance"] != expected_source:
            cached = None
    cache_hit = cached is not None
    if cached is None:
        jobs, provenance = fetch_adzuna(
            q=q, where=where, page=page, country=country_code
        )
        if not jobs and _using_sql():
            # Older SQL cache rows derive provenance from their cards. An
            # empty list cannot retain the source, so avoid caching it rather
            # than mislabeling a live empty search as sample data.
            fetched_at = _now()
        else:
            put_cached_search(
                q, where, page, jobs, provenance=provenance, country=country_code
            )
            cached = get_cached_search(q, where, page, country_code)
            assert cached is not None
            jobs = cached["jobs"]
            fetched_at = cached["fetched_at"]
            provenance = cached["provenance"]
    else:
        jobs = cached["jobs"]
        provenance = cached["provenance"]
        fetched_at = cached["fetched_at"]

    user_skills = user_skills_for_overlay(user_id)
    cards = []
    for job in jobs:
        card = {
            "id": job["id"],
            "title": job["title"],
            "company": job["company"],
            "location": job["location"],
            "salary_min": job.get("salary_min"),
            "salary_max": job.get("salary_max"),
            "salary_is_predicted": job.get("salary_is_predicted"),
            "salary_currency": job.get("salary_currency"),
            "created": job.get("created"),
            "skills": job.get("skills") or [],
            "match_pct": match_pct(job.get("skills") or [], user_skills),
            "redirect_url": job.get("redirect_url"),
            "snippet": job.get("snippet"),
            "provenance": job.get("provenance") or provenance,
            "attribution": {
                "label": "Jobs by Adzuna",
                "jobs_href": _adzuna_home(country_code),
                "logo_href": _adzuna_home(country_code),
            },
        }
        cards.append(card)

    fetched_iso = (
        fetched_at.isoformat()
        if isinstance(fetched_at, datetime)
        else str(fetched_at)
    )

    empty_reason = None
    if not cards:
        if provenance == "live":
            empty_reason = "No openings matched this search."
        else:
            empty_reason = _sample_empty_reason(provenance)

    return {
        "jobs": cards,
        "count": len(cards),
        "page": page,
        "q": q,
        "where": where,
        "country": country_code,
        "source": provenance,
        "provenance": provenance,
        "cache_hit": cache_hit,
        "fetched_at": fetched_iso,
        "empty_reason": empty_reason or _sample_empty_reason(provenance),
        "disclaimer": (
            f"Listings from Adzuna ({country_code.upper()}). "
            "View job opens the original Adzuna redirect in a new tab. "
            "interViv is not affiliated with LinkedIn or Naukri."
        ),
    }


def _greenhouse_card(job: dict[str, Any]) -> dict[str, Any]:
    snippet = _sanitize_text(job.get("snippet") or "")
    skills = extract_skills_from_text(f"{job.get('title') or ''}\n{snippet}")
    external_id = f"{job['token']}:{job['external_id']}"
    redirect = safe_greenhouse_url(job.get("redirect_url")) or ""
    return {
        "id": f"{PROVIDER_GREENHOUSE}:{external_id}",
        "provider": PROVIDER_GREENHOUSE,
        "external_id": external_id,
        "title": job.get("title") or "",
        "company": job.get("company") or "",
        "location": job.get("location") or "",
        "created": job.get("updated_at"),
        "salary_min": None,
        "salary_max": None,
        "salary_is_predicted": None,
        "salary_currency": None,
        "snippet": snippet,
        "redirect_url": redirect,
        "skills": skills,
        "payload": {
            "title": job.get("title") or "",
            "company": job.get("company") or "",
            "location": job.get("location") or "",
            "description": snippet,
            "redirect_url": redirect,
            "id": external_id,
            "skills": skills,
        },
        "provenance": "greenhouse",
    }


def search_greenhouse_jobs(
    *,
    q: str,
    where: str,
    page: int,
    user_id: str,
) -> dict[str, Any]:
    """Public Greenhouse boards, filtered by the same keyword and city fields."""
    page = max(1, int(page or 1))
    q = (q or "").strip()
    where = (where or "").strip()
    # JOBS_LIVE_FETCH=0 means no board or description request at all; offline
    # results are sample listings with their own cache key and label.
    live = bool(get_settings().jobs_live_fetch)
    provenance = "greenhouse" if live else "sample"
    key = f"greenhouse|{provenance}|{(q or '').lower()}|{where.lower()}|{page}"
    cached = _SEARCH_MEMORY.get(key)
    cache_hit = False
    note = None
    if cached and _now() - _as_utc(cached["fetched_at"]) <= _cache_ttl():
        cache_hit = True
        jobs = cached["jobs"]
        fetched_at = cached["fetched_at"]
        note = cached.get("note")
    else:
        listed = load_board_jobs() if live else load_greenhouse_sample_jobs()
        if not listed:
            fetched_at = _now()
            return {
                "jobs": [],
                "count": 0,
                "page": page,
                "q": q,
                "where": where,
                "country": None,
                "source": "greenhouse",
                "provenance": "greenhouse",
                "cache_hit": False,
                "fetched_at": fetched_at.isoformat(),
                "empty_reason": "Greenhouse boards could not be loaded. Try again shortly.",
                "note": None,
                "disclaimer": (
                    "Listings from public Greenhouse company boards. "
                    "View job opens the original Greenhouse posting. "
                    "interViv is not affiliated with Greenhouse."
                ),
            }
        matched, note = filter_jobs(listed, q=q, where=where)
        start = (page - 1) * GREENHOUSE_PAGE_SIZE
        page_slice = matched[start : start + GREENHOUSE_PAGE_SIZE]
        page_jobs = attach_descriptions(page_slice) if live else page_slice
        jobs = [_greenhouse_card(job) for job in page_jobs]
        fetched_at = _now()
        stamped = _stamp_provenance(jobs, provenance=provenance, fetched_at=fetched_at)
        for job in stamped:
            _upsert_job(job, fetched_at=fetched_at)
        _SEARCH_MEMORY[key] = {
            "fetched_at": fetched_at,
            "jobs": list(stamped),
            "provenance": provenance,
            "note": note,
        }
        jobs = stamped

    user_skills = user_skills_for_overlay(user_id)
    cards = []
    for job in jobs:
        cards.append(
            {
                "id": job["id"],
                "title": job["title"],
                "company": job["company"],
                "location": job["location"],
                "salary_min": None,
                "salary_max": None,
                "salary_is_predicted": None,
                "salary_currency": None,
                "created": job.get("created"),
                "skills": job.get("skills") or [],
                "match_pct": match_pct(job.get("skills") or [], user_skills),
                "redirect_url": job.get("redirect_url"),
                "snippet": job.get("snippet"),
                "provenance": provenance,
                "attribution": {
                    "label": "Greenhouse" if live else "Sample listing",
                    "jobs_href": job.get("redirect_url") or "https://www.greenhouse.com/",
                    "logo_href": "https://www.greenhouse.com/",
                },
            }
        )
    fetched_iso = (
        fetched_at.isoformat() if isinstance(fetched_at, datetime) else str(fetched_at)
    )
    empty_reason = None if cards else (
        "No Greenhouse openings matched this search." if live
        else "No sample listings matched this search."
    )
    return {
        "jobs": cards,
        "count": len(cards),
        "page": page,
        "q": q,
        "where": where,
        "country": None,
        "source": "greenhouse",
        "provenance": provenance,
        "sample": not live,
        "cache_hit": cache_hit,
        "fetched_at": fetched_iso,
        "empty_reason": empty_reason,
        "note": note,
        "disclaimer": (
            "Listings from public Greenhouse company boards. "
            "View job opens the original Greenhouse posting. "
            "interViv is not affiliated with Greenhouse."
        ) if live else GREENHOUSE_SAMPLE_DISCLAIMER,
    }


def _adzuna_home(country: str) -> str:
    # Local domains per Adzuna ToS branding guidance.
    mapping = {
        "gb": "https://www.adzuna.co.uk/",
        "in": "https://www.adzuna.co.in/",
        "au": "https://www.adzuna.com.au/",
        "us": "https://www.adzuna.com/",
        "ca": "https://www.adzuna.ca/",
        "de": "https://www.adzuna.de/",
        "fr": "https://www.adzuna.fr/",
        "nl": "https://www.adzuna.nl/",
        "br": "https://www.adzuna.com.br/",
        "za": "https://www.adzuna.co.za/",
    }
    return mapping.get(country, "https://www.adzuna.com/")


def missing_skills_for_job(job: dict[str, Any], user_skills: list[str] | None) -> list[str]:
    job_skills = list(job.get("skills") or [])
    user = {s.lower() for s in (user_skills or [])}
    missing = [s for s in job_skills if s.lower() not in user]
    seen = set()
    out = []
    for s in missing:
        if s not in seen:
            seen.add(s)
            out.append(s)
    return out[:MAX_PRACTICE_SKILLS] or job_skills[:MAX_PRACTICE_SKILLS]


def build_practice_prepare_payload(
    *,
    job: dict[str, Any],
    user_skills: list[str] | None,
    full_jd: str | None = None,
) -> dict[str, Any]:
    """Draft practice handoff — no session started.

    Snippet-derived skills are proposals only. Optional full_jd may refine
    lexicon skills; neither invents company-specific interview questions.
    """
    base_skills = missing_skills_for_job(job, user_skills)
    jd_note = (
        "Listing snippet is not a complete requirements specification. "
        "Confirm skills and blocks before starting. Ordinary Practice remains available."
    )
    refined = list(base_skills)
    if full_jd and full_jd.strip():
        # Lexicon extraction only — never treated as scored content or bundle promotion.
        extra = extract_skills_from_text(full_jd.strip()[:8000])
        for skill in extra:
            if skill not in refined:
                refined.append(skill)
        refined = refined[:MAX_PRACTICE_SKILLS] or base_skills
        jd_note = (
            "Skills were refined from your pasted full job description (lexicon only). "
            "Confirm before starting. This does not change scoring or invent questions."
        )

    offline_uncached = False
    if not refined and (job.get("title") or full_jd or job.get("snippet")):
        from modules.role_skills import OFFLINE_UNCACHED_MESSAGE, extract_role_skills

        rs = extract_role_skills(
            role=job.get("title"),
            jd_text=full_jd or job.get("snippet"),
            max_skills=MAX_PRACTICE_SKILLS,
        )
        refined = [s for s in (rs.get("skills") or []) if s][:MAX_PRACTICE_SKILLS]
        if not refined and rs.get("offline_uncached"):
            offline_uncached = True
            jd_note = str(rs.get("message") or OFFLINE_UNCACHED_MESSAGE)

    blocks = [
        {
            "round_type": "technical_short_answer",
            "category": "interview",
            "skills": [skill],
            "count": 1,
        }
        for skill in refined[:3]
    ]
    if any(s in MCQ_ABLE for s in refined):
        mcq_skills = [s for s in refined if s in MCQ_ABLE][:1]
        if mcq_skills:
            blocks.append({
                "round_type": "mcq",
                "category": "oa",
                "skills": mcq_skills,
                "count": 8,
                "duration_minutes": 30,
            })

    return {
        "job_id": job.get("id"),
        "title": job.get("title"),
        "company": job.get("company") or "",
        "role": job.get("title") or "",
        "location": job.get("location") or "",
        "proposed_skills": refined,
        "proposed_blocks": blocks,
        "offline_uncached": offline_uncached,
        "snippet_is_incomplete": True,
        "confirmation_required": True,
        "note": jd_note,
        "practice_href": "/practice",
        "navigate_confirm": f"/jobs/{job.get('id')}/prepare",
    }


def build_practice_start_payload(
    *,
    skills: list[str] | None = None,
    candidate_id: str | None = None,
    blocks: list[dict[str, Any]] | None = None,
    role: str | None = None,
    jd_text: str | None = None,
) -> dict[str, Any]:
    cleaned_skills = [str(s).strip() for s in (skills or []) if str(s).strip()][:MAX_PRACTICE_SKILLS]
    if blocks:
        payload: dict[str, Any] = {"blocks": blocks}
        if candidate_id:
            payload["candidate_id"] = candidate_id
        return payload

    if not cleaned_skills and (role or jd_text):
        from modules.role_skills import extract_role_skills

        rs = extract_role_skills(role=role, jd_text=jd_text, max_skills=MAX_PRACTICE_SKILLS)
        cleaned_skills = [str(s).strip() for s in (rs.get("skills") or []) if str(s).strip()][:MAX_PRACTICE_SKILLS]

    if not cleaned_skills:
        return {
            "skills": [],
            "round_plan": [],
            "mode": "offline_uncached",
            "offline_uncached": True,
            "error": "Role is not cached for offline practice and no LLM connection is available.",
        }

    include_mcq = any(s in MCQ_ABLE for s in cleaned_skills)
    round_plan = ["technical_short_answer"] * min(3, max(1, len(cleaned_skills)))
    if include_mcq:
        round_plan.append("mcq")
    payload = {
        "skills": cleaned_skills,
        "rounds_per_skill": 1,
        "round_plan": round_plan,
        "round_type": round_plan[0],
        "round_config": (
            {"duration_minutes": 30, "count": 8}
            if include_mcq
            else {"duration_minutes": 30}
        ),
    }
    if candidate_id:
        payload["candidate_id"] = candidate_id
    return payload


# ── SQL helpers ─────────────────────────────────────────────────────────────

def _upsert_job_sql(job: dict[str, Any]) -> None:
    from backend.db.sqlalchemy_models import JobsCacheRow
    from backend.db.sqlalchemy_store import session_scope

    with session_scope() as session:
        row = (
            session.query(JobsCacheRow)
            .filter_by(provider=job["provider"], external_id=job["external_id"])
            .one_or_none()
        )
        if row is None:
            row = JobsCacheRow(
                provider=job["provider"],
                external_id=job["external_id"],
                payload=job.get("payload") or {},
                snippet=job.get("snippet") or "",
                redirect_url=job.get("redirect_url") or "",
                fetched_at=job.get("fetched_at") or _now(),
            )
            session.add(row)
        else:
            row.payload = job.get("payload") or {}
            row.snippet = job.get("snippet") or ""
            row.redirect_url = job.get("redirect_url") or ""
            row.fetched_at = job.get("fetched_at") or _now()


def _get_job_sql(provider: str, external_id: str) -> dict[str, Any] | None:
    from backend.db.sqlalchemy_models import JobsCacheRow
    from backend.db.sqlalchemy_store import session_scope

    with session_scope() as session:
        row = (
            session.query(JobsCacheRow)
            .filter_by(provider=provider, external_id=external_id)
            .one_or_none()
        )
        if row is None:
            return None
        payload = dict(row.payload or {})
        if provider != PROVIDER_ADZUNA:
            return {
                "id": f"{provider}:{row.external_id}",
                "provider": provider,
                "external_id": row.external_id,
                "title": payload.get("title") or "",
                "company": payload.get("company") or "",
                "location": payload.get("location") or "",
                "snippet": row.snippet or payload.get("description") or "",
                "redirect_url": row.redirect_url or payload.get("redirect_url") or "",
                "skills": payload.get("skills") or [],
                "payload": payload,
                "provenance": "greenhouse",
            }
        payload.setdefault("id", row.external_id)
        payload.setdefault("description", row.snippet)
        payload.setdefault("redirect_url", row.redirect_url)
        return _normalize_adzuna_item(payload, from_fixture=True)


def _get_search_sql(key: str) -> dict[str, Any] | None:
    from backend.db.sqlalchemy_models import JobsSearchCacheRow
    from backend.db.sqlalchemy_store import session_scope

    with session_scope() as session:
        row = session.query(JobsSearchCacheRow).filter_by(query_hash=key).one_or_none()
        if row is None:
            return None
        fetched_at = _as_utc(row.fetched_at)
        if _now() - fetched_at > _cache_ttl():
            return None
        jobs = []
        for item in row.results_json or []:
            jobs.append(item if "skills" in item else _normalize_adzuna_item(item, from_fixture=True))
        return {
            "jobs": jobs,
            "fetched_at": fetched_at,
            "provenance": _provenance_from_jobs(jobs),
        }


def _put_search_sql(
    key: str,
    page: int,
    jobs: list[dict[str, Any]],
    fetched: datetime,
    *,
    provenance: str,
) -> None:
    from backend.db.sqlalchemy_models import JobsSearchCacheRow
    from backend.db.sqlalchemy_store import session_scope

    with session_scope() as session:
        row = session.query(JobsSearchCacheRow).filter_by(query_hash=key).one_or_none()
        cards = [
            {
                "id": j["id"],
                "provider": j["provider"],
                "external_id": j["external_id"],
                "title": j["title"],
                "company": j["company"],
                "location": j["location"],
                "created": j.get("created"),
                "salary_min": j.get("salary_min"),
                "salary_max": j.get("salary_max"),
                "snippet": j.get("snippet"),
                "redirect_url": j.get("redirect_url"),
                "skills": j.get("skills") or [],
                "payload": j.get("payload") or {},
                "provenance": j.get("provenance") or provenance,
                "fetched_at_iso": j.get("fetched_at_iso")
                or (fetched.isoformat() if isinstance(fetched, datetime) else str(fetched)),
            }
            for j in jobs
        ]
        if row is None:
            session.add(
                JobsSearchCacheRow(
                    query_hash=key,
                    page=page,
                    results_json=cards,
                    fetched_at=fetched,
                )
            )
        else:
            row.page = page
            row.results_json = cards
            row.fetched_at = fetched
