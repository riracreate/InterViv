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
GENERATION_PURPOSES = frozenset({"bundle_generation", "bundle_regeneration"})
CHECK_PURPOSES = frozenset({"bundle_blind_answer", "bundle_check_audit"})
ALLOWED_BUNDLE_PURPOSES = GENERATION_PURPOSES | CHECK_PURPOSES
CONTENT_PURPOSES = ALLOWED_BUNDLE_PURPOSES
PERSONAL_PURPOSES = frozenset({"role_skill_extraction", "resume_extraction", "interviewer_turn", "debrief"})
DIRECT_PROVIDER_USER_AGENT = "InterViv/1.0"
GENERATED_BUNDLE_KEYS = (
    "question", "reference_answer", "acceptable_variants", "keywords",
    "required_concepts", "optional_concepts", "misconceptions", "depth_markers",
    "rubric_descriptors", "followups", "calibration_examples",
)
_RUBRIC_KEYS = ("coverage", "accuracy", "depth", "clarity")


def _string_list() -> dict:
    return {"type": "array", "items": {"type": "string"}}


def _object_schema(required: tuple[str, ...], properties: dict) -> dict:
    return {
        "type": "object",
        "additionalProperties": False,
        "required": list(required),
        "properties": properties,
    }


def _concept_schema() -> dict:
    return _object_schema(
        ("id", "descriptor", "aliases", "expected_propositions"),
        {
            "id": {"type": "string"},
            "descriptor": {"type": "string"},
            "aliases": _string_list(),
            "expected_propositions": _string_list(),
        },
    )


def _bounded_array(items: dict, minimum: int, maximum: int) -> dict:
    return {"type": "array", "items": items, "minItems": minimum, "maxItems": maximum}


def _required_concept_schema() -> dict:
    """Required concepts also carry 2-3 one-sentence positive_examples."""
    return _object_schema(
        ("id", "descriptor", "aliases", "expected_propositions", "positive_examples"),
        {
            "id": {"type": "string"},
            "descriptor": {"type": "string"},
            "aliases": _string_list(),
            "expected_propositions": _string_list(),
            "positive_examples": _bounded_array({"type": "string"}, 2, 3),
        },
    )


def generated_bundle_schema() -> dict:
    """Strict payload for bundle_generation and bundle_regeneration.

    Keys and nested fields match what ``validate_generated_bundle_doc`` reads
    after assembly. Counts follow the Prompt B rules that are tighter than the
    validator floors: 3-4 required concepts, 1-2 optional, 1-2 misconceptions,
    exactly 2 follow-ups and exactly 2 calibration examples.
    """
    concept = _concept_schema()
    return _object_schema(
        GENERATED_BUNDLE_KEYS,
        {
            "question": {"type": "string"},
            "reference_answer": {"type": "string"},
            "acceptable_variants": _string_list(),
            "keywords": _string_list(),
            "required_concepts": _bounded_array(_required_concept_schema(), 3, 4),
            "optional_concepts": _bounded_array(concept, 1, 2),
            "misconceptions": _bounded_array(
                _object_schema(
                    ("id", "description", "candidate_patterns"),
                    {
                        "id": {"type": "string"},
                        "description": {"type": "string"},
                        "candidate_patterns": _string_list(),
                    },
                ),
                1, 2,
            ),
            "depth_markers": _string_list(),
            "rubric_descriptors": _object_schema(
                _RUBRIC_KEYS,
                {key: {"type": "string"} for key in _RUBRIC_KEYS},
            ),
            "followups": _bounded_array(
                _object_schema(
                    ("prompt", "targets_concept"),
                    {"prompt": {"type": "string"}, "targets_concept": {"type": "string"}},
                ),
                2, 2,
            ),
            "calibration_examples": _bounded_array(
                _object_schema(
                    ("author_level", "expected_band", "answer"),
                    {
                        "author_level": {"type": "integer"},
                        "expected_band": {"type": "string"},
                        "answer": {"type": "string"},
                    },
                ),
                2, 2,
            ),
        },
    )


def check_audit_schema() -> dict:
    return _object_schema(
        ("root_cause", "issue_type", "missed_concepts", "fixes"),
        {
            "root_cause": {"type": "string"},
            "issue_type": {
                "type": "string",
                "enum": [
                    "propositions", "question", "misconceptions",
                    "reference", "over_specific_concept",
                ],
            },
            "missed_concepts": _string_list(),
            "fixes": _string_list(),
        },
    )


def response_format_for(purpose: str, lane: str, expect_json: bool) -> dict | None:
    """Content lane JSON always uses strict json_schema and never json_object."""
    if not expect_json or (lane == "content" and purpose == "bundle_blind_answer"):
        return None
    if lane == "content" and purpose in GENERATION_PURPOSES:
        return {
            "type": "json_schema",
            "json_schema": {
                "name": purpose,
                "strict": True,
                "schema": generated_bundle_schema(),
            },
        }
    if lane == "content" and purpose == "bundle_check_audit":
        return {
            "type": "json_schema",
            "json_schema": {
                "name": "bundle_check_audit",
                "strict": True,
                "schema": check_audit_schema(),
            },
        }
    if lane == "content":
        raise RoutingError(f"Content lane never sends json_object; unsupported JSON purpose {purpose!r}.")
    return {"type": "json_object"}
