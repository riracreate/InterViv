"""Adaptive question selector — Phase 2 Task 7.

After each round, the selector:

  1. Reads the user's ``ConceptMastery`` for the skill the rotation
     picked for the NEXT round.
  2. Identifies the weakest concepts (Untested + Weak levels) — up
     to ``DEFAULT_TARGET_CONCEPT_LIMIT``.
  3. If at least one target concept is available AND an LLM
     provider is configured, generates a question via the LLM
     with the spec-7b prompt extension that primes the model on
     the target concepts.
  4. Otherwise falls back transparently to
     ``modules.question_bank.get_next_question(...)``, which
     handles its own LLM/CSV/template chain.

Design notes
------------

- We deliberately do NOT override the rotation's skill choice.
  The session route already rotates skills (``A A A B B B …``)
  based on the user's selected resume skills; that's the breadth
  guarantee. The adaptive layer adds depth WITHIN the rotation
  skill by steering question generation at the concept level.
  Concept mastery accumulates as the session progresses, so this
  naturally produces "rounds 3-6 increasingly target the user's
  weak concepts" — the evidence the spec asks for.

- We do not modify ``modules/question_bank.py`` (it's on the
  protected list). We reuse its ``_build_llm_prompt`` helper and
  route HTTP/cache/retry behavior through ``modules.question_runtime``.

- Falls back gracefully when:
    - the user is anonymous (``user_id`` empty) → no concepts
    - the user has no concept mastery yet  → empty target list
    - the LLM call fails / times out      → CSV/template fallback
    - the target skill is unknown to the KG → empty target list
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Optional

from modules.concept_mastery import ConceptMastery, MasteryLevel
from modules.question_runtime import (
    MarketQuestionContext,
    QuestionCacheContext,
    build_question_prompt,
    call_llm_with_cache_retry,
    generate_question,
    parse_llm_json,
)
from modules.skill_graph import StudentSkillGraph


LOGGER = logging.getLogger(__name__)


DEFAULT_TARGET_CONCEPT_LIMIT = 2
_CURRENT_CACHE_CONTEXT: QuestionCacheContext | None = None
_CURRENT_ASKED: list[str] = []


SPEC_PROMPT_EXTENSION_TEMPLATE = (
    "\n\nADDITIONAL TARGETING: Generate a question that primarily tests "
    "the following concepts: {concept_list}. The question should naturally "
    "require the candidate to demonstrate understanding of these concepts.\n"
)


@dataclass(frozen=True)
class AdaptiveTarget:
    skill: str
    difficulty: str
    target_concepts: list[str]
    source: str
    current_elo: float | None = None
    target_role_id: str | None = None

    def to_dict(self) -> dict:
        return {
            "skill": self.skill,
            "difficulty": self.difficulty,
            "target_concepts": self.target_concepts,
            "source": self.source,
            "current_elo": self.current_elo,
            "target_role_id": self.target_role_id,
        }


def _difficulty_from_elo(elo: float | None, fallback: str) -> str:
    if elo is None:
        return fallback
    if elo < 1200:
        return "easy"
    if elo < 1700:
        return "medium"
    return "hard"


def _display_concept(value: str) -> str:
    return str(value).replace("_", " ").strip()


def _normalise_skill_set(skills: list[str] | None) -> set[str]:
    return {str(skill).strip().lower() for skill in (skills or []) if str(skill).strip()}


def _state_for_skill(state: dict, skill: str):
    direct = state.get(skill)
    if direct is not None:
        return direct
    lower = skill.lower()
    for name, node in state.items():
        if str(name).lower() == lower:
            return node
    return None


def _candidate_elo(candidate_elo_by_skill: dict[str, float] | None, skill: str) -> float | None:
    if not candidate_elo_by_skill:
        return None
    if skill in candidate_elo_by_skill:
        return float(candidate_elo_by_skill[skill])
    lower = skill.lower()
    for name, elo in candidate_elo_by_skill.items():
        if str(name).lower() == lower:
            return float(elo)
    return None


def _skill_graph_elo(state: dict, skill: str) -> float | None:
    node = _state_for_skill(state, skill)
    if node is None:
        return None
    try:
        return float(getattr(node, "current_elo", 1200.0))
    except (TypeError, ValueError):
        return None


def choose_adaptive_target(
    *,
    user_id: Optional[str],
    fallback_skill: str,
    fallback_difficulty: str,
    session_skills: list[str] | None = None,
    target_role_id: Optional[str] = None,
    candidate_elo_by_skill: dict[str, float] | None = None,
    concept_limit: int = DEFAULT_TARGET_CONCEPT_LIMIT,
) -> AdaptiveTarget:
    """Choose the next skill + weakest concepts for Task 7.

    Priority:
      1. If a role is selected, recompute Gap Analysis and pick the
         top ranked weak area.
      2. Otherwise, pick the lowest-scoring skill from StudentSkillGraph.
      3. If neither has usable data, preserve the existing rotation skill.

    The selected difficulty is based on the skill's current Elo when
    available, with the route-provided difficulty as the fallback.
    """
    skill = fallback_skill
    source = "rotation"
    state = StudentSkillGraph(user_id or "").get_current_state() if user_id else {}
    allowed = _normalise_skill_set(session_skills)

    if user_id and target_role_id:
        try:
            from modules.gap_analysis import GapAnalyzer

            report = GapAnalyzer().compute_gap(user_id=user_id, role_id=str(target_role_id))
            for weak_area in report.ranked_weak_areas:
                skill = weak_area.skill
                source = "gap_analysis"
                break
        except Exception as exc:  # pragma: no cover - defensive, fallback by design
            LOGGER.info("Gap analysis unavailable for adaptive target: %s", exc)

    if source == "rotation" and user_id:
        candidates = []
        for name, node in state.items():
            if allowed and str(name).lower() not in allowed:
                continue
            attempts = int(getattr(node, "attempts", 0) or 0)
            score = float(getattr(node, "current_score", 0.0) or 0.0)
            candidates.append((attempts > 0, score, str(name)))
        if candidates:
            # Untested skills are treated as weakest first; then lowest score.
            _, _, skill = sorted(candidates, key=lambda item: (item[0], item[1], item[2]))[0]
            source = "skill_graph"

    elo = _skill_graph_elo(state, skill)
    if elo is None:
        elo = _candidate_elo(candidate_elo_by_skill, skill)
    difficulty = _difficulty_from_elo(elo, fallback_difficulty)
    target_concepts = pick_target_concepts(user_id or "", skill, concept_limit) if user_id else []

    return AdaptiveTarget(
        skill=skill,
        difficulty=difficulty,
        target_concepts=target_concepts,
        source=source,
        current_elo=elo,
        target_role_id=str(target_role_id) if target_role_id else None,
    )


def pick_target_concepts(
    user_id: str,
    skill: str,
    limit: int = DEFAULT_TARGET_CONCEPT_LIMIT,
) -> list[str]:
    """Return up to ``limit`` concepts the user hasn't demonstrated for
    ``skill``. Weak concepts come before Untested so practice rounds
    keep reinforcing observed gaps first.

    Returns ``[]`` when there is no concept-mastery data — the caller
    must treat that as "use the default selector."
    """
    if not user_id or not skill:
        return []
    try:
        mastery_details = ConceptMastery().get_mastery_details(user_id)
    except Exception as exc:  # pragma: no cover - defensive
        LOGGER.warning("ConceptMastery read failed: %s", exc)
        return []
    skill_map = mastery_details.get(skill, {})
    if not skill_map:
        return []

    weak: list[tuple[float, int, str]] = []
    untested: list[str] = []
    for concept, node in skill_map.items():
        level = node.get("mastery_level")
        attempts = int(node.get("attempts") or 0)
        demonstrated = int(node.get("demonstrated") or 0)
        rate = demonstrated / attempts if attempts else 0.0
        if level == MasteryLevel.WEAK:
            weak.append((rate, -attempts, concept))
        elif level == MasteryLevel.UNTESTED:
            untested.append(concept)
    targets = ([item[2] for item in sorted(weak)] + sorted(untested))[: max(0, int(limit))]
    return [_display_concept(c) for c in targets]


def build_targeted_prompt(
    skill: str,
    sub_domain: Optional[str],
    difficulty: str,
    asked: list[str],
    target_concepts: list[str],
    target_company_id: Optional[str] = None,
    target_role_id: Optional[str] = None,
    resume_skills: Optional[list[str]] = None,
    weak_skills: Optional[list[str]] = None,
) -> str:
    """Existing question_bank prompt + the spec-verbatim extension."""
    base_prompt = build_question_prompt(
        skill=skill,
        sub_domain=sub_domain,
        difficulty=difficulty,
        asked=asked,
        target_concepts=[],
        market_context=MarketQuestionContext(
            company_id=target_company_id,
            role_id=target_role_id,
            resume_skills=tuple(resume_skills or ()),
            weak_skills=tuple(weak_skills or target_concepts or ()),
        ),
    )
    if not target_concepts:
        return base_prompt
    concept_list = ", ".join(target_concepts)
    return base_prompt + SPEC_PROMPT_EXTENSION_TEMPLATE.format(concept_list=concept_list)


def _call_llm(prompt: str) -> Optional[str]:
    """POST the prompt to the configured LLM and return raw content.

    Tests override this at module level (``adaptive_question_selector._call_llm``)
    to assert prompt content + return canned JSON without hitting the
    network.
    """
    if _CURRENT_CACHE_CONTEXT is None:
        return None
    return call_llm_with_cache_retry(
        prompt,
        _CURRENT_CACHE_CONTEXT,
        asked=_CURRENT_ASKED,
    )


def _parse_llm_json(content: str) -> Optional[dict]:
    """The model returns a JSON blob like ``{"question": "...", ...}``."""
    return parse_llm_json(content)


def _generate_targeted_question(
    *,
    skill: str,
    sub_domain: Optional[str],
    difficulty: str,
    asked: list[str],
    target_concepts: list[str],
    target_company_id: Optional[str] = None,
    target_role_id: Optional[str] = None,
    resume_skills: Optional[list[str]] = None,
    weak_skills: Optional[list[str]] = None,
) -> Optional[dict]:
    global _CURRENT_CACHE_CONTEXT, _CURRENT_ASKED
    prompt = build_targeted_prompt(
        skill,
        sub_domain,
        difficulty,
        asked,
        target_concepts,
        target_company_id=target_company_id,
        target_role_id=target_role_id,
        resume_skills=resume_skills,
        weak_skills=weak_skills,
    )
    _CURRENT_CACHE_CONTEXT = QuestionCacheContext(
        skill=skill,
        sub_domain=sub_domain or "general",
        difficulty=difficulty,
        target_concepts=tuple(target_concepts or ()),
    )
    _CURRENT_ASKED = list(asked or [])
    try:
        raw = _call_llm(prompt)
        if not raw:
            return None
        payload = _parse_llm_json(raw)
        if not payload or "question" not in payload:
            return None
        payload["skill"] = skill
        payload["sub_domain"] = sub_domain or "general"
        payload["difficulty"] = difficulty
        payload["source"] = "llm-adaptive"
        return payload
    finally:
        _CURRENT_CACHE_CONTEXT = None
        _CURRENT_ASKED = []


def select_next_question(
    *,
    user_id: Optional[str],
    skill: str,
    sub_domain: Optional[str],
    difficulty: str,
    asked: list[str],
    target_role_id: Optional[str] = None,
    target_company_id: Optional[str] = None,
    target_concepts: Optional[list[str]] = None,
    resume_skills: Optional[list[str]] = None,
    weak_skills: Optional[list[str]] = None,
    concept_limit: int = DEFAULT_TARGET_CONCEPT_LIMIT,
) -> dict:
    """Adaptive question selector entry point.

    Computes ``target_concepts`` from the user's concept mastery for
    ``skill`` when not explicitly provided. When at least one target
    concept is available, generates a question via the LLM with the
    spec-7b prompt extension. On failure or empty targets, delegates
    to ``question_bank.get_next_question(...)``.

    The returned dict always includes the additional metadata
    ``target_concepts`` (list of strings, may be empty) and
    ``adaptive_selected`` (bool) so callers and downstream tests can
    observe whether adaptive targeting was applied.
    """
    if target_concepts is None and user_id:
        target_concepts = pick_target_concepts(user_id, skill, concept_limit)
    target_concepts = list(target_concepts or [])

    if target_concepts:
        targeted = _generate_targeted_question(
            skill=skill,
            sub_domain=sub_domain,
            difficulty=difficulty,
            asked=asked,
            target_concepts=target_concepts,
            target_company_id=target_company_id,
            target_role_id=target_role_id,
            resume_skills=resume_skills,
            weak_skills=weak_skills,
        )
        if targeted is not None:
            targeted["target_concepts"] = target_concepts
            targeted["adaptive_selected"] = True
            return targeted

    payload = generate_question(
        skill,
        sub_domain,
        difficulty,
        asked,
        target_concepts=target_concepts,
        market_context=MarketQuestionContext(
            company_id=target_company_id,
            role_id=target_role_id,
            resume_skills=tuple(resume_skills or ()),
            weak_skills=tuple(weak_skills or target_concepts or ()),
        ),
    )
    if isinstance(payload, dict):
        payload.setdefault("target_concepts", target_concepts)
        payload.setdefault("adaptive_selected", False)
    return payload


__all__ = [
    "AdaptiveTarget",
    "DEFAULT_TARGET_CONCEPT_LIMIT",
    "SPEC_PROMPT_EXTENSION_TEMPLATE",
    "build_targeted_prompt",
    "choose_adaptive_target",
    "pick_target_concepts",
    "select_next_question",
]
