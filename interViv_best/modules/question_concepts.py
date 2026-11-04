"""Additive question-scoped diagnostics; never feeds calibrated score features.

Bank rubrics come from the checked-in offline index. No ideal-answer extraction
is performed here. Unknown/stale questions retain explicit keywords only.
"""
from __future__ import annotations

import hashlib
import json
import re
from functools import lru_cache
from pathlib import Path
from typing import Any

from backend.config import SEMANTIC_MODEL_REVISION
from modules.knowledge_graph import ALIASES

INDEX_PATH = Path(__file__).resolve().parents[1] / 'data/question_concepts_v1.json'
TIER3_SIMILARITY_THRESHOLD = 0.62
# Additive confidence bands, chosen from the in-sample manual audit. They do
# not replace the legacy binary threshold above or Tier 2's 0.72 credit rule.
# Lowest reviewed partial evidence: 0.3009; lowest false miss: 0.3015.
# Unsupported Tier-3 hits span 0.6212–0.7048. Treat that region as uncertain.
CONCEPT_MISS_MAX_SIMILARITY = 0.30  # strictly below
CONCEPT_MATCH_MIN_SIMILARITY = 0.72
CONCEPT_STATUS_VERSION = 'concept_status_v1_in_sample'
_TOKEN = re.compile(r'[^\W_]+|[+#@]', re.UNICODE)


def normalize(text: str) -> str:
    return ' '.join(m.group().casefold() for m in _TOKEN.finditer(str(text)))


def canonical(text: str) -> str:
    value = normalize(text)
    return {normalize(k): normalize(v) for k, v in ALIASES.items()}.get(value, value)


def aliases_for(concept: str, extra: list[str] | None = None) -> list[str]:
    from modules.nlp_scorer import _KEYWORD_ALIASES
    key = canonical(concept)
    aliases = {normalize(concept), key, *(normalize(x) for x in (extra or []))}
    aliases.update(normalize(a) for a, c in ALIASES.items() if normalize(c) == key)
    aliases.update(normalize(a) for a in _KEYWORD_ALIASES.get(normalize(concept), set()))
    return sorted(a for a in aliases if a)


def first_offset(text: str, surfaces: list[str]) -> int | None:
    """Whole normalized token sequences, with offsets into the original text."""
    tokens = [(m.group().casefold(), m.start()) for m in _TOKEN.finditer(text)]
    words = [x[0] for x in tokens]
    positions = []
    for surface in surfaces:
        wanted = normalize(surface).split()
        if not wanted:
            continue
        for i in range(len(words) - len(wanted) + 1):
            if words[i:i + len(wanted)] == wanted:
                positions.append(tokens[i][1])
                break
    return min(positions) if positions else None


def keyword_list(value: Any) -> list[str]:
    if isinstance(value, str):
        return [s.strip() for s in re.split(r'[,|]', value) if s.strip()]
    return [str(s).strip() for s in (value or []) if str(s).strip()]


def question_id(skill: str, question: str, source: str = 'v6') -> str:
    digest = hashlib.sha256((skill.casefold().strip() + '\0' + normalize(question)).encode()).hexdigest()
    return f'{source}:{digest[:24]}'


def rubric_hash(context: dict) -> str:
    raw = [context.get('ideal_answer') or context.get('reference_answer') or '',
           keyword_list(context.get('ideal_keywords') or context.get('keywords'))]
    return hashlib.sha256(json.dumps(raw, ensure_ascii=False).encode()).hexdigest()


def explicit_entries(required: list, source: str) -> list[dict]:
    entries, seen = [], set()
    for item in required:
        concept = str(item.get('id') or item.get('concept_id') or '') if isinstance(item, dict) else str(item)
        key = canonical(concept)
        if not key or key in seen:
            continue
        seen.add(key)
        entries.append({'concept':concept, 'source':source, 'order':len(entries),
                        'aliases':aliases_for(concept, item.get('aliases', []) if isinstance(item, dict) else [])})
    return entries


@lru_cache(maxsize=1)
def load_index() -> dict:
    # Missing index degrades diagnostics, never the established score path.
    if not INDEX_PATH.exists():
        return {'questions':{}}
    return json.loads(INDEX_PATH.read_text())


def lookup(context: dict) -> tuple[dict | None, str]:
    questions = load_index()['questions']
    ids = [context.get('question_id')]
    if context.get('bundle_id') and context.get('bundle_version'):
        ids.append(f"bundle:{context['bundle_id']}:v{context['bundle_version']}")
    ids.extend(question_id(context.get('skill', ''), context.get('question', ''), source) for source in ('v6', 'fallback'))
    for qid in ids:
        entry = questions.get(qid)
        if entry is not None:
            if entry['rubric_hash'] != rubric_hash(context):
                # Text may coincide across sources; continue to a matching rubric.
                continue
            return entry, 'indexed'
    return None, 'unindexed_or_stale'


def _concept_status(*, source: str, method: str, matched: bool,
                    similarity: float | None, literal_evidence: bool,
                    empty_answer: bool) -> tuple[str, str]:
    """Three-state diagnostic, independent of existing binary match credit.

    These are operational evidence bands, not calibrated probabilities.
    Missing semantic evidence on a nonempty answer never implies a miss.
    """
    if source == 'bundle_v2':
        if method == 'supported':
            return 'matched', 'bundle_supported'
        if method in {'contradicted', 'not_demonstrated'}:
            return 'missed', 'bundle_' + method
        return 'uncertain', 'bundle_uncertain'
    if method in {'exact', 'alias'}:
        if literal_evidence:
            return 'matched', 'token_' + method
        return 'uncertain', 'legacy_hit_without_token_evidence'
    if empty_answer:
        return 'missed', 'empty_answer'
    if similarity is None:
        return 'uncertain', 'semantic_evidence_unavailable'
    # Tier 2 exposes rounded cosines; require its original credit decision as
    # well, so a rounded-up 0.71999 cannot newly become a confident match.
    if matched and similarity >= CONCEPT_MATCH_MIN_SIMILARITY:
        return 'matched', 'semantic_high'
    if similarity < CONCEPT_MISS_MAX_SIMILARITY:
        return 'missed', 'semantic_low'
    return 'uncertain', 'semantic_ambiguity_band'


