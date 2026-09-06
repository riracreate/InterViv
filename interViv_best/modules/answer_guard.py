"""
answer_guard.py — Anti-gaming quality gate for interViv.

Runs BEFORE the NLP scorer. Returns a cap instruction that pipeline.py
applies to final_score after scoring. Detections are evaluated in order
and the first match wins.

Two entry points:
  • check_answer_quality(answer, ideal_keywords)             — original v1
  • check_answer_quality_v2(answer, question_text=,          — extended:
        ideal_keywords=, ideal_answer=)                        adds parroting,
                                                               low-density
                                                               (fluff) and
                                                               off-topic.
"""

from __future__ import annotations

import logging
import re
from collections import Counter

_logger = logging.getLogger(__name__)

_GIBBERISH_PATTERNS = re.compile(
    r"(asdf|qwer|qwerty|jkl|zxcv|hjkl|bnm|dfgh|sdfg|wert|xcvb|uiop)"
)

_VOWELS = frozenset("aeiouAEIOU")
_GUARD_MESSAGE = "Your answer looks incomplete or gibberish. Please write a meaningful explanation."

# Stopwords used for parroting / density analysis. Deliberately small;
# the guard isn't meant to do deep linguistic analysis, just spot gaming.
_STOPWORDS = frozenset({
    "the", "is", "a", "an", "of", "to", "and", "or", "in", "on", "at",
    "what", "why", "how", "when", "where", "which", "who",
    "explain", "describe", "define", "discuss", "elaborate",
    "with", "that", "this", "it", "are", "was", "were", "be",
    "can", "could", "do", "does", "would", "should", "for",
    "by", "as", "you", "your", "user", "users",
})

# Generic-fluff vocabulary. Tokens that contribute almost no information.
_FLUFF_VOCAB = frozenset({
    "important", "interesting", "useful", "great", "good", "nice",
    "basically", "essentially", "really", "very", "simply", "actually",
    "quite", "helpful", "valuable", "beneficial", "complex", "simple",
    "popular", "common", "modern", "advanced", "powerful", "robust",
    "comprehensive", "holistic",
})

_TECHNICAL_OR_MEANINGFUL = frozenset({
    # general explanation verbs/nouns
    "answer", "approach", "because", "compare", "concept", "decides",
    "divides", "example", "explain", "found", "improves", "meaningful",
    "performance", "reducing", "target", "until", "works",
    # DSA / programming
    "algorithm", "array", "arrays", "binary", "complexity", "data",
    "divide", "halves", "hash", "index", "middle", "queue", "range",
    "recursion", "search", "sorted", "stack", "structure", "table",
    "target", "tree",
    # databases / systems
    "cpu", "database", "indexing", "process", "query", "scheduling",
    "scans", "system", "time",
    # common interview/product terms
    "api", "cache", "design", "docker", "http", "java", "javascript",
    "node", "python", "react", "redis", "rest", "sql",
})

_COMMON_BIGRAMS = frozenset({
    "al", "an", "ar", "at", "ay", "be", "bi", "by", "ce", "ch", "ck",
    "co", "da", "de", "di", "du", "ea", "ed", "em", "en", "er", "es",
    "et", "fo", "gh", "ha", "he", "hi", "ic", "id", "ig", "il", "in",
    "io", "is", "it", "iv", "le", "li", "me", "mi", "mp", "na", "nd",
    "ne", "ng", "ni", "no", "nt", "on", "oo", "or", "ou", "pe", "pr",
    "qu", "ra", "rc", "re", "ri", "ro", "ry", "sc", "se", "ss", "st",
    "ta", "te", "th", "ti", "to", "uc", "ul", "ur", "ve", "vi", "wo",
})

# Function words that signal a cut-off mid-clause when they end the answer.
_DANGLING_ENDINGS = frozenset({
    "a", "an", "the", "to", "of", "and", "or", "but", "with", "for",
    "from", "by", "as", "that", "which", "who", "whom", "whose",
    "into", "onto", "upon", "over", "under", "about", "like", "than",
    "then", "when", "while", "where", "because", "if", "whether",
})