CATALOG_URL = "https://openrouter.ai/api/v1/models"
CHAT_URL = "https://openrouter.ai/api/v1/chat/completions"
NVIDIA_CHAT_URL = "https://integrate.api.nvidia.com/v1/chat/completions"
GROQ_CHAT_URL = "https://api.groq.com/openai/v1/chat/completions"
DEFAULT_NVIDIA_CONTENT_MODEL = "nvidia/nemotron-3.5-super-vl-120b-a12b"
DEFAULT_GROQ_CHECK_MODEL = "openai/gpt-oss-120b"
DEFAULT_GROQ_CONTENT_BACKUP_MODEL = "qwen/qwen3.8-27b"
VALID_CONTENT_PROVIDERS = frozenset({"openrouter", "nvidia", "groq"})
DIRECT_PROVIDER_CAPABILITIES: dict[tuple[str, str], dict] = {
    ("nvidia", "nvidia/nemotron-3.5-super-vl-120b-a12b"): {
        "provider": "nvidia",
        "id": "nvidia/nemotron-3.5-super-vl-120b-a12b",
        "canonical_slug": "private/nvidia/nemotron-3.5-super-120b-a12b",
        "family": "nemotron",
        "context_length": 262144,
        "max_completion_tokens": 32768,
        "supports_json_schema": True,
        "supports_json_object": True,
        "reasoning_control": "chat_template_thinking_off",
        "cost": 0,
    },
    ("nvidia", "nvidia/llama-3.3-nemotron-super-49b-v1.5"): {
        "provider": "nvidia",
        "id": "nvidia/llama-3.3-nemotron-super-49b-v1.5",
        "family": "nemotron",
        "context_length": 131072,
        "max_completion_tokens": 32768,
        "supports_json_schema": False,
        "supports_json_object": True,
        "reasoning_control": "chat_template_thinking_off",
        "cost": 0,
    },
    ("nvidia", "nvidia/llama-3.3-nemotron-super-49b-v1"): {
        "provider": "nvidia",
        "id": "nvidia/llama-3.3-nemotron-super-49b-v1",
        "family": "nemotron",
        "context_length": 131072,
        "max_completion_tokens": 32768,
        "supports_json_schema": False,
        "supports_json_object": True,
        "reasoning_control": "chat_template_thinking_off",
        "cost": 0,
    },
    ("nvidia", "nvidia/llama-3.1-nemotron-ultra-253b-v1"): {
        "provider": "nvidia",
        "id": "nvidia/llama-3.1-nemotron-ultra-253b-v1",
        "family": "nemotron",
        "context_length": 131072,
        "max_completion_tokens": 32768,
        "supports_json_schema": False,
        "supports_json_object": True,
        "reasoning_control": "chat_template_thinking_off",
        "cost": 0,
    },
    ("nvidia", "nvidia/llama-3.1-nemotron-70b-instruct"): {
        "provider": "nvidia",
        "id": "nvidia/llama-3.1-nemotron-70b-instruct",
        "family": "nemotron",
        "context_length": 131072,
        "max_completion_tokens": 16384,
        "supports_json_schema": False,
        "supports_json_object": True,
        "reasoning_control": None,
        "cost": 0,
    },
    ("groq", "qwen/qwen3.8-27b"): {
        "provider": "groq",
        "id": "qwen/qwen3.8-27b",
        "family": "qwen",
        "context_length": 131072,
        "max_completion_tokens": 32768,
        "supports_json_schema": True,
        "supports_json_object": True,
        "reasoning_control": "effort_none",
        "cost": 0,
    },
    ("groq", "openai/gpt-oss-120b"): {
        "provider": "groq",
        "id": "openai/gpt-oss-120b",
        "family": "gpt-oss",
        "context_length": 131072,
        "max_completion_tokens": 32768,
        "supports_json_schema": True,
        "supports_json_object": True,
        "reasoning_control": "effort_low",
        "cost": 0,
    },
    ("groq", "openai/gpt-oss-20b"): {
        "provider": "groq",
        "id": "openai/gpt-oss-20b",
        "family": "gpt-oss",
        "context_length": 131072,
        "max_completion_tokens": 32768,
        "supports_json_schema": True,
        "supports_json_object": True,
        "reasoning_control": "effort_low",
        "cost": 0,
    },
    ("groq", "llama-3.3-70b-versatile"): {
        "provider": "groq",
        "id": "llama-3.3-70b-versatile",
        "family": "llama",
        "context_length": 131072,
        "max_completion_tokens": 32768,
        "supports_json_schema": False,
        "supports_json_object": True,
        "reasoning_control": None,
        "cost": 0,
    },
    ("groq", "llama-3.1-8b-instant"): {
        "provider": "groq",
        "id": "llama-3.1-8b-instant",
        "family": "llama",
        "context_length": 131072,
        "max_completion_tokens": 131072,
        "supports_json_schema": False,
        "supports_json_object": True,
        "reasoning_control": None,
        "cost": 0,
    },
}
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
    check_models: tuple[str, ...] = ()
    allow_content_discovery: bool = False
    allow_self_check: bool = False
    min_content_context: int = MIN_CONTENT_CONTEXT
    content_reasoning_max_tokens: int = DEFAULT_CONTENT_REASONING_MAX_TOKENS
    conversation_model: str = PAID_CONVERSATION_MODEL
    allow_paid_content: bool = False
    high_free_limit: bool = False
    account: str = "default"
    state_path: Path = Path(__file__).resolve().parents[1] / "artifacts" / "interview_llm_limits.json"
    direct_providers_enabled: bool = False
    content_provider: str = "openrouter"
    check_provider: str = "openrouter"
    nvidia_content_model: str = DEFAULT_NVIDIA_CONTENT_MODEL
    groq_check_model: str = DEFAULT_GROQ_CHECK_MODEL
    groq_content_backup_model: str = DEFAULT_GROQ_CONTENT_BACKUP_MODEL

    @classmethod
    def from_env(cls):
        return cls(
            content_models=tuple(x.strip() for x in os.getenv("INTERVIEW_CONTENT_MODELS", "").split(",") if x.strip()),
            check_models=tuple(x.strip() for x in os.getenv("INTERVIEW_CHECK_MODELS", "").split(",") if x.strip()),
            allow_content_discovery=_flag("INTERVIEW_ALLOW_CONTENT_DISCOVERY"),
            allow_self_check=_flag("INTERVIEW_ALLOW_SELF_CHECK"),
            min_content_context=int(os.getenv("INTERVIEW_CONTENT_MIN_CONTEXT") or MIN_CONTENT_CONTEXT),
            content_reasoning_max_tokens=int(
                os.getenv("INTERVIEW_CONTENT_REASONING_MAX_TOKENS") or DEFAULT_CONTENT_REASONING_MAX_TOKENS
            ),
            conversation_model=os.getenv("INTERVIEW_CONVERSATION_MODEL", PAID_CONVERSATION_MODEL).strip(),
            allow_paid_content=_flag("ALLOW_PAID_CONTENT_FALLBACK"),
            high_free_limit=_flag("OPENROUTER_FREE_HIGH_LIMIT_CONFIRMED"),
            account=os.getenv("INTERVIEW_LLM_ACCOUNT", "default").strip(),
            state_path=Path(os.getenv("INTERVIEW_LLM_STATE_PATH") or str(cls.state_path)),
            direct_providers_enabled=_flag("INTERVIEW_DIRECT_PROVIDERS_ENABLED"),
            content_provider=(os.getenv("INTERVIEW_CONTENT_PROVIDER") or "openrouter").strip().lower(),
            check_provider=(os.getenv("INTERVIEW_CHECK_PROVIDER") or "openrouter").strip().lower(),
            nvidia_content_model=(os.getenv("NVIDIA_CONTENT_MODEL") or DEFAULT_NVIDIA_CONTENT_MODEL).strip(),
            groq_check_model=(os.getenv("GROQ_CHECK_MODEL") or DEFAULT_GROQ_CHECK_MODEL).strip(),
            groq_content_backup_model=(
                os.getenv("GROQ_CONTENT_BACKUP_MODEL", DEFAULT_GROQ_CONTENT_BACKUP_MODEL).strip()
            ),
        )