def question_concepts_summary(*, answer_text: str, question_context: dict,
                              keyword_details: dict | None, semantic_scorer: Any = None) -> dict:
    context = question_context
    bundle = context.get('bundle_content') or context
    required = bundle.get('required_concepts') or []
    indexed, index_status = lookup(context)
    if required:
        from modules.concept_evaluator_v2 import evaluate_answer
        entries = explicit_entries(required, 'bundle_v2')
        # Explicit CSV keywords may supplement a bundle, but never override a
        # bundle concept or one of its registered aliases (including uncertain
        # and contradicted evidence). Never extract an ideal answer here.
        occupied = {surface for entry in entries for surface in entry['aliases']}
        for entry in explicit_entries(keyword_list(context.get('ideal_keywords')), 'ideal_keywords'):
            if occupied.intersection(entry['aliases']):
                continue
            entry['order'] = len(entries)
            entries.append(entry)
            occupied.update(entry['aliases'])
        evidence = evaluate_answer(answer_text=answer_text, bundle_content=bundle)
        states = {canonical(c['concept_id']):c['state'] for c in evidence['concepts']}
        source = 'bundle_v2'
        index_status = 'explicit_bundle'
    else:
        entries = (indexed or {}).get('concepts')
        if entries is None:
            entries = explicit_entries(keyword_list(context.get('ideal_keywords')), 'ideal_keywords')
        states = {}
        source = (indexed or {}).get('source', 'ideal_keywords' if entries else 'ideal_answer_kg')
    excluded_texts = [context.get('question') or bundle.get('question') or '',
                      *keyword_list(context.get('prompt_supplied_concepts'))]
    # Do not join unrelated prompt fragments: a phrase may not straddle them.
    excluded, trace = [], []
    matches = {canonical(m['keyword']):m for m in (keyword_details or {}).get('matches', [])}
    answer_candidates = None
    for entry in entries:
        concept, entry_source = entry['concept'], entry['source']
        surfaces = entry['aliases']
        if any(first_offset(text, surfaces) is not None for text in excluded_texts):
            excluded.append(concept)
            continue
        similarity = None
        threshold = None
        if entry_source == 'bundle_v2':
            method = states.get(canonical(concept), 'not_demonstrated')
            matched = method == 'supported'
        elif entry_source == 'ideal_keywords':
            detail = matches.get(canonical(concept), {})
            matched = bool(detail.get('covered'))
            method = detail.get('method') or ('exact' if detail.get('exact') else 'alias' if detail.get('alias') else 'not_matched')
            similarity = detail.get('similarity', detail.get('semantic_similarity'))
            threshold = (keyword_details or {}).get('semantic_threshold', 0.72)
        else:
            exact = first_offset(answer_text, [normalize(concept)]) is not None
            alias = not exact and first_offset(answer_text, surfaces) is not None
            matched = exact or alias
            method = 'exact' if exact else 'alias' if alias else 'not_matched'
            threshold = TIER3_SIMILARITY_THRESHOLD
            if not matched and semantic_scorer is not None:
                if answer_candidates is None:
                    from modules.nlp_scorer import _answer_ngram_candidates, _tokenize
                    answer_candidates = _answer_ngram_candidates(_tokenize(answer_text))
                similarity = semantic_scorer.max_similarity(normalize(concept), answer_candidates)
                matched = similarity is not None and similarity >= threshold
                method = 'semantic' if matched else 'not_matched'
        status, status_reason = _concept_status(
            source=entry_source, method=method, matched=bool(matched),
            similarity=similarity,
            literal_evidence=first_offset(answer_text, surfaces) is not None,
            empty_answer=not answer_text.strip(),
        )
        trace.append({'concept':concept, 'source':entry_source, 'order':entry['order'],
                      'matched':bool(matched), 'method':method,
                      'similarity':round(float(similarity), 4) if similarity is not None else None,
                      'threshold':threshold, 'model_revision':SEMANTIC_MODEL_REVISION,
                      'status':status, 'status_reason':status_reason})
    missed = [t for t in trace if not t['matched']]
    # Bundle contradictions precede other misses; each group retains rubric order.
    missed.sort(key=lambda t: 0 if t['method'] == 'contradicted' else 1)
    return {'matched_concepts':[t['concept'] for t in trace if t['matched']],
            'missed_concepts':[t['concept'] for t in missed],
            'question_concepts_excluded':excluded, 'concept_source':source,
            'concept_match_trace':trace, 'concept_index_status':index_status,
            'concept_status_version':CONCEPT_STATUS_VERSION,
            'concept_statuses':{
                state:[t['concept'] for t in trace if t['status'] == state]
                for state in ('matched', 'uncertain', 'missed')
            },
            'concept_status_cutoffs':{
                'miss_below':CONCEPT_MISS_MAX_SIMILARITY,
                'match_at_least':CONCEPT_MATCH_MIN_SIMILARITY,
                'calibration_status':'in_sample_manual_review',
            }}
