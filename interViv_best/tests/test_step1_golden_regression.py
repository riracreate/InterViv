"""Compare against the JSON committed BEFORE Step 1; never regenerate it here."""
import copy
import hashlib
import json
from pathlib import Path

import pytest

from backend.config import SEMANTIC_MODEL_NAME, SEMANTIC_MODEL_REVISION
from backend.scoring.pipeline import run_scoring_pipeline
from modules.question_concepts import (aliases_for, canonical, first_offset, load_index,
    question_concepts_summary, question_id)

ROOT = Path(__file__).resolve().parents[1]
GOLDEN_PATH = ROOT / 'tests/fixtures/step1_golden_prechange.json'
GOLDEN_SHA256 = 'b8d482e27040e1164700cb3a006867573c86114f9cd87de5e06d52a3c8240915'
GOLDEN = json.loads(GOLDEN_PATH.read_text())
ADDITIONS = {'matched_concepts','missed_concepts','question_concepts_excluded',
             'concept_source','concept_match_trace','concept_index_status',
             'concept_statuses','concept_status_version','concept_status_cutoffs'}


@pytest.fixture(scope='module')
def loaded_revision_audit():
    audit = {'printed':False}
    yield audit
    # The test run must never rewrite the committed baseline.
    assert hashlib.sha256(GOLDEN_PATH.read_bytes()).hexdigest() == GOLDEN_SHA256


def legacy_projection(result):
    result = copy.deepcopy(result)
    for concepts in (result['concepts'], result['scoring_breakdown']['concepts']):
        for field in ADDITIONS:
            concepts.pop(field, None)
    for item in (result['scoring_breakdown'].get('keyword_coverage_details') or {}).get('matches', []):
        item.pop('similarity', None)
        item.pop('method', None)
    return result


def assert_same(actual, expected, path='result'):
    if isinstance(expected, dict):
        assert actual.keys() == expected.keys(), path
        for key in expected:
            assert_same(actual[key], expected[key], f'{path}.{key}')
    elif isinstance(expected, list):
        assert len(actual) == len(expected), path
        for i, (a, e) in enumerate(zip(actual, expected)):
            assert_same(a, e, f'{path}[{i}]')
    elif isinstance(expected, float):
        assert round(actual, 4) == round(expected, 4), (path, actual, expected)
    else:
        assert actual == expected, (path, actual, expected)


def test_capture_integrity_and_runtime_pin():
    assert hashlib.sha256(GOLDEN_PATH.read_bytes()).hexdigest() == GOLDEN_SHA256
    assert SEMANTIC_MODEL_REVISION == GOLDEN['capture']['model_revision']
    assert SEMANTIC_MODEL_NAME == GOLDEN['capture']['model_name']
    assert len([c for c in GOLDEN['cases'] if c['group'] == 'validation']) == 50
    assert len([c for c in GOLDEN['cases'] if c['group'] == 'regression_fixture']) == 10
    for name in ('data/interview_dataset_v6.csv','data/baseline_v2_key.csv',
                 'data/baseline_v2_system_scores.csv','scripts/scoring_regression.py'):
        assert hashlib.sha256((ROOT/name).read_bytes()).hexdigest() == GOLDEN['capture']['source_sha256'][name]


@pytest.mark.parametrize('case', GOLDEN['cases'], ids=lambda c:c['id'])
def test_frozen_outputs_and_concept_invariants(case, monkeypatch, loaded_revision_audit):
    for k, v in GOLDEN['capture']['flags'].items():
        monkeypatch.setenv(k, v)
    result = run_scoring_pipeline(**case['input'])
    assert_same(legacy_projection(result), case['output'])
    if case['input']['answer_text']:
        assert result['scoring_breakdown']['semantic_scoring_available'], 'Golden requires pinned model; no lexical substitute'
        # Inspect the live model used by the pipeline's dynamically loaded NLP
        # scorer, not merely the configured revision or a separately loaded model.
        from backend.integrations import load_module
        nlp = load_module('nlp_scorer_patch', 'nlp_scorer_patch.py')
        semantic = nlp._BaseNLPScorer.get_feature_scores.__globals__['_get_semantic_scorer']()
        model = semantic.score.__func__.__globals__['_model']
        actual_revision = model[0].auto_model.config._commit_hash
        assert actual_revision == SEMANTIC_MODEL_REVISION
        if not loaded_revision_audit['printed']:
            print(f'\nSCORING_MODEL_REVISION_LOADED={actual_revision}')
            loaded_revision_audit['printed'] = True
    concepts = result['concepts']
    assert concepts == result['scoring_breakdown']['concepts']
    matched = {canonical(c) for c in concepts['matched_concepts']}
    missed = {canonical(c) for c in concepts['missed_concepts']}
    assert not matched & missed
    assert len(matched) == len(concepts['matched_concepts'])
    assert len(missed) == len(concepts['missed_concepts'])
    question = case['input']['question_context']['question']
    assert all(first_offset(question, aliases_for(c)) is None for c in concepts['matched_concepts'] + concepts['missed_concepts'])
    trace = concepts['concept_match_trace']
    assert [t['order'] for t in trace] == sorted(t['order'] for t in trace)
    assert concepts['matched_concepts'] == [t['concept'] for t in trace if t['matched']]
    assert concepts['missed_concepts'] == [t['concept'] for t in trace if not t['matched']]
    statuses = concepts['concept_statuses']
    assert set(statuses) == {'matched','uncertain','missed'}
    flattened = [canonical(c) for names in statuses.values() for c in names]
    assert len(flattened) == len(set(flattened)) == len(trace)
    for status, names in statuses.items():
        assert names == [t['concept'] for t in trace if t['status'] == status]


