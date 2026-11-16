"""Production question-generation hardening.

This module wraps the existing question bank without editing
``modules/question_bank.py``. It adds the Phase 2 production controls around
LLM question generation:

- Redis cache for 24 hours keyed by
  (skill, sub_domain, difficulty, target_concepts)
- per-minute LLM rate limiting, using Redis when configured and an in-memory
  fallback otherwise
- exponential-backoff retry with a maximum of 3 attempts
- deterministic CSV/domain/template fallback after final LLM failure

The LLM is still used only for question generation. All scoring, decisions,
feedback, and recommendations remain deterministic Python.
"""
from __future__ import annotations

import json
import logging
import os
import re
import ssl
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from modules import question_bank

try:
    import certifi

    _SSL_CTX = ssl.create_default_context(cafile=certifi.where())
except ImportError:  # pragma: no cover - optional production nicety
    _SSL_CTX = None


LOGGER = logging.getLogger(__name__)

DEFAULT_CACHE_TTL_SECONDS = 24 * 60 * 60
DEFAULT_MAX_RETRIES = 3
DEFAULT_RETRY_BASE_SECONDS = 0.25
DEFAULT_LLM_RATE_LIMIT_PER_MINUTE = 60

_REDIS_CLIENT = None
_REDIS_UNAVAILABLE = False
_IN_MEMORY_CACHE: dict[str, tuple[float, str]] = {}
_IN_MEMORY_LIMITS: dict[str, tuple[int, int]] = {}
_LAST_RUNTIME_ERROR: str | None = None
_STRUCTURED_BANK: list[dict[str, str]] | None = None


@dataclass(frozen=True)
class QuestionCacheContext:
    skill: str
    sub_domain: str | None
    difficulty: str
    target_concepts: tuple[str, ...] = ()
    company: str | None = None
    role: str | None = None
    resume_skills: tuple[str, ...] = ()
    weak_skills: tuple[str, ...] = ()


@dataclass(frozen=True)
class MarketQuestionContext:
    company: str | None = None
    role: str | None = None
    company_id: str | None = None
    role_id: str | None = None
    resume_skills: tuple[str, ...] = ()
    weak_skills: tuple[str, ...] = ()


def last_runtime_error() -> str | None:
    return _LAST_RUNTIME_ERROR


def _set_last_error(message: str | None) -> None:
    global _LAST_RUNTIME_ERROR
    _LAST_RUNTIME_ERROR = message


def _normalise(value: str | None) -> str:
    return (value or "general").strip().lower().replace(" ", "_")


def _normalise_concepts(concepts: tuple[str, ...] | list[str] | None) -> list[str]:
    return sorted(
        _normalise(str(concept)).replace("__", "_")
        for concept in (concepts or [])
        if str(concept).strip()
    )


def _optional_token(value: str | None) -> str:
    return (value or "").strip().lower().replace(" ", "_")


def question_cache_key(context: QuestionCacheContext) -> str:
    payload = {
        "skill": _normalise(context.skill),
        "sub_domain": _normalise(context.sub_domain),
        "difficulty": _normalise(context.difficulty),
        "target_concepts": _normalise_concepts(context.target_concepts),
        "company": _optional_token(context.company),
        "role": _optional_token(context.role),
        "resume_skills": _normalise_concepts(context.resume_skills),
        "weak_skills": _normalise_concepts(context.weak_skills),
    }
    compact = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return f"interviv:question:v2:{compact}"


def _display_list(items: tuple[str, ...] | list[str] | None) -> str:
    values = [str(item).strip() for item in (items or []) if str(item).strip()]
    return ", ".join(values) if values else "none supplied"


def _safe_json_schema() -> str:
    return json.dumps(
        {
            "question": "...",
            "ideal_answer": "...",
            "ideal_keywords": ["...", "..."],
            "sub_domain": "...",
            "topic": "...",
            "difficulty": "easy|medium|hard",
            "question_type": "conceptual|coding|system_design|behavioral|resume_based",
            "company": "...",
            "role": "...",
            "followups": ["...", "..."],
        },
        indent=2,
    )


