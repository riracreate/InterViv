"""Answer guard v4 (scorer v4 only; v3 keeps modules/answer_guard.py frozen).

Fixes over v3, each tied to a measured Mohler false positive:
- No penultimate-word truncated rule (v3 words[-2] fired on complete
  noun-phrase answers).
- Repetition requires at least 4 tokens and a repeated word.
- Vowel-ratio gibberish check counts letters only, needs >= 8 letters,
  and exempts code/maths-looking answers.
- Parroting is not flagged when the words the candidate added beyond the
  question overlap the reference answer.
- too_short / truncated_fragment use reference-length gating: short
  answers are capped only when they are also short relative to the
  reference (absolute floor: < 3 tokens or < 5 chars always caps).
"""

from __future__ import annotations

import re
from collections import Counter
from typing import Any

from modules import answer_guard as _v3

_GUARD_MESSAGE = _v3._GUARD_MESSAGE
_CODE_HINT_RE = re.compile(r"[{}();=<>]|->|=>|::|\b\d+(?:\.\d+)?\s*[-+*/=<>]|\$\$|\\[a-zA-Z]+")


def _cap(reason: str, score_cap: int) -> dict:
    return {
        "cap_required": True,
        "score_cap": score_cap,
        "reason": reason,
        "message": _GUARD_MESSAGE,
        "guards_fired": [{"reason": reason, "score_cap": score_cap}],
    }


def _looks_like_code_or_math(text: str) -> bool:
    if _CODE_HINT_RE.search(text or ""):
        return True
    letters = sum(1 for c in text if c.isalpha())
    if letters == 0:
        return False
    non_space = [c for c in text if not c.isspace()]
    symbols = sum(1 for c in non_space if not c.isalnum())
    return bool(non_space) and symbols / len(non_space) > 0.18


def _ends_as_truncated_fragment_v4(text: str) -> bool:
    t = (text or "").strip()
    if not t:
        return False
    if t[-1] in ",;:—":
        return True
    words = _v3._word_tokens(t.rstrip(".!?…"))
    if not words:
        return False
    return words[-1] in _v3._DANGLING_ENDINGS


def _check_basic_rules_v4(
    answer_text: str,
    ideal_keywords: str,
    question_text: str = "",
    ideal_answer: str = "",
) -> dict | None:
    text = (answer_text or "").strip()
    if len(text) == 0:
        return _cap("empty", 5)

    tokens = _v3._word_tokens(text)
    alpha_tokens = _v3._alpha_tokens(text)
    known = _v3._reference_vocabulary(question_text, ideal_keywords, ideal_answer)

    if len(text) < 5 or len(tokens) < 3:
        return _cap("too_short", 20)
    if not tokens:
        return _cap("empty", 5)

    # Repetition: at least 4 tokens and an actually repeated word.
    if len(tokens) >= 4:
        repeated_char_tokens = [
            token for token in alpha_tokens
            if len(token) >= 4 and (_v3._max_char_run(token) >= 4 or _v3._repeated_pattern(token))
        ]
        if repeated_char_tokens and len(repeated_char_tokens) / len(alpha_tokens or tokens) >= 0.60:
            return _cap("repetition", 15)
        counts = Counter(tokens)
        word, freq = counts.most_common(1)[0]
        if freq >= 2 and freq / len(tokens) > 0.40:
            return _cap("repetition", 15)

    # Gibberish: letters-only vowel ratio with a minimum letter count.
    letters = [c for c in text if c.isalpha()]
    vowel_bad = (
        len(letters) >= 8
        and not _looks_like_code_or_math(text)
        and _v3._vowel_ratio(text) < 0.24
    )
    if (
        vowel_bad
        or _v3._GIBBERISH_PATTERNS.search(text.lower())
        or _v3._nonsense_token_ratio(alpha_tokens, known) >= 0.50
    ):
        return _cap("gibberish", 10)

    # Parroting: exempt when added words overlap the reference answer.
    if question_text:
        ans_content = _v3._content_tokens(text)
        q_content = _v3._content_tokens(question_text)
        if q_content and ans_content:
            extra = ans_content - q_content
            jaccard = len(ans_content & q_content) / len(ans_content | q_content)
            ref_content = _v3._content_tokens(ideal_answer)
            extra_in_ref = len(extra & ref_content) / len(extra) if extra else 0.0
            if jaccard > 0.55 and len(extra) < 8 and extra_in_ref < 0.50:
                return _cap("question_parroting", 25)

    # Reference-length gating for short / truncated answers.
    ref_tokens = _v3._word_tokens(ideal_answer) if ideal_answer else []
    short_vs_ref = bool(ref_tokens) and len(tokens) < 0.5 * len(ref_tokens)

    if _ends_as_truncated_fragment_v4(text) and (
        not ref_tokens or short_vs_ref or len(tokens) < 8
    ):
        if _v3._is_on_topic_fragment(text, ideal_keywords, ideal_answer):
            return _cap("truncated_fragment", 25)

    if ideal_keywords and ideal_keywords.strip() and tokens:
        kw_tokens = _v3._keyword_token_set(ideal_keywords)
        if kw_tokens:
            stuffed = sum(1 for t in tokens if t in kw_tokens)
            kw_ratio = stuffed / len(tokens)
            non_kw_tokens = [t for t in tokens if t not in kw_tokens]
            if kw_ratio > 0.45 and len(non_kw_tokens) < 8:
                return _cap("keyword_stuffing", 35)

    meaningful_tokens = [t for t in alpha_tokens if _v3._is_meaningful_token(t, known)]
    # A short answer that still covers most reference content is complete,
    # not too short (Mohler short full-marks answers; v4 fixture case).
    ref_content = _v3._content_tokens(ideal_answer)
    ans_content = _v3._content_tokens(text)
    content_recall = len(ans_content & ref_content) / len(ref_content) if ref_content else 0.0
    if len(tokens) < 8 and short_vs_ref and content_recall < 0.50:
        return _cap("too_short", 20)
    if len(tokens) < 8 and len(meaningful_tokens) < 3 and not ref_tokens:
        return _cap("too_short", 20)
    if len(tokens) >= 8 and len(meaningful_tokens) < 3:
        return _cap("gibberish", 10)
    return None


def check_answer_quality_v4(
    answer_text: str,
    question_text: str = "",
    ideal_keywords: str = "",
    ideal_answer: str = "",
) -> dict[str, Any]:
    """v4 guard. Same return shape as the v3 guard."""
    cap = _check_basic_rules_v4(
        answer_text, ideal_keywords, question_text, ideal_answer=ideal_answer
    )
    if cap is not None:
        return cap

    swap = _v3._check_entity_swap(answer_text or "", question_text or "", ideal_answer or "")
    if swap is not None:
        return swap

    answer_tokens = _v3._word_tokens(answer_text or "")
    fluff = _v3._check_low_density(answer_tokens)
    if fluff is not None:
        return fluff

    off = _v3._check_off_topic(answer_text or "", answer_tokens, ideal_answer, ideal_keywords)
    if off is not None:
        return off

    return {"cap_required": False, "score_cap": 100, "reason": "", "message": "", "guards_fired": []}
