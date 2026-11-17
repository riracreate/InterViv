"""Opt-in interview model lanes. Not wired into session routes (build step 1).

Admission happens before every completion/override, including a caller's retry.
No internal transport retry can escape the guard or durable attempt counters.
Quota failures defer to a future call; they never sleep/spin or change sessions.
"""
from __future__ import annotations

import contextvars
import json
import os
import ssl
import time
import urllib.error
import urllib.request
from contextlib import contextmanager
from dataclasses import dataclass, field
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
    # No hardcoded free IDs: an empty ordered override means catalog discovery.
    content_models: tuple[str, ...] = ()
    conversation_model: str = PAID_CONVERSATION_MODEL
    allow_paid_content: bool = False
    high_free_limit: bool = False
    account: str = "default"
    state_path: Path = Path(__file__).resolve().parents[1] / "artifacts" / "interview_llm_limits.json"

    @classmethod
    def from_env(cls):
        return cls(
            content_models=tuple(x.strip() for x in os.getenv("INTERVIEW_CONTENT_MODELS", "").split(",") if x.strip()),
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


_SCOPE: contextvars.ContextVar[InterviewScope | None] = contextvars.ContextVar("interview_llm_scope", default=None)


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


def _free_structured(entry: dict) -> bool:
    parameters = entry.get("supported_parameters")
    return (bool(entry.get("id")) and _price(entry, "prompt") == 0
            and _price(entry, "completion") == 0
            and isinstance(parameters, list) and "structured_outputs" in parameters
            and ("request" not in (entry.get("pricing") or {}) or _price(entry, "request") == 0))


@dataclass(frozen=True)
class Completion:
    text: str
    usage: tuple[int, int, int]
    model: str


class InterviewRouter:
    def __init__(self, settings: RoutingSettings, *, catalog_source: Callable[[], dict] | None = None,
                 clock=time.time, budget: RequestBudget | None = None):
        self.settings = settings
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
        choices = self.settings.content_models or tuple(sorted(model for model, row in models.items() if _free_structured(row))[:3])
        if len(set(choices)) != len(choices) or any(not _free_structured(models.get(model, {})) for model in choices):
            raise RoutingError("Every ordered content override must exist, be zero-priced and support structured output.")
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
        models = self._models(consumer, override is not None)
        choices = self.content_candidates(offline_override=override is not None) if lane == "content" else (self._paid_model(models),)
        if model is not None:
            if model not in choices:
                raise RoutingError("Requested model is not a validated lane candidate.")
            choices = (model,)
        for choice in choices:
            enforce_outbound_policy(purpose=purpose, model=choice, personal_text=personal_text)
            free = _free_structured(models.get(choice, {}))
            try:
                token = self.budget.reserve(interview_id=scope.interview_id, core_count=scope.core_count,
                                            lane=lane, model=choice, free=free)
            except DispatchDeferred as exc:
                if exc.reason == "model_backoff" and model is None:
                    continue
                if exc.reason == "free_daily" and self.settings.allow_paid_content and lane == "content" and free:
                    continue
                raise
            started = time.monotonic()
            usage = (0, 0, 0)
            status, error_kind = "ok", None
            try:
                # Recheck after catalog/admission as flags may have changed concurrently.
                _gate(consumer, offline_override=override is not None)
                enforce_outbound_policy(purpose=purpose, model=choice, personal_text=personal_text)
                scope.models[purpose] = choice
                if override is not None:
                    text, usage = override(choice)
                else:
                    text, usage = self._chat_once(choice, messages, max_tokens, temperature, timeout_s, expect_json)
                return Completion(text, usage, choice)
            except urllib.error.HTTPError as exc:
                status = "error"
                decision = classify_http_error(exc.code, exc.read(), exc.headers or {}, now=self.clock())
                error_kind = decision.kind
                self.budget.record_failure(choice, decision, free=free)
                raise DispatchDeferred(decision.kind, decision.retry_at) from exc
            except TimeoutError as exc:
                status, error_kind = "error", "timeout"
                raise DispatchDeferred("timeout") from exc
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
                    log_llm_usage(provider="openrouter", model=choice, purpose=purpose,
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
        if data.get("model", model) != model:
            raise PrivacyViolation("Provider returned an unrequested model identifier.")
        message = data["choices"][0]
        usage = data.get("usage") or {}
        counts = (int(usage.get("prompt_tokens") or 0), int(usage.get("completion_tokens") or 0))
        if message.get("finish_reason") == "length":
            from modules.llm_errors import LLMTruncatedError
            raise LLMTruncatedError(model=model, provider="openrouter", usage=(*counts, sum(counts)))
        return str(message["message"]["content"]), (*counts, sum(counts))


@lru_cache(maxsize=4)
def _router(settings: RoutingSettings) -> InterviewRouter:
    return InterviewRouter(settings)


def get_router() -> InterviewRouter:
    return _router(RoutingSettings.from_env())