@pytest.mark.parametrize('text,concept,expected', [
    ('classification and superclass', 'class', False),
    ('shipping and APIs', 'IP', False), ('scarcity', 'CAR', False),
    ('An IP address', 'IP', True), ('the parent_class', 'parent class', True),
    ('three-way handshake', 'three way handshake', True), ('overfitting', 'overfit', True), ('overfitment', 'overfit', False),
    ('the b-tree', 'B_tree', True),
])
def test_token_boundary_exclusion(text, concept, expected):
    assert (first_offset(text, aliases_for(concept)) is not None) is expected


def test_bundle_precedence_prompt_exclusion_and_contradiction_order():
    required = [
        {'id':'alpha','expected_propositions':['alpha works correctly']},
        {'id':'beta','expected_propositions':['beta works correctly']},
        {'id':'gamma','expected_propositions':['gamma works correctly']},
        {'id':'delta','aliases':['fourth term']},
    ]
    result = question_concepts_summary(answer_text='beta does not work correctly. gamma works correctly.',
        question_context={'question':'Explain fourth term.', 'required_concepts':required,
                          'prompt_supplied_concepts':['gamma']},
        keyword_details={'matches':[{'keyword':'beta','covered':True,'exact':True}]})
    assert result['matched_concepts'] == []
    assert result['missed_concepts'] == ['beta','alpha']
    assert result['question_concepts_excluded'] == ['gamma','delta']
    assert result['concept_match_trace'][1]['method'] == 'contradicted'


def test_no_ideal_extraction_at_runtime_and_stale_index(monkeypatch):
    from modules.knowledge_graph import KnowledgeGraphScorer
    from modules.ner_scorer import NERScorer
    def forbidden(*args, **kwargs):
        raise AssertionError('Runtime ideal-answer extraction is forbidden')
    monkeypatch.setattr(KnowledgeGraphScorer, '_find_nodes', forbidden)
    monkeypatch.setattr(NERScorer, 'extract_entities', forbidden)
    entry = next(q for q in load_index()['questions'].values() if q['bank_source']=='v6')
    result = question_concepts_summary(answer_text='x', keyword_details=None,
        question_context={'question_id':entry['question_id'], 'skill':entry['skill'],
                          'question':entry['question'], 'ideal_answer':'changed rubric'})
    assert result['concept_index_status'] == 'unindexed_or_stale'
    assert result['concept_match_trace'] == []


def test_index_has_all_bank_questions_in_deterministic_order():
    from scripts.build_question_concepts import build
    rebuilt = build()
    stored = load_index()
    mismatches = {path:(digest, stored['source_sha256'].get(path))
                  for path, digest in rebuilt['source_sha256'].items()
                  if digest != stored['source_sha256'].get(path)}
    assert not mismatches, mismatches
    assert rebuilt == stored
    questions = load_index()['questions']
    assert sum(q['bank_source']=='v6' for q in questions.values()) == 773
    assert sum(q['bank_source']=='fallback' for q in questions.values()) == 53
    assert sum(q['bank_source']=='bundle' for q in questions.values()) == 24
    for q in questions.values():
        assert [c['order'] for c in q['concepts']] == list(range(len(q['concepts'])))
        offsets = [c['ideal_answer_offset'] for c in q['concepts'] if c['source']=='ideal_answer_kg']
        assert offsets == sorted(offsets)


def test_tier3_threshold_preserves_below_threshold_trace(monkeypatch):
    from modules import question_concepts as module
    entry = {'source':'ideal_answer_kg', 'concepts':[
        {'concept':'alpha', 'source':'ideal_answer_kg', 'order':0, 'aliases':['alpha']},
        {'concept':'beta', 'source':'ideal_answer_kg', 'order':1, 'aliases':['beta']},
    ]}
    monkeypatch.setattr(module, 'lookup', lambda ctx:(entry, 'indexed'))
    class Semantic:
        def max_similarity(self, query, candidates):
            return {'alpha':0.61999, 'beta':0.62}[query]
    r = question_concepts_summary(answer_text='A paraphrased explanation.', question_context={},
                                 keyword_details=None, semantic_scorer=Semantic())
    assert r['matched_concepts'] == ['beta']
    assert r['missed_concepts'] == ['alpha']
    assert r['concept_match_trace'][0]['similarity'] == 0.62  # decision uses unrounded cosine
    assert r['concept_match_trace'][0]['matched'] is False