def _resolve_market_context(context: MarketQuestionContext | None) -> MarketQuestionContext:
    context = context or MarketQuestionContext()
    company = context.company
    role = context.role
    if company and role:
        return context
    try:
        from backend.db.company_seed import company_db_id_to_slug, role_db_id_to_slug
        from modules.company_graph import get_company_graph

        graph = get_company_graph()
        company_id = company_db_id_to_slug(context.company_id) or context.company_id
        role_id = role_db_id_to_slug(context.role_id) or context.role_id
        if company_id and not company:
            found = graph.get_company(str(company_id))
            if found:
                company = found.name
        if role_id and not role:
            found_role = graph.find_role(str(role_id))
            if found_role:
                _, role_obj = found_role
                role = f"{role_obj.title} ({role_obj.level})"
                if not company:
                    company = found_role[0].name
    except Exception:
        pass
    return MarketQuestionContext(
        company=company,
        role=role,
        company_id=context.company_id,
        role_id=context.role_id,
        resume_skills=context.resume_skills,
        weak_skills=context.weak_skills,
    )


def build_question_prompt(
    *,
    skill: str,
    sub_domain: Optional[str],
    difficulty: str,
    asked: list[str],
    target_concepts: list[str] | tuple[str, ...] | None = None,
    market_context: MarketQuestionContext | None = None,
) -> str:
    """Prompt for LLM question generation only.

    The model is explicitly prohibited from judging, scoring, or giving
    feedback. Returned reference material is consumed later by deterministic
    Python scoring.
    """
    market = _resolve_market_context(market_context)
    company = market.company or "general company-style practice"
    role = market.role or "general student/candidate role"
    asked_part = ""
    if asked:
        previous = "\n".join(f"- {q}" for q in asked[-8:])
        asked_part = f"\nAvoid repeating these previous questions:\n{previous}\n"
    concept_part = ""
    concepts = [str(item).strip() for item in (target_concepts or []) if str(item).strip()]
    if concepts:
        concept_part = (
            "\nGenerate a question that primarily tests the following concepts: "
            f"{', '.join(concepts)}. The question should naturally require the "
            "candidate to demonstrate understanding of these concepts.\n"
        )

    return (
        "You are generating interview practice content for interViv, an "
        "Interview Readiness Platform.\n"
        "Use the LLM only to generate the question and reference material. "
        "Do not score, judge, grade, evaluate, or give feedback on any user answer.\n\n"
        "Selection priority:\n"
        f"1. Selected company: {company}\n"
        f"2. Selected role: {role}\n"
        f"3. Resume skills: {_display_list(market.resume_skills)}\n"
        f"4. Weak skills/concepts: {_display_list(market.weak_skills or tuple(concepts))}\n"
        f"5. Adaptive difficulty: {difficulty}\n\n"
        f"Generate ONE {difficulty} question for skill '{skill}'"
        f"{f' / sub-domain {sub_domain}' if sub_domain else ''}.\n"
        f"{question_bank._domain_hint(skill, sub_domain)}"
        f"{concept_part}"
        f"{asked_part}\n"
        "Return STRICT JSON ONLY. No prose, no markdown fences.\n"
        "Required JSON shape:\n"
        f"{_safe_json_schema()}\n\n"
        "Rules:\n"
        "- question: 1-2 sentences, specific and market-standard\n"
        "- ideal_answer: 4-6 sentences, deterministic reference only\n"
        "- ideal_keywords: array of 5-8 technical keywords\n"
        "- question_type must be one of the listed enum values\n"
        "- followups: 2 short follow-up prompts\n"
        "- Do not include a score, rating, verdict, feedback, pass/fail, or hiring decision\n"
    )


def _redis_url() -> str | None:
    return (os.getenv("REDIS_URL") or "").strip() or None


def _redis():
    global _REDIS_CLIENT, _REDIS_UNAVAILABLE
    if _REDIS_UNAVAILABLE:
        return None
    if _REDIS_CLIENT is not None:
        return _REDIS_CLIENT
    url = _redis_url()
    if not url:
        return None
    try:
        import redis

        client = redis.Redis.from_url(
            url,
            decode_responses=True,
            socket_connect_timeout=0.5,
            socket_timeout=0.5,
        )
        client.ping()
        _REDIS_CLIENT = client
        return _REDIS_CLIENT
    except Exception as exc:  # pragma: no cover - depends on local Redis
        _REDIS_UNAVAILABLE = True
        LOGGER.warning("Redis unavailable; using in-process question controls: %s", exc)
        return None