def _cap(reason: str, score_cap: int) -> dict:
    return {
        "cap_required": True,
        "score_cap": score_cap,
        "reason": reason,
        "message": _GUARD_MESSAGE,
        "guards_fired": [{"reason": reason, "score_cap": score_cap}],
    }


def _vowel_ratio(text: str) -> float:
    letters = [c for c in text if c.isalpha()]
    if not letters:
        return 0.0
    return sum(1 for c in letters if c in _VOWELS) / len(letters)


def _word_tokens(text: str) -> list[str]:
    return re.findall(r"[a-zA-Z0-9]+", text.lower())


def _alpha_tokens(text: str) -> list[str]:
    return re.findall(r"[a-zA-Z]+", text.lower())


def _content_tokens(text: str) -> set[str]:
    """Content words from text: alphabetic, len > 2, not a stopword."""
    toks = re.findall(r"[a-zA-Z]+", text.lower())
    return {t for t in toks if t not in _STOPWORDS and len(t) > 2}


def _keyword_token_set(ideal_keywords: str) -> set[str]:
    if not ideal_keywords or not ideal_keywords.strip():
        return set()
    out: set[str] = set()
    for kw in ideal_keywords.split(","):
        out.update(_word_tokens(kw))
    return out


def _max_char_run(token: str) -> int:
    longest = 0
    current = 0
    last = ""
    for char in token:
        if char == last:
            current += 1
        else:
            last = char
            current = 1
        longest = max(longest, current)
    return longest


def _max_consonant_run(token: str) -> int:
    longest = 0
    current = 0
    for char in token:
        if char.isalpha() and char not in _VOWELS:
            current += 1
        else:
            current = 0
        longest = max(longest, current)
    return longest


def _common_bigram_ratio(token: str) -> float:
    token = re.sub(r"[^a-z]", "", token.lower())
    if len(token) < 2:
        return 1.0
    bigrams = [token[i : i + 2] for i in range(len(token) - 1)]
    return sum(1 for pair in bigrams if pair in _COMMON_BIGRAMS) / len(bigrams)