def test_offline_augmentation_preserves_explicit_then_text_order(monkeypatch):
    from scripts import build_question_concepts as builder
    row = {'skill':'Python', 'difficulty':'medium', 'question':'Explain Python.',
           'ideal_answer':'A string precedes a tuple and a list.',
           'ideal_keywords':'Python, tuple'}
    monkeypatch.setattr(builder, 'bank_rows', lambda:iter([('synthetic','v6',row)]))
    entry = builder.build()['questions']['synthetic']
    assert [c['concept'] for c in entry['concepts']] == ['Python','tuple','string','list']
    assert entry['source'] == 'ideal_keywords+ideal_answer_kg'
    assert entry['question_concepts_excluded'] == ['Python']


def test_model_loader_passes_revision(monkeypatch):
    import sentence_transformers
    from modules import semantic_scorer
    captured = {}
    model = object()
    def loader(name, **kwargs):
        captured.update(name=name, **kwargs)
        return model
    monkeypatch.setenv('DISABLE_SEMANTIC_SCORING', '0')
    monkeypatch.setattr(semantic_scorer, '_model', None)
    monkeypatch.setattr(semantic_scorer, '_model_load_error', False)
    monkeypatch.setattr(sentence_transformers, 'SentenceTransformer', loader)
    assert semantic_scorer._get_model() is model
    assert captured == {'name':SEMANTIC_MODEL_NAME, 'revision':SEMANTIC_MODEL_REVISION}


def test_bundle_alias_precedence_over_keyword_hit_and_supplement():
    r = question_concepts_summary(answer_text='A higher priority unknown proposition.',
        question_context={'bundle_content':{'question':'Discuss gamma.', 'required_concepts':[
            {'id':'alpha','aliases':['first term']}, {'id':'gamma'}]},
            'ideal_keywords':'first term, beta'},
        keyword_details={'matches':[{'keyword':'first term','covered':True,'exact':True},
                                    {'keyword':'beta','covered':True,'exact':True}]})
    assert r['matched_concepts'] == ['beta']
    assert r['missed_concepts'] == ['alpha']
    assert r['question_concepts_excluded'] == ['gamma']
    assert [t['source'] for t in r['concept_match_trace']] == ['bundle_v2','ideal_keywords']


@pytest.mark.parametrize('similarity, binary, status', [
    (0.29999,False,'missed'), (0.30,False,'uncertain'),
    (0.3009,False,'uncertain'), (0.3015,False,'uncertain'),
    (0.6107,False,'uncertain'), (0.61999,False,'uncertain'),
    (0.62,True,'uncertain'), (0.6212,True,'uncertain'),
    (0.6665,True,'uncertain'), (0.7048,True,'uncertain'),
    (0.71999,True,'uncertain'), (0.72,True,'matched'),
])
def test_three_state_is_additive_to_unchanged_062(monkeypatch, similarity, binary, status):
    from modules import question_concepts as module
    entry = {'source':'ideal_answer_kg','concepts':[
        {'concept':'concept', 'source':'ideal_answer_kg', 'order':0, 'aliases':['concept']}]}
    monkeypatch.setattr(module, 'lookup', lambda ctx:(entry,'indexed'))
    class Semantic:
        def max_similarity(self, query, candidates):
            return similarity
    result = question_concepts_summary(answer_text='An explanation.', question_context={},
                                      keyword_details=None, semantic_scorer=Semantic())
    trace = result['concept_match_trace'][0]
    assert trace['threshold'] == module.TIER3_SIMILARITY_THRESHOLD == 0.62
    assert trace['matched'] is binary
    assert trace['status'] == status
    assert result['concept_statuses'][status] == ['concept']
    assert result['matched_concepts'] == (['concept'] if binary else [])
    assert result['missed_concepts'] == ([] if binary else ['concept'])


@pytest.mark.parametrize('method,matched,sim,literal,empty,status', [
    ('exact',True,None,True,False,'matched'),
    ('alias',True,None,True,False,'matched'),
    ('exact',True,None,False,False,'uncertain'),
    ('semantic',True,.72,False,False,'matched'),
    ('not_matched',False,.72,False,False,'uncertain'),
    ('not_matched',False,None,False,False,'uncertain'),
    ('not_matched',False,None,False,True,'missed'),
])
def test_keyword_three_state_handles_unavailable_and_rounded_evidence(method,matched,sim,literal,empty,status):
    from modules.question_concepts import _concept_status
    result,_ = _concept_status(source='ideal_keywords',method=method,matched=matched,
        similarity=sim,literal_evidence=literal,empty_answer=empty)
    assert result==status


@pytest.mark.parametrize('method,status', [('supported','matched'), ('contradicted','missed'),
    ('not_demonstrated','missed'), ('uncertain','uncertain')])
def test_bundle_three_state_keeps_evaluator_authoritative(method,status):
    from modules.question_concepts import _concept_status
    result,_ = _concept_status(source='bundle_v2',method=method,matched=method=='supported',
        similarity=.99,literal_evidence=True,empty_answer=False)
    assert result==status