def _cache_ttl_seconds() -> int:
    raw = os.getenv("QUESTION_CACHE_TTL_SECONDS")
    try:
        return max(1, int(raw)) if raw else DEFAULT_CACHE_TTL_SECONDS
    except ValueError:
        return DEFAULT_CACHE_TTL_SECONDS


def _normalise_question_text(text: str | None) -> str:
    return " ".join(str(text or "").strip().lower().split())


def _extract_asked_from_prompt(prompt: str) -> list[str]:
    if not prompt:
        return []
    match = re.search(
        r"avoid repeating these previous questions:\s*((?:- .+\n?)+)",
        prompt,
        flags=re.I,
    )
    if not match:
        return []
    return [
        line.lstrip("-").strip()
        for line in match.group(1).splitlines()
        if line.strip().startswith("-")
    ]


def _cache_get(context: QuestionCacheContext, asked: list[str]) -> str | None:
    key = question_cache_key(context)
    asked_norm = {_normalise_question_text(item) for item in (asked or []) if str(item).strip()}
    value = None
    client = _redis()
    if client is not None:
        try:
            value = client.get(key)
        except Exception as exc:  # pragma: no cover - depends on local Redis
            LOGGER.warning("Redis question cache read failed: %s", exc)
    if value is None:
        cached = _IN_MEMORY_CACHE.get(key)
        if cached:
            expires_at, raw = cached
            if expires_at >= time.time():
                value = raw
            else:
                _IN_MEMORY_CACHE.pop(key, None)
    if not value:
        return None
    question = _extract_question_from_raw(value)
    if not question or _normalise_question_text(question) in asked_norm:
        return None
    return value


def _cache_set(context: QuestionCacheContext, raw: str) -> None:
    if not raw:
        return
    key = question_cache_key(context)
    ttl = _cache_ttl_seconds()
    client = _redis()
    if client is not None:
        try:
            client.setex(key, ttl, raw)
            return
        except Exception as exc:  # pragma: no cover - depends on local Redis
            LOGGER.warning("Redis question cache write failed: %s", exc)
    _IN_MEMORY_CACHE[key] = (time.time() + ttl, raw)


def _rate_limit_per_minute() -> int:
    raw = os.getenv("QUESTION_LLM_RATE_LIMIT_PER_MINUTE")
    try:
        return int(raw) if raw else DEFAULT_LLM_RATE_LIMIT_PER_MINUTE
    except ValueError:
        return DEFAULT_LLM_RATE_LIMIT_PER_MINUTE


