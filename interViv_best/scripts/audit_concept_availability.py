"""Read-only availability bounds from saved scoring traces; no probe selection."""
from collections import Counter, defaultdict
import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from modules.question_concepts import canonical


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--embeddings', required=True)
    args = parser.parse_args()
    import numpy as np
    cached = np.load(args.embeddings)
    vectors = dict(zip(cached['ids'].tolist(), cached['vectors']))
    out = ROOT / 'data/audits/concept_review'
    index = json.loads((ROOT / 'data/question_concepts_v1.json').read_text())['questions']
    summary = json.loads((out / 'full_replay_summary.json').read_text())
    target_questions = defaultdict(set)
    for q in index.values():
        if q['bank_source'] == 'v6':
            for concept in q['concepts']:
                target_questions[q['skill'], canonical(concept['concept'])].add(q['question_id'])
    counts = defaultdict(Counter)
    opportunities = []
    for line in (out / 'all_rows.jsonl').open():
        row = json.loads(line)
        if row['band'] != 'vague':
            continue
        counts[row['skill']]['vague'] += 1
        generic = summary['generic_filter_metrics'][row['skill']]['filtered_generic_concepts']
        surviving = [t for t in row['concept_trace'] if t['status'] == 'missed' and
                     (t['source'] != 'ideal_answer_kg' or canonical(t['concept']) not in generic)]
        candidates = {}
        for t in surviving:
            others = target_questions[row['skill'], canonical(t['concept'])] - {row['question_id']}
            eligible = sorted(qid for qid in others if float(vectors[qid] @ vectors[row['question_id']]) < .85)
            if eligible:
                candidates[t['concept']] = eligible
        if candidates:
            counts[row['skill']]['with_other_question_after_dedup'] += 1
            counts[row['skill']]['hr_disabled'] += row['skill'] != 'HR'
            opportunities.append({'row_index': row['row_index'], 'skill': row['skill'],
                                  'question_id': row['question_id'], 'concept_to_question_ids': candidates})
    payload = {'definition': 'Include a target in the other question’s offline rubric even when that question names it and excludes it from credit. Only current question seen; primary bank; cosine >=0.85 duplicates excluded; no actual session caps/history. This is availability, not a probe implementation.',
               'by_skill': dict(counts), 'opportunities': opportunities,
               'total_with_other_question': sum(c['with_other_question_after_dedup'] for c in counts.values()),
               'total_hr_disabled': sum(c['hr_disabled'] for c in counts.values())}
    (out / 'prompt_inclusive_availability.json').write_text(json.dumps(payload, indent=2) + '\n')
    print(json.dumps({'by_skill': payload['by_skill'], 'total': payload['total_with_other_question'],
                      'hr_disabled': payload['total_hr_disabled']}))


if __name__ == '__main__':
    main()