@dataclass
class InterviewScope:
    interview_id: str
    core_count: int
    models: dict[str, str] = field(default_factory=dict)
    providers: dict[str, str] = field(default_factory=dict)


@dataclass
class BatchScope:
    batch_id: str
    max_requests: int
    models: dict[str, str] = field(default_factory=dict)
    providers: dict[str, str] = field(default_factory=dict)


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


def actual_provider(purpose: str, default: str = "openrouter") -> str:
    scope = _SCOPE.get()
    return scope.providers.get(purpose, default) if scope is not None else default


def lane_for(purpose: str) -> str:
    if purpose in ALLOWED_BUNDLE_PURPOSES:
        return "content"
    if purpose in PERSONAL_PURPOSES:
        return "conversation"
    raise PrivacyViolation("Unclassified purpose; no dispatch permitted.")


def consumer_for(purpose: str) -> str:
    lane_for(purpose)
    return "interviewer" if purpose in {"interviewer_turn", "debrief"} else "questions"


def enforce_outbound_policy(*, purpose: str, model: str, personal_text: bool = False,
                            provider: str = "openrouter") -> None:
    if provider not in VALID_CONTENT_PROVIDERS:
        raise PrivacyViolation(f"Unsupported outbound provider {provider!r}.")
    is_free_model = isinstance(model, str) and model.casefold().endswith(":free")
    if provider != "openrouter" or is_free_model:
        if purpose not in ALLOWED_BUNDLE_PURPOSES:
            raise PrivacyViolation(
                f"Direct providers and :free models accept only {sorted(ALLOWED_BUNDLE_PURPOSES)}; refused {purpose!r}."
            )
        if personal_text:
            raise PrivacyViolation("Personal text cannot be sent to a direct provider or :free model.")
    lane = lane_for(purpose)
    personal = personal_text or purpose in PERSONAL_PURPOSES
    if lane == "conversation" and (model != PAID_CONVERSATION_MODEL or provider != "openrouter"):
        raise PrivacyViolation("Conversation text requires the paid Claude Haiku 4.5 allowlist.")
    if lane == "content" and personal:
        raise PrivacyViolation("Personal text is not permitted in the content lane.")


COACH_CHAT_PURPOSE = "coach_chat"


def enforce_coach_chat_outbound(*, model: str, provider: str = "openrouter") -> None:
    """Coach-chat conversation lane only: Haiku on OpenRouter, nothing else.

    Separate from the interview lanes so content/check routing is untouched.
    TODO(gemini_paid): allow gemini-2.5-flash-lite here only when the
    provider is gemini_paid and GEMINI_PAID_TIER_CONFIRMED is exactly true,
    per docs/design/coach_chat_v1.md. Not built tonight.
    """
    if provider == "gemini_paid":
        raise PrivacyViolation("gemini_paid is not built for coach chat; Haiku only.")
    if provider != "openrouter" or not isinstance(model, str) or model.casefold().endswith(":free"):
        raise PrivacyViolation("Coach chat requires the paid Claude Haiku 4.5 allowlist.")
    if model != PAID_CONVERSATION_MODEL:
        raise PrivacyViolation("Coach chat requires the paid Claude Haiku 4.5 allowlist.")


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


def _vendor_prefix(model: str | None) -> str:
    if not isinstance(model, str):
        return ""
    cleaned = model.strip().casefold().removeprefix("private/")
    if "/" not in cleaned:
        return ""
    return cleaned.split("/", 1)[0].strip()


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


def model_family(model: str | None, provider: str = "openrouter") -> str:
    """Resolve model family across providers for writer/checker separation."""
    if model and (provider, model) in DIRECT_PROVIDER_CAPABILITIES:
        return str(DIRECT_PROVIDER_CAPABILITIES[(provider, model)]["family"])
    low = (model or "").strip().casefold().removeprefix("private/")
    if not low:
        return ""
    if "nemotron" in low:
        return "nemotron"
    if "gpt-oss" in low:
        return "gpt-oss"
    if "qwen" in low:
        return "qwen"
    if low.startswith(("meta-llama/", "llama-", "llama3", "llama4")):
        return "llama"
    return _vendor_prefix(model)


def _same_writer_family(
    cand_provider: str, cand_model: str,
    gen_provider: str | None, gen_model: str | None,
) -> bool:
    if not gen_model:
        return False
    cand_fam = model_family(cand_model, cand_provider)
    gen_fam = model_family(gen_model, gen_provider or "openrouter")
    if cand_fam and gen_fam and cand_fam == gen_fam:
        return True
    cand_vendor = _vendor_prefix(cand_model)
    gen_vendor = _vendor_prefix(gen_model)
    return bool(cand_vendor and gen_vendor and cand_vendor == gen_vendor)


def _strip_thinking_tags(text: str) -> str:
    return re.sub(r"(?is)^\s*<think>.*?</think>\s*", "", text).strip()


def _prepare_direct_request(
    provider: str,
    model: str,
    purpose: str,
    lane: str,
    messages: list[dict[str, str]],
    max_tokens: int,
    expect_json: bool,
    reasoning_cap: int = DEFAULT_CONTENT_REASONING_MAX_TOKENS,
) -> tuple[list[dict[str, str]], int, dict | None, str | None, dict | None]:
    cap = DIRECT_PROVIDER_CAPABILITIES.get((provider, model))
    prepared = [dict(msg) for msg in messages]
    reasoning_control = cap.get("reasoning_control") if cap else None
    reasoning_effort: str | None = None
    chat_template_kwargs: dict | None = None
    if reasoning_control == "chat_template_thinking_off":
        chat_template_kwargs = {"enable_thinking": False}
    elif reasoning_control == "effort_none":
        reasoning_effort = "none"
    elif reasoning_control == "effort_low":
        reasoning_effort = "low"

    req_max = max_tokens + reasoning_cap if reasoning_control == "effort_low" else max_tokens
    if cap and type(cap.get("max_completion_tokens")) is int and cap["max_completion_tokens"] > 0:
        req_max = min(req_max, cap["max_completion_tokens"])

    resp_format: dict | None = None
    if expect_json:
        if not (cap and cap.get("supports_json_schema")):
            raise RoutingError(
                f"Direct model {(provider, model)!r} lacks strict json_schema support."
            )
        resp_format = response_format_for(purpose, lane, True)
        if resp_format is None or resp_format.get("type") != "json_schema":
            raise RoutingError(
                f"Content lane never sends json_object; unsupported format for {purpose!r}."
            )
    return prepared, req_max, resp_format, reasoning_effort, chat_template_kwargs


