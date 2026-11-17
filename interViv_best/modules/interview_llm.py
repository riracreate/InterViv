"""Opt-in interview model lanes. Not wired into session routes (build step 1).

Admission happens before every completion/override, including a caller's retry.
No internal transport retry can escape the guard or durable attempt counters.
Quota failures defer to a future call; they never sleep/spin or change sessions.
"""
from __future__ import annotations

import contextvars
import http.client
import json
import logging
import os
import re
import ssl
import time
import urllib.error
import urllib.request
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal, InvalidOperation
from functools import lru_cache
from pathlib import Path
from typing import Callable

import certifi

from modules import llm_outbound_gate
from modules.interview_llm_budget import DispatchDeferred, RequestBudget
from modules.llm_http_policy import LimitDecision, classify_http_error

PAID_CONVERSATION_MODEL = "anthropic/claude-haiku-4.5"
CONTENT_PURPOSES = frozenset({"bundle_generation", "bundle_blind_answer", "bundle_check_audit", "bundle_regeneration"})
PERSONAL_PURPOSES = frozenset({"role_skill_extraction", "resume_extraction", "interviewer_turn", "debrief"})
CATALOG_URL = "https://openrouter.ai/api/v1/models"
CHAT_URL = "https://openrouter.ai/api/v1/chat/completions"
MIN_CONTENT_CONTEXT = 16384
DEFAULT_CONTENT_REASONING_MAX_TOKENS = 1024
LOGGER = logging.getLogger("interviv.interview_llm")
_SSL_CTX = ssl.create_default_context(cafile=certifi.where())


class RoutingError(RuntimeError):
    pass


class PrivacyViolation(RoutingError):
    pass


class ProviderResponseDeferred(DispatchDeferred):
    """Validated response failure, carrying billed metadata back to admission."""
    def __init__(self, reason, *, usage=(0, 0, 0), model=None, reasoning_tokens=None,
                 code=None, body="", headers=None):
        super().__init__(reason, reasoning_tokens=reasoning_tokens)
        self.usage, self.model, self.code = usage, model, code
        self.body, self.headers = body, headers or {}


def enabled() -> bool:
    return os.getenv("AI_INTERVIEW_ROUTING_ENABLED", "0").strip().lower() in {"1", "true", "yes", "on"}


def _flag(name: str) -> bool:
    return os.getenv(name, "0").strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class RoutingSettings:
    # Real content dispatch requires an owner order unless discovery is opted in.
    content_models: tuple[str, ...] = ()
    allow_content_discovery: bool = False
    min_content_context: int = MIN_CONTENT_CONTEXT
    content_reasoning_max_tokens: int = DEFAULT_CONTENT_REASONING_MAX_TOKENS
    conversation_model: str = PAID_CONVERSATION_MODEL
    allow_paid_content: bool = False
    high_free_limit: bool = False
    account: str = "default"
    state_path: Path = Path(__file__).resolve().parents[1] / "artifacts" / "interview_llm_limits.json"

    @classmethod
    def from_env(cls):
        return cls(
            content_models=tuple(x.strip() for x in os.getenv("INTERVIEW_CONTENT_MODELS", "").split(",") if x.strip()),
            allow_content_discovery=_flag("INTERVIEW_ALLOW_CONTENT_DISCOVERY"),
            min_content_context=int(os.getenv("INTERVIEW_CONTENT_MIN_CONTEXT") or MIN_CONTENT_CONTEXT),
            content_reasoning_max_tokens=int(
                os.getenv("INTERVIEW_CONTENT_REASONING_MAX_TOKENS") or DEFAULT_CONTENT_REASONING_MAX_TOKENS
            ),
            conversation_model=os.getenv("INTERVIEW_CONVERSATION_MODEL", PAID_CONVERSATION_MODEL).strip(),
            allow_paid_content=_flag("ALLOW_PAID_CONTENT_FALLBACK"),
            high_free_limit=_flag("OPENROUTER_FREE_HIGH_LIMIT_CONFIRMED"),
            account=os.getenv("INTERVIEW_LLM_ACCOUNT", "default").strip(),
            state_path=Path(os.getenv("INTERVIEW_LLM_STATE_PATH") or str(cls.state_path)),
        )


