"""Opt-in interview model lanes. Not wired into session routes (build step 1).

Admission happens before every completion/override, including a caller's retry.
No internal transport retry can escape the guard or durable attempt counters.
Quota failures defer to a future call; they never sleep/spin or change sessions.
"""
from __future__ import annotations

import contextvars
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

from modules import llm_outbound_gate
from modules.interview_llm_budget import DispatchDeferred, RequestBudget
from modules.llm_http_policy import classify_http_error

PAID_CONVERSATION_MODEL = "anthropic/claude-haiku-4.5"
CONTENT_PURPOSES = frozenset({"bundle_generation", "bundle_blind_answer", "bundle_check_audit", "bundle_regeneration"})
PERSONAL_PURPOSES = frozenset({"role_skill_extraction", "resume_extraction", "interviewer_turn", "debrief"})
CATALOG_URL = "https://openrouter.ai/api/v1/models"
CHAT_URL = "https://openrouter.ai/api/v1/chat/completions"
MIN_CONTENT_CONTEXT = 16384
LOGGER = logging.getLogger("interviv.interview_llm")


class RoutingError(RuntimeError):
    pass


class PrivacyViolation(RoutingError):
    pass


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


def _fetch_catalog() -> dict:
    # Only called after _gate; offline overrides require an injected catalog.
    request = urllib.request.Request(CATALOG_URL, headers={"Accept": "application/json"})
    with urllib.request.urlopen(request, timeout=20, context=ssl.create_default_context()) as response:
        return json.loads(response.read())


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
    if "context_length" in provider:
        limit = provider["context_length"]
        if type(limit) is not int or limit <= 0:
            return 0
        context = min(context, limit)
    return context


def _free_structured(entry: dict, min_context: int = MIN_CONTENT_CONTEXT) -> bool:
    parameters = entry.get("supported_parameters")
    model = entry.get("id") or ""
    architecture = entry.get("architecture") or {}
    if not isinstance(architecture, dict):
        return False
    inputs, outputs = architecture.get("input_modalities"), architecture.get("output_modalities")
    model_type = entry.get("type", entry.get("model_type", "chat"))
    return (isinstance(model, str) and "/" in model and not model.casefold().startswith("openrouter/")
            and not any(kind in model.casefold() for kind in ("rerank", "embedding"))
            and isinstance(model_type, str) and model_type in {"chat", "text-generation", "text_generation", "language", "llm"}
            and isinstance(inputs, list) and "text" in inputs and outputs == ["text"]
            and content_context_length(entry) >= min_context and _price(entry, "prompt") == 0
            and _price(entry, "completion") == 0
            and isinstance(parameters, list)
            and all(isinstance(parameter, str) for parameter in parameters)
            and {"structured_outputs", "response_format", "max_tokens"}.issubset(parameters)
            and ("request" not in (entry.get("pricing") or {}) or _price(entry, "request") == 0))


def same_model_family(requested: str, returned: str | None) -> bool:
    """Only exact identities or valid date snapshots of the same vendor/name.

    A :free request may be reported by its base family, but a paid request may
    never be reported as :free. Versions, sizes and vendors are not aliases.
    """
    if not returned or not isinstance(returned, str):
        return False
    if returned.endswith(":free") and not requested.endswith(":free"):
        return False
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


