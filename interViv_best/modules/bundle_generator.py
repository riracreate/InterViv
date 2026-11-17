"""On-demand YAML-v2 question bundle generator + Step E blind checker (WS2).

Generates complete YAML-v2 concept-assessed bundles for any (skill, topic,
difficulty) cell, runs deterministic Step E.1 schema/overlap validation,
stores them as ``generated`` in ``bundle_store``, runs Step E.2 blind-answer
verification through ``concept_evaluator_v3`` (without leaking grading
criteria to the blind answerer), and performs at most one Step E.3 audit and
regeneration retry on failure.

Never regenerates a cell that already has a cached ``reviewed``,
``auto_checked``, or ``generated`` bundle unless ``force=True``.
"""

from __future__ import annotations

import copy
import inspect
import io
import json
import logging
import os
import re
import ssl
import threading
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

import certifi

from modules import (
    bundle_store,
    concept_evaluator_v3,
    interview_llm,
    llm_outbound_gate,
    llm_usage,
    question_bank,
    role_skills,
)
from modules.bundle_store import BundleStoreError
from modules.evaluation_overlap import check_overlap
from modules.llm_errors import LLMCreditExhaustedError, LLMTruncatedError
from modules.question_bundles import (
    BUNDLE_ID_RE,
    DEFAULT_CATEGORY,
    DIFFICULTIES,
    MAX_BUNDLE_ID_LEN,
    BundleContentError,
    evaluate_calibration_length_bias,
    safe_slug,
    validate_generated_bundle_doc,
)

log = logging.getLogger("interviv.bundle_generator")

ROOT = Path(__file__).resolve().parents[1]
_SSL_CTX = ssl.create_default_context(cafile=certifi.where())
_LLM_OVERRIDE: Callable[..., Any] | None = None
_AUDIT_FILE_LOCK = threading.Lock()

DEFAULT_GENERATION_TIMEOUT_S = 45
DEFAULT_BLIND_CHECK_TIMEOUT_S = 30
DEFAULT_GENERATION_MAX_TOKENS = 2200
DEFAULT_BLIND_CHECK_MAX_TOKENS = 380
DEFAULT_AUDIT_MAX_TOKENS = 400
DEFAULT_PROMPT_A_MAX_TOKENS = 700

OPENROUTER_KEY_URL = "https://openrouter.ai/api/v1/key"
OPENROUTER_CREDITS_URL = "https://openrouter.ai/api/v1/credits"
OPENROUTER_MODELS_URL = "https://openrouter.ai/api/v1/models"
_DEFAULT_REJECTED_AUDIT_PATH = ROOT / "artifacts" / "rejected_bundles_audit.jsonl"
_DEFAULT_DEMOTED_AUDIT_PATH = ROOT / "artifacts" / "demoted_concepts_audit.jsonl"


class BundleGenerationError(RuntimeError):
    """Raised when bundle generation or Step E validation fails unrecoverably."""


def set_bundle_llm_override(fn: Callable[..., Any] | None) -> None:
    """Register or clear a test/mock override hook for bundle LLM calls."""
    global _LLM_OVERRIDE
    _LLM_OVERRIDE = fn


def _slug_underscore(text: str, max_len: int = 32) -> str:
    slug = re.sub(r"[^a-z0-9]+", "_", str(text or "").strip().lower()).strip("_")
    return (slug[:max_len].strip("_") or "concept")


def normalize_difficulty(difficulty: str | None) -> str:
    norm = str(difficulty or "medium").strip().lower()
    if norm not in DIFFICULTIES:
        raise BundleGenerationError(
            f"Unsupported difficulty {difficulty!r}; expected one of {DIFFICULTIES}."
        )
    return norm


def build_bundle_id_for_cell(skill: str, topic: str, difficulty: str) -> str:
    """Build a collision-free bundle_id per (skill, topic, difficulty) cell.

    ``selectable_versions`` selects only the latest version per ``bundle_id``,
    so easy/medium/hard variants for the same (skill, topic) must occupy
    distinct ``bundle_id``s while respecting ``BUNDLE_ID_RE`` and <= 64 chars.
    """
    s_slug = safe_slug(skill, 20)
    t_slug = safe_slug(topic, 28)
    d_slug = safe_slug(difficulty, 8)
    bid = f"{s_slug}.{t_slug}-{d_slug}"
    if len(bid) > MAX_BUNDLE_ID_LEN:
        keep_t = max(6, MAX_BUNDLE_ID_LEN - len(s_slug) - len(d_slug) - 2)
        t_trimmed = t_slug[:keep_t].strip("-") or "topic"
        bid = f"{s_slug}.{t_trimmed}-{d_slug}"
    if len(bid) > MAX_BUNDLE_ID_LEN or not BUNDLE_ID_RE.match(bid):
        raise BundleGenerationError(f"Could not construct valid bundle_id: {bid!r}")
    return bid


def resolve_generation_provider_and_model() -> tuple[str, str]:
    """Return the configured (provider, model) pair for bundle generation."""
    if interview_llm.enabled():
        return "openrouter", interview_llm.get_router().resolve_content_model(offline_override=_LLM_OVERRIDE is not None)
    provider, _api_key, model = question_bank._llm_provider()
    if not provider or not model:
        return (
            "openrouter" if os.getenv("OPENROUTER_API_KEY") else "ollama",
            (
                os.getenv("OPENROUTER_MODEL")
                or os.getenv("OPENAI_MODEL")
                or os.getenv("OLLAMA_MODEL")
                or "gemma2:2b"
            ).strip(),
        )
    return str(provider), str(model)


def resolve_checker_provider_and_model() -> tuple[str, str]:
    """Return the configured (provider, model) pair for Step E blind checks.

    Change E: ``BUNDLE_CHECK_MODEL`` env var, defaulting to ``OPENROUTER_MODEL``,
    else ``question_bank._llm_provider()`` model.
    """
    if interview_llm.enabled():
        return resolve_generation_provider_and_model()
    gen_provider, gen_model = resolve_generation_provider_and_model()
    explicit_model = (os.getenv("BUNDLE_CHECK_MODEL") or "").strip()
    explicit_provider = (os.getenv("BUNDLE_CHECK_PROVIDER") or "").strip().lower()
    openrouter_model = (os.getenv("OPENROUTER_MODEL") or "").strip()

    if explicit_model:
        model = explicit_model
    elif openrouter_model and (
        gen_provider == "openrouter"
        or (
            os.getenv("OPENROUTER_API_KEY", "").strip()
            and os.getenv("QUESTION_LLM_PROVIDER", "").strip().lower() != "ollama"
        )
    ):
        model = openrouter_model
    else:
        model = gen_model

    if explicit_provider:
        provider = explicit_provider
    elif explicit_model and "/" in explicit_model and os.getenv("OPENROUTER_API_KEY", "").strip():
        provider = "openrouter"
    elif openrouter_model and model == openrouter_model and os.getenv("OPENROUTER_API_KEY", "").strip():
        provider = "openrouter"
    else:
        provider = gen_provider

    return provider, model


