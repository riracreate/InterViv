"""System-initiated follow-ups (Slice 1): flag, trigger registry, prompt check.

Default-off and inert. Insertion additionally requires a registered
trigger that actually proposes a prompt, and the shipped default trigger
always returns ``None`` -- so even with ``SYSTEM_FOLLOW_UPS_ENABLED=true``
nothing is scheduled until a trigger is registered (tests inject a stub).

A proposal is only a request. Scheduling happens inside the parent's own
attempt commit through the shared ``modules.follow_ups`` rules, which call
:func:`validate_system_prompt` for the system initiator only.

The trigger receives deep copies and its exceptions are contained: a
failing trigger yields no follow-up, never a failed submission.
"""

from __future__ import annotations

import copy
import logging
import re
from dataclasses import dataclass
from typing import Any, Callable

logger = logging.getLogger(__name__)

SYSTEM_PROMPT_MAX_CHARS = 300

# Score / feedback language a neutral follow-up question must not carry:
# the follow-up is asked before (or without) any reveal, so it may not
# grade, praise, or diagnose the parent answer.
_FEEDBACK_PATTERNS = tuple(
    re.compile(pattern, re.IGNORECASE)
    for pattern in (
        r"\bscor(?:e|es|ed|ing)\b",
        r"\bgrad(?:e|es|ed|ing)\b",
        r"\bmarks?\b",
        r"\bpercent(?:age)?\b",
        r"\d\s*%",
        r"\b\d+\s*/\s*\d+\b",
        r"\bout of \d+\b",
        r"\bfeedback\b",
        r"\b(?:in)?correct(?:ly)?\b",
        r"\bwrong\b",
        r"\bmistakes?\b",
        r"\byou (?:missed|forgot|omitted|overlooked)\b",
        r"\byou (?:did not|didn't|failed to) (?:mention|explain|cover|address)\b",
        r"\byour answer (?:was|is|lacked|lacks|missed)\b",
        r"\b(?:well done|good job|great job|nice job|great answer|good answer)\b",
        r"\b(?:excellent|perfect)\b",
    )
)


@dataclass(frozen=True)
class SystemFollowUpProposal:
    prompt: str
    kind: str = "clarification"


TriggerFn = Callable[[dict[str, Any]], "SystemFollowUpProposal | str | dict | None"]


def default_trigger(context: dict[str, Any]) -> None:
    """Shipped trigger: never proposes. Real triggers are later slices."""
    return None


_TRIGGER: TriggerFn | None = default_trigger


def register_trigger(trigger: TriggerFn | None) -> None:
    global _TRIGGER
    _TRIGGER = trigger


def reset_trigger() -> None:
    register_trigger(default_trigger)


def current_trigger() -> TriggerFn | None:
    return _TRIGGER


def system_follow_ups_enabled() -> bool:
    from backend.config import get_settings

    return bool(getattr(get_settings(), "system_follow_ups_enabled", False))


def _ideal_surfaces(question_context: dict[str, Any]) -> list[list[str]]:
    """Alias surfaces for every rubric concept of the parent question.

    Same sources and matcher inputs as concept exclusion
    (``modules.question_concepts``): bundle required concepts, explicit
    ideal keywords, and indexed bank concepts. Read-only; no extraction.
    """
    from modules.question_concepts import explicit_entries, keyword_list, lookup

    context = question_context or {}
    bundle = context.get("bundle_content") or context
    entries: list[dict[str, Any]] = []
    entries += explicit_entries(list(bundle.get("required_concepts") or []), "bundle_v2")
    keywords = keyword_list(context.get("ideal_keywords")) + keyword_list(
        context.get("ideal_keywords_list")
    )
    entries += explicit_entries(keywords, "ideal_keywords")
    if context.get("question"):
        indexed, _status = lookup(context)
        entries += list((indexed or {}).get("concepts") or [])
    return [list(entry.get("aliases") or []) for entry in entries if entry.get("aliases")]


def validate_system_prompt(
    prompt: Any,
    *,
    parent_answer: str | None,
    question_context: dict[str, Any] | None,
) -> tuple[bool, str]:
    """Validate a system follow-up prompt. Returns ``(ok, reason)``.

    Rules: trimmed non-empty; exactly one ``?``; at most 300 characters;
    no score/feedback language; no rubric concept that the candidate's
    submitted parent answer does not itself contain (whole-token alias
    match via ``aliases_for`` + ``first_offset``, as in concept exclusion).
    """
    from modules.question_concepts import first_offset

    text = str(prompt or "").strip()
    if not text:
        return False, "prompt_empty"
    if text.count("?") != 1:
        return False, "prompt_question_mark_count"
    if len(text) > SYSTEM_PROMPT_MAX_CHARS:
        return False, "prompt_too_long"
    if any(pattern.search(text) for pattern in _FEEDBACK_PATTERNS):
        return False, "prompt_feedback_language"
    answer = str(parent_answer or "")
    for surfaces in _ideal_surfaces(question_context or {}):
        if first_offset(text, surfaces) is not None and first_offset(answer, surfaces) is None:
            return False, "prompt_reveals_unstated_concept"
    return True, ""


def _normalize_proposal(raw: Any) -> SystemFollowUpProposal | None:
    if raw is None:
        return None
    if isinstance(raw, SystemFollowUpProposal):
        return raw
    if isinstance(raw, str):
        return SystemFollowUpProposal(prompt=raw)
    if isinstance(raw, dict) and raw.get("prompt") is not None:
        return SystemFollowUpProposal(
            prompt=str(raw["prompt"]), kind=str(raw.get("kind") or "clarification")
        )
    return None


def propose_system_follow_up(
    *,
    session: dict[str, Any],
    parent_round_doc: dict[str, Any],
    parent_answer: str | None,
    scoring_result: dict[str, Any] | None,
) -> SystemFollowUpProposal | None:
    """Ask the registered trigger for a follow-up, after cheap gates.

    Gates (all required): flag on; a registered trigger; the existing
    session opt-in ``allow_optional_follow_ups``; a non-follow-up short
    answer parent; complete mandatory indices; mandatory work remaining.
    Consent (``accept_eligibility_consequence``) is a candidate-request
    field and is never consulted here. Caps, capacity, placement safety
    and the prompt rules are re-checked at commit time on a fresh read.
    """
    from modules.follow_ups import mandatory_indices_complete, remaining_questions

    if not system_follow_ups_enabled():
        return None
    trigger = current_trigger()
    if trigger is None:
        return None
    if not isinstance(session, dict) or session.get("allow_optional_follow_ups") is not True:
        return None
    if not isinstance(parent_round_doc, dict) or parent_round_doc.get("is_follow_up"):
        return None
    if (parent_round_doc.get("round_type") or "technical_short_answer") != "technical_short_answer":
        return None
    if not mandatory_indices_complete(session):
        return None
    if remaining_questions(session, int(parent_round_doc.get("round") or 0)) < 1:
        return None
    context = {
        "session": copy.deepcopy(session),
        "parent_round": copy.deepcopy(parent_round_doc),
        "parent_answer": str(parent_answer or ""),
        "scoring_result": copy.deepcopy(scoring_result or {}),
    }
    try:
        return _normalize_proposal(trigger(context))
    except Exception:
        logger.warning("System follow-up trigger failed; no follow-up proposed.", exc_info=True)
        return None