def _repeated_pattern(token: str) -> bool:
    token = token.lower()
    if len(token) < 6:
        return False
    for size in (1, 2, 3):
        if len(token) % size == 0 and token[:size] * (len(token) // size) == token:
            return True
    return False


def _is_meaningful_token(token: str) -> bool:
    token = token.lower()
    if token in _TECHNICAL_OR_MEANINGFUL:
        return True
    if len(token) <= 2 or token in _STOPWORDS or token in _FLUFF_VOCAB:
        return False
    if _looks_like_nonsense_token(token):
        return False
    return True


def _looks_like_nonsense_token(token: str) -> bool:
    token = re.sub(r"[^a-z]", "", token.lower())
    if not token:
        return False
    if _GIBBERISH_PATTERNS.search(token):
        return True
    if _repeated_pattern(token):
        return True
    if _max_char_run(token) >= 4:
        return True
    if len(token) >= 8 and _max_consonant_run(token) >= 4:
        return True
    if len(token) >= 6:
        vowel_ratio = _vowel_ratio(token)
        if vowel_ratio < 0.24 or vowel_ratio > 0.82:
            return True
        if token not in _TECHNICAL_OR_MEANINGFUL and _common_bigram_ratio(token) < 0.45:
            return True
    return False


def _nonsense_token_ratio(tokens: list[str]) -> float:
    alpha = [token for token in tokens if token.isalpha()]
    if not alpha:
        return 0.0
    return sum(1 for token in alpha if _looks_like_nonsense_token(token)) / len(alpha)


# ── Shared rule helpers ──────────────────────────────────────────────────────

def _check_basic_rules(
    answer_text: str,
    ideal_keywords: str,
    question_text: str = "",
    ideal_answer: str = "",
) -> dict | None:
    """Run the v1 rules 1–5 (+ parroting / truncated); return cap dict or None."""
    text = (answer_text or "").strip()

    if len(text) == 0:
        return _cap("empty", 5)

    tokens = _word_tokens(text)
    alpha_tokens = _alpha_tokens(text)

    if len(text) < 5:
        return _cap("too_short", 20)

    if not tokens:
        return _cap("empty", 5)

    repeated_char_tokens = [
        token for token in alpha_tokens
        if len(token) >= 4 and (_max_char_run(token) >= 4 or _repeated_pattern(token))
    ]
    if len(tokens) >= 2 and repeated_char_tokens and len(repeated_char_tokens) / len(alpha_tokens or tokens) >= 0.60:
        return _cap("repetition", 15)

    if (
        _vowel_ratio(text) < 0.24
        or _GIBBERISH_PATTERNS.search(text.lower())
        or _nonsense_token_ratio(alpha_tokens) >= 0.50
    ):
        return _cap("gibberish", 10)

    if len(tokens) >= 2:
        counts = Counter(tokens)
        most_common_count = counts.most_common(1)[0][1]
        if most_common_count / len(tokens) > 0.40:
            return _cap("repetition", 15)

    # Rule 3.5 — Question parroting. Sits before keyword_stuffing because a
    # parroted question often passes the keyword-stuffing test (low kw ratio).
    if question_text:
        ans_content = _content_tokens(text)
        q_content = _content_tokens(question_text)
        if q_content and ans_content:
            extra = ans_content - q_content
            jaccard = len(ans_content & q_content) / len(ans_content | q_content)
            if jaccard > 0.55 and len(extra) < 8:
                return _cap("question_parroting", 25)

    # Truncated on-topic fragment before stuffing — incomplete sentences often
    # look like keyword lists to the stuffing ratio check.
    truncated = _check_truncated_fragment(
        text,
        ideal_keywords=ideal_keywords,
        ideal_answer=ideal_answer,
    )
    if truncated is not None:
        return truncated

    # Keyword stuffing intentionally before too-short so short keyword spam
    # ("stateless caching URI HTTP JSON") gets the harder gaming cap.
    if ideal_keywords and ideal_keywords.strip() and tokens:
        kw_tokens = _keyword_token_set(ideal_keywords)
        if kw_tokens:
            stuffed = sum(1 for t in tokens if t in kw_tokens)
            kw_ratio = stuffed / len(tokens)
            non_kw_tokens = [t for t in tokens if t not in kw_tokens]
            if kw_ratio > 0.45 and len(non_kw_tokens) < 8:
                return _cap("keyword_stuffing", 35)

    meaningful_tokens = [token for token in alpha_tokens if _is_meaningful_token(token)]
    if len(tokens) < 4:
        return _cap("too_short", 20)
    if len(tokens) < 8 and len(meaningful_tokens) < 4:
        return _cap("too_short", 20)
    if len(tokens) >= 8 and len(meaningful_tokens) < 3:
        return _cap("gibberish", 10)

    return None


def check_answer_quality(
    answer_text: str,
    ideal_keywords: str = "",
    question_text: str = "",
) -> dict:
    """
    Original v1 entry point. Evaluate answer for anti-gaming signals.

    Parameters
    ----------
    answer_text : str
    ideal_keywords : str
        Comma-separated string. Optional.
    question_text : str
        Question that elicited the answer. Optional. When supplied, enables
        the question-parroting rule. Kept positional-friendly so existing
        callers that pass only (answer, ideal_keywords) still work.

    Returns
    -------
    dict with keys:
        cap_required  bool
        score_cap     int
        reason        str
        guards_fired  list
    """
    cap = _check_basic_rules(answer_text, ideal_keywords, question_text)
    if cap is not None:
        return cap
    return {"cap_required": False, "score_cap": 100, "reason": "", "message": "", "guards_fired": []}


# ── v2: fluff, off-topic ────────────────────────────────────────────────────
# (Question parroting now lives in _check_basic_rules so v1 catches it too.)


def _ends_as_truncated_fragment(text: str) -> bool:
    """True when the answer appears cut off mid-thought (dangling close)."""
    t = (text or "").strip()
    if not t:
        return False
    if t[-1] in ",;:—":
        return True
    body = t.rstrip(".!?…")
    words = _word_tokens(body)
    if not words:
        return False
    if words[-1] in _DANGLING_ENDINGS:
        return True
    # Short cutoffs like "… from common." / "… for machine."
    if 2 <= len(words) <= 12 and words[-2] in _DANGLING_ENDINGS:
        return True
    return False


def _is_on_topic_fragment(
    answer_text: str,
    ideal_keywords: str,
    ideal_answer: str,
) -> bool:
    """Require topical overlap so off-topic short text is not called truncated."""
    ans = _content_tokens(answer_text)
    if not ans:
        return False
    kw = _keyword_token_set(ideal_keywords)
    if kw and (ans & kw):
        return True
    ideal = _content_tokens(ideal_answer)
    if not ideal:
        return False
    overlap = len(ans & ideal)
    if overlap >= 2:
        return True
    return overlap / len(ans | ideal) >= 0.15


def _check_truncated_fragment(
    answer_text: str,
    ideal_keywords: str = "",
    ideal_answer: str = "",
) -> dict | None:
    """
    Truncated on-topic fragment: topical start, cut off mid-clause.

    Fires only when basic length rules did not already cap the answer.
    Cap only — does not replace scoring.
    """
    text = (answer_text or "").strip()
    if not _ends_as_truncated_fragment(text):
        return None
    if not _is_on_topic_fragment(text, ideal_keywords, ideal_answer):
        return None
    return _cap("truncated_fragment", 25)


def _check_low_density(answer_tokens: list[str]) -> dict | None:
    if not answer_tokens:
        return None
    total = len(answer_tokens)
    fluff = sum(1 for t in answer_tokens if t in _FLUFF_VOCAB)
    if fluff / total <= 0.25:
        return None
    content = sum(
        1 for t in answer_tokens
        if t not in _STOPWORDS and t not in _FLUFF_VOCAB
    )
    if content / total < 0.40:
        return _cap("low_density", 30)
    return None


def _check_off_topic(
    answer_text: str,
    answer_tokens: list[str],
    ideal_answer: str,
    ideal_keywords: str,
) -> dict | None:
    if not ideal_answer or len(ideal_answer.strip()) <= 20:
        return None

    # Lazy import to avoid pulling sentence-transformers when v2 isn't used.
    try:
        from modules.semantic_scorer import SemanticScorer
    except ImportError:
        try:
            from semantic_scorer import SemanticScorer  # fallback for direct sys.path
        except Exception:
            return None
    except Exception:
        return None

    try:
        sem_score = SemanticScorer().score(answer_text, ideal_answer)
    except Exception as exc:
        _logger.debug("off_topic semantic check skipped: %s", exc)
        return None

    if sem_score is None:
        return None

    kw_set = _keyword_token_set(ideal_keywords)
    overlap = sum(1 for t in answer_tokens if t in kw_set)

    if sem_score < 0.20 and overlap == 0:
        return _cap("off_topic", 30)
    return None


def check_answer_quality_v2(
    answer_text: str,
    question_text: str = "",
    ideal_keywords: str = "",
    ideal_answer: str = "",
) -> dict:
    """
    Extended guard. Order:
      1 empty, 2 gibberish, 3 repetition, 3.5 question_parroting,
      4 truncated_fragment, 5 keyword_stuffing, 6 too_short,
      7 low_density, 8 off_topic
    First match wins.
    """
    cap = _check_basic_rules(
        answer_text,
        ideal_keywords,
        question_text,
        ideal_answer=ideal_answer,
    )
    if cap is not None:
        return cap

    answer_tokens = _word_tokens(answer_text or "")

    fluff = _check_low_density(answer_tokens)
    if fluff is not None:
        return fluff

    off = _check_off_topic(answer_text or "", answer_tokens, ideal_answer, ideal_keywords)
    if off is not None:
        return off

    return {"cap_required": False, "score_cap": 100, "reason": "", "message": "", "guards_fired": []}