def _rate_limiter_allows(provider: str | None) -> bool:
    limit = _rate_limit_per_minute()
    if limit <= 0:
        return True
    minute = int(time.time() // 60)
    bucket = f"interviv:llm-rate:{provider or 'unknown'}:{minute}"
    client = _redis()
    if client is not None:
        try:
            count = int(client.incr(bucket))
            if count == 1:
                client.expire(bucket, 65)
            return count <= limit
        except Exception as exc:  # pragma: no cover - depends on local Redis
            LOGGER.warning("Redis LLM rate limit failed; using in-memory limiter: %s", exc)
    count, seen_minute = _IN_MEMORY_LIMITS.get(bucket, (0, minute))
    if seen_minute != minute:
        count = 0
    count += 1
    _IN_MEMORY_LIMITS[bucket] = (count, minute)
    return count <= limit


def _max_retries() -> int:
    raw = os.getenv("QUESTION_LLM_MAX_RETRIES")
    try:
        return max(1, int(raw)) if raw else DEFAULT_MAX_RETRIES
    except ValueError:
        return DEFAULT_MAX_RETRIES


def _retry_base_seconds() -> float:
    raw = os.getenv("QUESTION_LLM_RETRY_BASE_SECONDS")
    try:
        return max(0.0, float(raw)) if raw else DEFAULT_RETRY_BASE_SECONDS
    except ValueError:
        return DEFAULT_RETRY_BASE_SECONDS


def call_llm_with_cache_retry(
    prompt: str,
    context: QuestionCacheContext,
    *,
    asked: list[str] | None = None,
) -> str | None:
    """Return raw LLM content or ``None`` after retries/fallback-worthy errors.

    Phase Q: ``LLM_LIVE_FETCH`` and ``QUESTION_GENERATION_MODE`` are enforced
    here so adaptive and non-adaptive callers share one outbound boundary.
    """
    from modules.llm_outbound_gate import question_llm_outbound_allowed

    _set_last_error(None)
    if not question_llm_outbound_allowed():
        _set_last_error(
            "LLM outbound gated off (LLM_LIVE_FETCH / QUESTION_GENERATION_MODE)."
        )
        return None

    effective_asked = list(asked) if asked is not None else _extract_asked_from_prompt(prompt)
    asked_norm = {
        _normalise_question_text(item)
        for item in effective_asked
        if str(item).strip()
    }
    cached = _cache_get(context, effective_asked)
    if cached:
        return cached

    provider, api_key, model = question_bank._llm_provider()
    if not provider or not api_key or not model:
        _set_last_error("No supported LLM provider/key/model was configured.")
        return None

    body = json.dumps(
        {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": int(os.getenv("QUESTION_LLM_MAX_TOKENS", "600")),
            "temperature": float(os.getenv("QUESTION_LLM_TEMPERATURE", "0.7")),
        }
    ).encode("utf-8")
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "HTTP-Referer": os.getenv("OPENROUTER_SITE_URL", "http://localhost:5173"),
        "X-Title": os.getenv("OPENROUTER_APP_NAME", "interViv"),
    }
    attempts = _max_retries()
    delay = _retry_base_seconds()
    url = question_bank._chat_completion_url(provider)
    ssl_ctx = _SSL_CTX if url.startswith("https://") else None
    timeout = float(os.getenv("QUESTION_LLM_TIMEOUT_SECONDS", "20"))

    for attempt in range(1, attempts + 1):
        if not _rate_limiter_allows(provider):
            _set_last_error("LLM rate limit exceeded.")
            return None
        req = urllib.request.Request(
            url,
            data=body,
            headers=headers,
            method="POST",
        )
        try:
            with urllib.request.urlopen(
                req,
                timeout=timeout,
                context=ssl_ctx,
            ) as resp:
                raw = resp.read().decode("utf-8")
            content = _extract_provider_content(raw)
            if content:
                question = _extract_question_from_raw(content)
                if question and _normalise_question_text(question) in asked_norm:
                    _set_last_error("LLM returned a duplicate question already in asked.")
                else:
                    _cache_set(context, content)
                    return content
            else:
                _set_last_error("LLM response did not include message content.")
        except urllib.error.HTTPError as exc:
            if provider == "ollama" and exc.code == 404:
                try:
                    gen_req = urllib.request.Request(
                        f"{question_bank._ollama_base_url()}/api/generate",
                        data=json.dumps(
                            {
                                "model": model,
                                "prompt": prompt,
                                "stream": False,
                                "format": "json",
                            }
                        ).encode("utf-8"),
                        headers={"Content-Type": "application/json"},
                        method="POST",
                    )
                    with urllib.request.urlopen(
                        gen_req,
                        timeout=timeout,
                        context=None,
                    ) as resp:
                        raw = resp.read().decode("utf-8")
                    content = _extract_provider_content(raw)
                    if content:
                        question = _extract_question_from_raw(content)
                        if question and _normalise_question_text(question) in asked_norm:
                            _set_last_error("LLM returned a duplicate question already in asked.")
                        else:
                            _cache_set(context, content)
                            return content
                    else:
                        _set_last_error("LLM response did not include message content.")
                except Exception as fallback_exc:
                    _set_last_error(f"HTTP {exc.code}: {str(fallback_exc)[:500]}")
            else:
                try:
                    detail = exc.read().decode("utf-8", errors="replace")
                except Exception:
                    detail = str(exc)
                _set_last_error(f"HTTP {exc.code}: {detail[:500]}")
        except urllib.error.URLError as exc:
            _set_last_error(f"Network error: {getattr(exc, 'reason', exc)}")
        except TimeoutError:
            _set_last_error("Timed out waiting for the LLM provider.")
        except Exception as exc:  # pragma: no cover - defensive
            _set_last_error(f"Unexpected request error: {exc}")

        if attempt < attempts and delay > 0:
            time.sleep(delay * (2 ** (attempt - 1)))

    LOGGER.warning("LLM question generation failed after %d attempts: %s", attempts, _LAST_RUNTIME_ERROR)
    return None