def check_nvidia_json_schema_support(
    *,
    model: str = DEFAULT_NVIDIA_CONTENT_MODEL,
    timeout_s: float = 15,
    opener=None,
) -> dict:
    """Check whether NVIDIA's hosted endpoint accepts response_format=json_schema for ``model``."""
    if opener is None:
        if not llm_outbound_gate.llm_consumer_enabled("questions"):
            raise RoutingError("LLM_LIVE_FETCH=1 and the questions consumer are required for NVIDIA schema probe.")
        key = os.getenv("NVIDIA_API_KEY", "").strip()
        if not key:
            raise RoutingError("NVIDIA_API_KEY is missing.")
    else:
        key = os.getenv("NVIDIA_API_KEY", "").strip() or "probe-override"
    body = {
        "model": model,
        "messages": [
            {"role": "user", "content": "Return {\"ok\": true}."},
        ],
        "max_tokens": 32,
        "temperature": 0.0,
        "chat_template_kwargs": {"enable_thinking": False},
        "response_format": {
            "type": "json_schema",
            "json_schema": {
                "name": "schema_probe",
                "strict": True,
                "schema": _object_schema(("ok",), {"ok": {"type": "boolean"}}),
            },
        },
    }
    req = urllib.request.Request(
        NVIDIA_CHAT_URL,
        data=json.dumps(body).encode(),
        method="POST",
        headers={
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
            "User-Agent": DIRECT_PROVIDER_USER_AGENT,
        },
    )
    do_open = opener or (lambda r: urllib.request.urlopen(r, timeout=timeout_s, context=_SSL_CTX))
    try:
        with do_open(req) as resp:
            status = getattr(resp, "status", 200)
            raw = resp.read()
        parsed = json.loads(raw) if raw else {}
        choices = parsed.get("choices") if isinstance(parsed, dict) else None
        supported = isinstance(choices, list) and bool(choices) and "error" not in parsed
        return {
            "provider": "nvidia",
            "model": model,
            "json_schema_supported": supported,
            "status": status,
            "detail": "ok" if supported else "unexpected_payload",
        }
    except urllib.error.HTTPError as exc:
        return {
            "provider": "nvidia",
            "model": model,
            "json_schema_supported": False,
            "status": exc.code,
            "detail": f"http_{exc.code}",
        }
    except (OSError, http.client.HTTPException, ValueError, TypeError) as exc:
        return {
            "provider": "nvidia",
            "model": model,
            "json_schema_supported": False,
            "status": type(exc).__name__,
            "detail": type(exc).__name__,
        }


@dataclass(frozen=True)
class Completion:
    text: str
    usage: tuple[int, int, int]
    model: str
    requested_model: str | None = None
    truncated: bool = False
    reasoning_tokens: int | None = None
    provider: str = "openrouter"
    headers: dict = field(default_factory=dict, repr=False, compare=False)


