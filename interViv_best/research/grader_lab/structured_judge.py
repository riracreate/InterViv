"""Deferred structured-LLM judge contract.

The lab registers this baseline so reports remain explicit about the missing
comparison, but the deferred object has no client, credential, or transport.
"""

from __future__ import annotations

from dataclasses import dataclass


class DeferredBaselineError(RuntimeError):
    pass


@dataclass
class StructuredJudgeBaseline:
    name: str = "structured_llm_rubric_judge"
    status: str = "deferred"
    api_call_count: int = 0
    model_version: str = "unscoped"

    # TODO: add structured-judge baseline once cost/latency/API policy is scoped
    def predict(self, *_args, **_kwargs):
        raise DeferredBaselineError(
            "Structured judge is deferred and must not execute until policy is scoped."
        )

    def manifest_versions(self) -> dict[str, str]:
        return {
            "structured_judge": self.model_version,
            "execution": "deferred_zero_api_calls",
        }
