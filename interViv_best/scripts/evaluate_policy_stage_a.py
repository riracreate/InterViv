"""Offline policy mechanics evaluation; never imports or changes session wiring.

Uses the same bank, answer rows and difficulty labels as calibration. Outcomes
are replayed answers selected by an explicit synthetic ability model, not new
human observations. Results are not an independent effectiveness estimate.
"""
from collections import Counter, defaultdict
from dataclasses import asdict
import argparse
import hashlib
import itertools
import json
from pathlib import Path
import random
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from backend.config import SEMANTIC_MODEL_REVISION
from modules.adaptive_policy import (
    Question, QuestionBank, SkillProfile, make_state, next_adaptive_move,
    record_outcome, expected_score, observed_ratings, DIFFICULTIES,
)
from modules.adaptive_skill_graph import CANONICAL_SKILLS, bridge_coverage
from scripts.audit_question_concepts import expected


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--embeddings', required=True)
    parser.add_argument('--output-dir', required=True)
    args = parser.parse_args()
    import numpy as np
    cached = np.load(args.embeddings)
    vectors = dict(zip(cached['ids'].tolist(), cached['vectors']))
    index = json.loads((ROOT / 'data/question_concepts_v1.json').read_text())['questions']
    questions = tuple(Question(q['question_id'], q['skill'], q['question'], q['difficulty'].lower(),
                               q['bank_source'], frozenset(expected(q)))
                      for q in index.values() if q['bank_source'] == 'v6')
    similarities = {tuple(sorted((a.id, b.id))): float(np.clip(vectors[a.id] @ vectors[b.id], -1, 1))
                    for a, b in itertools.combinations(questions, 2) if a.skill == b.skill}
    bank = QuestionBank.from_similarities(questions, similarities, model_revision=SEMANTIC_MODEL_REVISION)
    rows = [json.loads(line) for line in (ROOT / 'data/audits/concept_review/all_rows.jsonl').open()]
    outcomes = defaultdict(dict)
    for row in rows:
        outcomes[row['question_id']][row['label']] = row
    assert all(set(outcomes[q.id]) == {'Good', 'Average', 'Poor'} for q in questions)

    out = Path(args.output_dir)
    out.mkdir(parents=True, exist_ok=True)
    counts = Counter()
    per_skill = defaultdict(Counter)
    sessions = []
    with (out / 'simulation_moves.jsonl').open('w') as stream:
        for seed in range(100):
            rng = random.Random(seed)
            mode = ('strong', 'mixed', 'weak')[seed % 3]
            skills = rng.sample(list(CANONICAL_SKILLS), len(CANONICAL_SKILLS))
            profiles = tuple(SkillProfile(s, 'role_gap' if i == 10 else
                'claimed_keyword_only' if i % 3 == 2 else 'claimed_evidenced', 11-i)
                for i, s in enumerate(skills))
            state = make_state(profiles, total_questions=8+seed % 5, seed=seed)
            must_cover = state.must_cover
            for round_index in range(state.total_questions):
                previous = state.history[-1] if state.history else None
                decision = next_adaptive_move(state, bank)
                q = decision.question
                counts['moves'] += 1
                counts[decision.move] += 1
                per_skill[q.skill]['selected'] += 1
                if decision.difficulty_relaxed:
                    counts['difficulty_relaxations'] += 1
                    per_skill[q.skill]['difficulty_relaxations'] += 1
                attempted_harder = decision.move == 'PROBE_HARDER' or any(reason in decision.fallback_reasons
                    for reason in ('no_unseen_harder_question', 'already_at_max_difficulty'))
                if attempted_harder:
                    counts['harder_attempts'] += 1
                    per_skill[previous.skill]['harder_attempts'] += 1
                    key = 'harder_selected' if decision.move == 'PROBE_HARDER' else 'harder_fallbacks'
                    counts[key] += 1
                    per_skill[previous.skill][key] += 1
                for reason in decision.fallback_reasons:
                    counts['fallback:' + reason] += 1
                if decision.bridge_direction:
                    counts['bridge:' + decision.bridge_direction] += 1
                # Same heuristic labels/model as calibration, no invented scores:
                # choose an existing Good/Average/Poor answer, then use its replay.
                tier = next(p.evidence_tier for p in state.profiles if p.skill == q.skill)
                ability = {'strong': .9, 'mixed': .6, 'weak': .3}[mode]
                ability += {'claimed_evidenced': .1, 'claimed_keyword_only': -.1, 'role_gap': -.2}[tier]
                margin = ability - {'easy': .25, 'medium': .5, 'hard': .75}[q.difficulty] + rng.uniform(-.25, .25)
                label = 'Good' if margin > .15 else 'Poor' if margin < -.15 else 'Average'
                answer = outcomes[q.id][label]
                demonstrated = [t['concept'] for t in answer['concept_trace'] if t['status'] == 'matched']
                state = record_outcome(state, decision, band=answer['band'], score=answer['final_score'],
                                       demonstrated=demonstrated)
                record = {'seed': seed, 'profile': mode, 'round': round_index+1,
                          'decision': asdict(decision), 'answer_row_index': answer['row_index'],
                          'observed_band': answer['band'], 'observed_score': answer['final_score']}
                record['decision']['question']['concepts'] = sorted(q.concepts)
                stream.write(json.dumps(record, separators=(',', ':')) + '\n')
            ids = [a.question_id for a in state.history]
            assert len(ids) == len(set(ids))
            assert not any(bank.conflicts(a, [b]) for a, b in itertools.combinations(ids, 2))
            assert not state.uncovered and state.remaining == 0
            assert all(sum(a.skill == p.skill for a in state.history) <=
                       (1 if p.evidence_tier == 'role_gap' else 3) for p in profiles)
            assert next_adaptive_move(state, bank).move == 'END'
            sessions.append({'seed': seed, 'profile': mode, 'must_cover': must_cover,
                             'covered': sorted({a.skill for a in state.history}),
                             'observed_elo': observed_ratings(state)})
            if seed % 10 == 0:
                print('SIMULATION', seed+1, '/100', flush=True)
    cold = {}
    for skill in CANONICAL_SKILLS:
        pool = [q for q in questions if q.skill == skill]
        unavailable = sum(not any(DIFFICULTIES.index(other.difficulty) > DIFFICULTIES.index(q.difficulty)
                          and not bank.conflicts(other.id, [q.id]) for other in pool) for q in pool)
        cold[skill] = {'questions': len(pool), 'difficulty_counts': dict(Counter(q.difficulty for q in pool)),
                       'no_higher_after_current_and_near_dedup': unavailable}
    summary = {
        'protocol': '100 seeds, budgets 8–12; 34 strong/33 mixed/33 weak synthetic profiles. Primary bank only, all 11 canonical buckets. Same data and difficulty model as calibration; not independent validation or production firing rates.',
        'counts': dict(counts), 'per_skill': dict(per_skill), 'sessions': sessions,
        'cold_bank': cold, 'bridge_coverage': bridge_coverage(),
        'complete_sessions': 100, 'must_cover_fully_covered': 100,
        'question_repeats': 0, 'near_duplicates': 0, 'concept_probes': 0,
        'difficulty_relaxation_rate': counts['difficulty_relaxations'] / counts['moves'],
        'harder_fallback_rate': counts['harder_fallbacks'] / counts['harder_attempts'],
        'neutral_expected_scores': {d: expected_score(1200, d) for d in DIFFICULTIES},
        'model_revision': SEMANTIC_MODEL_REVISION,
        'source_sha256': {name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest() for name in
            ('modules/adaptive_policy.py', 'modules/adaptive_skill_graph.py', 'modules/answer_bands.py',
             'backend/config.py', 'data/question_concepts_v1.json', 'data/audits/concept_review/all_rows.jsonl')},
    }
    (out / 'simulation_summary.json').write_text(json.dumps(summary, indent=2) + '\n')
    print(json.dumps(dict(counts)), flush=True)


if __name__ == '__main__':
    main()
