"""Narration provider boundary (Phase 3B).

Providers turn an attempt snapshot + rules feedback into a proposed narration
artifact. Calls happen **outside** scoring transactions — the attempt commit
only enqueues a job; the worker (or a test harness) invokes the provider after
the score is durable.

Live generation stays behind ``llm_live_fetch_enabled()``. The default
provider returns ``None`` so production keeps deterministic rules narration.
"""
from __future__ import annotations

from typing import Any, Protocol


class NarrationProvider(Protocol):
    def generate_narration(
        self,
        *,
        snapshot: dict[str, Any],
        rules_feedback: dict[str, Any] | None,
        job: dict[str, Any],
    ) -> dict[str, Any] | None:
        """Return a proposed narration artifact dict, or None if unavailable."""


class NullNarrationProvider:
    """Default live-disabled provider: never generates."""

    def generate_narration(
        self,
        *,
        snapshot: dict[str, Any],
        rules_feedback: dict[str, Any] | None,
        job: dict[str, Any],
    ) -> dict[str, Any] | None:
        return None


class FakeNarrationProvider:
    """Test double: scripted artifact, invalid payload, or raised error."""

    def __init__(
        self,
        *,
        artifact: dict[str, Any] | None = None,
        invalid: bool = False,
        raise_error: BaseException | None = None,
        model: str = "fake-narration",
    ) -> None:
        self.artifact = artifact
        self.invalid = invalid
        self.raise_error = raise_error
        self.model = model
        self.calls = 0

    def generate_narration(
        self,
        *,
        snapshot: dict[str, Any],
        rules_feedback: dict[str, Any] | None,
        job: dict[str, Any],
    ) -> dict[str, Any] | None:
        self.calls += 1
        if self.raise_error is not None:
            raise self.raise_error
        if self.invalid:
            return {
                "version": 1,
                "source": self.model,
                "script": "See https://evil.example/leak for the ideal answer.",
                "sections": {
                    "content": ["injected"],
                    "strengths": [],
                    "weakness": [],
                    "next_step": "",
                },
                "invented_score": 99.0,
            }
        if self.artifact is not None:
            payload = dict(self.artifact)
            payload.setdefault("source", self.model)
            payload.setdefault(
                "metadata",
                {"model": self.model, "prompt_version": 1, "schema_version": 1},
            )
            return payload
        feedback = rules_feedback or {}
        content = feedback.get("content") or []
        if isinstance(content, str):
            content = [content] if content else []
        script = " ".join(str(item) for item in content) or "Practice feedback narration."
        return {
            "version": 1,
            "source": self.model,
            "script": script[:500],
            "sections": {
                "content": [str(item) for item in content][:6],
                "strengths": list(feedback.get("strengths") or [])[:6],
                "weakness": list(
                    feedback.get("weakness") or feedback.get("weaknesses") or []
                )[:6],
                "next_step": str(feedback.get("next_step") or ""),
            },
            "metadata": {
                "model": self.model,
                "prompt_version": 1,
                "schema_version": 1,
            },
        }


_PROVIDER: NarrationProvider = NullNarrationProvider()


def set_narration_provider(provider: NarrationProvider | None) -> None:
    """Inject a provider for tests; ``None`` restores the null default."""
    global _PROVIDER
    _PROVIDER = provider if provider is not None else NullNarrationProvider()


def get_narration_provider() -> NarrationProvider:
    return _PROVIDER