def _extract_provider_content(raw: str) -> str | None:
    try:
        payload = json.loads(raw)
        if isinstance(payload, dict):
            if "choices" in payload:
                return str(payload["choices"][0]["message"]["content"]).strip()
            if isinstance(payload.get("message"), dict) and "content" in payload["message"]:
                return str(payload["message"]["content"]).strip()
            if "response" in payload:
                return str(payload["response"]).strip()
        return str(payload["choices"][0]["message"]["content"]).strip()
    except Exception as exc:
        _set_last_error(f"Invalid provider response: {exc}")
        return None


def _strip_json_fences(content: str) -> str:
    stripped = (content or "").strip()
    if stripped.startswith("```"):
        stripped = re.sub(r"^```(?:json)?", "", stripped, flags=re.I).strip()
        stripped = re.sub(r"```$", "", stripped).strip()
    return stripped


def parse_llm_json(content: str) -> dict | None:
    stripped = _strip_json_fences(content)
    try:
        return json.loads(stripped)
    except ValueError:
        start = stripped.find("{")
        end = stripped.rfind("}")
        if start != -1 and end != -1 and end > start:
            try:
                return json.loads(stripped[start : end + 1])
            except ValueError:
                return None
        return None


def _extract_question_from_raw(raw: str) -> str | None:
    payload = parse_llm_json(raw)
    if not payload:
        return None
    question = payload.get("question")
    return str(question) if question else None


def _with_question_shape(
    row: dict,
    *,
    skill: str,
    sub_domain: str | None,
    difficulty: str,
    source: str | None = None,
) -> dict:
    row["skill"] = skill
    row["sub_domain"] = sub_domain or "general"
    row["difficulty"] = difficulty
    if source:
        row["source"] = source
    return row


def _structured_bank_path() -> Path:
    return Path(__file__).resolve().parents[1] / "data" / "fallback_question_bank.csv"


def _load_structured_bank() -> list[dict[str, str]]:
    global _STRUCTURED_BANK
    if _STRUCTURED_BANK is not None:
        return _STRUCTURED_BANK
    path = _structured_bank_path()
    if not path.exists():
        _STRUCTURED_BANK = []
        return _STRUCTURED_BANK
    import csv

    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        _STRUCTURED_BANK = [row for row in csv.DictReader(handle) if row.get("question")]
    return _STRUCTURED_BANK


def structured_bank_rows() -> list[dict[str, str]]:
    """Cached structured-bank rows selection filters (read-only shared rows)."""
    return _load_structured_bank()


def _normalised_match(row_value: str | None, target: str | None) -> bool:
    if not target:
        return True
    row_norm = _normalise(row_value)
    target_norm = _normalise(target)
    return row_norm == target_norm or target_norm in row_norm or row_norm in target_norm


