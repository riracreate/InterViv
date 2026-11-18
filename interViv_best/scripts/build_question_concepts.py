"""Offline, deterministic rubric index builder. Never called by the server.

Run .venv/bin/python scripts/build_question_concepts.py [--check].
The artifact contains raw ordered concepts and separate prompt exclusions;
frequency filtering is a read-only audit/proposed policy rule, not score credit.
"""
from __future__ import annotations
import argparse
import csv
import hashlib
import json
import sys
from pathlib import Path
import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from modules.knowledge_graph import KnowledgeGraphScorer
from modules.ner_scorer import NERScorer
from modules.question_concepts import (INDEX_PATH, aliases_for, canonical, explicit_entries,
    first_offset, keyword_list, question_id, rubric_hash)


def bank_rows():
    for source, name in [('v6','interview_dataset_v6.csv'), ('fallback','fallback_question_bank.csv')]:
        seen = set()
        for row in csv.DictReader((ROOT/'data'/name).open(newline='')):
            qid = question_id(row['skill'], row['question'], source)
            if qid in seen:
                continue
            seen.add(qid)
            yield qid, source, row
    for path in sorted((ROOT/'data/question_bundles').rglob('*.yaml')):
        for row in yaml.safe_load(path.read_text()):
            yield f"bundle:{row['bundle_id']}:v{row['version']}", 'bundle', row


def build():
    kg, ner = KnowledgeGraphScorer(), NERScorer()
    questions = {}
    for qid, bank_source, row in bank_rows():
        question = row['question']
        ideal = row.get('ideal_answer') or row.get('reference_answer') or ''
        required = row.get('required_concepts') or []
        if required:
            concepts = explicit_entries(required, 'bundle_v2')
            source = 'bundle_v2'
        else:
            concepts = explicit_entries(keyword_list(row.get('ideal_keywords') or row.get('keywords')), 'ideal_keywords')
            non_prompt = [c for c in concepts if first_offset(question, c['aliases']) is None]
            if len(non_prompt) < 2:
                graph = kg.graphs.get(row['skill'])
                skill_nodes = set(graph.nodes()) if graph is not None else set()
                extracted = (kg._find_nodes(ideal) & skill_nodes) | set(ner.extract_entities(ideal))
                seen = {canonical(c['concept']) for c in concepts}
                extra = []
                for concept in sorted(extracted):
                    key = canonical(concept)
                    surfaces = aliases_for(concept)
                    offset = first_offset(ideal, surfaces)
                    # Reject substring-only KG/stem hits that have no token evidence.
                    if key in seen or offset is None:
                        continue
                    seen.add(key)
                    extra.append({'concept':concept.replace('_',' '), 'source':'ideal_answer_kg',
                                  'aliases':surfaces, 'ideal_answer_offset':offset})
                extra.sort(key=lambda c:(c['ideal_answer_offset'], canonical(c['concept'])))
                concepts.extend(extra)
            sources = {c['source'] for c in concepts}
            source = ('ideal_keywords+ideal_answer_kg' if len(sources) > 1 else
                      next(iter(sources)) if sources else 'ideal_answer_kg')
        for order, c in enumerate(concepts):
            c['order'] = order
        excluded = [c['concept'] for c in concepts if first_offset(question, c['aliases']) is not None]
        questions[qid] = {'question_id':qid, 'skill':row['skill'], 'difficulty':row['difficulty'].lower(),
                          'bank_source':bank_source, 'question':question, 'source':source,
                          'rubric_hash':rubric_hash(row), 'concepts':concepts,
                          'question_concepts_excluded':excluded,
                          'review_status':'external_db_required_draft_in_source' if bank_source == 'bundle' else 'automatic_extraction'}
    paths = [ROOT/'data/interview_dataset_v6.csv', ROOT/'data/fallback_question_bank.csv',
             *sorted((ROOT/'data/question_bundles').rglob('*.yaml')),
             ROOT/'modules/knowledge_graph.py', ROOT/'modules/ner_scorer.py',
             ROOT/'modules/question_concepts.py', ROOT/'modules/nlp_scorer.py', Path(__file__).resolve()]
    return {'schema_version':1, 'builder':'scripts/build_question_concepts.py',
            'source_sha256':{str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths},
            'ordering':'explicit rubric order; augment only below two non-prompt keywords; then first ideal-answer token offset',
            'questions':questions}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    rendered = json.dumps(build(), indent=2, ensure_ascii=False, allow_nan=False)+'\n'
    if args.check:
        if not INDEX_PATH.exists() or INDEX_PATH.read_text() != rendered:
            raise SystemExit('Concept index is stale; rebuild offline and review the diff.')
        print('Concept index is reproducible and current.')
    else:
        INDEX_PATH.write_text(rendered)
        print(f'Wrote {INDEX_PATH}')

if __name__ == '__main__':
    main()
