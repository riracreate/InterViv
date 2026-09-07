"""Shared gate for chat-completion outbound (Phase Q).

``LLM_LIVE_FETCH`` defaults to ``0`` via ``backend.runtime_env.apply_runtime_env``.
Absent credentials are not a gate — this flag must be on before any
``urlopen`` to OpenAI/OpenRouter.

Question-generation dials also require ``QUESTION_GENERATION_MODE`` in
``{llm, llm_csv_fallback}`` so the adaptive path cannot bypass the mode
check that ``generate_question`` already honors.
"""

from __future__ import annotations

import os


def llm_live_fetch_enabled() -> bool:
    raw = os.getenv("LLM_LIVE_FETCH")
    if raw is None:
        return False
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def question_generation_mode() -> str:
    """Mirror ``question_bank._question_generation_mode`` without importing it.

    Kept local so the gate module stays free of circular imports with
    ``question_bank`` / ``question_runtime``.
    """
    raw = (
        os.getenv("QUESTION_GENERATION_MODE")
        or os.getenv("INTERVIV_QUESTION_SOURCE")
        or "llm"
    )
    mode = raw.strip().lower().replace("-", "_")
    aliases = {
        "llm_with_csv_fallback": "llm_csv_fallback",
        "llm_csv": "llm_csv_fallback",
        "dataset": "csv",
        "question_bank": "csv",
    }
    mode = aliases.get(mode, mode)
    allowed = {"llm", "csv", "llm_csv_fallback"}
    return mode if mode in allowed else "llm"


def question_llm_outbound_allowed() -> bool:
    """True only when live fetch is on and generation mode permits dialing."""
    if not llm_live_fetch_enabled():
        return False
    return question_generation_mode() in {"llm", "llm_csv_fallback"}