class InterviewRouter:
    def __init__(self, settings: RoutingSettings, *, catalog_source: Callable[[], dict] | None = None,
                 clock=time.time, budget: RequestBudget | None = None):
        self.settings = settings
        if type(settings.min_content_context) is not int or settings.min_content_context < 1:
            raise RoutingError("Content context minimum must be a positive integer.")
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
                rows = self.catalog_source()["data"]
                if not isinstance(rows, list):
                    raise ValueError("invalid catalog")
                catalog = {}
                for row in rows:
                    if not isinstance(row, dict) or not isinstance(row.get("id"), str):
                        continue
                    model = row["id"]
                    if not model or model in catalog:
                        raise ValueError("duplicate/empty model ID")
                    catalog[model] = row
            except (KeyError, TypeError, ValueError, OSError) as exc:
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
        models = self._models("questions", offline_override)
        choices = self.settings.content_models or tuple(sorted(model for model, row in models.items()
                                                               if _free_structured(row, self.settings.min_content_context))[:3])
        if len(set(choices)) != len(choices) or any(not _free_structured(models.get(model, {}), self.settings.min_content_context) for model in choices):
            raise RoutingError("Every content ID must be an eligible zero-priced text chat model with sufficient context and JSON capabilities.")
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
        models = self._models(consumer, override is not None)
        choices = self.content_candidates(offline_override=override is not None) if lane == "content" else (self._paid_model(models),)
        if model is not None:
            if model not in choices:
                raise RoutingError("Requested model is not a validated lane candidate.")
            choices = (model,)
        for choice in choices:
            enforce_outbound_policy(purpose=purpose, model=choice, personal_text=personal_text)
            free = _free_structured(models.get(choice, {}), self.settings.min_content_context)
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
                    else:
                        text, usage = result
                        returned_model = choice
                else:
                    result = self._chat_once(choice, messages, max_tokens, temperature, timeout_s, expect_json)
                    text, usage, returned_model = result.text, result.usage, result.model
                if not same_model_family(choice, returned_model):
                    raise PrivacyViolation("Provider model identifier is missing or outside the requested family.")
                scope.models[purpose] = returned_model
                if isinstance(result, Completion) and result.truncated:
                    from modules.llm_errors import LLMTruncatedError
                    raise LLMTruncatedError(model=returned_model, provider="openrouter", usage=usage)
                return Completion(text, usage, returned_model, choice)
            except urllib.error.HTTPError as exc:
                status = "error"
                decision = classify_http_error(exc.code, exc.read(), exc.headers or {}, now=self.clock(), lane=lane)
                error_kind = decision.kind
                self.budget.record_failure(choice, decision, free=free)
                raise DispatchDeferred(decision.kind, decision.retry_at) from exc
            except (urllib.error.URLError, TimeoutError) as exc:
                from modules.llm_http_policy import LimitDecision
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
                    LOGGER.info("interview_llm_dispatch requested_model=%s returned_model=%s status=%s",
                                choice, returned_model, status,
                                extra={"requested_model": choice, "returned_model": returned_model, "purpose": purpose})
                    log_llm_usage(provider="openrouter", model=returned_model or choice, purpose=purpose,
                                  prompt_tokens=usage[0], completion_tokens=usage[1], total_tokens=usage[2],
                                  latency_ms=int((time.monotonic() - started) * 1000), status=status,
                                  error=error_kind, bundle_id=bundle_id)
        raise DispatchDeferred("content_models_unavailable")

    @staticmethod
    def _chat_once(model, messages, max_tokens, temperature, timeout_s, expect_json):
        key = os.getenv("OPENROUTER_API_KEY", "").strip()
        if not key:
            raise RoutingError("OPENROUTER_API_KEY is missing.")
        body = {"model": model, "messages": messages, "max_tokens": max_tokens, "temperature": temperature}
        if expect_json:
            body["response_format"] = {"type": "json_object"}
        request = urllib.request.Request(CHAT_URL, data=json.dumps(body).encode(), method="POST",
                                         headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"})
        with urllib.request.urlopen(request, timeout=timeout_s, context=ssl.create_default_context()) as response:
            data = json.loads(response.read())
        message = data["choices"][0]
        usage = data.get("usage") or {}
        counts = (int(usage.get("prompt_tokens") or 0), int(usage.get("completion_tokens") or 0))
        return Completion(str(message["message"]["content"]), (*counts, sum(counts)), data.get("model"), model,
                          message.get("finish_reason") == "length")


@lru_cache(maxsize=4)
def _router(settings: RoutingSettings) -> InterviewRouter:
    return InterviewRouter(settings)


def get_router() -> InterviewRouter:
    return _router(RoutingSettings.from_env())
