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


# ── Entity-swap detection ─────────────────────────────────────────────────────
# Comparison questions ("difference between TCP and UDP") are where embedding
# similarity and keyword coverage are blind: an answer that gives TCP's
# properties to UDP and vice versa scores like a correct one. This check reads
# the reference answer to learn which properties belong to which side, then
# counts how often the candidate attaches them to the other side.
#
# Deliberately conservative: it is a no-op unless the question names a clear
# A/B pair and the reference gives each side at least one distinctive property.
# Clauses that mention both sides or contain a negation are not counted.

ENTITY_SWAP_CAP = 35
ENTITY_SWAP_MIN_CROSSED = 2
ENTITY_SWAP_RATIO = 2.0

_CONTRAST_PATTERNS = (
    re.compile(r"\bdifferences?\s+between\s+(?P<a>.+?)\s+and\s+(?P<b>.+?)(?=[?.,:;(]|\s+(?:in|when|with|for|and\s+when|and\s+how|and\s+why)\b|$)", re.I),
    re.compile(r"\bdistinguish\s+between\s+(?P<a>.+?)\s+and\s+(?P<b>.+?)(?=[?.,:;(]|\s+(?:in|when|with|for)\b|$)", re.I),
    re.compile(r"\bcompare\s+(?:and\s+contrast\s+)?(?P<a>.+?)\s+(?:and|with|to|vs\.?|versus)\s+(?P<b>.+?)(?=[?.,:;(]|\s+(?:in|when|for)\b|$)", re.I),
    re.compile(r"\bhow\s+(?:does|do|is|are)\s+(?P<a>.+?)\s+differ(?:ent)?\s+from\s+(?P<b>.+?)(?=[?.,:;(]|\s+(?:in|when|for)\b|$)", re.I),
    re.compile(r"(?P<a>[\w+#\-/ ]+?)\s+(?:vs\.?|versus)\s+(?P<b>[\w+#\-/ ]+?)(?=[?.,:;(]|$)", re.I),
)

# Leading words a question wraps around the entity phrase.
_PHRASE_FILLER = frozenset({
    "the", "a", "an", "between", "of", "what", "is", "are", "explain",
    "describe", "difference", "differences", "key", "main", "major",
})

# Parentheses are not split points: a parenthetical elaborates its own clause
# ("use copy.deepcopy() for deep copies").
_CLAUSE_SPLIT = re.compile(
    r"[;\n]+|[.!?]+(?=\s|$)|,|\b(?:whereas|while|but|however|unlike|in\s+contrast|on\s+the\s+other\s+hand|compared\s+(?:to|with)|as\s+opposed\s+to)\b",
    re.I,
)

# A clause that opens with one of these refers back to the previous subject,
# even if it later uses a side's name as an ordinary noun ("It guarantees
# ordered pod deployment" is still about the StatefulSet).
_PRONOUN_OPENERS = frozenset({"it", "its", "they", "their", "this", "these", "such"})

_SWAP_NEGATION = re.compile(
    r"\b(?:not|no|never|isn't|isnt|aren't|arent|doesn't|doesnt|don't|dont|without|cannot|can't|cant|neither|nor|lacks?)\b",
    re.I,
)

# Words that carry no side-specific property. Comparative words are excluded
# because "more"/"less" flip meaning depending on which side is the subject.
_SWAP_STOPWORDS = _STOPWORDS | frozenset({
    "has", "have", "had", "its", "their", "they", "them", "there", "these",
    "those", "than", "more", "less", "both", "also", "only", "each", "other",
    "same", "such", "used", "use", "uses", "using", "like", "into", "from",
    "between", "difference", "differences", "whereas", "while", "however",
    "unlike", "because", "since", "then", "than", "one", "two", "very",
    "much", "many", "most", "some", "any", "all", "will", "may", "might",
    "must", "not", "never", "without", "which", "where", "while", "example",
    "examples", "case", "cases", "typically", "usually", "generally", "often",
    "way", "ways", "thing", "things", "type", "types", "called",
    "new", "make", "makes", "made", "create", "creates", "created",
    "good", "better", "work", "works", "based", "need", "needs",
    "provide", "provides", "allow", "allows", "support", "supports",
    "handle", "handles", "completely", "fully", "just", "still",
})


def _swap_stem(token: str) -> str:
    if len(token) > 4 and token.endswith("ies"):
        return token[:-3] + "y"
    if token.endswith("sses"):
        return token[:-2]
    if len(token) > 4 and token.endswith(("ches", "shes", "xes", "zes")):
        return token[:-2]
    if len(token) > 3 and token.endswith("s") and not token.endswith(("ss", "us", "is")):
        return token[:-1]
    return token


def _swap_tokens(text: str) -> list[str]:
    return [_swap_stem(t) for t in re.findall(r"[a-z0-9+#]+", text.lower())]


def _clean_entity_phrase(phrase: str) -> list[str]:
    tokens = _swap_tokens(phrase)
    while tokens and tokens[0] in _PHRASE_FILLER:
        tokens.pop(0)
    return tokens


