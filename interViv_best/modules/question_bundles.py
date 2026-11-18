"""Canonical question-bundle content: schema, hash, YAML loading, payload views.

Canonical source is YAML under ``data/question_bundles/<skill>/``. A YAML file
carries content and provenance only. Review state (status, decisions) lives in
the database and is never read from or written to YAML.

The content hash is sha256 over the canonical JSON of ``CONTENT_FIELDS``
(sorted keys, compact separators, stripped strings). Anything outside those
fields (author, source, attribution) is provenance and does not move the hash.
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any, Iterator

import yaml

DIFFICULTIES = ("easy", "medium", "hard")
SOURCES = ("imported_csv", "llm_draft", "human_authored")
DEFAULT_CATEGORY = "technical_short_answer"
BUNDLE_ID_RE = re.compile(r"^[a-z0-9-]+(\.[a-z0-9-]+)+$")
MAX_BUNDLE_ID_LEN = 64
GOOD_CALIBRATION_MAX_WORDS = 35
POOR_CALIBRATION_MIN_WORDS = 90

# Order is irrelevant for the hash (sorted keys), listed here for readers.
# ``version`` is deliberately not hashed: it numbers content, it is not content,
# so identical content re-numbered is caught by the (bundle_id, content_hash) rule.
CONTENT_FIELDS = (
    "bundle_id", "category", "skill", "topic", "difficulty",
    "question", "reference_answer", "acceptable_variants", "keywords",
    "required_concepts", "optional_concepts", "misconceptions", "depth_markers",
    "rubric_descriptors", "followups", "calibration_examples",
)
_LIST_FIELDS = (
    "acceptable_variants", "keywords", "required_concepts", "optional_concepts",
    "misconceptions", "depth_markers", "followups", "calibration_examples",
)
# Keys that describe review state and must never appear in canonical YAML.
_REVIEW_STATE_KEYS = ("status", "reviewed", "reviewers", "review", "decisions", "approved", "approved_by")
# Author-supplied labels hidden from reviewers until they have rated blind.
_AUTHOR_LABEL_KEYS = ("difficulty",)


class BundleContentError(ValueError):
    pass


def _clean(value: Any) -> Any:
    if isinstance(value, str):
        return " ".join(value.split())
    if isinstance(value, list):
        return [_clean(v) for v in value if v not in (None, "")]
    if isinstance(value, dict):
        return {str(k): _clean(v) for k, v in value.items()}
    return value


def canonical_content(doc: dict[str, Any]) -> dict[str, Any]:
    """Hashed content fields only (no version, no provenance)."""
    content: dict[str, Any] = {}
    for key in CONTENT_FIELDS:
        value = doc.get(key)
        if key in _LIST_FIELDS:
            value = value or []
        elif key == "rubric_descriptors":
            value = value or {}
        elif key == "category":
            value = value or DEFAULT_CATEGORY
        content[key] = _clean(value)
    content["difficulty"] = str(content["difficulty"] or "").lower()
    return content


def content_hash(content: dict[str, Any]) -> str:
    blob = json.dumps(content, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def validate_bundle_doc(doc: dict[str, Any]) -> dict[str, Any]:
    """Return ``{content, version, content_hash, source, attribution, author_id}`` or raise."""
    if not isinstance(doc, dict):
        raise BundleContentError("bundle document must be a mapping")
    present_state = [k for k in _REVIEW_STATE_KEYS if k in doc]
    if present_state:
        raise BundleContentError(
            f"review state keys {present_state} are not allowed in canonical content; "
            "review state lives only in the database"
        )
    content = canonical_content(doc)
    for key in ("bundle_id", "skill", "topic", "question", "reference_answer"):
        if not content.get(key):
            raise BundleContentError(f"missing required content field: {key}")
    version = doc.get("version")
    if not isinstance(version, int) or isinstance(version, bool) or version < 1:
        raise BundleContentError("version must be an integer >= 1")
    if content["difficulty"] not in DIFFICULTIES:
        raise BundleContentError(f"difficulty must be one of {DIFFICULTIES}")
    for key in _LIST_FIELDS:
        if not isinstance(content[key], list):
            raise BundleContentError(f"{key} must be a list")
    if not isinstance(content["rubric_descriptors"], dict):
        raise BundleContentError("rubric_descriptors must be a mapping")
    source = str(doc.get("source") or "").strip()
    if source not in SOURCES:
        raise BundleContentError(f"source must be one of {SOURCES}")
    author_id = str(doc.get("author") or "").strip()
    if not author_id:
        raise BundleContentError("author is required (identity of who wrote the content)")
    attribution = doc.get("attribution") or {}
    if not isinstance(attribution, dict):
        raise BundleContentError("attribution must be a mapping")
    if source == "imported_csv" and not attribution.get("source_file"):
        raise BundleContentError("imported_csv content must name attribution.source_file")
    return {
        "content": content,
        "version": version,
        "content_hash": content_hash(content),
        "source": source,
        "attribution": _clean(attribution),
        "author_id": author_id,
    }


def safe_slug(text: str, max_len: int = 28) -> str:
    """Return a clean ``[a-z0-9-]+`` slug bounded to ``max_len`` characters."""
    limit = max(1, int(max_len))
    raw = str(text or "").strip().lower()
    slug = re.sub(r"[^a-z0-9]+", "-", raw)
    slug = re.sub(r"-{2,}", "-", slug).strip("-")
    if len(slug) > limit:
        slug = slug[:limit].strip("-")
    return slug or ("item"[:limit])


def build_bundle_id(skill: str, topic: str) -> str:
    """Build a safe canonical bundle_id ``<skill-slug>.<topic-slug>`` (<= 57 chars)."""
    return f"{safe_slug(skill, 24)}.{safe_slug(topic, 32)}"


def safe_bundle_relative_path(skill: str, bundle_id: str) -> Path:
    """Return a strictly validated relative ``<skill_slug>/<bundle_id>.yaml`` path."""
    bid = str(bundle_id or "").strip()
    if (
        not bid
        or ".." in bid
        or "/" in bid
        or "\\" in bid
        or len(bid) > MAX_BUNDLE_ID_LEN
        or not BUNDLE_ID_RE.fullmatch(bid)
    ):
        raise BundleContentError(
            f"invalid bundle_id for file path: {bundle_id!r}"
        )
    skill_dir = safe_slug(skill, 32)
    rel = Path(skill_dir) / f"{bid}.yaml"
    if rel.is_absolute() or len(rel.parts) != 2 or ".." in rel.parts:
        raise BundleContentError(f"unsafe relative bundle path: {rel!r}")
    return rel


def _non_empty_str_list(
    items: Any,
    label: str,
    *,
    min_len: int = 1,
    max_len: int | None = None,
) -> list[str]:
    if not isinstance(items, list):
        raise BundleContentError(f"{label} must be a list")
    cleaned = [item.strip() for item in items if isinstance(item, str) and item.strip()]
    if len(cleaned) != len(items):
        raise BundleContentError(f"{label} must contain only non-empty strings")
    if len(cleaned) < min_len:
        raise BundleContentError(f"{label} must contain at least {min_len} item(s)")
    if max_len is not None and len(cleaned) > max_len:
        raise BundleContentError(f"{label} must contain at most {max_len} item(s)")
    return cleaned


def _validate_concept_entries(
    items: Any,
    field_name: str,
    *,
    min_len: int,
    max_len: int | None = None,
) -> list[str]:
    if not isinstance(items, list) or len(items) < min_len or (max_len is not None and len(items) > max_len):
        bound = f"{min_len}..{max_len}" if max_len is not None else f">= {min_len}"
        raise BundleContentError(f"{field_name} must have {bound} concept entries")
    ids: list[str] = []
    for idx, entry in enumerate(items):
        if not isinstance(entry, dict):
            raise BundleContentError(f"{field_name}[{idx}] must be a mapping")
        cid = entry.get("id").strip() if isinstance(entry.get("id"), str) else ""
        if not cid:
            raise BundleContentError(f"{field_name}[{idx}].id must be a non-empty string")
        desc_val = entry.get("description") if entry.get("description") is not None else entry.get("descriptor")
        desc = desc_val.strip() if isinstance(desc_val, str) else ""
        if not desc:
            raise BundleContentError(f"{field_name}[{idx}].description must be a non-empty string")
        _non_empty_str_list(entry.get("aliases"), f"{field_name}[{idx}].aliases", min_len=1)
        _non_empty_str_list(
            entry.get("expected_propositions"),
            f"{field_name}[{idx}].expected_propositions",
            min_len=1,
        )
        ids.append(cid)
    return ids


def evaluate_calibration_length_bias(
    answer: str,
    author_level: Any,
    expected_band: Any,
) -> tuple[int, bool | None, str | None]:
    """Return ``(word_count, length_bias_usable, unusable_reason)`` without clamping."""
    words = len(str(answer or "").split())
    if isinstance(author_level, bool):
        return words, None, None
    if author_level == 3 and expected_band == "Good":
        if 0 < words <= GOOD_CALIBRATION_MAX_WORDS:
            return words, True, None
        reason = "empty_answer" if words == 0 else "good_exceeded_35_words"
        return words, False, reason
    if author_level == 0 and expected_band == "Poor":
        if words >= POOR_CALIBRATION_MIN_WORDS:
            return words, True, None
        reason = "empty_answer" if words == 0 else "poor_under_90_words"
        return words, False, reason
    return words, None, None


_LEAK_PAREN_RE = re.compile(
    r"\([^)]*\b(?:words?|max(?:imum)?|min(?:imum)?|limit|sentences?|chars?|characters?)\b[^)]*\)",
    re.IGNORECASE,
)
_LEAK_LIMIT_RE = re.compile(
    r"\b(?:40\s+words?\b|\d+\s+words?\s+(?:max|limit)|(?:at\s+most|max|maximum|under)\s+\d+\s+(?:words?|sentences?)|two\s+sentences?\s+(?:max|limit))\b",
    re.IGNORECASE,
)
_LEAK_SCHEMA_KEY_RE = re.compile(
    r"\b(?:reference_answer|acceptable_variants|required_concepts|optional_concepts|"
    r"depth_markers|rubric_descriptors|calibration_examples|targets_concept|"
    r"expected_propositions|candidate_patterns|author_level|expected_band)\b",
    re.IGNORECASE,
)
_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+|\n+")
# Same token and term splitting as concept_evaluator_v2 term matching.
_TERM_TOKEN_RE = re.compile(r"[A-Za-z0-9_]+(?:'[A-Za-z]+)?")
_TERM_PART_SPLIT_RE = re.compile(r"[\s_/.-]+")


def _fold_plural(token: str) -> str:
    """Crude singular form so 'tuples'/'tuple' and 'queries'/'query' compare equal."""
    if len(token) > 4 and token.endswith("ies"):
        return token[:-3] + "y"
    if len(token) > 3 and token.endswith("s") and not token.endswith("ss"):
        return token[:-1]
    return token


def _question_term_tokens(question: str) -> list[str]:
    return [_fold_plural(m.group(0).casefold()) for m in _TERM_TOKEN_RE.finditer(question or "")]


def _term_in_question(term: str, q_tokens: list[str]) -> bool:
    """True when ``term`` occurs in the question as a whole-token sequence.

    Terms split exactly as the concept evaluator splits concept ids and
    aliases (whitespace, underscore, slash, dot, hyphen), with plural folding.
    """
    parts: list[str] = []
    for piece in _TERM_PART_SPLIT_RE.split(str(term or "").casefold()):
        parts.extend(_fold_plural(m.group(0)) for m in _TERM_TOKEN_RE.finditer(piece))
    if not parts or len(parts) > len(q_tokens):
        return False
    n = len(parts)
    return any(q_tokens[i : i + n] == parts for i in range(len(q_tokens) - n + 1))


def alias_question_overlap(content: dict[str, Any]) -> list[tuple[str, str]]:
    """``(concept_id, term)`` pairs whose id or alias appears in the question.

    The concept evaluator matches a concept's id and aliases as terms, so a
    term that is already a question word is credited to any answer that
    merely repeats the question.
    """
    q_tokens = _question_term_tokens(str(content.get("question") or ""))
    hits: list[tuple[str, str]] = []
    if not q_tokens:
        return hits
    for field_name in ("required_concepts", "optional_concepts"):
        for concept in content.get(field_name) or []:
            if not isinstance(concept, dict):
                continue
            cid = str(concept.get("id") or "").strip()
            terms = [cid, *[str(a) for a in (concept.get("aliases") or [])]]
            for term in terms:
                if term.strip() and _term_in_question(term, q_tokens):
                    hits.append((cid, term.strip()))
    return hits


POSITIVE_EXAMPLES_MIN = 2
POSITIVE_EXAMPLES_MAX = 3
POSITIVE_EXAMPLE_MIN_WORDS = 6
POSITIVE_EXAMPLE_MAX_WORDS = 25
# Two texts are near copies when their word sets overlap this much (Jaccard),
# or when almost every word of the shorter one appears in the longer one.
NEAR_COPY_JACCARD = 0.7
NEAR_COPY_CONTAINMENT = 0.85
_INNER_SENTENCE_RE = re.compile(r"[.!?]\s+\S")


def _word_set(text: str) -> set[str]:
    return {m.group(0).casefold() for m in _TERM_TOKEN_RE.finditer(text or "")}


def _near_copy(a: str, b: str) -> bool:
    wa, wb = _word_set(a), _word_set(b)
    if not wa or not wb:
        return False
    inter = len(wa & wb)
    if inter / len(wa | wb) >= NEAR_COPY_JACCARD:
        return True
    return inter / min(len(wa), len(wb)) >= NEAR_COPY_CONTAINMENT


def near_copy_source(text: str, sources: list[str]) -> str | None:
    """Return the first source sentence that ``text`` nearly copies, if any."""
    for source in sources:
        for sentence in _SENTENCE_SPLIT_RE.split(str(source or "")):
            if sentence.strip() and _near_copy(text, sentence):
                return sentence.strip()
    return None


def positive_example_copies(
    content: dict[str, Any], sources: list[str]
) -> list[tuple[str, str, str]]:
    """``(concept_id, example, source_sentence)`` for required-concept examples
    that nearly copy a sentence from ``sources``."""
    hits: list[tuple[str, str, str]] = []
    for concept in content.get("required_concepts") or []:
        if not isinstance(concept, dict):
            continue
        cid = str(concept.get("id") or "").strip()
        for example in concept.get("positive_examples") or []:
            source = near_copy_source(str(example), sources)
            if source is not None:
                hits.append((cid, str(example), source))
    return hits


def _validate_positive_examples(content: dict[str, Any]) -> None:
    """Each required concept carries 2-3 natural one-sentence correct answers.

    Examples are 6-25 words, one sentence, worded differently from each other,
    and not copied from the reference answer. They feed the evaluator's
    semantic tier, so a copied or duplicated example would make the check
    easier without adding evidence.
    """
    reference = str(content.get("reference_answer") or "")
    for idx, concept in enumerate(content.get("required_concepts") or []):
        cid = str(concept.get("id") or f"required_concepts[{idx}]").strip()
        label = f"required_concepts[{idx}].positive_examples"
        examples = _non_empty_str_list(
            concept.get("positive_examples"),
            label,
            min_len=POSITIVE_EXAMPLES_MIN,
            max_len=POSITIVE_EXAMPLES_MAX,
        )
        for example in examples:
            words = len(example.split())
            if not POSITIVE_EXAMPLE_MIN_WORDS <= words <= POSITIVE_EXAMPLE_MAX_WORDS:
                raise BundleContentError(
                    f"positive example for concept {cid!r} must be "
                    f"{POSITIVE_EXAMPLE_MIN_WORDS}-{POSITIVE_EXAMPLE_MAX_WORDS} words "
                    f"({words} words): {example!r}"
                )
            if "\n" in example or _INNER_SENTENCE_RE.search(example):
                raise BundleContentError(
                    f"positive example for concept {cid!r} must be one sentence: {example!r}"
                )
            copied = near_copy_source(example, [reference])
            if copied is not None:
                raise BundleContentError(
                    f"positive example for concept {cid!r} is copied from the reference "
                    f"answer: {example!r} ~ {copied!r}"
                )
        for i in range(len(examples)):
            for j in range(i + 1, len(examples)):
                if _near_copy(examples[i], examples[j]):
                    raise BundleContentError(
                        f"positive examples for concept {cid!r} must use different wording: "
                        f"{examples[i]!r} ~ {examples[j]!r}"
                    )


def validate_generated_bundle_text_quality(content: dict[str, Any]) -> None:
    """Reject brittle propositions, instruction leakage, and repeated sentences in Step E.1."""
    question_text = str(content.get("question") or "")
    q_words = set(re.findall(r"[a-z0-9_]+", question_text.casefold()))

    overlap = alias_question_overlap(content)
    if overlap:
        listed = ", ".join(f"{term!r} (concept {cid!r})" for cid, term in overlap)
        raise BundleContentError(
            "aliases must not be words from the question; concept id or alias "
            f"found in the question: {listed}"
        )

    seen_props: dict[str, str] = {}
    for field_name in ("required_concepts", "optional_concepts"):
        for idx, concept in enumerate(content.get(field_name) or []):
            cid = str(concept.get("id") or f"{field_name}[{idx}]").strip()
            for prop in concept.get("expected_propositions") or []:
                prop_str = str(prop or "").strip()
                p_words = re.findall(r"[A-Za-z0-9_]+", prop_str)
                if len(p_words) < 3:
                    raise BundleContentError(
                        f"proposition in concept {cid!r} has under 3 words ({len(p_words)} words): {prop_str!r}"
                    )
                p_lower = {w.casefold() for w in p_words}
                if q_words and p_lower.issubset(q_words):
                    raise BundleContentError(
                        f"proposition in concept {cid!r} only restates words from the question: {prop_str!r}"
                    )
                norm_prop = " ".join(w.casefold() for w in p_words)
                if norm_prop in seen_props and seen_props[norm_prop] != cid:
                    raise BundleContentError(
                        f"duplicate proposition {prop_str!r} shared between concepts "
                        f"{seen_props[norm_prop]!r} and {cid!r}"
                    )
                seen_props[norm_prop] = cid

    learner_fields: list[tuple[str, str]] = [("question", question_text)]
    for idx, fu in enumerate(content.get("followups") or []):
        learner_fields.append((f"followups[{idx}].prompt", str((fu or {}).get("prompt") or "")))
    for field_name, text in learner_fields:
        for pattern in (_LEAK_PAREN_RE, _LEAK_LIMIT_RE, _LEAK_SCHEMA_KEY_RE):
            m = pattern.search(text)
            if m is not None:
                raise BundleContentError(
                    f"instruction leakage in {field_name}: {m.group(0)!r}"
                )

    text_fields: list[tuple[str, str]] = [
        ("question", question_text),
        ("reference_answer", str(content.get("reference_answer") or "")),
    ]
    for idx, fu in enumerate(content.get("followups") or []):
        text_fields.append((f"followups[{idx}].prompt", str((fu or {}).get("prompt") or "")))
    for idx, ex in enumerate(content.get("calibration_examples") or []):
        text_fields.append((f"calibration_examples[{idx}].answer", str((ex or {}).get("answer") or "")))

    q_norm_sentences = {
        " ".join(re.findall(r"[a-z0-9_]+", s.casefold()))
        for s in _SENTENCE_SPLIT_RE.split(question_text)
        if s.strip()
    }
    q_norm_sentences = {ns for ns in q_norm_sentences if len(ns.split()) >= 3}

    for field_name, text in text_fields:
        seen_sentences: set[str] = set()
        for sent in _SENTENCE_SPLIT_RE.split(text):
            clean_sent = sent.strip()
            if not clean_sent:
                continue
            norm_s = " ".join(re.findall(r"[a-z0-9_]+", clean_sent.casefold()))
            if len(norm_s.split()) < 3:
                continue
            if norm_s in seen_sentences:
                raise BundleContentError(
                    f"repeated sentence in {field_name}: {clean_sent!r}"
                )
            if field_name.startswith("followups[") and norm_s in q_norm_sentences:
                raise BundleContentError(
                    f"repeated sentence in {field_name} matching question: {clean_sent!r}"
                )
            seen_sentences.add(norm_s)


def validate_generated_bundle_doc(doc: dict[str, Any]) -> dict[str, Any]:
    """Validate a newly generated WS2 bundle document (strict Step E.1 structural checks)."""
    parsed = validate_bundle_doc(doc)
    content = parsed["content"]

    if content["category"] != DEFAULT_CATEGORY:
        raise BundleContentError(
            f"generated bundle category must be {DEFAULT_CATEGORY!r}, got {content['category']!r}"
        )

    bundle_id = str(content["bundle_id"])
    if len(bundle_id) > MAX_BUNDLE_ID_LEN or not BUNDLE_ID_RE.fullmatch(bundle_id):
        raise BundleContentError(
            f"bundle_id must match {BUNDLE_ID_RE.pattern} and be <= {MAX_BUNDLE_ID_LEN} chars"
        )

    required_ids = set(
        _validate_concept_entries(content["required_concepts"], "required_concepts", min_len=2, max_len=5)
    )
    _validate_positive_examples(content)
    _validate_concept_entries(content["optional_concepts"], "optional_concepts", min_len=1)
    _non_empty_str_list(content["keywords"], "keywords", min_len=3, max_len=10)

    misconceptions = content["misconceptions"]
    if not isinstance(misconceptions, list) or len(misconceptions) < 1:
        raise BundleContentError("misconceptions must contain at least 1 entry")
    for idx, entry in enumerate(misconceptions):
        if not isinstance(entry, dict):
            raise BundleContentError(f"misconceptions[{idx}] must be a mapping")
        mid = entry.get("id").strip() if isinstance(entry.get("id"), str) else ""
        mdesc = entry.get("description").strip() if isinstance(entry.get("description"), str) else ""
        if not mid or not mdesc:
            raise BundleContentError(
                f"misconceptions[{idx}] must have non-empty id and description"
            )
        _non_empty_str_list(
            entry.get("candidate_patterns"),
            f"misconceptions[{idx}].candidate_patterns",
            min_len=1,
        )

    followups = content["followups"]
    if not isinstance(followups, list) or len(followups) < 2:
        raise BundleContentError("followups must contain at least 2 entries")
    for idx, entry in enumerate(followups):
        if not isinstance(entry, dict):
            raise BundleContentError(f"followups[{idx}] must be a mapping with prompt and targets_concept")
        prompt = entry.get("prompt").strip() if isinstance(entry.get("prompt"), str) else ""
        target = entry.get("targets_concept").strip() if isinstance(entry.get("targets_concept"), str) else ""
        if not prompt or not target:
            raise BundleContentError(f"followups[{idx}] must have non-empty prompt and targets_concept")
        if target not in required_ids:
            raise BundleContentError(
                f"followups[{idx}].targets_concept {target!r} must match an id in required_concepts"
            )

    examples = content["calibration_examples"]
    if not isinstance(examples, list) or len(examples) < 2:
        raise BundleContentError("calibration_examples must contain at least 2 entries")
    has_good = False
    has_poor = False
    for idx, ex in enumerate(examples):
        if not isinstance(ex, dict):
            raise BundleContentError(f"calibration_examples[{idx}] must be a mapping")
        answer = ex.get("answer").strip() if isinstance(ex.get("answer"), str) else ""
        if not answer:
            raise BundleContentError(f"calibration_examples[{idx}].answer must be non-empty")
        level = ex.get("author_level")
        band = ex.get("expected_band")
        words, usable, reason = evaluate_calibration_length_bias(answer, level, band)
        ex["word_count"] = words
        if usable is not None:
            ex["length_bias_usable"] = usable
            if reason is not None:
                ex["length_bias_unusable_reason"] = reason
            else:
                ex.pop("length_bias_unusable_reason", None)
        else:
            ex.pop("length_bias_usable", None)
            ex.pop("length_bias_unusable_reason", None)
        if not isinstance(level, bool) and level == 3 and band == "Good":
            has_good = True
        if not isinstance(level, bool) and level == 0 and band == "Poor":
            has_poor = True

    if not has_good:
        raise BundleContentError(
            "calibration_examples must include a Good example (author_level=3, expected_band='Good')"
        )
    if not has_poor:
        raise BundleContentError(
            "calibration_examples must include a Poor example (author_level=0, expected_band='Poor')"
        )

    validate_generated_bundle_text_quality(content)

    parsed["content_hash"] = content_hash(content)
    return parsed


def default_bundle_root() -> Path:
    return Path(__file__).resolve().parents[1] / "data" / "question_bundles"


def iter_bundle_files(root: Path | None = None) -> Iterator[tuple[Path, dict[str, Any]]]:
    root = root or default_bundle_root()
    for path in sorted(root.rglob("*.yaml")) + sorted(root.rglob("*.yml")):
        with path.open("r", encoding="utf-8") as fh:
            loaded = yaml.safe_load(fh)
        docs = loaded if isinstance(loaded, list) else [loaded]
        for doc in docs:
            if doc is None:
                continue
            yield path, doc


def candidate_payload(version_doc: dict[str, Any]) -> dict[str, Any]:
    """Candidate-facing view: identity + question only. No reference material."""
    content = version_doc["content_json"]
    status = version_doc.get("status")
    payload_source = (
        "reviewed_bundle"
        if status in ("reviewed", "draft", None)
        else f"{status}_bundle"
    )
    return {
        "bundle_id": version_doc["bundle_id"],
        "version": version_doc["version"],
        "content_hash": version_doc["content_hash"],
        "category": content["category"],
        "skill": content["skill"],
        "topic": content["topic"],
        "difficulty": content["difficulty"],
        "question": content["question"],
        "source": payload_source,
    }


def reviewer_blind_view(version_doc: dict[str, Any]) -> dict[str, Any]:
    """Full content for a reviewer, minus the author's labels (difficulty,
    per-example author levels). Reviewers rate those blind first."""
    content = json.loads(json.dumps(version_doc["content_json"]))
    for key in _AUTHOR_LABEL_KEYS:
        content.pop(key, None)
    content["calibration_examples"] = [
        {k: v for k, v in ex.items() if k != "author_level"} if isinstance(ex, dict) else ex
        for ex in content.get("calibration_examples", [])
    ]
    return {
        "bundle_id": version_doc["bundle_id"],
        "version": version_doc["version"],
        "content_hash": version_doc["content_hash"],
        "status": version_doc["status"],
        "source": version_doc["source"],
        "attribution": version_doc["attribution_json"],
        "content": content,
    }
