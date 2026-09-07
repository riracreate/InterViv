"""Job explorer — Adzuna (IN) + cache + lexicon skill overlay.

No scrapers. No LLM JD parse. Apply = outbound redirect_url only.
"""

from __future__ import annotations

import hashlib
import json
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable

import httpx

from backend.config import get_settings
from modules.resume_parser import extract_skills_from_text

PROVIDER_ADZUNA = "adzuna"
ROOT = Path(__file__).resolve().parents[1]
FIXTURE_PATH = ROOT / "data" / "jobs_fixture_adzuna.json"

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


def reset_memory_store() -> None:
    _SEARCH_MEMORY.clear()
    _JOB_MEMORY.clear()
    _RATE.clear()


def set_fetch_override(fn: Callable[..., list[dict[str, Any]]] | None) -> None:
    global _FETCH_OVERRIDE
    _FETCH_OVERRIDE = fn


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _as_utc(dt: datetime) -> datetime:
    """SQLite often returns naive datetimes; compare only in UTC-aware form."""
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _using_sql() -> bool:
    return bool(get_settings().database_url)


def query_hash(q: str, where: str, page: int) -> str:
    raw = f"{(q or '').strip().lower()}|{(where or '').strip().lower()}|{int(page)}"
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
    if from_fixture or "redirect_url" in raw and "company" in raw and isinstance(raw.get("company"), str):
        company = raw.get("company") or ""
        location = raw.get("location") or ""
        external_id = str(raw.get("id") or "")
        title = str(raw.get("title") or "")
        snippet = str(raw.get("description") or "")[:2000]
        redirect = str(raw.get("redirect_url") or "")
        created = raw.get("created")
        salary_min = raw.get("salary_min")
        salary_max = raw.get("salary_max")
    else:
        # Live Adzuna shape
        external_id = str(raw.get("id") or "")
        title = str(raw.get("title") or "")
        company = str((raw.get("company") or {}).get("display_name") or "")
        location = str((raw.get("location") or {}).get("display_name") or "")
        snippet = str(raw.get("description") or "")[:2000]
        redirect = str(raw.get("redirect_url") or "")
        created = raw.get("created")
        salary_min = raw.get("salary_min")
        salary_max = raw.get("salary_max")

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
    results_per_page: int = MAX_RESULTS,
) -> tuple[list[dict[str, Any]], str]:
    """Return (jobs, provenance) where provenance is live|fixture|fixture_fallback|override.

    Live HTTP runs only when JOBS_LIVE_FETCH is enabled *and* credentials exist.
    The code path is retained for a future authorized integration; default is offline.
    """
    if _FETCH_OVERRIDE is not None:
        return _FETCH_OVERRIDE(q=q, where=where, page=page), "override"

    settings = get_settings()
    if not settings.jobs_live_fetch:
        # Phase O gate: no outbound attempt under the default configuration.
        return load_fixture_jobs()[:results_per_page], "fixture"

    app_id = settings.adzuna_app_id
    app_key = settings.adzuna_app_key
    if not app_id or not app_key:
        # Documented empty credentials → fixture for demos/tests
        return load_fixture_jobs()[:results_per_page], "fixture"

    page = max(1, int(page))
    url = f"https://api.adzuna.com/v1/api/jobs/in/search/{page}"
    params = {
        "app_id": app_id,
        "app_key": app_key,
        "results_per_page": min(MAX_RESULTS, max(1, int(results_per_page))),
        "what": q or "software intern",
    }
    if where:
        params["where"] = where

    try:
        with httpx.Client(timeout=15.0) as client:
            resp = client.get(url, params=params)
            resp.raise_for_status()
            data = resp.json()
    except Exception:
        # Silent degrade to fixtures (SemanticScorer-like), not fail-loud.
        return load_fixture_jobs()[:results_per_page], "fixture_fallback"

    results = data.get("results") or []
    jobs = [_normalize_adzuna_item(item) for item in results[:MAX_RESULTS]]
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
    if provenance not in {"fixture", "fixture_fallback"}:
        return None
    settings = get_settings()
    if provenance == "fixture_fallback":
        return (
            "Live Adzuna fetch failed — showing fixture listings (not live market data)."
        )
    if not settings.jobs_live_fetch:
        return (
            "JOBS_LIVE_FETCH is off — showing fixture listings (not live Adzuna). "
            "Set JOBS_LIVE_FETCH=1 and Adzuna credentials in .env for live India jobs."
        )
    return (
        "ADZUNA_APP_ID / ADZUNA_APP_KEY not configured — showing fixture listings "
        "(not live Adzuna). Set credentials in .env for live India jobs."
    )


def get_cached_search(q: str, where: str, page: int) -> dict[str, Any] | None:
    """Return ``{jobs, fetched_at, provenance}`` or None on miss/expiry."""
    key = query_hash(q, where, page)
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
) -> None:
    key = query_hash(q, where, page)
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
) -> dict[str, Any]:
    page = max(1, int(page or 1))
    q = (q or "software intern OR backend OR data").strip()
    where = (where or "").strip()

    cached = get_cached_search(q, where, page)
    cache_hit = cached is not None
    if cached is None:
        jobs, provenance = fetch_adzuna(q=q, where=where, page=page)
        put_cached_search(q, where, page, jobs, provenance=provenance)
        # Re-read so fetched_at / stamps match what cache stores.
        cached = get_cached_search(q, where, page)
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
            "created": job.get("created"),
            "skills": job.get("skills") or [],
            "match_pct": match_pct(job.get("skills") or [], user_skills),
            "redirect_url": job.get("redirect_url"),
            "snippet": job.get("snippet"),
            "provenance": job.get("provenance") or provenance,
        }
        cards.append(card)

    fetched_iso = (
        fetched_at.isoformat()
        if isinstance(fetched_at, datetime)
        else str(fetched_at)
    )

    return {
        "jobs": cards,
        "count": len(cards),
        "page": page,
        "q": q,
        "where": where,
        # provenance travels with the data; cache_hit is a separate axis.
        "source": provenance,
        "provenance": provenance,
        "cache_hit": cache_hit,
        "fetched_at": fetched_iso,
        "empty_reason": _sample_empty_reason(provenance),
        "disclaimer": (
            "Listings from Adzuna (India). Apply opens the original site in a new tab. "
            "interViv is not affiliated with LinkedIn or Naukri."
        ),
    }


def missing_skills_for_job(job: dict[str, Any], user_skills: list[str] | None) -> list[str]:
    job_skills = list(job.get("skills") or [])
    user = {s.lower() for s in (user_skills or [])}
    missing = [s for s in job_skills if s.lower() not in user]
    # Prefer unique order preserved
    seen = set()
    out = []
    for s in missing:
        if s not in seen:
            seen.add(s)
            out.append(s)
    return out[:MAX_PRACTICE_SKILLS] or job_skills[:MAX_PRACTICE_SKILLS] or ["DSA"]


def build_practice_start_payload(
    *,
    skills: list[str],
    candidate_id: str | None = None,
) -> dict[str, Any]:
    skills = [s for s in skills if s][:MAX_PRACTICE_SKILLS] or ["DSA"]
    include_mcq = any(s in MCQ_ABLE for s in skills)
    round_plan = ["technical_short_answer"] * min(3, max(1, len(skills)))
    if include_mcq:
        round_plan.append("mcq")
    payload: dict[str, Any] = {
        "skills": skills,
        "rounds_per_skill": 1,
        "round_plan": round_plan,
        "round_type": round_plan[0],
        "round_config": {"duration_minutes": 30, "count": 8} if include_mcq else {"duration_minutes": 30},
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