@dataclass
class InterviewScope:
    interview_id: str
    core_count: int
    models: dict[str, str] = field(default_factory=dict)


@dataclass
class BatchScope:
    batch_id: str
    max_requests: int
    models: dict[str, str] = field(default_factory=dict)


_SCOPE: contextvars.ContextVar[InterviewScope | BatchScope | None] = contextvars.ContextVar("interview_llm_scope", default=None)


@contextmanager
def interview_scope(interview_id: str, core_count: int):
    """Future adapters must carry this stable pre-session ID across worker calls."""
    if not interview_id or core_count not in {2, 4} or type(core_count) is not int:
        raise RoutingError("A stable interview ID and 2/4 core slots are required.")
    scope = InterviewScope(interview_id, core_count)
    token = _SCOPE.set(scope)
    try:
        yield scope
    finally:
        _SCOPE.reset(token)


@contextmanager
def batch_scope(batch_id: str, *, max_requests: int):
    """Explicit content-only allowance; never a source of conversation budget."""
    if not batch_id or type(max_requests) is not int or max_requests < 1:
        raise RoutingError("A stable batch ID and positive explicit max_requests are required.")
    scope = BatchScope(batch_id, max_requests)
    token = _SCOPE.set(scope)
    try:
        yield scope
    finally:
        _SCOPE.reset(token)


def actual_model(purpose: str, default: str) -> str:
    scope = _SCOPE.get()
    return scope.models.get(purpose, default) if scope is not None else default


def lane_for(purpose: str) -> str:
    if purpose in CONTENT_PURPOSES:
        return "content"
    if purpose in PERSONAL_PURPOSES:
        return "conversation"
    raise RoutingError("Unclassified purpose; no dispatch permitted.")


def consumer_for(purpose: str) -> str:
    lane_for(purpose)
    return "interviewer" if purpose in {"interviewer_turn", "debrief"} else "questions"


def enforce_outbound_policy(*, purpose: str, model: str, personal_text: bool = False) -> None:
    lane = lane_for(purpose)
    personal = personal_text or purpose in PERSONAL_PURPOSES
    if personal and model.casefold().endswith(":free"):
        raise PrivacyViolation("Personal text cannot be sent to a :free model.")
    if lane == "conversation" and model != PAID_CONVERSATION_MODEL:
        raise PrivacyViolation("Conversation text requires the paid Claude Haiku 4.5 allowlist.")
    if lane == "content" and personal:
        raise PrivacyViolation("Personal text is not permitted in the content lane.")


def _gate(consumer: str, *, offline_override: bool) -> None:
    if not enabled():
        raise RoutingError("AI interview routing is disabled.")
    allowed = llm_outbound_gate.llm_live_consumers()
    if allowed is not None and consumer not in allowed:
        raise RoutingError(f"LLM consumer {consumer} is disabled.")
    if not offline_override and not llm_outbound_gate.llm_consumer_enabled(consumer):
        raise RoutingError("LLM live fetch is disabled.")


def catalog_rows(payload: dict) -> list[dict]:
    """Require a complete single page, including for injected offline catalogs."""
    if not isinstance(payload, dict) or not isinstance(payload.get("data"), list):
        raise RoutingError("Model catalog must contain a data array.")
    links = payload.get("links")
    if links is not None and not isinstance(links, dict):
        raise RoutingError("Model catalog links are invalid; completeness is unverified.")
    if isinstance(links, dict) and links.get("next") not in (None, ""):
        raise RoutingError(f"Model catalog pagination unsupported: total_rows_received={len(payload['data'])}, "
                           "links.next present; refusing an incomplete catalog.")
    return payload["data"]