def _strip_code_fences(text: str) -> str:
    cleaned = str(text or "").strip()
    cleaned = re.sub(r"^```(?:json|yaml)?\s*", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s*```$", "", cleaned)
    return cleaned.strip()


def _parse_json_object(raw_text: Any) -> dict[str, Any]:
    if isinstance(raw_text, dict):
        return raw_text
    cleaned = _strip_code_fences(str(raw_text or ""))
    try:
        parsed = json.loads(cleaned)
    except ValueError:
        start = cleaned.find("{")
        end = cleaned.rfind("}")
        if start == -1 or end == -1 or end <= start:
            raise BundleGenerationError(
                f"LLM did not return a JSON object: {cleaned[:240]!r}"
            )
        try:
            parsed = json.loads(cleaned[start : end + 1])
        except ValueError as exc:
            raise BundleGenerationError(
                f"Malformed JSON object from LLM: {exc}"
            ) from exc
    if not isinstance(parsed, dict):
        raise BundleGenerationError("Expected a JSON object from LLM.")
    return parsed


def _extract_usage_counts(data: dict[str, Any]) -> tuple[int, int, int]:
    usage = data.get("usage")
    if isinstance(usage, dict):
        pt = int(usage.get("prompt_tokens") or usage.get("input_tokens") or 0)
        ct = int(usage.get("completion_tokens") or usage.get("output_tokens") or 0)
        tt = int(usage.get("total_tokens") or (pt + ct))
        return max(0, pt), max(0, ct), max(0, tt)
    if "prompt_eval_count" in data or "eval_count" in data:
        pt = int(data.get("prompt_eval_count") or 0)
        ct = int(data.get("eval_count") or 0)
        return max(0, pt), max(0, ct), max(0, pt + ct)
    pt = int(data.get("prompt_tokens") or 0)
    ct = int(data.get("completion_tokens") or 0)
    tt = int(data.get("total_tokens") or (pt + ct))
    return max(0, pt), max(0, ct), max(0, tt)


def _extract_text_from_response(data: dict[str, Any]) -> str:
    if "content" in data and isinstance(data["content"], str):
        return data["content"].strip()
    if "text" in data and isinstance(data["text"], str):
        return data["text"].strip()
    if "choices" in data and isinstance(data["choices"], list) and data["choices"]:
        msg = data["choices"][0].get("message") or {}
        content = msg.get("content")
        if isinstance(content, list):
            parts = [
                str(p.get("text") or "")
                for p in content
                if isinstance(p, dict)
            ]
            return "".join(parts).strip()
        return str(content or "").strip()
    if isinstance(data.get("message"), dict) and "content" in data["message"]:
        return str(data["message"]["content"] or "").strip()
    if "response" in data:
        return str(data["response"] or "").strip()
    raise BundleGenerationError(f"Unrecognized LLM payload keys: {sorted(data)}")


def _detect_truncation_reason(data: dict[str, Any]) -> str | None:
    """Return ``'length'`` when an LLM payload indicates token-limit truncation."""
    choices = data.get("choices")
    if isinstance(choices, list) and choices and isinstance(choices[0], dict):
        finish_reason = str(choices[0].get("finish_reason") or "").strip().lower()
        if finish_reason == "length":
            return "length"
    top_finish = str(data.get("finish_reason") or "").strip().lower()
    if top_finish == "length":
        return "length"
    done_reason = str(data.get("done_reason") or "").strip().lower()
    if done_reason == "length":
        return "length"
    return None


def _parse_credit_error_body(raw_err: bytes | str) -> tuple[str, dict[str, Any]]:
    """Extract clean credit exhaustion message and structured details from HTTP 402 body."""
    if isinstance(raw_err, bytes):
        text = raw_err.decode("utf-8", errors="replace").strip()
    else:
        text = str(raw_err or "").strip()

    info: dict[str, Any] = {}
    msg = text
    try:
        parsed = json.loads(text) if text else {}
    except ValueError:
        parsed = {}

    if isinstance(parsed, dict):
        err_obj = parsed.get("error") if isinstance(parsed.get("error"), dict) else parsed
        if isinstance(err_obj, dict):
            if err_obj.get("message"):
                msg = str(err_obj["message"]).strip()
            if err_obj.get("code") is not None:
                info["code"] = err_obj["code"]
            if isinstance(err_obj.get("metadata"), dict):
                info["metadata"] = dict(err_obj["metadata"])

    req_match = re.search(r"requested up to\s+(\d+)\s+tokens", msg, flags=re.IGNORECASE)
    if req_match:
        info["requested_tokens"] = int(req_match.group(1))
    aff_match = re.search(r"can only afford\s+(\d+)", msg, flags=re.IGNORECASE)
    if aff_match:
        info["affordable_tokens"] = int(aff_match.group(1))
    if msg:
        info["message"] = msg[:500]
    return (msg[:500] if msg else "Insufficient credits."), info


def _invoke_override(
    fn: Callable[..., Any],
    *,
    purpose: str,
    provider: str,
    model: str,
    messages: list[dict[str, str]],
    max_tokens: int,
    temperature: float,
) -> tuple[str, tuple[int, int, int]]:
    call_kwargs: dict[str, Any] = {
        "purpose": purpose,
        "provider": provider,
        "model": model,
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": temperature,
    }
    try:
        sig = inspect.signature(fn)
        params = sig.parameters
        accepts_var_kw = any(
            p.kind == inspect.Parameter.VAR_KEYWORD for p in params.values()
        )
        if not accepts_var_kw:
            call_kwargs = {k: v for k, v in call_kwargs.items() if k in params}
    except (TypeError, ValueError):
        pass

    result = fn(**call_kwargs)
    if isinstance(result, str):
        return result.strip(), (0, 0, 0)
    if isinstance(result, dict):
        usage = _extract_usage_counts(result)
        trunc_reason = _detect_truncation_reason(result)
        if trunc_reason:
            raise LLMTruncatedError(
                f"LLM response truncated ({trunc_reason}) for model {model!r}.",
                finish_reason=trunc_reason,
                provider=provider,
                model=model,
                purpose=purpose,
                usage=usage,
            )
        if "payload" in result and isinstance(result["payload"], dict):
            return json.dumps(result["payload"]), usage
        if "doc" in result and isinstance(result["doc"], dict):
            return json.dumps(result["doc"]), usage
        if "content" in result or "text" in result or "choices" in result or "response" in result:
            return _extract_text_from_response(result), usage
        return json.dumps(result), usage
    raise BundleGenerationError(
        f"Bundle LLM override returned unsupported type: {type(result).__name__}"
    )


def _dial_http_llm(
    *,
    provider: str,
    model: str,
    messages: list[dict[str, str]],
    expect_json: bool,
    max_tokens: int,
    temperature: float,
    timeout_s: int,
) -> tuple[str, tuple[int, int, int]]:
    if provider == "openrouter":
        api_key = (os.getenv("OPENROUTER_API_KEY") or "").strip()
        if not api_key:
            raise BundleGenerationError("OPENROUTER_API_KEY is missing.")
        url = question_bank._chat_completion_url("openrouter")
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://interviv.local",
            "X-Title": "InterViv",
        }
        body: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        raw = _post_json(url, body=body, headers=headers, timeout_s=timeout_s, retry_transient=True)
        data = json.loads(raw)
        usage = _extract_usage_counts(data)
        trunc_reason = _detect_truncation_reason(data)
        if trunc_reason:
            raise LLMTruncatedError(
                f"LLM response truncated ({trunc_reason}) for model {model!r}.",
                finish_reason=trunc_reason,
                provider=provider,
                model=model,
                usage=usage,
            )
        return _extract_text_from_response(data), usage

    if provider == "openai":
        api_key = (os.getenv("OPENAI_API_KEY") or "").strip()
        if not api_key:
            raise BundleGenerationError("OPENAI_API_KEY is missing.")
        url = question_bank._chat_completion_url("openai")
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        body = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        raw = _post_json(url, body=body, headers=headers, timeout_s=timeout_s, retry_transient=True)
        data = json.loads(raw)
        usage = _extract_usage_counts(data)
        trunc_reason = _detect_truncation_reason(data)
        if trunc_reason:
            raise LLMTruncatedError(
                f"LLM response truncated ({trunc_reason}) for model {model!r}.",
                finish_reason=trunc_reason,
                provider=provider,
                model=model,
                usage=usage,
            )
        return _extract_text_from_response(data), usage

    if provider == "ollama":
        base = question_bank._ollama_base_url()
        chat_url = f"{base}/api/chat"
        chat_body: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "stream": False,
            "options": {"temperature": temperature},
        }
        if expect_json:
            chat_body["format"] = "json"
        try:
            raw = _post_json(
                chat_url,
                body=chat_body,
                headers={"Content-Type": "application/json"},
                timeout_s=timeout_s,
            )
            data = json.loads(raw)
            usage = _extract_usage_counts(data)
            trunc_reason = _detect_truncation_reason(data)
            if trunc_reason:
                raise LLMTruncatedError(
                    f"LLM response truncated ({trunc_reason}) for model {model!r}.",
                    finish_reason=trunc_reason,
                    provider=provider,
                    model=model,
                    usage=usage,
                )
            return _extract_text_from_response(data), usage
        except urllib.error.HTTPError as exc:
            if exc.code != 404:
                raise
            prompt = "\n\n".join(
                f"{m.get('role', 'user').upper()}: {m.get('content', '')}"
                for m in messages
            )
            gen_url = f"{base}/api/generate"
            gen_body: dict[str, Any] = {
                "model": model,
                "prompt": prompt,
                "stream": False,
                "options": {"temperature": temperature},
            }
            if expect_json:
                gen_body["format"] = "json"
            raw = _post_json(
                gen_url,
                body=gen_body,
                headers={"Content-Type": "application/json"},
                timeout_s=timeout_s,
            )
            data = json.loads(raw)
            usage = _extract_usage_counts(data)
            trunc_reason = _detect_truncation_reason(data)
            if trunc_reason:
                raise LLMTruncatedError(
                    f"LLM response truncated ({trunc_reason}) for model {model!r}.",
                    finish_reason=trunc_reason,
                    provider=provider,
                    model=model,
                    usage=usage,
                )
            return _extract_text_from_response(data), usage

    raise BundleGenerationError(f"Unsupported LLM provider {provider!r}.")


def _post_json(
    url: str,
    *,
    body: dict[str, Any],
    headers: dict[str, str],
    timeout_s: int,
    retry_transient: bool = False,
) -> str:
    payload_bytes = json.dumps(body).encode("utf-8")
    ssl_ctx = _SSL_CTX if url.startswith("https://") else None
    backoffs = (0, 2, 4, 8, 16) if retry_transient else (0,)
    for attempt, delay_s in enumerate(backoffs):
        if delay_s > 0:
            time.sleep(delay_s)
        req = urllib.request.Request(
            url,
            data=payload_bytes,
            headers=headers,
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=timeout_s, context=ssl_ctx) as resp:
                return resp.read().decode("utf-8")
        except urllib.error.HTTPError as exc:
            try:
                raw_err = exc.read()
            except Exception:
                raw_err = b""
            if exc.code == 402:
                msg, credit_info = _parse_credit_error_body(raw_err)
                raise LLMCreditExhaustedError(
                    f"LLM credit exhausted (HTTP 402): {msg}",
                    status_code=402,
                    detail=msg,
                    credit_info=credit_info,
                ) from exc
            is_retryable = retry_transient and exc.code == 429
            if is_retryable and attempt + 1 < len(backoffs):
                continue
            raise urllib.error.HTTPError(
                exc.url, exc.code, exc.msg, exc.headers, io.BytesIO(raw_err)
            ) from exc
    raise BundleGenerationError("HTTP request retries exhausted.")


def _get_json(
    url: str,
    *,
    headers: dict[str, str] | None = None,
    timeout_s: int = 15,
) -> dict[str, Any]:
    ssl_ctx = _SSL_CTX if url.startswith("https://") else None
    req = urllib.request.Request(url, headers=headers or {}, method="GET")
    with urllib.request.urlopen(req, timeout=timeout_s, context=ssl_ctx) as resp:
        raw = resp.read().decode("utf-8")
    parsed = json.loads(raw)
    if not isinstance(parsed, dict):
        raise BundleGenerationError(f"Expected JSON object from GET {url}")
    return parsed


def fetch_openrouter_credits(
    *, api_key: str | None = None, timeout_s: int = 15
) -> dict[str, Any]:
    """Query OpenRouter GET /api/v1/key and /api/v1/credits without leaking secrets."""
    key = (api_key or os.getenv("OPENROUTER_API_KEY") or "").strip()
    if not key:
        raise BundleGenerationError("OPENROUTER_API_KEY is missing for pre-flight credit check.")
    headers = {"Authorization": f"Bearer {key}", "Accept": "application/json"}

    key_data: dict[str, Any] = {}
    credits_data: dict[str, Any] = {}
    errors: list[str] = []
    sources: list[str] = []

    try:
        key_resp = _get_json(OPENROUTER_KEY_URL, headers=headers, timeout_s=timeout_s)
        if isinstance(key_resp.get("data"), dict):
            key_data = key_resp["data"]
            sources.append("key")
    except urllib.error.HTTPError as exc:
        errors.append(f"/api/v1/key HTTP {exc.code}")
    except Exception as exc:
        errors.append(f"/api/v1/key error: {exc}")

    try:
        credits_resp = _get_json(OPENROUTER_CREDITS_URL, headers=headers, timeout_s=timeout_s)
        if isinstance(credits_resp.get("data"), dict):
            credits_data = credits_resp["data"]
            sources.append("credits")
    except urllib.error.HTTPError as exc:
        errors.append(f"/api/v1/credits HTTP {exc.code}")
    except Exception as exc:
        errors.append(f"/api/v1/credits error: {exc}")

    if not sources:
        raise BundleGenerationError(
            "Unable to query OpenRouter credit balance: " + "; ".join(errors)
        )

    def _opt_float(val: Any) -> float | None:
        if val is None or isinstance(val, bool):
            return None
        try:
            return float(val)
        except (TypeError, ValueError):
            return None

    key_limit = _opt_float(key_data.get("limit"))
    key_usage = _opt_float(key_data.get("usage"))
    key_limit_remaining = _opt_float(key_data.get("limit_remaining"))
    if key_limit_remaining is None and key_limit is not None and key_usage is not None:
        key_limit_remaining = key_limit - key_usage

    total_credits = _opt_float(credits_data.get("total_credits"))
    total_usage = _opt_float(credits_data.get("total_usage"))
    account_remaining = (
        total_credits - total_usage
        if total_credits is not None and total_usage is not None
        else None
    )

    candidates = [c for c in (key_limit_remaining, account_remaining) if c is not None]
    remaining_usd = min(candidates) if candidates else None

    return {
        "remaining_usd": remaining_usd,
        "key_limit": key_limit,
        "key_usage": key_usage,
        "key_limit_remaining": key_limit_remaining,
        "account_total_credits": total_credits,
        "account_total_usage": total_usage,
        "account_remaining": account_remaining,
        "is_free_tier": key_data.get("is_free_tier"),
        "label": key_data.get("label"),
        "sources": sources,
        "warnings": errors,
    }


def fetch_openrouter_model_pricing(
    model_id: str,
    *,
    api_key: str | None = None,
    timeout_s: int = 20,
) -> dict[str, Any]:
    """Fetch per-token pricing for ``model_id`` from OpenRouter GET /api/v1/models."""
    target = str(model_id or "").strip()
    if not target:
        raise BundleGenerationError("Model identifier is empty.")
    key = (api_key or os.getenv("OPENROUTER_API_KEY") or "").strip()
    headers = {"Accept": "application/json"}
    if key:
        headers["Authorization"] = f"Bearer {key}"

    resp = _get_json(OPENROUTER_MODELS_URL, headers=headers, timeout_s=timeout_s)
    models = resp.get("data")
    if not isinstance(models, list):
        raise BundleGenerationError("OpenRouter /api/v1/models returned invalid catalog format.")

    matched: dict[str, Any] | None = None
    target_cf = target.casefold()
    for entry in models:
        if not isinstance(entry, dict):
            continue
        eid = str(entry.get("id") or "").strip()
        if eid == target:
            matched = entry
            break
        if matched is None and eid.casefold() == target_cf:
            matched = entry

    if matched is None:
        raise BundleGenerationError(
            f"Model {target!r} was not found in OpenRouter /api/v1/models."
        )

    pricing = matched.get("pricing") if isinstance(matched.get("pricing"), dict) else {}

    def _price_float(val: Any) -> float:
        try:
            return max(0.0, float(val or 0.0))
        except (TypeError, ValueError):
            return 0.0

    return {
        "model": str(matched.get("id") or target),
        "prompt_per_token": _price_float(pricing.get("prompt")),
        "completion_per_token": _price_float(pricing.get("completion")),
        "request_cost": _price_float(pricing.get("request")),
        "context_length": matched.get("context_length"),
    }


def estimate_pregeneration_cost(
    *,
    planned_cells: list[dict[str, str]],
    force: bool = False,
    uncached_role_count: int = 0,
    gen_provider: str | None = None,
    gen_model: str | None = None,
    check_provider: str | None = None,
    check_model: str | None = None,
    credits_info: dict[str, Any] | None = None,
    pricing_by_model: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Estimate USD cost for uncached cells and compare against OpenRouter credit."""
    if gen_provider is None or gen_model is None:
        g_prov, g_mod = resolve_generation_provider_and_model()
        gen_provider = gen_provider or g_prov
        gen_model = gen_model or g_mod
    if check_provider is None or check_model is None:
        c_prov, c_mod = resolve_checker_provider_and_model()
        check_provider = check_provider or c_prov
        check_model = check_model or c_mod

    cached_done_count = 0
    pending_check_count = 0
    uncached_count = 0

    for cell in planned_cells:
        if force:
            uncached_count += 1
            continue
        canon_skill, _ = role_skills.resolve_skill_identity(cell["skill"], register=False)
        clean_topic = " ".join(str(cell["topic"] or "").strip().split()) or canon_skill
        norm_diff = normalize_difficulty(cell["difficulty"])
        cached = bundle_store.find_cached_bundle(
            skill=canon_skill,
            topic=clean_topic,
            difficulty=norm_diff,
            role=None,
        )
        if cached is None:
            uncached_count += 1
            continue
        attr = cached.get("attribution_json") or {}
        if cached.get("status") in {"reviewed", "auto_checked"} or attr.get("auto_check_ran"):
            cached_done_count += 1
        else:
            pending_check_count += 1

    uses_openrouter = gen_provider == "openrouter" or check_provider == "openrouter"
    pricing_cache: dict[str, dict[str, Any]] = dict(pricing_by_model or {})
    if uses_openrouter:
        if gen_provider == "openrouter" and gen_model not in pricing_cache:
            pricing_cache[gen_model] = fetch_openrouter_model_pricing(gen_model)
        if check_provider == "openrouter" and check_model not in pricing_cache:
            pricing_cache[check_model] = fetch_openrouter_model_pricing(check_model)

    if credits_info is None and uses_openrouter:
        credits_info = fetch_openrouter_credits()

    def _call_cost(
        provider: str,
        model: str,
        prompt_tokens: int,
        expected_completion: int,
        max_completion: int,
    ) -> tuple[float, float]:
        if provider != "openrouter":
            return 0.0, 0.0
        p = pricing_cache[model]
        exp = (
            prompt_tokens * p["prompt_per_token"]
            + expected_completion * p["completion_per_token"]
            + p.get("request_cost", 0.0)
        )
        worst = (
            prompt_tokens * p["prompt_per_token"]
            + max_completion * p["completion_per_token"]
            + p.get("request_cost", 0.0)
        )
        return exp, worst

    # Per-call token baselines matching Prompt A, Prompt B, and Step E.2 blind check
    gen_exp, gen_max = _call_cost(
        gen_provider, gen_model, 800, 1300, DEFAULT_GENERATION_MAX_TOKENS
    )
    chk_exp, chk_max = _call_cost(
        check_provider, check_model, 180, 240, DEFAULT_BLIND_CHECK_MAX_TOKENS
    )
    role_exp, role_max = _call_cost(
        gen_provider, gen_model, 500, 350, DEFAULT_PROMPT_A_MAX_TOKENS
    )

    expected_cost_usd = (
        uncached_count * (gen_exp + chk_exp)
        + pending_check_count * chk_exp
        + max(0, int(uncached_role_count)) * role_exp
    )
    max_cost_usd = (
        uncached_count * (gen_max + chk_max)
        + pending_check_count * chk_max
        + max(0, int(uncached_role_count)) * role_max
    )

    remaining_usd = credits_info.get("remaining_usd") if isinstance(credits_info, dict) else None
    if not uses_openrouter or max_cost_usd == 0.0:
        fits = True
    elif remaining_usd is None:
        fits = True
    else:
        fits = float(remaining_usd) >= float(max_cost_usd)

    return {
        "uses_openrouter": uses_openrouter,
        "gen_provider": gen_provider,
        "gen_model": gen_model,
        "check_provider": check_provider,
        "check_model": check_model,
        "planned_cells": len(planned_cells),
        "cached_cells": cached_done_count,
        "pending_check_cells": pending_check_count,
        "uncached_cells": uncached_count,
        "uncached_roles": max(0, int(uncached_role_count)),
        "calls_per_uncached_cell": 2,
        "estimated_calls": (
            uncached_count * 2 + pending_check_count + max(0, int(uncached_role_count))
        ),
        "expected_cost_usd": round(expected_cost_usd, 6),
        "max_cost_usd": round(max_cost_usd, 6),
        "remaining_usd": round(float(remaining_usd), 6) if remaining_usd is not None else None,
        "fits": fits,
        "pricing": pricing_cache,
        "credits": credits_info,
    }


def _call_bundle_llm(
    *,
    purpose: str,
    provider: str,
    model: str,
    messages: list[dict[str, str]],
    expect_json: bool = True,
    max_tokens: int = 2400,
    temperature: float = 0.25,
    timeout_s: int = DEFAULT_GENERATION_TIMEOUT_S,
    bundle_id: str | None = None,
    role: str | None = None,
    allow_live: bool | None = None,
) -> str:
    """Invoke override or HTTP LLM and log every call to ``llm_usage``."""
    t0 = time.monotonic()
    pt = ct = tt = 0
    status = "ok"
    err_msg: str | None = None
    routed = False
    try:
        consumers = llm_outbound_gate.llm_live_consumers()
        if consumers is not None and "questions" not in consumers:
            raise BundleGenerationError("LLM consumer questions is disabled.")
        if interview_llm.enabled():
            routed = True
            if allow_live is False and _LLM_OVERRIDE is None:
                raise BundleGenerationError("Live bundle dispatch was explicitly disabled.")
            def override(actual_model):
                return _invoke_override(
                    _LLM_OVERRIDE, purpose=purpose, provider="openrouter", model=actual_model,
                    messages=messages, max_tokens=max_tokens, temperature=temperature,
                )
            result = interview_llm.get_router().dispatch(
                purpose=purpose, messages=messages, max_tokens=max_tokens,
                temperature=temperature, timeout_s=timeout_s,
                override=override if _LLM_OVERRIDE is not None else None,
                expect_json=expect_json,
                bundle_id=bundle_id,
            )
            provider, model = "openrouter", result.model
            pt, ct, tt = result.usage
            return result.text
        if _LLM_OVERRIDE is not None:
            text, (pt, ct, tt) = _invoke_override(
                _LLM_OVERRIDE,
                purpose=purpose,
                provider=provider,
                model=model,
                messages=messages,
                max_tokens=max_tokens,
                temperature=temperature,
            )
            return text

        live_ok = (
            llm_outbound_gate.llm_live_fetch_enabled()
            if allow_live is None
            else bool(allow_live)
        )
        if not live_ok:
            raise BundleGenerationError(
                "LLM live fetch is disabled (set LLM_LIVE_FETCH=1 or pass allow_live=True)."
            )

        text, (pt, ct, tt) = _dial_http_llm(
            provider=provider,
            model=model,
            messages=messages,
            expect_json=expect_json,
            max_tokens=max_tokens,
            temperature=temperature,
            timeout_s=timeout_s,
        )
        return text
    except LLMTruncatedError as exc:
        status = "truncated"
        err_msg = str(exc)[:400]
        if getattr(exc, "usage", None):
            pt, ct, tt = exc.usage
        raise
    except LLMCreditExhaustedError as exc:
        status = "error"
        err_msg = str(exc)[:400]
        raise
    except urllib.error.HTTPError as exc:
        status = "error"
        try:
            detail = exc.read().decode("utf-8", errors="replace")[:300]
        except Exception:
            detail = str(exc)
        err_msg = f"HTTP {exc.code}: {detail}"
        raise BundleGenerationError(f"{purpose} failed: {err_msg}") from exc
    except Exception as exc:
        status = "error"
        err_msg = str(exc)[:400]
        if isinstance(exc, BundleGenerationError):
            raise
        raise BundleGenerationError(f"{purpose} failed: {err_msg}") from exc
    finally:
        latency_ms = max(0, int((time.monotonic() - t0) * 1000))
        try:
            if not routed:
                llm_usage.log_llm_usage(
                    provider=provider,
                    model=model,
                    purpose=purpose,
                    prompt_tokens=pt,
                    completion_tokens=ct,
                    total_tokens=tt,
                    latency_ms=latency_ms,
                    bundle_id=bundle_id,
                    role=role,
                    status=status,
                    error=err_msg,
                )
        except Exception as log_exc:  # pragma: no cover - defensive logging
            log.warning("Failed to log llm_usage (%s): %s", purpose, log_exc)


# ─── Prompt builders ──────────────────────────────────────────────────────────


def _build_prompt_b_messages(
    *,
    skill: str,
    topic: str,
    difficulty: str,
    role: str | None = None,
    validation_feedback: str | None = None,
) -> list[dict[str, str]]:
    role_ctx = f" for a {role!r} interview" if role else ""
    system_prompt = (
        "You are an expert technical interviewer and rubric author designing a "
        "concept-assessed technical short-answer question bundle in strict JSON.\n"
        "Follow EVERY rule carefully:\n"
        "1. Output ONLY valid JSON matching the schema below — no markdown fences, no commentary.\n"
        "2. question: 1-3 crisp, unambiguous interview sentences testing applied "
        "understanding of the skill/topic/difficulty (never trivial yes/no or generic "
        "benchmark wording).\n"
        "3. reference_answer: accurate, self-contained expert answer (80-160 words) "
        "that explicitly supports every required_concept.\n"
        "4. acceptable_variants: 1-2 short valid paraphrases.\n"
        "5. keywords: 4-7 concise technical domain terms.\n"
        "6. required_concepts (3-4 items) and optional_concepts (1-2 items): each has:\n"
        "   - id: short snake_case identifier (e.g. 'mutex_ownership')\n"
        "   - descriptor: clear 4-10 word description\n"
        "   - aliases: 2-4 synonymous surface terms\n"
        "   - expected_propositions: CRITICAL RULE FOR AUTOMATED CONCEPT SCORING: "
        "the evaluator extracts every token with length > 2 from each proposition and "
        "requires 100% of those words to co-occur inside a 25-token window, AND marks an "
        "answer contradicted if any negation word appears in the proposition match. "
        "Therefore, write 3-5 AFFIRMATIVE **2-word** key-term propositions per concept "
        "that any strong expert answer naturally states using standard domain terminology "
        "(e.g. 'parse json', 'request body', 'validate schema', 'status codes', 'segment customers'), "
        "avoid rare one-off function names in propositions unless required by the question, "
        "and NEVER include negation words (not, no, never, without, cannot) in expected_propositions.\n"
        "7. misconceptions (1-2 items): each has id (snake_case), description "
        "(phrased directly as the FALSE claim itself so a correct answer will not hit "
        "its tokens), and candidate_patterns (2-3 specific verbatim false-claim phrases "
        "a confused candidate writes, never appearing in a correct answer).\n"
        "8. depth_markers: 3-4 concise phrases showing deeper architectural/edge knowledge.\n"
        "9. rubric_descriptors: object with string keys 'coverage', 'accuracy', 'depth', 'clarity'.\n"
        "10. followups: EXACTLY 2 objects, each {'prompt': '...', 'targets_concept': '<id from required_concepts>'}.\n"
        "11. calibration_examples: EXACTLY 2 objects:\n"
        "   - Item 0 (Strong concise answer): author_level=3, expected_band='Good', "
        "at most 35 words (<= 35 words), accurately covering the core point.\n"
        "   - Item 1 (Verbose wrong/fluff answer): author_level=0, expected_band='Poor', "
        "at least 90 words (>= 90 words), rambling/off-point/wrong.\n"
        "12. Keep all JSON values crisp and compact so the full JSON fits easily within 1500 tokens."
    )
    user_lines = [
        f"Generate a complete question bundle JSON{role_ctx}:",
        f"- skill: {skill}",
        f"- topic: {topic}",
        f"- difficulty: {difficulty}",
        "",
        "Required top-level JSON keys:",
        "question, reference_answer, acceptable_variants, keywords, "
        "required_concepts, optional_concepts, misconceptions, depth_markers, "
        "rubric_descriptors, followups, calibration_examples",
    ]
    if validation_feedback:
        user_lines.extend(
            [
                "",
                "IMPORTANT — fix these validation/overlap failures from the previous attempt:",
                validation_feedback,
            ]
        )
    return [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": "\n".join(user_lines)},
    ]


def _build_blind_answer_messages(*, question: str, skill: str, difficulty: str) -> list[dict[str, str]]:
    system_prompt = (
        f"You are a strong senior candidate in {skill} answering an interview "
        "question concisely and accurately. Output ONLY plain prose (120-180 words) "
        "as a strong candidate would answer, with direct, affirmative explanations "
        "of concrete mechanisms, standard APIs/frameworks, tradeoffs, and practical execution."
    )
    user_prompt = (
        f"Skill: {skill}\n"
        f"Difficulty: {difficulty}\n"
        f"Interview Question: {question}\n\n"
        "Write a clear, thorough, direct affirmative 120-180 word expert interview "
        "answer as a strong candidate would answer, addressing every part of the question explicitly."
    )
    return [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]


def _build_audit_messages(
    *,
    content_json: dict[str, Any],
    blind_answer: str,
    eval_res: dict[str, Any],
) -> list[dict[str, str]]:
    missed = [
        c.get("concept_id")
        for c in (eval_res.get("concepts") or [])
        if c.get("state") != "supported"
    ]
    hit_misc = [
        m.get("id")
        for m in (eval_res.get("misconceptions") or [])
        if m.get("matched") and not m.get("refuted")
    ]
    system_prompt = (
        "You are auditing why an automated blind-answer check failed on a generated "
        "interview question bundle. Output ONLY JSON with keys: "
        "'root_cause' (string), 'issue_type' "
        "('propositions'|'question'|'misconceptions'|'reference'|'over_specific_concept'), "
        "'missed_concepts' (list[str]), 'fixes' (list[str] of concrete changes). "
        "Use 'over_specific_concept' when the blind answer is strong and accurate overall "
        "but missed a single overly narrow required concept that belongs as optional."
    )
    user_payload = {
        "question": content_json.get("question"),
        "reference_answer": content_json.get("reference_answer"),
        "required_concepts": content_json.get("required_concepts"),
        "misconceptions": content_json.get("misconceptions"),
        "blind_answer": blind_answer,
        "coverage": eval_res.get("coverage"),
        "assessable": eval_res.get("assessable"),
        "missed_or_uncertain_concepts": missed,
        "misconception_false_positives": hit_misc,
    }
    return [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": json.dumps(user_payload, ensure_ascii=False)},
    ]


def _build_regeneration_messages(
    *,
    skill: str,
    topic: str,
    difficulty: str,
    previous_content: dict[str, Any],
    blind_answer: str,
    eval_res: dict[str, Any],
    audit_diagnosis: dict[str, Any],
    role: str | None = None,
) -> list[dict[str, str]]:
    base = _build_prompt_b_messages(skill=skill, topic=topic, difficulty=difficulty, role=role)
    missed = [
        c.get("concept_id")
        for c in (eval_res.get("concepts") or [])
        if c.get("state") != "supported"
    ]
    hit_misc = [
        m.get("id")
        for m in (eval_res.get("misconceptions") or [])
        if m.get("matched") and not m.get("refuted")
    ]
    repair_note = {
        "previous_bundle": {
            k: previous_content.get(k)
            for k in (
                "question",
                "reference_answer",
                "required_concepts",
                "optional_concepts",
                "misconceptions",
                "followups",
                "calibration_examples",
            )
        },
        "blind_answer_excerpt": blind_answer[:700],
        "missed_concepts": missed,
        "misconception_hits": hit_misc,
        "audit_diagnosis": audit_diagnosis,
        "repair_rules": [
            "Keep expected_propositions short (2-4 content words each) and include synonymous variants matching how a strong engineer writes.",
            "Ensure the question explicitly asks for every required concept so a knowledgeable engineer does not omit one.",
            "Ensure misconception descriptions and candidate_patterns represent genuinely FALSE statements absent from a correct answer.",
            "Keep calibration_examples targets: author_level=3 expected_band='Good' (at most 35 words, <= 35 words) and author_level=0 expected_band='Poor' (at least 90 words, >= 90 words).",
        ],
    }
    base[1]["content"] += (
        "\n\nREGENERATION CONTEXT (fix the previous blind-check failure):\n"
        + json.dumps(repair_note, ensure_ascii=False)
    )
    return base


# ─── Normalization & Step E.1 code checks ─────────────────────────────────────


_PROP_NEGATION_RE = re.compile(
    r"\b(?:not|no|never|without|cannot|can't|cant|doesn't|doesnt|isn't|isnt|aren't|arent)\b",
    re.IGNORECASE,
)


def _clean_proposition(raw_prop: str) -> str:
    cleaned = _PROP_NEGATION_RE.sub(" ", str(raw_prop or ""))
    cleaned = " ".join(cleaned.strip().strip(",.;:-").split())
    if not cleaned:
        return ""
    words = cleaned.split()
    content_words = [w for w in words if len(re.sub(r"[^A-Za-z0-9_]", "", w)) > 2]
    if 2 <= len(content_words) <= 4:
        return " ".join(content_words)
    if len(content_words) > 4:
        return " ".join(content_words[:4])
    return cleaned


def _normalize_concepts(raw_list: Any) -> list[dict[str, Any]]:
    if not isinstance(raw_list, list):
        return []
    out: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    for idx, item in enumerate(raw_list):
        if not isinstance(item, dict):
            continue
        desc = str(item.get("descriptor") or item.get("description") or "").strip()
        cid = _slug_underscore(str(item.get("id") or desc or f"concept_{idx + 1}"))
        if cid in seen_ids:
            cid = f"{cid}_{idx + 1}"
        seen_ids.add(cid)
        aliases = [str(a).strip() for a in (item.get("aliases") or []) if str(a).strip()]
        props: list[str] = []
        seen_props: set[str] = set()
        for raw_p in (item.get("expected_propositions") or []):
            s = str(raw_p).strip()
            if not s:
                continue
            cleaned = _clean_proposition(s)
            candidate = cleaned or " ".join(_PROP_NEGATION_RE.sub(" ", s).split())
            if candidate and candidate.lower() not in seen_props:
                seen_props.add(candidate.lower())
                props.append(candidate)
        out.append(
            {
                "id": cid,
                "descriptor": desc,
                "aliases": aliases,
                "expected_propositions": props,
            }
        )
    return out


def _normalize_misconceptions(raw_list: Any) -> list[dict[str, Any]]:
    if not isinstance(raw_list, list):
        return []
    out: list[dict[str, Any]] = []
    for idx, item in enumerate(raw_list):
        if not isinstance(item, dict):
            continue
        desc = str(item.get("description") or item.get("descriptor") or "").strip()
        mid = _slug_underscore(str(item.get("id") or desc or f"misconception_{idx + 1}"))
        patterns = [
            str(p).strip()
            for p in (item.get("candidate_patterns") or [])
            if str(p).strip()
        ]
        out.append(
            {
                "id": mid,
                "description": desc,
                "candidate_patterns": patterns,
            }
        )
    return out


def _normalize_followups(raw_list: Any, required_ids: list[str]) -> list[dict[str, str]]:
    if not isinstance(raw_list, list):
        return []
    id_map = {rid.lower(): rid for rid in required_ids}
    out: list[dict[str, str]] = []
    for item in raw_list:
        if isinstance(item, dict):
            prompt = str(item.get("prompt") or "").strip()
            tc_raw = str(item.get("targets_concept") or "").strip()
            tc_slug = _slug_underscore(tc_raw) if tc_raw else ""
            tc = id_map.get(tc_raw.lower()) or id_map.get(tc_slug.lower()) or tc_raw
            out.append({"prompt": prompt, "targets_concept": tc})
    return out


def _normalize_calibration_examples(raw_list: Any) -> list[dict[str, Any]]:
    """Normalize calibration examples without truncating or padding answers."""
    if not isinstance(raw_list, list):
        return []
    band_map = {"good": "Good", "poor": "Poor", "partial": "Partial", "excellent": "Good"}
    out: list[dict[str, Any]] = []
    for item in raw_list:
        if not isinstance(item, dict):
            continue
        lvl = item.get("author_level")
        if isinstance(lvl, str) and lvl.strip().isdigit():
            lvl = int(lvl.strip())
        raw_band = str(item.get("expected_band") or "").strip()
        band = band_map.get(raw_band.lower(), raw_band)
        ans = str(item.get("answer") or "").strip()
        words, usable, reason = evaluate_calibration_length_bias(ans, lvl, band)
        entry: dict[str, Any] = {
            "answer": ans,
            "author_level": lvl,
            "expected_band": band,
            "word_count": words,
        }
        if usable is not None:
            entry["length_bias_usable"] = usable
            if reason is not None:
                entry["length_bias_unusable_reason"] = reason
        out.append(entry)
    return out


def _assemble_and_validate_doc(
    *,
    raw_payload: dict[str, Any],
    bundle_id: str,
    version: int,
    canonical_skill: str,
    canonical_topic: str,
    difficulty: str,
    model: str,
    provider: str,
    role: str | None,
    extra_attribution: dict[str, Any] | None = None,
) -> tuple[dict[str, Any], list[str]]:
    """Construct full YAML-v2 dict and run Step E.1 schema + overlap checks."""
    req_concepts = _normalize_concepts(raw_payload.get("required_concepts"))
    req_ids = [c["id"] for c in req_concepts]
    rubric = raw_payload.get("rubric_descriptors")
    rubric_clean = (
        {str(k): str(v).strip() for k, v in rubric.items() if str(v).strip()}
        if isinstance(rubric, dict)
        else {}
    )
    attribution: dict[str, Any] = {
        "roles": [role] if role else [],
        "generated_by_model": model,
        "generated_by_provider": provider,
        "ws": "ws2",
    }
    if extra_attribution:
        attribution.update(extra_attribution)

    doc: dict[str, Any] = {
        "schema_version": 2,
        "bundle_id": bundle_id,
        "version": int(version),
        "category": DEFAULT_CATEGORY,
        "skill": canonical_skill,
        "topic": canonical_topic,
        "difficulty": difficulty,
        "question": str(raw_payload.get("question") or "").strip(),
        "reference_answer": str(raw_payload.get("reference_answer") or "").strip(),
        "acceptable_variants": [
            str(v).strip()
            for v in (raw_payload.get("acceptable_variants") or [])
            if str(v).strip()
        ],
        "keywords": [
            str(k).strip()
            for k in (raw_payload.get("keywords") or [])
            if str(k).strip()
        ],
        "required_concepts": req_concepts,
        "optional_concepts": _normalize_concepts(raw_payload.get("optional_concepts")),
        "misconceptions": _normalize_misconceptions(raw_payload.get("misconceptions")),
        "depth_markers": [
            str(d).strip()
            for d in (raw_payload.get("depth_markers") or [])
            if str(d).strip()
        ],
        "rubric_descriptors": rubric_clean,
        "followups": _normalize_followups(raw_payload.get("followups"), req_ids),
        "calibration_examples": _normalize_calibration_examples(
            raw_payload.get("calibration_examples")
        ),
        "source": "llm_draft",
        "author": f"llm:{model}",
        "attribution": attribution,
    }

    # Step E.1: schema validation
    validate_generated_bundle_doc(doc)

    # Step E.1: evaluation overlap guard
    overlap = check_overlap(doc["question"])
    if overlap.get("exact"):
        hits = ", ".join(
            f"{h.get('source')}#{h.get('item_id')}" for h in overlap["exact"]
        )
        raise BundleContentError(f"evaluation overlap (exact): {hits}")

    paraphrase_hits: list[str] = []
    if overlap.get("paraphrase"):
        paraphrase_hits = [
            f"{h.get('source')}#{h.get('item_id')} (jaccard {h.get('jaccard')})"
            for h in overlap["paraphrase"]
        ]
        doc["attribution"]["evaluation_overlap"] = {"paraphrase": paraphrase_hits}

    return doc, paraphrase_hits


def _generate_validated_doc(
    *,
    bundle_id: str,
    version: int,
    canonical_skill: str,
    canonical_topic: str,
    difficulty: str,
    gen_provider: str,
    gen_model: str,
    role: str | None,
    allow_live: bool | None,
) -> tuple[dict[str, Any], list[str]]:
    """Call Prompt B and run Step E.1, with one schema/overlap feedback retry."""
    last_err: Exception | None = None
    feedback: str | None = None
    for attempt in range(2):
        messages = _build_prompt_b_messages(
            skill=canonical_skill,
            topic=canonical_topic,
            difficulty=difficulty,
            role=role,
            validation_feedback=feedback,
        )
        raw_text = _call_bundle_llm(
            purpose="bundle_generation",
            provider=gen_provider,
            model=gen_model,
            messages=messages,
            expect_json=True,
            max_tokens=2200,
            temperature=0.25 if attempt == 0 else 0.15,
            bundle_id=bundle_id,
            role=role,
            allow_live=allow_live,
        )
        try:
            raw_payload = _parse_json_object(raw_text)
            return _assemble_and_validate_doc(
                raw_payload=raw_payload,
                bundle_id=bundle_id,
                version=version,
                canonical_skill=canonical_skill,
                canonical_topic=canonical_topic,
                difficulty=difficulty,
                model=interview_llm.actual_model("bundle_generation", gen_model),
                provider=gen_provider,
                role=role,
            )
        except (BundleContentError, BundleGenerationError) as exc:
            last_err = exc
            feedback = str(exc)
    raise BundleGenerationError(
        f"Bundle failed Step E.1 validation after retry: {last_err}"
    )


# ─── Step E.2 & Step E.3 automated checking ──────────────────────────────────


def resolve_rejected_audit_path(explicit_path: Path | str | None = None) -> Path:
    """Resolve the JSONL path where genuinely rejected bundles are audited."""
    if explicit_path is not None and str(explicit_path).strip():
        return Path(explicit_path)
    env_path = (os.getenv("REJECTED_BUNDLES_AUDIT_PATH") or "").strip()
    if env_path:
        return Path(env_path)
    return _DEFAULT_REJECTED_AUDIT_PATH


def resolve_demoted_audit_path(explicit_path: Path | str | None = None) -> Path:
    """Resolve the JSONL path where Step E.3 demoted concepts are audited."""
    if explicit_path is not None and str(explicit_path).strip():
        return Path(explicit_path)
    env_path = (os.getenv("DEMOTED_BUNDLES_AUDIT_PATH") or "").strip()
    if env_path:
        return Path(env_path)
    return _DEFAULT_DEMOTED_AUDIT_PATH


def _append_jsonl_record(target: Path, record: dict[str, Any]) -> Path:
    line = json.dumps(record, ensure_ascii=False)
    with _AUDIT_FILE_LOCK:
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("a", encoding="utf-8") as fh:
            fh.write(line + "\n")
    return target


def _build_missed_concept_records(
    content_json: dict[str, Any], missed_ids: list[str]
) -> list[dict[str, str]]:
    by_id = {
        str(c.get("id")): c
        for c in (content_json.get("required_concepts") or [])
        if isinstance(c, dict) and c.get("id")
    }
    records: list[dict[str, str]] = []
    for cid in missed_ids:
        entry = by_id.get(str(cid), {})
        desc = str(entry.get("descriptor") or entry.get("description") or "").strip()
        label = str(entry.get("label") or desc or cid).strip()
        records.append(
            {
                "id": str(cid),
                "label": label,
                "descriptor": desc or label,
            }
        )
    return records


def _build_demoted_concept_details(
    content_json: dict[str, Any], missed_id: str
) -> dict[str, Any]:
    entry = next(
        (
            c
            for c in (content_json.get("required_concepts") or [])
            if isinstance(c, dict) and str(c.get("id")) == str(missed_id)
        ),
        {},
    )
    desc = str(entry.get("descriptor") or entry.get("description") or "").strip()
    label = str(entry.get("label") or desc or missed_id).strip()
    return {
        "id": str(missed_id),
        "label": label,
        "descriptor": desc or label,
        "aliases": list(entry.get("aliases") or []),
        "expected_propositions": list(entry.get("expected_propositions") or []),
    }


def _append_rejected_bundle_audit(
    *,
    audit_path: Path | str | None,
    bundle_id: str,
    version: int,
    stage: str,
    canonical_skill: str,
    canonical_topic: str,
    difficulty: str,
    content_json: dict[str, Any],
    missed_ids: list[str],
    hits: list[str],
    blind_answer: str,
    failure_reason: str,
    audit_diag: dict[str, Any] | None,
) -> Path:
    """Append a structured JSONL audit record for a genuinely rejected bundle."""
    target = resolve_rejected_audit_path(audit_path)
    record = {
        "bundle_id": bundle_id,
        "version": int(version),
        "stage": stage,
        "skill": canonical_skill,
        "skill_slug": safe_slug(canonical_skill, 32),
        "topic": canonical_topic,
        "topic_slug": safe_slug(canonical_topic, 32),
        "difficulty": difficulty,
        "question": str(content_json.get("question") or ""),
        "missed_concepts": _build_missed_concept_records(content_json, missed_ids),
        "misconception_hits": list(hits),
        "blind_answer": blind_answer,
        "failure_reason": failure_reason,
        "audit": audit_diag,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    return _append_jsonl_record(target, record)


def _append_demoted_concept_audit(
    *,
    audit_path: Path | str | None,
    bundle_id: str,
    from_version: int,
    to_version: int,
    canonical_skill: str,
    canonical_topic: str,
    difficulty: str,
    content_json: dict[str, Any],
    demoted_concept: str,
    blind_answer: str,
    audit_reason: str,
    audit_diag: dict[str, Any] | None,
) -> Path:
    """Append a structured JSONL audit record whenever Step E.3 demotes a concept."""
    target = resolve_demoted_audit_path(audit_path)
    record = {
        "bundle_id": bundle_id,
        "from_version": int(from_version),
        "to_version": int(to_version),
        "skill": canonical_skill,
        "skill_slug": safe_slug(canonical_skill, 32),
        "topic": canonical_topic,
        "topic_slug": safe_slug(canonical_topic, 32),
        "difficulty": difficulty,
        "question": str(content_json.get("question") or ""),
        "demoted_concept": str(demoted_concept),
        "missed_concept_details": _build_demoted_concept_details(
            content_json, demoted_concept
        ),
        "blind_answer": blind_answer,
        "audit_reason": audit_reason,
        "audit": audit_diag,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    return _append_jsonl_record(target, record)


def _score_with_concept_evaluator(
    *,
    answer_text: str,
    bundle_content: dict[str, Any],
    bundle_content_hash: str | None,
) -> dict[str, Any]:
    """Run the configured Step E concept evaluator (v3)."""
    return concept_evaluator_v3.evaluate_answer(
        answer_text=answer_text,
        bundle_content=bundle_content,
        bundle_content_hash=bundle_content_hash,
    )


def _evaluate_blind_answer(
    *,
    stored_version: dict[str, Any],
    canonical_skill: str,
    difficulty: str,
    check_provider: str,
    check_model: str,
    bundle_id: str,
    role: str | None,
    allow_live: bool | None,
) -> tuple[str, dict[str, Any], bool, list[str]]:
    content = stored_version["content_json"]
    messages = _build_blind_answer_messages(
        question=str(content["question"]),
        skill=canonical_skill,
        difficulty=difficulty,
    )
    blind_answer = _call_bundle_llm(
        purpose="bundle_blind_answer",
        provider=check_provider,
        model=check_model,
        messages=messages,
        expect_json=False,
        max_tokens=DEFAULT_BLIND_CHECK_MAX_TOKENS,
        temperature=0.2,
        timeout_s=DEFAULT_BLIND_CHECK_TIMEOUT_S,
        bundle_id=bundle_id,
        role=role,
        allow_live=allow_live,
    )
    eval_res = _score_with_concept_evaluator(
        answer_text=blind_answer,
        bundle_content=content,
        bundle_content_hash=stored_version["content_hash"],
    )
    coverage = eval_res.get("coverage") or {}
    k_sup = int(coverage.get("k_supported") or 0)
    n_req = int(coverage.get("n_required") or 0)
    hits = [
        str(m.get("id"))
        for m in (eval_res.get("misconceptions") or [])
        if m.get("matched") and not m.get("refuted")
    ]
    passed = bool(eval_res.get("assessable")) and n_req > 0 and k_sup == n_req and not hits
    return blind_answer, eval_res, passed, hits


def _build_demoted_bundle_doc(
    *,
    stored_version: dict[str, Any],
    missed_id: str,
    next_version: int,
    gen_model: str,
) -> dict[str, Any]:
    """Move a single over-specific required concept into optional_concepts."""
    content = copy.deepcopy(stored_version["content_json"])
    req_list = [c for c in (content.get("required_concepts") or []) if isinstance(c, dict)]
    demoted_entry: dict[str, Any] | None = None
    remaining_req: list[dict[str, Any]] = []
    for entry in req_list:
        if entry.get("id") == missed_id and demoted_entry is None:
            demoted_entry = copy.deepcopy(entry)
        else:
            remaining_req.append(entry)

    if demoted_entry is None or len(remaining_req) < 2:
        raise BundleContentError(
            f"Cannot demote {missed_id!r}: requires >= 2 remaining required concepts."
        )

    opt_list = [c for c in (content.get("optional_concepts") or []) if isinstance(c, dict)]
    if not any(c.get("id") == missed_id for c in opt_list):
        opt_list.append(demoted_entry)

    content["required_concepts"] = remaining_req
    content["optional_concepts"] = opt_list

    remaining_ids = [str(c.get("id")) for c in remaining_req if c.get("id")]
    followups = [copy.deepcopy(f) for f in (content.get("followups") or []) if isinstance(f, dict)]
    already_targeted = {
        str(f.get("targets_concept"))
        for f in followups
        if f.get("targets_concept") in remaining_ids
    }
    for fu in followups:
        if fu.get("targets_concept") == missed_id:
            replacement = next(
                (rid for rid in remaining_ids if rid not in already_targeted),
                remaining_ids[0],
            )
            fu["targets_concept"] = replacement
            already_targeted.add(replacement)
    content["followups"] = followups

    base_attr = {
        k: copy.deepcopy(v)
        for k, v in (stored_version.get("attribution_json") or {}).items()
        if k not in {"auto_check_ran", "auto_check"}
    }
    base_attr.update(
        {
            "demoted_from_version": int(stored_version["version"]),
            "demoted_concept": missed_id,
            "auto_check_demotion": True,
        }
    )
    demoted_doc: dict[str, Any] = {
        **content,
        "version": int(next_version),
        "source": str(stored_version.get("source") or "llm_draft"),
        "author": str(stored_version.get("author_id") or f"llm:{gen_model}"),
        "attribution": base_attr,
    }
    validate_generated_bundle_doc(demoted_doc)
    return demoted_doc


def _run_step_e_for_version(
    *,
    stored_version: dict[str, Any],
    canonical_skill: str,
    canonical_topic: str,
    difficulty: str,
    role: str | None,
    gen_provider: str,
    gen_model: str,
    check_provider: str,
    check_model: str,
    allow_live: bool | None,
    cache_hit: bool,
    rejected_audit_path: Path | str | None = None,
    demoted_audit_path: Path | str | None = None,
) -> dict[str, Any]:
    bundle_id = str(stored_version["bundle_id"])
    version = int(stored_version["version"])

    blind_answer, eval_res, passed, hits = _evaluate_blind_answer(
        stored_version=stored_version,
        canonical_skill=canonical_skill,
        difficulty=difficulty,
        check_provider=check_provider,
        check_model=check_model,
        bundle_id=bundle_id,
        role=role,
        allow_live=allow_live,
    )
    check_model = interview_llm.actual_model("bundle_blind_answer", check_model)
    coverage = eval_res.get("coverage") or {}
    evaluator_version = str(eval_res.get("evaluator_version") or "unknown")
    if passed:
        updated = bundle_store.transition_automated_check(
            bundle_id,
            version,
            to_status="auto_checked",
            reason=(
                "Blind answer covered all required concepts with zero "
                "misconceptions."
            ),
            check_meta={
                "check_model": check_model,
                "check_provider": check_provider,
                "evaluator_version": evaluator_version,
                "blind_answer_words": len(blind_answer.split()),
                "coverage": coverage,
                "misconception_hits": hits,
                "retried": False,
            },
        )
        return {
            "bundle_id": bundle_id,
            "version": updated["version"],
            "status": updated["status"],
            "skill": canonical_skill,
            "topic": canonical_topic,
            "difficulty": difficulty,
            "bundle": updated,
            "cache_hit": cache_hit,
            "auto_check_ran": True,
            "step_e_passed": True,
            "retried": False,
            "blind_eval": eval_res,
            "audit": None,
        }

    # Step E.3: single audit + demotion (if single over-specific concept) or single regeneration
    audit_raw = _call_bundle_llm(
        purpose="bundle_check_audit",
        provider=check_provider,
        model=check_model,
        messages=_build_audit_messages(
            content_json=stored_version["content_json"],
            blind_answer=blind_answer,
            eval_res=eval_res,
        ),
        expect_json=True,
        max_tokens=DEFAULT_AUDIT_MAX_TOKENS,
        temperature=0.15,
        timeout_s=DEFAULT_BLIND_CHECK_TIMEOUT_S,
        bundle_id=bundle_id,
        role=role,
        allow_live=allow_live,
    )
    try:
        audit_diag = _parse_json_object(audit_raw)
    except BundleGenerationError:
        audit_diag = {"raw": audit_raw[:400]}

    missed_ids = [
        str(c.get("concept_id"))
        for c in (eval_res.get("concepts") or [])
        if c.get("state") != "supported"
    ]
    req_concepts = list((stored_version.get("content_json") or {}).get("required_concepts") or [])
    can_demote = (
        not hits
        and len(missed_ids) == 1
        and len(req_concepts) >= 3
        and str(audit_diag.get("issue_type") or "").strip().lower() == "over_specific_concept"
    )
    if can_demote:
        missed_id = missed_ids[0]
        existing_all = bundle_store.list_versions(bundle_id=bundle_id)
        next_version = max((int(v["version"]) for v in existing_all), default=version) + 1
        try:
            demoted_doc = _build_demoted_bundle_doc(
                stored_version=stored_version,
                missed_id=missed_id,
                next_version=next_version,
                gen_model=gen_model,
            )
            bundle_store.transition_automated_check(
                bundle_id,
                version,
                to_status="rejected",
                reason=(
                    f"Superseded by v{next_version}: demoted over-specific required "
                    f"concept {missed_id!r} to optional (no regeneration)."
                ),
                check_meta={
                    "check_model": check_model,
                    "check_provider": check_provider,
                    "evaluator_version": evaluator_version,
                    "blind_answer_words": len(blind_answer.split()),
                    "coverage": coverage,
                    "missed_concepts": missed_ids,
                    "misconception_hits": hits,
                    "audit": audit_diag,
                    "demoted_concept": missed_id,
                    "demoted_to_version": next_version,
                    "retried": False,
                },
            )
            demote_audit_reason = (
                f"Step E.3 over-specific concept demotion from v{version} ({missed_id})"
            )
            stored_demoted = bundle_store.import_bundle(
                demoted_doc,
                actor_id="bundle_generator",
                initial_status="generated",
                audit_reason=demote_audit_reason,
            )["version"]
            demoted_eval = _score_with_concept_evaluator(
                answer_text=blind_answer,
                bundle_content=stored_demoted["content_json"],
                bundle_content_hash=stored_demoted["content_hash"],
            )
            demoted_cov = demoted_eval.get("coverage") or {}
            final_demoted = bundle_store.transition_automated_check(
                bundle_id,
                stored_demoted["version"],
                to_status="auto_checked",
                reason=(
                    f"Blind answer passed after demoting over-specific required "
                    f"concept {missed_id!r} to optional."
                ),
                check_meta={
                    "check_model": check_model,
                    "check_provider": check_provider,
                    "evaluator_version": str(demoted_eval.get("evaluator_version") or evaluator_version),
                    "blind_answer_words": len(blind_answer.split()),
                    "coverage": demoted_cov,
                    "original_coverage": coverage,
                    "misconception_hits": hits,
                    "audit": audit_diag,
                    "demoted_concept": missed_id,
                    "demoted_from_version": version,
                    "auto_check_demotion": True,
                    "retried": False,
                },
            )
            _append_demoted_concept_audit(
                audit_path=demoted_audit_path,
                bundle_id=bundle_id,
                from_version=version,
                to_version=final_demoted["version"],
                canonical_skill=canonical_skill,
                canonical_topic=canonical_topic,
                difficulty=difficulty,
                content_json=stored_version["content_json"],
                demoted_concept=missed_id,
                blind_answer=blind_answer,
                audit_reason=demote_audit_reason,
                audit_diag=audit_diag,
            )
            return {
                "bundle_id": bundle_id,
                "version": final_demoted["version"],
                "status": final_demoted["status"],
                "skill": canonical_skill,
                "topic": canonical_topic,
                "difficulty": difficulty,
                "bundle": final_demoted,
                "cache_hit": cache_hit,
                "auto_check_ran": True,
                "step_e_passed": True,
                "retried": False,
                "demoted_concept": missed_id,
                "blind_eval": demoted_eval,
                "audit": audit_diag,
            }
        except (BundleContentError, BundleStoreError) as exc:
            log.warning(
                "Concept demotion failed for %s v%s (%s); falling back to regeneration.",
                bundle_id,
                version,
                exc,
            )

    fail_reason = (
        f"Blind check failed ({coverage.get('k_supported', 0)}/"
        f"{coverage.get('n_required', 0)} concepts supported; "
        f"missed={missed_ids}; misconceptions={hits})."
    )
    rejected_v1 = bundle_store.transition_automated_check(
        bundle_id,
        version,
        to_status="rejected",
        reason=fail_reason,
        check_meta={
            "check_model": check_model,
            "check_provider": check_provider,
            "evaluator_version": evaluator_version,
            "coverage": coverage,
            "missed_concepts": missed_ids,
            "misconception_hits": hits,
            "audit": audit_diag,
            "retried": False,
        },
    )
    _append_rejected_bundle_audit(
        audit_path=rejected_audit_path,
        bundle_id=bundle_id,
        version=version,
        stage="initial",
        canonical_skill=canonical_skill,
        canonical_topic=canonical_topic,
        difficulty=difficulty,
        content_json=stored_version["content_json"],
        missed_ids=missed_ids,
        hits=hits,
        blind_answer=blind_answer,
        failure_reason=fail_reason,
        audit_diag=audit_diag,
    )

    regen_raw = _call_bundle_llm(
        purpose="bundle_regeneration",
        provider=gen_provider,
        model=gen_model,
        messages=_build_regeneration_messages(
            skill=canonical_skill,
            topic=canonical_topic,
            difficulty=difficulty,
            previous_content=stored_version["content_json"],
            blind_answer=blind_answer,
            eval_res=eval_res,
            audit_diagnosis=audit_diag,
            role=role,
        ),
        expect_json=True,
        max_tokens=DEFAULT_GENERATION_MAX_TOKENS,
        temperature=0.2,
        bundle_id=bundle_id,
        role=role,
        allow_live=allow_live,
    )
    existing_all = bundle_store.list_versions(bundle_id=bundle_id)
    next_version = max((int(v["version"]) for v in existing_all), default=version) + 1
    try:
        regen_payload = _parse_json_object(regen_raw)
        regen_doc, _ = _assemble_and_validate_doc(
            raw_payload=regen_payload,
            bundle_id=bundle_id,
            version=next_version,
            canonical_skill=canonical_skill,
            canonical_topic=canonical_topic,
            difficulty=difficulty,
            model=interview_llm.actual_model("bundle_regeneration", gen_model),
            provider=gen_provider,
            role=role,
            extra_attribution={"retried_from_version": version},
        )
    except (BundleContentError, BundleGenerationError) as exc:
        raise BundleGenerationError(
            f"Regenerated bundle {bundle_id} v{next_version} failed Step E.1: {exc}"
        ) from exc

    try:
        stored_retry = bundle_store.import_bundle(
            regen_doc,
            actor_id="bundle_generator",
            initial_status="generated",
            audit_reason=f"Step E.3 regeneration from v{version}",
        )["version"]
    except BundleStoreError as exc:
        if getattr(exc, "code", getattr(exc, "kind", None)) == "conflict":
            log.warning(
                "Regenerated bundle %s produced identical content to existing version: %s",
                bundle_id,
                exc,
            )
            return {
                "bundle_id": bundle_id,
                "version": rejected_v1["version"],
                "status": rejected_v1["status"],
                "skill": canonical_skill,
                "topic": canonical_topic,
                "difficulty": difficulty,
                "bundle": rejected_v1,
                "cache_hit": False,
                "auto_check_ran": True,
                "step_e_passed": False,
                "retried": True,
                "blind_eval": eval_res,
                "audit": {**(audit_diag or {}), "regeneration_conflict": str(exc)},
            }
        raise

    blind2, eval2, passed2, hits2 = _evaluate_blind_answer(
        stored_version=stored_retry,
        canonical_skill=canonical_skill,
        difficulty=difficulty,
        check_provider=check_provider,
        check_model=check_model,
        bundle_id=bundle_id,
        role=role,
        allow_live=allow_live,
    )
    cov2 = eval2.get("coverage") or {}
    eval2_ver = str(eval2.get("evaluator_version") or "unknown")
    missed2 = [
        str(c.get("concept_id"))
        for c in (eval2.get("concepts") or [])
        if c.get("state") != "supported"
    ]
    if passed2:
        final_v = bundle_store.transition_automated_check(
            bundle_id,
            stored_retry["version"],
            to_status="auto_checked",
            reason="Regenerated bundle passed Step E.2 blind answer check.",
            check_meta={
                "check_model": check_model,
                "check_provider": check_provider,
                "evaluator_version": eval2_ver,
                "blind_answer_words": len(blind2.split()),
                "coverage": cov2,
                "misconception_hits": hits2,
                "audit": audit_diag,
                "retried": True,
                "retried_from_version": version,
            },
        )
    else:
        fail_reason2 = (
            f"Blind check failed after regeneration ({cov2.get('k_supported', 0)}/"
            f"{cov2.get('n_required', 0)} concepts; missed={missed2}; "
            f"misconceptions={hits2})."
        )
        final_v = bundle_store.transition_automated_check(
            bundle_id,
            stored_retry["version"],
            to_status="rejected",
            reason=fail_reason2,
            check_meta={
                "check_model": check_model,
                "check_provider": check_provider,
                "evaluator_version": eval2_ver,
                "blind_answer_words": len(blind2.split()),
                "coverage": cov2,
                "missed_concepts": missed2,
                "misconception_hits": hits2,
                "audit": audit_diag,
                "retried": True,
                "retried_from_version": version,
            },
        )
        _append_rejected_bundle_audit(
            audit_path=rejected_audit_path,
            bundle_id=bundle_id,
            version=stored_retry["version"],
            stage="regeneration",
            canonical_skill=canonical_skill,
            canonical_topic=canonical_topic,
            difficulty=difficulty,
            content_json=stored_retry["content_json"],
            missed_ids=missed2,
            hits=hits2,
            blind_answer=blind2,
            failure_reason=fail_reason2,
            audit_diag=audit_diag,
        )

    return {
        "bundle_id": bundle_id,
        "version": final_v["version"],
        "status": final_v["status"],
        "skill": canonical_skill,
        "topic": canonical_topic,
        "difficulty": difficulty,
        "bundle": final_v,
        "cache_hit": False,
        "auto_check_ran": True,
        "step_e_passed": passed2,
        "retried": True,
        "blind_eval": eval2,
        "audit": audit_diag,
    }


# ─── Public API ───────────────────────────────────────────────────────────────


def generate_and_check_bundle(
    *,
    skill: str,
    topic: str,
    difficulty: str,
    role: str | None = None,
    allow_live: bool | None = None,
    force: bool = False,
    rejected_audit_path: Path | str | None = None,
    demoted_audit_path: Path | str | None = None,
) -> dict[str, Any]:
    """Generate (or return cached) concept-assessed bundle + run Step E check.

    Rule ('Never regenerate', Change C):
    - Resolves canonical skill via ``role_skills.resolve_skill_identity``.
    - Checks ``bundle_store.find_cached_bundle`` unless ``force=True``.
    - If a reviewed or already auto-checked bundle exists, returns it immediately
      with ``cache_hit=True`` and zero LLM calls.
    - If an unchecked ``generated`` bundle exists, runs Step E verification on it
      instead of regenerating from scratch.
    """
    canonical_skill, _ = role_skills.resolve_skill_identity(skill, register=True)
    norm_diff = normalize_difficulty(difficulty)
    clean_topic = " ".join(str(topic or "").strip().split()) or canonical_skill
    clean_role = " ".join(str(role or "").strip().split()) or None

    gen_provider, gen_model = resolve_generation_provider_and_model()
    check_provider, check_model = resolve_checker_provider_and_model()

    if not force:
        cached = bundle_store.find_cached_bundle(
            skill=canonical_skill,
            topic=clean_topic,
            difficulty=norm_diff,
            role=clean_role,
        )
        if cached is not None:
            attr = cached.get("attribution_json") or {}
            status = str(cached.get("status") or "")
            auto_ran = bool(attr.get("auto_check_ran"))
            if status in {"reviewed", "auto_checked"} or auto_ran:
                return {
                    "bundle_id": cached["bundle_id"],
                    "version": cached["version"],
                    "status": status,
                    "skill": canonical_skill,
                    "topic": (cached.get("content_json") or {}).get("topic") or clean_topic,
                    "difficulty": cached.get("difficulty") or norm_diff,
                    "bundle": cached,
                    "cache_hit": True,
                    "auto_check_ran": auto_ran,
                    "step_e_passed": status in {"reviewed", "auto_checked"},
                    "retried": bool((attr.get("auto_check") or {}).get("retried")),
                    "blind_eval": None,
                    "audit": None,
                }
            if status == "generated" and not auto_ran:
                return _run_step_e_for_version(
                    stored_version=cached,
                    canonical_skill=canonical_skill,
                    canonical_topic=(
                        (cached.get("content_json") or {}).get("topic") or clean_topic
                    ),
                    difficulty=norm_diff,
                    role=clean_role,
                    gen_provider=gen_provider,
                    gen_model=gen_model,
                    check_provider=check_provider,
                    check_model=check_model,
                    allow_live=allow_live,
                    cache_hit=True,
                    rejected_audit_path=rejected_audit_path,
                    demoted_audit_path=demoted_audit_path,
                )

    bundle_id = build_bundle_id_for_cell(canonical_skill, clean_topic, norm_diff)
    existing_versions = bundle_store.list_versions(bundle_id=bundle_id)
    next_version = max((int(v["version"]) for v in existing_versions), default=0) + 1
    canonical_topic = (
        str((existing_versions[0].get("content_json") or {}).get("topic") or clean_topic)
        if existing_versions
        else clean_topic
    )

    doc, _paraphrase = _generate_validated_doc(
        bundle_id=bundle_id,
        version=next_version,
        canonical_skill=canonical_skill,
        canonical_topic=canonical_topic,
        difficulty=norm_diff,
        gen_provider=gen_provider,
        gen_model=gen_model,
        role=clean_role,
        allow_live=allow_live,
    )

    stored = bundle_store.import_bundle(
        doc,
        actor_id="bundle_generator",
        initial_status="generated",
        audit_reason="WS2 Prompt B bundle generation",
    )["version"]

    return _run_step_e_for_version(
        stored_version=stored,
        canonical_skill=canonical_skill,
        canonical_topic=canonical_topic,
        difficulty=norm_diff,
        role=clean_role,
        gen_provider=gen_provider,
        gen_model=gen_model,
        check_provider=check_provider,
        check_model=check_model,
        allow_live=allow_live,
        cache_hit=False,
        rejected_audit_path=rejected_audit_path,
        demoted_audit_path=demoted_audit_path,
    )