def _structured_fallback_question(
    skill: str,
    sub_domain: Optional[str],
    difficulty: str,
    asked: list[str],
    *,
    company: str | None = None,
    role: str | None = None,
) -> dict | None:
    rows = _load_structured_bank()
    if not rows:
        return None
    asked_norm = {q.lower().strip() for q in asked}
    filters = [
        lambda r: _normalised_match(r.get("company"), company)
        and _normalised_match(r.get("role"), role)
        and _normalised_match(r.get("skill"), skill)
        and _normalised_match(r.get("sub_domain"), sub_domain)
        and _normalised_match(r.get("difficulty"), difficulty),
        lambda r: _normalised_match(r.get("role"), role)
        and _normalised_match(r.get("skill"), skill)
        and _normalised_match(r.get("difficulty"), difficulty),
        lambda r: _normalised_match(r.get("skill"), skill)
        and _normalised_match(r.get("difficulty"), difficulty),
        lambda r: _normalised_match(r.get("skill"), skill),
    ]
    for predicate in filters:
        candidates = [
            row for row in rows
            if predicate(row) and (row.get("question") or "").lower().strip() not in asked_norm
        ]
        if candidates:
            row = candidates[0]
            return {
                "question": row["question"],
                "ideal_answer": row.get("ideal_answer", ""),
                "ideal_keywords": [item.strip() for item in (row.get("ideal_keywords") or "").split("|") if item.strip()],
                "source": "structured_fallback",
                "company": row.get("company") or company,
                "role": row.get("role") or role,
                "skill": row.get("skill") or skill,
                "sub_domain": row.get("sub_domain") or sub_domain or "general",
                "topic": row.get("topic") or sub_domain or skill,
                "difficulty": row.get("difficulty") or difficulty,
                "question_type": row.get("question_type") or "conceptual",
                "followups": [item.strip() for item in (row.get("followups") or "").split("|") if item.strip()],
            }
    return None


def fallback_question(
    skill: str,
    sub_domain: Optional[str],
    difficulty: str,
    asked: list[str],
    *,
    mode: str | None = None,
    company: str | None = None,
    role: str | None = None,
) -> dict:
    """Deterministic fallback that bypasses strict LLM settings."""
    resolved_skill, resolved_sub = question_bank.resolve_skill(skill)
    if sub_domain is None or sub_domain == "general":
        sub_domain = resolved_sub

    selected_mode = mode or question_bank._question_generation_mode()
    if selected_mode != "template":
        structured = _structured_fallback_question(
            resolved_skill,
            sub_domain,
            difficulty,
            asked,
            company=company,
            role=role,
        )
        if structured:
            return structured
        row = question_bank._get_bank().pick(resolved_skill, sub_domain, difficulty, asked)
        if row:
            return _with_question_shape(
                row,
                skill=resolved_skill,
                sub_domain=sub_domain,
                difficulty=difficulty,
                source=row.get("source") or "csv",
            )
        row = question_bank._domain_fallback_question(resolved_skill, sub_domain, asked)
        asked_norm = {_normalise_question_text(item) for item in (asked or []) if str(item).strip()}
        if row and _normalise_question_text(row.get("question")) not in asked_norm:
            return _with_question_shape(
                row,
                skill=resolved_skill,
                sub_domain=sub_domain,
                difficulty=difficulty,
                source=row.get("source") or "domain_fallback",
            )

    row = question_bank._template_question(resolved_skill, sub_domain, difficulty)
    asked_norm = {_normalise_question_text(item) for item in (asked or []) if str(item).strip()}
    if _normalise_question_text(row.get("question")) in asked_norm:
        templates = question_bank._TEMPLATES.get(difficulty.lower(), question_bank._TEMPLATES["medium"])
        topic = question_bank._template_topic(resolved_skill, sub_domain)
        available = [
            template.format(topic=topic, skill=resolved_skill)
            for template in templates
            if _normalise_question_text(template.format(topic=topic, skill=resolved_skill)) not in asked_norm
        ]
        if available:
            row["question"] = available[0]
        else:
            row["question"] = (
                f"For {resolved_skill}, explain a concrete lesson learned from working with "
                f"{topic} (round {len(asked) + 1}). Include trade-offs and one edge case."
            )
    return _with_question_shape(
        row,
        skill=resolved_skill,
        sub_domain=sub_domain,
        difficulty=difficulty,
        source=row.get("source") or "template",
    )