def _fetch_catalog() -> dict:
    # Single GET only; a non-empty links.next fails closed, never silently truncates.
    # Only called after the live gate; overrides require an injected catalog.
    request = urllib.request.Request(CATALOG_URL, headers={"Accept": "application/json"})
    with urllib.request.urlopen(request, timeout=20, context=_SSL_CTX) as response:
        payload = json.loads(response.read())
    catalog_rows(payload)
    return payload


def _price(entry: dict, key: str) -> Decimal | None:
    try:
        price = Decimal(str(entry["pricing"][key]))
        return price if price.is_finite() and price >= 0 else None
    except (KeyError, TypeError, InvalidOperation):
        return None


def content_context_length(entry: dict) -> int:
    """Respect a lower advertised provider limit as well as the model limit."""
    context = entry.get("context_length")
    provider = entry.get("top_provider") or {}
    if type(context) is not int or context <= 0 or not isinstance(provider, dict):
        return 0
    if provider.get("context_length") is not None:
        limit = provider["context_length"]
        if type(limit) is not int or limit <= 0:
            return 0
        context = min(context, limit)
    return context


def _content_ineligible_reason(entry: dict | None, min_context: int = MIN_CONTENT_CONTEXT) -> str | None:
    if not isinstance(entry, dict) or not entry:
        return "absent_from_catalog"
    model = entry.get("id") or ""
    model_type = entry.get("type", entry.get("model_type", "chat"))
    if not (isinstance(model, str) and "/" in model and not model.casefold().startswith("openrouter/")
            and not any(kind in model.casefold() for kind in ("rerank", "embedding"))
            and isinstance(model_type, str)
            and model_type in {"chat", "text-generation", "text_generation", "language", "llm"}):
        return "disallowed_model_kind"
    architecture = entry.get("architecture") or {}
    if not isinstance(architecture, dict):
        return "unsupported_modalities"
    inputs, outputs = architecture.get("input_modalities"), architecture.get("output_modalities")
    if not (isinstance(inputs, list) and "text" in inputs and outputs == ["text"]):
        return "unsupported_modalities"
    if content_context_length(entry) < min_context:
        return "insufficient_context"
    if not (_price(entry, "prompt") == 0 and _price(entry, "completion") == 0
            and ("request" not in (entry.get("pricing") or {}) or _price(entry, "request") == 0)):
        return "nonzero_or_missing_price"
    parameters = entry.get("supported_parameters")
    if not (isinstance(parameters, list) and all(isinstance(parameter, str) for parameter in parameters)
            and {"structured_outputs", "response_format", "max_tokens"}.issubset(parameters)):
        return "missing_structured_params"
    return None


def _free_structured(entry: dict, min_context: int = MIN_CONTENT_CONTEXT) -> bool:
    return _content_ineligible_reason(entry, min_context) is None


def _estimate_prompt_tokens(messages: list[dict[str, str]]) -> int:
    total = 16
    for msg in messages:
        content = str(msg.get("content") or "") if isinstance(msg, dict) else ""
        total += (len(content) + 2) // 3 + 6
    return total