class InterviewRouter:
    def __init__(self, settings: RoutingSettings, *, catalog_source: Callable[[], dict] | None = None,
                 clock=time.time, budget: RequestBudget | None = None, sleep: Callable[[float], None] | None = None):
        self.settings = settings
        if type(settings.min_content_context) is not int or settings.min_content_context < 1:
            raise RoutingError("Content context minimum must be a positive integer.")
        if type(settings.content_reasoning_max_tokens) is not int or settings.content_reasoning_max_tokens < 1:
            raise RoutingError("Content reasoning token cap must be a positive integer.")
        if settings.content_provider not in VALID_CONTENT_PROVIDERS:
            raise RoutingError(f"Unsupported INTERVIEW_CONTENT_PROVIDER {settings.content_provider!r}.")
        if settings.check_provider not in VALID_CONTENT_PROVIDERS:
            raise RoutingError(f"Unsupported INTERVIEW_CHECK_PROVIDER {settings.check_provider!r}.")
        self.clock = clock
        self.sleep = sleep
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

    def _select_free_candidates(self, configured: tuple[str, ...], setting_name: str,
                                models: dict[str, dict]) -> tuple[str, ...]:
        if len(set(configured)) != len(configured):
            raise RoutingError(f"Duplicate content model IDs in {setting_name}.")
        if configured:
            eligible: list[str] = []
            for candidate in configured:
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
            return tuple(eligible)
        return tuple(sorted(model for model, row in models.items()
                            if _free_structured(row, self.settings.min_content_context)))

    def _direct_model_for(self, provider: str, *, is_check: bool, model_override: str | None = None) -> str:
        if model_override:
            model = model_override
        elif provider == "nvidia":
            model = self.settings.nvidia_content_model or DEFAULT_NVIDIA_CONTENT_MODEL
        elif provider == "groq":
            model = (
                (self.settings.groq_check_model or DEFAULT_GROQ_CHECK_MODEL)
                if is_check
                else (self.settings.groq_content_backup_model or DEFAULT_GROQ_CONTENT_BACKUP_MODEL)
            )
        else:
            raise RoutingError(f"Unsupported direct provider {provider!r}.")
        cap = DIRECT_PROVIDER_CAPABILITIES.get((provider, model))
        if cap is None:
            raise RoutingError(
                f"Direct model {(provider, model)!r} is missing from DIRECT_PROVIDER_CAPABILITIES."
            )
        if int(cap.get("context_length") or 0) < self.settings.min_content_context:
            raise RoutingError(
                f"Direct model {model!r} context length below {self.settings.min_content_context}."
            )
        if int(cap.get("cost") or 0) != 0:
            raise RoutingError(f"Direct model {model!r} is not zero-cost.")
        if not cap.get("supports_json_schema"):
            raise RoutingError(
                f"Direct model {model!r} on {provider!r} lacks strict json_schema support."
            )
        return model

    def _groq_backup_writer_available(self, *, offline_override: bool) -> bool:
        return bool(
            self.settings.groq_content_backup_model
            and (offline_override or os.getenv("GROQ_API_KEY", "").strip())
        )

    def _openrouter_fallback_available(self, *, offline_override: bool, is_check: bool) -> bool:
        configured = self.settings.check_models if is_check else self.settings.content_models
        if not configured and not self.settings.allow_content_discovery:
            return False
        return bool(offline_override or self.injected_catalog or os.getenv("OPENROUTER_API_KEY", "").strip())

    def content_candidates(self, *, offline_override: bool = False) -> tuple[str, ...]:
        return tuple(model for _, model in self.content_candidates_with_providers(offline_override=offline_override))

    def content_candidates_with_providers(self, *, offline_override: bool = False) -> tuple[tuple[str, str], ...]:
        if len(set(self.settings.content_models)) != len(self.settings.content_models):
            raise RoutingError("Duplicate content model IDs in INTERVIEW_CONTENT_MODELS.")
        if self.settings.direct_providers_enabled and self.settings.content_provider in {"nvidia", "groq"}:
            direct = (self.settings.content_provider, self._direct_model_for(self.settings.content_provider, is_check=False))
            candidates: list[tuple[str, str]] = [direct]
            if (
                self.settings.content_provider == "nvidia"
                and self._groq_backup_writer_available(offline_override=offline_override)
            ):
                backup = (
                    "groq",
                    self._direct_model_for(
                        "groq", is_check=False, model_override=self.settings.groq_content_backup_model
                    ),
                )
                if backup != direct:
                    candidates.append(backup)
            if self._openrouter_fallback_available(offline_override=offline_override, is_check=False):
                models = self._models("questions", offline_override)
                raw = self._select_free_candidates(self.settings.content_models, "INTERVIEW_CONTENT_MODELS", models)
                or_choices = raw if self.settings.content_models else raw[:3]
                candidates.extend(("openrouter", m) for m in or_choices)
            return tuple(candidates)
        models = self._models("questions", offline_override)
        raw = self._select_free_candidates(self.settings.content_models, "INTERVIEW_CONTENT_MODELS", models)
        choices = raw if self.settings.content_models else raw[:3]
        if self.settings.allow_paid_content and not self.settings.direct_providers_enabled:
            choices = (*choices, self._paid_model(models))
        if not choices:
            raise RoutingError("No zero-priced structured-output content model is available.")
        return tuple(("openrouter", m) for m in choices)

    def _active_generator_identity(self, *, offline_override: bool = False) -> tuple[str | None, str | None]:
        scope = _SCOPE.get()
        if scope is not None:
            for key in ("bundle_regeneration", "bundle_generation"):
                if key in scope.models and scope.models[key]:
                    return scope.providers.get(key, "openrouter"), scope.models[key]
        if self.settings.direct_providers_enabled and self.settings.content_provider in {"nvidia", "groq"}:
            try:
                return self.resolve_content_provider_and_model(offline_override=offline_override)
            except RoutingError:
                return None, None
        if not offline_override and not self.settings.content_models and not self.settings.allow_content_discovery:
            return None, None
        try:
            return self.resolve_content_provider_and_model(offline_override=offline_override)
        except RoutingError:
            return None, None

    def _active_generator_model(self, *, offline_override: bool = False) -> str | None:
        return self._active_generator_identity(offline_override=offline_override)[1]

    def check_candidates(self, *, offline_override: bool = False,
                         generator_model: str | None = None) -> tuple[str, ...]:
        return tuple(
            model for _, model in self.check_candidates_with_providers(
                offline_override=offline_override, generator_model=generator_model
            )
        )

    def check_candidates_with_providers(
        self,
        *,
        offline_override: bool = False,
        generator_model: str | None = None,
        generator_provider: str | None = None,
    ) -> tuple[tuple[str, str], ...]:
        if len(set(self.settings.check_models)) != len(self.settings.check_models):
            raise RoutingError("Duplicate content model IDs in INTERVIEW_CHECK_MODELS.")
        scope = _SCOPE.get()
        scoped_gen = (
            (scope.models.get("bundle_regeneration") or scope.models.get("bundle_generation"))
            if scope is not None else None
        )
        scoped_prov = (
            (scope.providers.get("bundle_regeneration") or scope.providers.get("bundle_generation"))
            if scope is not None else None
        )
        active_prov, active_mod = self._active_generator_identity(offline_override=offline_override)
        gen_model = generator_model or scoped_gen or active_mod
        gen_provider = generator_provider or scoped_prov or active_prov or "openrouter"

        if self.settings.direct_providers_enabled and self.settings.check_provider in {"nvidia", "groq"}:
            direct_model = self._direct_model_for(self.settings.check_provider, is_check=True)
            if not self.settings.allow_self_check and _same_writer_family(
                self.settings.check_provider, direct_model, gen_provider, gen_model
            ):
                raise RoutingError(
                    f"Checker model family ({model_family(direct_model, self.settings.check_provider)!r}) "
                    "matches generator; configure an independent family or set INTERVIEW_ALLOW_SELF_CHECK=true."
                )
            candidates: list[tuple[str, str]] = [(self.settings.check_provider, direct_model)]
            if self._openrouter_fallback_available(offline_override=offline_override, is_check=True):
                models = self._models("questions", offline_override)
                raw = self._select_free_candidates(self.settings.check_models, "INTERVIEW_CHECK_MODELS", models)
                or_choices = raw if self.settings.check_models else raw[:3]
                for m in or_choices:
                    if not self.settings.allow_self_check and _same_writer_family("openrouter", m, gen_provider, gen_model):
                        LOGGER.warning(
                            "interview_llm_content_candidate_skipped model=%s reason=%s",
                            m, "same_family_as_generator",
                            extra={"requested_model": m, "reason": "same_family_as_generator"},
                        )
                        continue
                    candidates.append(("openrouter", m))
            return tuple(candidates)

        models = self._models("questions", offline_override)
        raw = self._select_free_candidates(self.settings.check_models, "INTERVIEW_CHECK_MODELS", models)
        if self.settings.allow_paid_content and not self.settings.direct_providers_enabled:
            raw = (*raw, self._paid_model(models))
        gen_vendor = _vendor_prefix(gen_model)
        legacy_unconfigured_override = (
            offline_override
            and generator_model is None
            and scoped_gen is None
            and not self.settings.check_models
            and not self.settings.content_models
            and not self.settings.allow_content_discovery
        )
        if not self.settings.allow_self_check and gen_model:
            independent: list[str] = []
            saw_same = False
            for candidate in raw:
                if _same_writer_family("openrouter", candidate, gen_provider, gen_model):
                    saw_same = True
                    if self.settings.check_models:
                        LOGGER.warning("interview_llm_content_candidate_skipped model=%s reason=%s",
                                       candidate, "same_vendor_as_generator",
                                       extra={"requested_model": candidate, "reason": "same_vendor_as_generator"})
                else:
                    independent.append(candidate)
            choices = tuple(independent if self.settings.check_models else independent[:3])
            if not choices and legacy_unconfigured_override:
                choices = raw[:3]
            if not choices:
                if saw_same:
                    raise RoutingError(
                        f"Checker vendor prefix {gen_vendor or model_family(gen_model, gen_provider)!r} matches generator; "
                        "configure an independent vendor in INTERVIEW_CHECK_MODELS or set INTERVIEW_ALLOW_SELF_CHECK=true."
                    )
                raise RoutingError("No zero-priced structured-output checker model is available.")
            return tuple(("openrouter", m) for m in choices)
        choices = raw if self.settings.check_models else raw[:3]
        if not choices:
            raise RoutingError("No zero-priced structured-output checker model is available.")
        return tuple(("openrouter", m) for m in choices)

    def resolve_content_provider_and_model(self, *, offline_override: bool = False) -> tuple[str, str]:
        return self.content_candidates_with_providers(offline_override=offline_override)[0]

    def resolve_check_provider_and_model(
        self,
        *,
        offline_override: bool = False,
        generator_model: str | None = None,
        generator_provider: str | None = None,
    ) -> tuple[str, str]:
        if (
            not offline_override
            and not (self.settings.direct_providers_enabled and self.settings.check_provider in {"nvidia", "groq"})
            and not self.settings.check_models
            and not self.settings.allow_content_discovery
        ):
            raise RoutingError("Real checker dispatch requires INTERVIEW_CHECK_MODELS or explicit discovery opt-in.")
        return self.check_candidates_with_providers(
            offline_override=offline_override,
            generator_model=generator_model,
            generator_provider=generator_provider,
        )[0]

    def resolve_content_model(self, *, offline_override: bool = False) -> str:
        return self.content_candidates(offline_override=offline_override)[0]

    def resolve_check_model(self, *, offline_override: bool = False,
                            generator_model: str | None = None) -> str:
        return self.resolve_check_provider_and_model(
            offline_override=offline_override, generator_model=generator_model
        )[1]

    def dispatch(self, *, purpose: str, messages: list[dict[str, str]], max_tokens: int = 700,
                 temperature: float = 0.1, timeout_s: float = 20, personal_text: bool = False,
                 model: str | None = None, expect_json: bool = True, bundle_id: str | None = None,
                 override: Callable[[str], tuple[str, tuple[int, int, int]]] | None = None,
                 provider: str | None = None) -> Completion:
        lane, consumer = lane_for(purpose), consumer_for(purpose)
        expect_json = bool(expect_json and purpose != "bundle_blind_answer")
        is_check = purpose in CHECK_PURPOSES
        requested_provider = provider or ("openrouter" if lane == "conversation" else None)
        # Classify by purpose, not an optional caller-supplied privacy boolean.
        enforce_outbound_policy(
            purpose=purpose,
            model=model or self.settings.conversation_model,
            personal_text=personal_text,
            provider=requested_provider or "openrouter",
        )
        _gate(consumer, offline_override=override is not None)
        scope = _SCOPE.get()
        if scope is None:
            raise RoutingError("Missing interview_scope; no unbudgeted routing is permitted.")
        if isinstance(scope, BatchScope) and lane != "content":
            raise PrivacyViolation("Batch scope is content-only; conversation purposes are forbidden.")
        target_provider = (self.settings.check_provider if is_check else self.settings.content_provider)
        direct_for_lane = self.settings.direct_providers_enabled and target_provider in {"nvidia", "groq"}
        if lane == "content" and override is None and not self.settings.allow_content_discovery and not direct_for_lane:
            if is_check and not self.settings.check_models:
                raise RoutingError("Real checker dispatch requires INTERVIEW_CHECK_MODELS or explicit discovery opt-in.")
            if not is_check and not self.settings.content_models:
                raise RoutingError("Real content dispatch requires INTERVIEW_CONTENT_MODELS or explicit discovery opt-in.")
        if lane == "content":
            choices = (
                self.check_candidates_with_providers(offline_override=override is not None)
                if is_check
                else self.content_candidates_with_providers(offline_override=override is not None)
            )
            models = (
                self._models(consumer, override is not None)
                if any(p == "openrouter" for p, _ in choices)
                else {}
            )
        else:
            models = self._models(consumer, override is not None)
            choices = (("openrouter", self._paid_model(models)),)
        if model is not None:
            matched = tuple((p, m) for p, m in choices if m == model and (provider is None or p == provider))
            if not matched:
                raise RoutingError("Requested model is not a validated lane candidate.")
            choices = matched

        def log_fallback(idx_from: int, from_prov: str, from_mod: str, reason: str) -> None:
            next_prov, next_mod = choices[idx_from + 1]
            LOGGER.warning(
                "interview_llm_writer_fallback purpose=%s from_provider=%s from_model=%s to_provider=%s to_model=%s reason=%s",
                purpose, from_prov, from_mod, next_prov, next_mod, reason,
                extra={
                    "purpose": purpose, "from_provider": from_prov, "from_model": from_mod,
                    "to_provider": next_prov, "to_model": next_mod, "reason": reason,
                },
            )

        for idx, (choice_provider, choice) in enumerate(choices):
            has_fallback = idx + 1 < len(choices)
            is_direct = choice_provider in {"nvidia", "groq"}
            enforce_outbound_policy(
                purpose=purpose, model=choice, personal_text=personal_text, provider=choice_provider
            )
            entry = models.get(choice, {}) if choice_provider == "openrouter" else {}
            free = (not is_direct) and _free_structured(entry, self.settings.min_content_context)
            if is_direct:
                (
                    send_messages,
                    request_max_tokens,
                    direct_resp_fmt,
                    direct_effort,
                    direct_chat_template_kwargs,
                ) = _prepare_direct_request(
                    choice_provider, choice, purpose, lane, messages, max_tokens, expect_json,
                    reasoning_cap=self.settings.content_reasoning_max_tokens,
                )
                reasoning_cfg = None
            else:
                send_messages = messages
                direct_resp_fmt = response_format_for(purpose, lane, expect_json)
                direct_effort = None
                direct_chat_template_kwargs = None
                reasoning_cfg, request_max_tokens = (
                    _content_reasoning_config(entry, max_tokens, self.settings.content_reasoning_max_tokens, messages)
                    if lane == "content" else (None, max_tokens)
                )

            max_attempts = 2 if is_direct else 1
            for attempt in range(max_attempts):
                try:
                    if isinstance(scope, BatchScope):
                        token = self.budget.reserve_batch(
                            batch_id=scope.batch_id, max_requests=scope.max_requests,
                            lane=lane, model=choice, free=free, timeout_s=timeout_s,
                            provider=choice_provider,
                        )
                    else:
                        token = self.budget.reserve(
                            interview_id=scope.interview_id, core_count=scope.core_count,
                            lane=lane, model=choice, free=free, timeout_s=timeout_s,
                            provider=choice_provider,
                        )
                except DispatchDeferred as exc:
                    if (
                        exc.reason in {"model_backoff", "nvidia_backoff", "nvidia_minute", "groq_rate_limit"}
                        and model is None and lane == "content" and has_fallback
                    ):
                        log_fallback(idx, choice_provider, choice, exc.reason)
                        break
                    if (
                        exc.reason == "free_daily"
                        and not self.settings.direct_providers_enabled
                        and self.settings.allow_paid_content
                        and lane == "content"
                        and free
                    ):
                        break
                    raise

                started = time.monotonic()
                usage = (0, 0, 0)
                returned_model = None
                reasoning_tokens = None
                status, error_kind = "ok", None
                try:
                    # Recheck after catalog/admission as flags may have changed concurrently.
                    _gate(consumer, offline_override=override is not None)
                    enforce_outbound_policy(
                        purpose=purpose, model=choice, personal_text=personal_text, provider=choice_provider
                    )
                    scope.models[purpose] = choice
                    scope.providers[purpose] = choice_provider
                    if override is not None:
                        result = override(choice)
                        if isinstance(result, Completion):
                            text, usage, returned_model = result.text, result.usage, result.model
                            reasoning_tokens = result.reasoning_tokens
                            resp_headers = result.headers or {}
                        else:
                            text, usage = result
                            returned_model = choice
                            resp_headers = {}
                    elif is_direct:
                        result = self._chat_direct_once(
                            choice_provider, choice, send_messages, request_max_tokens,
                            temperature, timeout_s, expect_json, direct_resp_fmt, direct_effort,
                            direct_chat_template_kwargs,
                        )
                        text, usage, returned_model = result.text, result.usage, result.model
                        reasoning_tokens = result.reasoning_tokens
                        resp_headers = result.headers or {}
                    else:
                        result = self._chat_once(
                            choice, send_messages, request_max_tokens, temperature, timeout_s, expect_json,
                            reasoning_cfg, direct_resp_fmt,
                        )
                        text, usage, returned_model = result.text, result.usage, result.model
                        reasoning_tokens = result.reasoning_tokens
                        resp_headers = getattr(result, "headers", {}) or {}
                    if choice_provider == "groq" and resp_headers:
                        self.budget.record_groq_headers(resp_headers)
                    canonical_slug = (
                        models.get(choice, {}).get("canonical_slug")
                        if choice_provider == "openrouter"
                        else DIRECT_PROVIDER_CAPABILITIES.get((choice_provider, choice), {}).get("canonical_slug")
                    )
                    if not same_model_family(choice, returned_model, canonical_slug=canonical_slug):
                        raise PrivacyViolation("Provider model identifier is missing or outside the requested family.")
                    self.budget.record_served_model(choice, returned_model, provider=choice_provider)
                    scope.models[purpose] = returned_model
                    scope.providers[purpose] = choice_provider
                    if isinstance(result, Completion) and result.truncated:
                        from modules.llm_errors import LLMTruncatedError
                        raise LLMTruncatedError(model=returned_model, provider=choice_provider, usage=usage)
                    return Completion(
                        text, usage, returned_model, choice, False, reasoning_tokens, choice_provider, resp_headers
                    )
                except urllib.error.HTTPError as exc:
                    status = "error"
                    hdrs = exc.headers or {}
                    if choice_provider == "groq":
                        self.budget.record_groq_headers(hdrs)
                    decision = classify_http_error(exc.code, exc.read(), hdrs, now=self.clock(), lane=lane)
                    error_kind = decision.kind
                    if decision.kind in {"authorization", "credits"}:
                        self.budget.record_failure(choice, decision, free=free, provider=choice_provider)
                        raise DispatchDeferred(decision.kind, decision.retry_at) from exc
                    if is_direct and decision.kind in {"rpm", "in_flight", "upstream"} and attempt + 1 < max_attempts:
                        if self.sleep is not None and decision.retry_at is not None:
                            delay = min(5.0, max(0.0, decision.retry_at - self.clock()))
                            if delay > 0:
                                self.sleep(delay)
                        continue
                    self.budget.record_failure(choice, decision, free=free, provider=choice_provider)
                    if is_direct and has_fallback:
                        log_fallback(idx, choice_provider, choice, error_kind)
                        break
                    raise DispatchDeferred(decision.kind, decision.retry_at) from exc
                except ProviderResponseDeferred as exc:
                    usage, returned_model, reasoning_tokens = exc.usage, exc.model, exc.reasoning_tokens
                    if choice_provider == "groq" and exc.headers:
                        self.budget.record_groq_headers(exc.headers)
                    status = "truncated" if exc.reason == "truncated" else "error"
                    decision = (classify_http_error(exc.code, exc.body, exc.headers, now=self.clock(), lane=lane)
                                if exc.code is not None else LimitDecision(exc.reason, self.clock() + 300))
                    if decision.kind == "http_error":
                        decision = LimitDecision("provider_error", self.clock() + 300)
                    error_kind = decision.kind
                    self.budget.record_failure(choice, decision, free=free, provider=choice_provider)
                    if decision.kind in {"authorization", "credits"}:
                        raise DispatchDeferred(decision.kind, decision.retry_at,
                                               reasoning_tokens=reasoning_tokens) from exc
                    if is_direct and has_fallback:
                        log_fallback(idx, choice_provider, choice, error_kind)
                        break
                    raise DispatchDeferred(decision.kind, decision.retry_at,
                                           reasoning_tokens=reasoning_tokens) from exc
                except (OSError, http.client.HTTPException) as exc:
                    reason = getattr(exc, "reason", exc)
                    error_kind = "timeout" if isinstance(reason, TimeoutError) else "network_unavailable"
                    status = "error"
                    decision = LimitDecision(error_kind, self.clock() + 4)
                    self.budget.record_failure(choice, decision, free=free, provider=choice_provider)
                    if is_direct and has_fallback:
                        log_fallback(idx, choice_provider, choice, error_kind)
                        break
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
                        LOGGER.info(
                            "interview_llm_dispatch provider=%s requested_model=%s returned_model=%s status=%s reasoning_tokens=%s",
                            choice_provider, choice, returned_model, status, reasoning_tokens,
                            extra={"provider": choice_provider, "requested_model": choice,
                                   "returned_model": returned_model, "purpose": purpose,
                                   "reasoning_tokens": reasoning_tokens},
                        )
                        log_llm_usage(
                            provider=choice_provider, model=returned_model or choice, purpose=purpose,
                            prompt_tokens=usage[0], completion_tokens=usage[1], total_tokens=usage[2],
                            latency_ms=int((time.monotonic() - started) * 1000), status=status,
                            error=error_kind, bundle_id=bundle_id,
                        )
        raise DispatchDeferred("content_models_unavailable")

    @staticmethod
    def _chat_http_post(url: str, key: str, body: dict, model: str, timeout_s: float, *,
                        provider: str = "openrouter", strip_think: bool = False) -> Completion:
        headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
        if provider in {"nvidia", "groq"}:
            headers["User-Agent"] = DIRECT_PROVIDER_USER_AGENT
        request = urllib.request.Request(
            url, data=json.dumps(body).encode(), method="POST",
            headers=headers,
        )
        with urllib.request.urlopen(request, timeout=timeout_s, context=_SSL_CTX) as response:
            raw = response.read()
            headers = dict(getattr(response, "headers", {}) or {})
        try:
            data = json.loads(raw)
        except (ValueError, UnicodeDecodeError) as exc:
            raise ProviderResponseDeferred("invalid_response", headers=headers) from exc
        if not isinstance(data, dict):
            raise ProviderResponseDeferred("invalid_response", headers=headers)
        usage = data.get("usage")
        usage = usage if isinstance(usage, dict) else {}

        def count(source, k):
            value = source.get(k)
            if isinstance(value, str) and len(value) <= 20 and value.isascii() and value.isdigit():
                return int(value)
            return value if type(value) is int and value >= 0 else None

        prompt, completion = count(usage, "prompt_tokens") or 0, count(usage, "completion_tokens") or 0
        counts = (prompt, completion, count(usage, "total_tokens") or prompt + completion)
        details = usage.get("completion_tokens_details")
        reasoning_tokens = count(details, "reasoning_tokens") if isinstance(details, dict) else None
        metadata = {
            "usage": counts, "model": data.get("model"),
            "reasoning_tokens": reasoning_tokens, "headers": headers,
        }
        if "error" in data:
            error = data["error"]
            code = error.get("code") if isinstance(error, dict) else None
            if isinstance(code, str) and len(code) == 3 and code.isascii() and code.isdigit():
                code = int(code)
            code = code if type(code) is int and 400 <= code <= 599 else None
            raise ProviderResponseDeferred("provider_error", **metadata, code=code, body=json.dumps(data))
        choices = data.get("choices")
        if not isinstance(choices, list) or not choices or not isinstance(choices[0], dict):
            raise ProviderResponseDeferred("invalid_response", **metadata)
        if choices[0].get("finish_reason") == "length":
            raise ProviderResponseDeferred("truncated", **metadata)
        message = choices[0].get("message")
        if not isinstance(message, dict):
            raise ProviderResponseDeferred("invalid_response", **metadata)
        content = message.get("content")
        if not isinstance(content, str) if content is not None else False:
            raise ProviderResponseDeferred("invalid_response", **metadata)
        if strip_think and content is not None:
            content = _strip_thinking_tags(content)
        if content is None or not content.strip():
            raise ProviderResponseDeferred("empty_response", **metadata)
        return Completion(content, counts, data.get("model"), model, False, reasoning_tokens, provider, headers)

    @classmethod
    def _chat_once(cls, model, messages, max_tokens, temperature, timeout_s, expect_json, reasoning=None,
                   response_format=None):
        key = os.getenv("OPENROUTER_API_KEY", "").strip()
        if not key:
            raise RoutingError("OPENROUTER_API_KEY is missing.")
        body = {"model": model, "messages": messages, "max_tokens": max_tokens, "temperature": temperature}
        if response_format is not None:
            body["response_format"] = response_format
        elif expect_json:
            body["response_format"] = {"type": "json_object"}
        if reasoning is not None:
            body["reasoning"] = reasoning
        return cls._chat_http_post(CHAT_URL, key, body, model, timeout_s, provider="openrouter", strip_think=False)

    @classmethod
    def _chat_direct_once(cls, provider, model, messages, max_tokens, temperature, timeout_s,
                          expect_json, response_format=None, reasoning_effort=None,
                          chat_template_kwargs=None):
        if provider == "nvidia":
            url, env_name = NVIDIA_CHAT_URL, "NVIDIA_API_KEY"
        elif provider == "groq":
            url, env_name = GROQ_CHAT_URL, "GROQ_API_KEY"
        else:
            raise RoutingError(f"Unsupported direct provider {provider!r}.")
        key = os.getenv(env_name, "").strip()
        if not key:
            raise RoutingError(f"{env_name} is missing.")
        body = {"model": model, "messages": messages, "max_tokens": max_tokens, "temperature": temperature}
        if expect_json:
            if response_format is None or response_format.get("type") != "json_schema":
                raise RoutingError("Direct content/check lane requires strict json_schema, never json_object.")
            body["response_format"] = response_format
        elif response_format is not None:
            body["response_format"] = response_format
        if reasoning_effort is not None:
            body["reasoning_effort"] = reasoning_effort
        if chat_template_kwargs is not None:
            body["chat_template_kwargs"] = chat_template_kwargs
        return cls._chat_http_post(url, key, body, model, timeout_s, provider=provider, strip_think=True)


@lru_cache(maxsize=4)
def _router(settings: RoutingSettings) -> InterviewRouter:
    return InterviewRouter(settings)


def get_router() -> InterviewRouter:
    return _router(RoutingSettings.from_env())
