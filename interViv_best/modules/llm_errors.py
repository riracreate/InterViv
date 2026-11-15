"""Shared LLM error types for batch pre-generation and role-skill extraction."""

from __future__ import annotations

from typing import Any


class LLMCreditExhaustedError(RuntimeError):
    """Raised when an LLM API call returns HTTP 402 (credits exhausted / insufficient).

    HTTP 402 is non-retryable and must abort batch runs immediately so the caller
    can top up credits and resume from cached progress.
    """

    def __init__(
        self,
        message: str = "LLM credit exhausted (HTTP 402).",
        *,
        status_code: int = 402,
        provider: str | None = None,
        model: str | None = None,
        purpose: str | None = None,
        detail: str | None = None,
        credit_info: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.status_code = int(status_code)
        self.provider = provider
        self.model = model
        self.purpose = purpose
        self.detail = detail
        self.credit_info = dict(credit_info) if credit_info else {}


class LLMTruncatedError(RuntimeError):
    """Raised when an LLM output was truncated at the token limit.

    Triggered when OpenAI/OpenRouter returns ``finish_reason == "length"`` or
    Ollama returns ``done_reason == "length"``. Callers must log the failure and
    must NOT attempt to parse truncated JSON/text payloads.
    """

    def __init__(
        self,
        message: str = "LLM response truncated (finish_reason='length').",
        *,
        finish_reason: str = "length",
        provider: str | None = None,
        model: str | None = None,
        purpose: str | None = None,
        usage: tuple[int, int, int] | None = None,
    ) -> None:
        super().__init__(message)
        self.finish_reason = finish_reason
        self.provider = provider
        self.model = model
        self.purpose = purpose
        self.usage = usage
