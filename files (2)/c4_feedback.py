"""
c4_feedback.py — C4 Rule-Based Feedback Generator
Zero hallucination. Pure if/else logic.

C4 rules:
  - Answer < 60 words            → too short
  - Filler words > 3             → reduce fillers
  - Keyword match rate < 40%     → lists missing concepts
"""
from __future__ import annotations

import re

_FILLER_PATTERN = re.compile(
    r"\b(um+|uh+|like|you know|basically|literally|sort of|kind of|actually|right|so|well)\b",
    re.IGNORECASE,
)


def _count_filler_words(text: str) -> int:
    return len(_FILLER_PATTERN.findall(text))


def generate_feedback(
    answer: str | None = None,
    answer_text: str | None = None,
    question: str | None = None,
    ideal_answer: str | None = None,
    skill: str | None = None,
    sub_domain: str | None = None,
    nlp_score: float | None = None,
    svm_label: str | None = None,
    kg_score: float | None = None,
    final_score: float | None = None,
    ner_entities: list | None = None,
    word_count: int | None = None,
    filler_count: int | None = None,
    keyword_match_rate: float | None = None,
    missing_keywords: list | None = None,
    ideal_keywords: str | None = None,
) -> dict:
    text = answer_text or answer or ""
    wc = word_count if word_count is not None else len(text.split())
    fc = filler_count if filler_count is not None else _count_filler_words(text)

    content: list[str] = []
    strengths: list[str] = []
    next_step = ""

    # ── C4 Rule 1: Answer length ───────────────────────────────
    if wc < 60:
        content.append(
            f"Your answer is too short ({wc} words). Technical answers require "
            "at least 60 words to demonstrate adequate depth."
        )
        next_step = "Expand your answer — explain the 'why' and 'how' in detail."
    elif wc > 150:
        content.append("You provided a highly detailed explanation.")
        strengths.append("Comprehensive")
        if not next_step:
            next_step = "Ensure you don't lose the main point in the details. Keep it concise."
    else:
        content.append("Good length and pacing.")
        strengths.append("Concise")

    # ── C4 Rule 2: Filler words ────────────────────────────────
    if fc > 3:
        content.append(
            f"You used {fc} filler word(s) (e.g., 'um', 'uh', 'like', 'basically'). "
            "Reducing filler words will improve your communication clarity."
        )
        if not next_step:
            next_step = "Practise pausing instead of using filler words."

    # ── C4 Rule 3: Keyword match ───────────────────────────────
    _kw_rate = keyword_match_rate if keyword_match_rate is not None else None
    if _kw_rate is not None and _kw_rate < 0.40:
        _missing = missing_keywords or []
        if _missing:
            listed = ", ".join(_missing[:5])
            content.append(
                f"Your answer covers only {_kw_rate * 100:.0f}% of the expected keywords. "
                f"Missing key concepts: {listed}."
            )
        else:
            content.append(
                f"Keyword coverage is low ({_kw_rate * 100:.0f}%). "
                "Review the ideal answer for the key technical terms."
            )
        if not next_step:
            next_step = "Study and incorporate the missing concepts listed above."

    # ── Rule 4: Technical keyword density (NER) ────────────────
    if ner_entities and len(ner_entities) > 2:
        content.append(
            f"You successfully included key technical entities like: "
            f"{', '.join(str(e) for e in ner_entities[:3])}."
        )
        strengths.append("Technical Vocabulary")
    elif ner_entities:
        content.append(
            "You mentioned some core concepts, but there is room for deeper technical vocabulary."
        )
    else:
        content.append("Your answer lacked specific technical keywords associated with this topic.")
        if not next_step:
            next_step = "Try incorporating precise industry terminology."

    # ── Rule 5: ML label / NLP score ──────────────────────────
    if svm_label == "Good":
        strengths.append("High Relevance")
        if not next_step:
            next_step = "Maintain this level of detail for future questions."
    elif svm_label == "Poor":
        if not next_step:
            next_step = "Review the core concepts for this topic before the real interview."

    if not next_step:
        next_step = "Continue to the next round."

    return {
        "content": content,
        "strengths": strengths,
        "next_step": next_step,
    }