def generate_question(
    skill: str,
    sub_domain: Optional[str],
    difficulty: str,
    asked: list[str],
    *,
    target_concepts: list[str] | tuple[str, ...] | None = None,
    market_context: MarketQuestionContext | None = None,
) -> dict:
    """Hardened non-scoring question-generation entry point."""
    raw_sub = sub_domain
    resolved_skill, resolved_sub = question_bank.resolve_skill(skill)
    if sub_domain is None or sub_domain == "general":
        sub_domain = resolved_sub
    mode = question_bank._question_generation_mode()
    market = _resolve_market_context(market_context)
    asked_norm = {_normalise_question_text(item) for item in (asked or []) if str(item).strip()}

    try:
        from modules.bundle_selector import reviewed_bundles_only, select_bundle_question

        if not reviewed_bundles_only():
            norm_topic = str(raw_sub or "").strip()
            explicit_topic = (
                None
                if not norm_topic or norm_topic.lower() in {"general", "all", "default"}
                else norm_topic
            )
            bundle_hit = select_bundle_question(
                skill=skill,
                difficulty=difficulty,
                asked=asked,
                topic=explicit_topic,
            )
            if bundle_hit is not None:
                return {
                    "question": bundle_hit["question"],
                    "skill": bundle_hit.get("skill") or resolved_skill,
                    "sub_domain": bundle_hit.get("topic") or sub_domain,
                    "topic": bundle_hit.get("topic") or sub_domain,
                    "difficulty": bundle_hit.get("difficulty") or difficulty,
                    "source": bundle_hit.get("source") or "auto_checked_bundle",
                    "bundle_id": bundle_hit.get("bundle_id"),
                    "version": bundle_hit.get("version"),
                    "content_hash": bundle_hit.get("content_hash"),
                    "target_concepts": [],
                    "adaptive_selected": False,
                }
    except Exception:
        pass

    if mode in {"llm", "llm_csv_fallback"}:
        prompt = build_question_prompt(
            skill=resolved_skill,
            sub_domain=sub_domain,
            difficulty=difficulty,
            asked=asked,
            target_concepts=target_concepts,
            market_context=market,
        )
        context = QuestionCacheContext(
            skill=resolved_skill,
            sub_domain=sub_domain or "general",
            difficulty=difficulty,
            target_concepts=tuple(target_concepts or ()),
            company=market.company,
            role=market.role,
            resume_skills=tuple(market.resume_skills or ()),
            weak_skills=tuple(market.weak_skills or ()),
        )
        raw = call_llm_with_cache_retry(prompt, context, asked=asked)
        payload = parse_llm_json(raw or "")
        if payload and payload.get("question"):
            question_text = str(payload["question"]).strip()
            if _normalise_question_text(question_text) not in asked_norm:
                provider, _, model = question_bank._llm_provider()
                return {
                    "question": question_text,
                    "ideal_answer": str(payload.get("ideal_answer", "")).strip(),
                    "ideal_keywords": payload.get("ideal_keywords", ""),
                    "source": "llm",
                    "llm_provider": provider,
                    "llm_model": model,
                    "skill": resolved_skill,
                    "sub_domain": sub_domain or "general",
                    "difficulty": difficulty,
                    "topic": str(payload.get("topic") or sub_domain or resolved_skill),
                    "question_type": str(payload.get("question_type") or "conceptual"),
                    "company": str(payload.get("company") or market.company or ""),
                    "role": str(payload.get("role") or market.role or ""),
                    "followups": list(payload.get("followups") or []),
                    "cache_key": question_cache_key(context),
                }
            _set_last_error("LLM returned a duplicate question already in asked.")

    row = fallback_question(
        resolved_skill,
        sub_domain,
        difficulty,
        asked,
        mode=mode,
        company=market.company,
        role=market.role,
    )
    row["llm_fallback_reason"] = last_runtime_error()
    row["fallback_generated_at"] = datetime.now(timezone.utc).isoformat()
    return row


def warm_question_runtime() -> dict[str, object]:
    """Startup warm-up for Redis connectivity and CSV parsing."""
    bank = question_bank._get_bank()
    redis_ready = _redis() is not None
    return {
        "csv_questions_loaded": len(getattr(bank, "rows", []) or []),
        "structured_fallback_questions_loaded": len(_load_structured_bank()),
        "redis_enabled": bool(_redis_url()),
        "redis_ready": redis_ready,
        "cache_ttl_seconds": _cache_ttl_seconds(),
        "llm_rate_limit_per_minute": _rate_limit_per_minute(),
    }


__all__ = [
    "QuestionCacheContext",
    "MarketQuestionContext",
    "build_question_prompt",
    "call_llm_with_cache_retry",
    "fallback_question",
    "generate_question",
    "last_runtime_error",
    "parse_llm_json",
    "question_cache_key",
    "warm_question_runtime",
]