def _contrast_pair(question_text: str) -> tuple[set[str], set[str], set[str]] | None:
    """Return (side A tokens, side B tokens, shared tokens) for a comparison question.

    "shallow copy and deep copy" -> ({"shallow"}, {"deep"}, {"copy"}); the
    shared head noun identifies neither side. "supervised and unsupervised
    learning" is read as "supervised learning" vs "unsupervised learning".
    """
    if not question_text:
        return None
    for pattern in _CONTRAST_PATTERNS:
        match = pattern.search(question_text)
        if not match:
            continue
        a = _clean_entity_phrase(match.group("a"))
        b = _clean_entity_phrase(match.group("b"))
        if not a or not b or len(a) > 4 or len(b) > 4:
            return None
        # Elided shared head: "supervised and unsupervised learning".
        if len(a) == 1 and len(b) > 1:
            a = a + b[1:]
        elif len(b) == 1 and len(a) > 1:
            b = b + a[1:]
        shared = set(a) & set(b)
        ident_a = {t for t in a if t not in shared and t not in _SWAP_STOPWORDS and len(t) > 1}
        ident_b = {t for t in b if t not in shared and t not in _SWAP_STOPWORDS and len(t) > 1}
        if not ident_a or not ident_b or ident_a & ident_b:
            return None
        return ident_a, ident_b, shared
    return None


def _side_clauses(
    text: str, ident_a: set[str], ident_b: set[str], shared: set[str]
) -> list[tuple[str, set[str], bool]]:
    """Split text into clauses and assign each one to side "a" or "b".

    A clause that names one side belongs to it. A clause that names neither,
    or that opens with a pronoun, inherits the previous clause's side. A clause
    that names both is ambiguous and resets the inherited side.
    Returns (side, content_tokens, negated) for every assigned clause.
    """
    out: list[tuple[str, set[str], bool]] = []
    current: str | None = None
    for raw in _CLAUSE_SPLIT.split(text or ""):
        if not raw or not raw.strip():
            continue
        tokens = _swap_tokens(raw)
        if not tokens:
            continue
        has_a = any(t in ident_a for t in tokens)
        has_b = any(t in ident_b for t in tokens)
        if tokens[0] in _PRONOUN_OPENERS and current is not None:
            pass
        elif has_a and has_b:
            current = None
            continue
        elif has_a:
            current = "a"
        elif has_b:
            current = "b"
        if current is None:
            continue
        content = {
            t for t in tokens
            if len(t) > 2
            and not t.isdigit()
            and t not in _SWAP_STOPWORDS
            and t not in ident_a
            and t not in ident_b
            and t not in shared
        }
        out.append((current, content, bool(_SWAP_NEGATION.search(raw))))
    return out


def entity_swap_evidence(
    answer_text: str, question_text: str, ideal_answer: str
) -> dict | None:
    """Count side-consistent vs side-crossed property mentions.

    Returns None when the check does not apply (no A/B pair in the question, or
    the reference answer gives no distinctive property for one side).
    """
    pair = _contrast_pair(question_text)
    if pair is None or not ideal_answer:
        return None
    ident_a, ident_b, shared = pair

    profile: dict[str, set[str]] = {"a": set(), "b": set()}
    for side, content, negated in _side_clauses(ideal_answer, ident_a, ident_b, shared):
        if not negated:
            profile[side] |= content
    attrs_a = profile["a"] - profile["b"]
    attrs_b = profile["b"] - profile["a"]
    if not attrs_a or not attrs_b:
        return None

    consistent: set[tuple[str, str]] = set()
    crossed: set[tuple[str, str]] = set()
    for side, content, negated in _side_clauses(answer_text, ident_a, ident_b, shared):
        if negated:
            continue
        own, other = (attrs_a, attrs_b) if side == "a" else (attrs_b, attrs_a)
        for token in content:
            if token in own:
                consistent.add((side, token))
            elif token in other:
                crossed.add((side, token))
    return {
        "consistent": len(consistent),
        "crossed": len(crossed),
        "crossed_sides": len({side for side, _ in crossed}),
        "crossed_terms": sorted(t for _, t in crossed),
    }


def entity_swap_fires(
    evidence: dict | None,
    min_crossed: int = ENTITY_SWAP_MIN_CROSSED,
    ratio: float = ENTITY_SWAP_RATIO,
) -> bool:
    """A swap moves properties both ways: each side must carry the other's."""
    if evidence is None:
        return False
    crossed = evidence["crossed"]
    return (
        evidence["crossed_sides"] == 2
        and crossed >= min_crossed
        and crossed > ratio * evidence["consistent"]
    )


def _check_entity_swap(
    answer_text: str, question_text: str, ideal_answer: str
) -> dict | None:
    evidence = entity_swap_evidence(answer_text, question_text, ideal_answer)
    if entity_swap_fires(evidence):
        return _cap("entity_swap", ENTITY_SWAP_CAP)
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
      6.5 entity_swap, 7 low_density, 8 off_topic
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

    swap = _check_entity_swap(answer_text or "", question_text or "", ideal_answer or "")
    if swap is not None:
        return swap

    answer_tokens = _word_tokens(answer_text or "")

    fluff = _check_low_density(answer_tokens)
    if fluff is not None:
        return fluff

    off = _check_off_topic(answer_text or "", answer_tokens, ideal_answer, ideal_keywords)
    if off is not None:
        return off

    return {"cap_required": False, "score_cap": 100, "reason": "", "message": "", "guards_fired": []}