def _content_reasoning_config(
    entry: dict,
    purpose_max_tokens: int,
    reasoning_cap: int,
    messages: list[dict[str, str]],
) -> tuple[dict | None, int]:
    """Build content-lane reasoning control and headroom-clamped max_tokens.

    Reads structured ``entry['reasoning']`` (``mandatory`` / ``default_enabled`` /
    ``supports_max_tokens``) when present alongside OpenRouter's live catalog
    ``supported_parameters`` entries (``reasoning``, ``include_reasoning``,
    ``reasoning_effort``) observed in the step 1e catalog read.
    """
    parameters = entry.get("supported_parameters")
    if not isinstance(parameters, list) or "reasoning" not in parameters:
        return None, purpose_max_tokens
    meta = entry.get("reasoning")
    if meta is False or (meta is not None and not isinstance(meta, dict)):
        return None, purpose_max_tokens
    has_meta_dict = isinstance(meta, dict) and bool(meta)
    pricing = entry.get("pricing")
    has_catalog_signals = (
        "include_reasoning" in parameters
        or "reasoning_effort" in parameters
        or (isinstance(pricing, dict) and "internal_reasoning" in pricing)
    )
    if not has_meta_dict and not has_catalog_signals:
        return None, purpose_max_tokens
    defaults = entry.get("default_parameters")
    default_reasoning = defaults.get("reasoning") if isinstance(defaults, dict) else None
    mandatory = (
        bool(meta.get("mandatory") or meta.get("required"))
        if has_meta_dict
        else bool(isinstance(default_reasoning, dict)
                  and (default_reasoning.get("mandatory") or default_reasoning.get("required")))
    )
    if not mandatory:
        return {"enabled": False, "exclude": True}, purpose_max_tokens
    available = content_context_length(entry) - _estimate_prompt_tokens(messages) - 1
    provider = entry.get("top_provider")
    if isinstance(provider, dict) and type(provider.get("max_completion_tokens")) is int and provider["max_completion_tokens"] > 0:
        available = min(available, provider["max_completion_tokens"])
    if available < 1:
        raise RoutingError("Prompt leaves no context headroom for content completion.")
    request_max_tokens = min(purpose_max_tokens + reasoning_cap, available)
    supports_max_tokens = bool(meta.get("supports_max_tokens")) if has_meta_dict else False
    if supports_max_tokens:
        cap = min(reasoning_cap, max(1, request_max_tokens - 1))
        return {"max_tokens": cap, "exclude": True}, request_max_tokens
    if "reasoning_effort" in parameters:
        return {"effort": "low", "exclude": True}, request_max_tokens
    return {"exclude": True}, request_max_tokens


def same_model_family(requested: str, returned: str | None, *, canonical_slug: str | None = None) -> bool:
    """Exact catalog canonical slug, or identities/date snapshots of one family.

    A :free request may be reported by its base family, but a paid request may
    never be reported as :free. Versions, sizes and vendors are not aliases.
    """
    if not returned or not isinstance(returned, str):
        return False
    if returned.endswith(":free") and not requested.endswith(":free"):
        return False
    if isinstance(canonical_slug, str) and canonical_slug:
        canonical_ids = {canonical_slug}
        if requested.endswith(":free"):
            canonical_ids.add(canonical_slug.removesuffix(":free"))
        if returned in canonical_ids:
            return True
    def family(model):
        model = model.removesuffix(":free")
        match = re.search(r"-(\d{8}|\d{4}-\d{2}-\d{2})$", model)
        if match:
            try:
                datetime.strptime(match[1].replace("-", ""), "%Y%m%d")
            except ValueError:
                return model
            model = model[:match.start()]
        return model
    return family(requested) == family(returned)


@dataclass(frozen=True)
class Completion:
    text: str
    usage: tuple[int, int, int]
    model: str
    requested_model: str | None = None
    truncated: bool = False
    reasoning_tokens: int | None = None


class InterviewRouter:
    def __init__(self, settings: RoutingSettings, *, catalog_source: Callable[[], dict] | None = None,
                 clock=time.time, budget: RequestBudget | None = None):
        self.settings = settings
        if type(settings.min_content_context) is not int or settings.min_content_context < 1:
            raise RoutingError("Content context minimum must be a positive integer.")
        if type(settings.content_reasoning_max_tokens) is not int or settings.content_reasoning_max_tokens < 1:
            raise RoutingError("Content reasoning token cap must be a positive integer.")
        self.clock = clock
        self.budget = budget or RequestBudget(settings.state_path, account=settings.account,
                                              high_free_limit=settings.high_free_limit, clock=clock)
        self.catalog_source = catalog_source or _fetch_catalog
        self.injected_catalog = catalog_source is not None
        self.catalog: dict[str, dict] | None = None
        self.catalog_until = 0.0

    def _models(self, consumer: str, offline_override: bool) -> dict[str, dict]:
        _gate(consumer, offline_override=offline_override)
        if self.catalog is None or self.clock() >= self.catalog_until:
            if offline_override and not self.injected_catalog:
                raise RoutingError("Offline override requires an injected model catalog.")
            try:
                rows = catalog_rows(self.catalog_source())
                catalog = {}
                for row in rows:
                    if not isinstance(row, dict) or not isinstance(row.get("id"), str):
                        continue
                    model = row["id"]
                    if not model or model in catalog:
                        raise ValueError("duplicate/empty model ID")
                    catalog[model] = row
            except (KeyError, TypeError, ValueError, OSError, http.client.HTTPException) as exc:
                raise RoutingError("Model catalog unavailable; no unvalidated model permitted.") from exc
            self.catalog, self.catalog_until = catalog, self.clock() + 300
        return self.catalog

    def _paid_model(self, models: dict[str, dict]) -> str:
        model = self.settings.conversation_model
        enforce_outbound_policy(purpose="role_skill_extraction", model=model)
        entry = models.get(model, {})
        prompt, completion = _price(entry, "prompt"), _price(entry, "completion")
        if prompt is None or completion is None or prompt + completion <= 0:
            raise RoutingError("Paid conversation model was not validated in the catalog.")
        return model

    def content_candidates(self, *, offline_override: bool = False) -> tuple[str, ...]:
        if len(set(self.settings.content_models)) != len(self.settings.content_models):
            raise RoutingError("Duplicate content model IDs in INTERVIEW_CONTENT_MODELS.")
        models = self._models("questions", offline_override)
        if self.settings.content_models:
            eligible: list[str] = []
            for candidate in self.settings.content_models:
                entry = models.get(candidate)
                reason = (
                    "absent_from_catalog"
                    if entry is None
                    else _content_ineligible_reason(entry, self.settings.min_content_context)
                )
                if reason is None:
                    eligible.append(candidate)
                else:
                    LOGGER.warning("interview_llm_content_candidate_skipped model=%s reason=%s",
                                   candidate, reason,
                                   extra={"requested_model": candidate, "reason": reason})
            choices: tuple[str, ...] = tuple(eligible)
        else:
            choices = tuple(sorted(model for model, row in models.items()
                                   if _free_structured(row, self.settings.min_content_context))[:3])
        if self.settings.allow_paid_content:
            choices = (*choices, self._paid_model(models))
        if not choices:
            raise RoutingError("No zero-priced structured-output content model is available.")
        return choices

    def resolve_content_model(self, *, offline_override: bool = False) -> str:
        return self.content_candidates(offline_override=offline_override)[0]

    def dispatch(self, *, purpose: str, messages: list[dict[str, str]], max_tokens: int = 700,
                 temperature: float = 0.1, timeout_s: float = 20, personal_text: bool = False,
                 model: str | None = None, expect_json: bool = True, bundle_id: str | None = None,
                 override: Callable[[str], tuple[str, tuple[int, int, int]]] | None = None) -> Completion:
        lane, consumer = lane_for(purpose), consumer_for(purpose)
        # Classify by purpose, not an optional caller-supplied privacy boolean.
        enforce_outbound_policy(purpose=purpose, model=model or self.settings.conversation_model, personal_text=personal_text)
        _gate(consumer, offline_override=override is not None)
        scope = _SCOPE.get()
        if scope is None:
            raise RoutingError("Missing interview_scope; no unbudgeted routing is permitted.")
        if isinstance(scope, BatchScope) and lane != "content":
            raise PrivacyViolation("Batch scope is content-only; conversation purposes are forbidden.")
        if lane == "content" and override is None and not self.settings.content_models and not self.settings.allow_content_discovery:
            raise RoutingError("Real content dispatch requires INTERVIEW_CONTENT_MODELS or explicit discovery opt-in.")
        if lane == "content":
            choices = self.content_candidates(offline_override=override is not None)
            models = self._models(consumer, override is not None)
        else:
            models = self._models(consumer, override is not None)
            choices = (self._paid_model(models),)
        if model is not None:
            if model not in choices:
                raise RoutingError("Requested model is not a validated lane candidate.")
            choices = (model,)
        for choice in choices:
            enforce_outbound_policy(purpose=purpose, model=choice, personal_text=personal_text)
            entry = models.get(choice, {})
            free = _free_structured(entry, self.settings.min_content_context)
            reasoning_cfg, request_max_tokens = (
                _content_reasoning_config(entry, max_tokens, self.settings.content_reasoning_max_tokens, messages)
                if lane == "content" else (None, max_tokens)
            )
            try:
                if isinstance(scope, BatchScope):
                    token = self.budget.reserve_batch(batch_id=scope.batch_id, max_requests=scope.max_requests,
                                                      lane=lane, model=choice, free=free, timeout_s=timeout_s)
                else:
                    token = self.budget.reserve(interview_id=scope.interview_id, core_count=scope.core_count,
                                                lane=lane, model=choice, free=free, timeout_s=timeout_s)
            except DispatchDeferred as exc:
                if exc.reason == "model_backoff" and model is None and lane == "content":
                    continue
                if exc.reason == "free_daily" and self.settings.allow_paid_content and lane == "content" and free:
                    continue
                raise
            started = time.monotonic()
            usage = (0, 0, 0)
            returned_model = None
            reasoning_tokens = None
            status, error_kind = "ok", None
            try:
                # Recheck after catalog/admission as flags may have changed concurrently.
                _gate(consumer, offline_override=override is not None)
                enforce_outbound_policy(purpose=purpose, model=choice, personal_text=personal_text)
                scope.models[purpose] = choice
                if override is not None:
                    result = override(choice)
                    if isinstance(result, Completion):
                        text, usage, returned_model = result.text, result.usage, result.model
                        reasoning_tokens = result.reasoning_tokens
                    else:
                        text, usage = result
                        returned_model = choice
                else:
                    result = self._chat_once(choice, messages, request_max_tokens, temperature,
                                             timeout_s, expect_json, reasoning_cfg)
                    text, usage, returned_model = result.text, result.usage, result.model
                    reasoning_tokens = result.reasoning_tokens
                if not same_model_family(choice, returned_model, canonical_slug=models[choice].get("canonical_slug")):
                    raise PrivacyViolation("Provider model identifier is missing or outside the requested family.")
                scope.models[purpose] = returned_model
                if isinstance(result, Completion) and result.truncated:
                    from modules.llm_errors import LLMTruncatedError
                    raise LLMTruncatedError(model=returned_model, provider="openrouter", usage=usage)
                return Completion(text, usage, returned_model, choice, False, reasoning_tokens)
            except urllib.error.HTTPError as exc:
                status = "error"
                decision = classify_http_error(exc.code, exc.read(), exc.headers or {}, now=self.clock(), lane=lane)
                error_kind = decision.kind
                self.budget.record_failure(choice, decision, free=free)
                raise DispatchDeferred(decision.kind, decision.retry_at) from exc
            except ProviderResponseDeferred as exc:
                usage, returned_model, reasoning_tokens = exc.usage, exc.model, exc.reasoning_tokens
                status = "truncated" if exc.reason == "truncated" else "error"
                decision = (classify_http_error(exc.code, exc.body, exc.headers, now=self.clock(), lane=lane)
                            if exc.code is not None else LimitDecision(exc.reason, self.clock() + 300))
                if decision.kind == "http_error":
                    decision = LimitDecision("provider_error", self.clock() + 300)
                error_kind = decision.kind
                self.budget.record_failure(choice, decision, free=free)
                raise DispatchDeferred(decision.kind, decision.retry_at,
                                       reasoning_tokens=reasoning_tokens) from exc
            except (OSError, http.client.HTTPException) as exc:
                reason = getattr(exc, "reason", exc)
                error_kind = "timeout" if isinstance(reason, TimeoutError) else "network_unavailable"
                status = "error"
                decision = LimitDecision(error_kind, self.clock() + 4)
                self.budget.record_failure(choice, decision, free=free)
                raise DispatchDeferred(error_kind, decision.retry_at) from exc
            except Exception as exc:
                from modules.llm_errors import LLMTruncatedError
                status, error_kind = "error", type(exc).__name__
                if isinstance(exc, LLMTruncatedError):
                    status, usage = "truncated", exc.usage or usage
                raise
            finally:
                try:
                    self.budget.release(token)
                finally:
                    from modules.llm_usage import log_llm_usage
                    LOGGER.info("interview_llm_dispatch requested_model=%s returned_model=%s status=%s reasoning_tokens=%s",
                                choice, returned_model, status, reasoning_tokens,
                                extra={"requested_model": choice, "returned_model": returned_model,
                                       "purpose": purpose, "reasoning_tokens": reasoning_tokens})
                    log_llm_usage(provider="openrouter", model=returned_model or choice, purpose=purpose,
                                  prompt_tokens=usage[0], completion_tokens=usage[1], total_tokens=usage[2],
                                  latency_ms=int((time.monotonic() - started) * 1000), status=status,
                                  error=error_kind, bundle_id=bundle_id)
        raise DispatchDeferred("content_models_unavailable")

    @staticmethod
    def _chat_once(model, messages, max_tokens, temperature, timeout_s, expect_json, reasoning=None):
        key = os.getenv("OPENROUTER_API_KEY", "").strip()
        if not key:
            raise RoutingError("OPENROUTER_API_KEY is missing.")
        body = {"model": model, "messages": messages, "max_tokens": max_tokens, "temperature": temperature}
        if expect_json:
            body["response_format"] = {"type": "json_object"}
        if reasoning is not None:
            body["reasoning"] = reasoning
        request = urllib.request.Request(CHAT_URL, data=json.dumps(body).encode(), method="POST",
                                         headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"})
        with urllib.request.urlopen(request, timeout=timeout_s, context=_SSL_CTX) as response:
            raw = response.read()
            headers = getattr(response, "headers", {})
        try:
            data = json.loads(raw)
        except (ValueError, UnicodeDecodeError) as exc:
            raise ProviderResponseDeferred("invalid_response") from exc
        if not isinstance(data, dict):
            raise ProviderResponseDeferred("invalid_response")
        usage = data.get("usage")
        usage = usage if isinstance(usage, dict) else {}
        def count(source, key):
            value = source.get(key)
            if isinstance(value, str) and len(value) <= 20 and value.isascii() and value.isdigit():
                return int(value)
            return value if type(value) is int and value >= 0 else None
        prompt, completion = count(usage, "prompt_tokens") or 0, count(usage, "completion_tokens") or 0
        counts = (prompt, completion, count(usage, "total_tokens") or prompt + completion)
        details = usage.get("completion_tokens_details")
        reasoning_tokens = count(details, "reasoning_tokens") if isinstance(details, dict) else None
        metadata = {"usage": counts, "model": data.get("model"), "reasoning_tokens": reasoning_tokens}
        if "error" in data:
            error = data["error"]
            code = error.get("code") if isinstance(error, dict) else None
            if isinstance(code, str) and len(code) == 3 and code.isascii() and code.isdigit():
                code = int(code)
            code = code if type(code) is int and 400 <= code <= 599 else None
            raise ProviderResponseDeferred("provider_error", **metadata, code=code,
                                           body=json.dumps(data), headers=headers)
        choices = data.get("choices")
        if not isinstance(choices, list) or not choices or not isinstance(choices[0], dict):
            raise ProviderResponseDeferred("invalid_response", **metadata)
        if choices[0].get("finish_reason") == "length":
            raise ProviderResponseDeferred("truncated", **metadata)
        message = choices[0].get("message")
        if not isinstance(message, dict):
            raise ProviderResponseDeferred("invalid_response", **metadata)
        content = message.get("content")
        if content is None or isinstance(content, str) and not content.strip():
            raise ProviderResponseDeferred("empty_response", **metadata)
        if not isinstance(content, str):
            raise ProviderResponseDeferred("invalid_response", **metadata)
        return Completion(content, counts, data.get("model"), model, False, reasoning_tokens)


@lru_cache(maxsize=4)
def _router(settings: RoutingSettings) -> InterviewRouter:
    return InterviewRouter(settings)


def get_router() -> InterviewRouter:
    return _router(RoutingSettings.from_env())
