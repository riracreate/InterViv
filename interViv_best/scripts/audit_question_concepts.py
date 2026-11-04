"""Read-only analysis of the banks and Step-1 diagnostics; no policy applied.

Writes only requested report artifacts. Does not edit rubrics, scores, or banks.
Usage: .venv/bin/python scripts/audit_question_concepts.py --output /tmp/audit.json
"""
from __future__ import annotations
import argparse
from collections import Counter, defaultdict
import json
import math
import os
from pathlib import Path
import sys
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ.update(HF_HUB_OFFLINE='1', TRANSFORMERS_OFFLINE='1', LLM_LIVE_FETCH='0',
                  JOBS_LIVE_FETCH='0', LENGTH_RATIO_MULTIPLIER_ENABLED='0', DISABLE_SEMANTIC_SCORING='0')
from backend.scoring.pipeline import run_scoring_pipeline
from modules.question_concepts import canonical, load_index

# Explicit generic-candidate vocabulary; frequency alone is not semantic quality.
# This is a proposed selector filter, NOT a scoring change.
GENERIC_CANDIDATES = set('function python java javascript ml oop interface list string array node root edge index unique right left inner transaction query object state process thread priority lightweight situation task action result learning feedback communication static'.split())
FREQUENCY_SHARE = 0.05
MIN_DOCUMENT_FREQUENCY = 3
# Proposed bands: in-sample, copied here ONLY for reporting. No runtime policy.
BAND_WRONG_SCORE = 52.0
BAND_WRONG_CORRECTNESS = 5.0
BAND_STRONG_SCORE = 72.0
BAND_STRONG_CORRECTNESS = 7.5
BAND_VAGUE_DEPTH = 4.2
NONANSWER = {'empty','gibberish','repetition','too_short','off_topic','question_parroting','low_density'}
REFUSALS = {"i don't know",'i do not know','no idea','not sure','skip','pass'}


def band(result, answer):
    guard, score, rubric = result['guard_applied'], result['final_score'], result['rubric']
    if guard in NONANSWER or answer.strip().lower().rstrip('.!?') in REFUSALS or (len(answer.split())<8 and score<40 and guard!='truncated_fragment'):
        return 'nonanswer'
    if score<BAND_WRONG_SCORE or rubric['correctness']<BAND_WRONG_CORRECTNESS or result['svm_label']=='Poor' or guard in {'entity_swap','truncated_fragment'}:
        return 'wrong'
    if score>=BAND_STRONG_SCORE and rubric['correctness']>=BAND_STRONG_CORRECTNESS and not guard:
        return 'strong'
    if result['concepts']['missed_concepts'] and (score<BAND_STRONG_SCORE or rubric['depth']<BAND_VAGUE_DEPTH):
        return 'vague'
    return 'adequate'


def expected(q):
    return {canonical(c['concept']) for c in q['concepts'] if c['concept'] not in q['question_concepts_excluded']}


def bank_stats(questions):
    by_skill = defaultdict(list)
    for q in questions:
        by_skill[q['skill']].append(q)
    result = {}
    for skill, bank in sorted(by_skill.items()):
        counts = Counter(c for q in bank for c in expected(q))
        cut = max(MIN_DOCUMENT_FREQUENCY, math.ceil(FREQUENCY_SHARE*len(bank)))
        filtered = {c for c,n in counts.items() if c in GENERIC_CANDIDATES and n>=cut}
        before_occ = sum(counts.values())
        after_counts = {c:n for c,n in counts.items() if c not in filtered}
        dominated = sum(bool(expected(q)) and len(expected(q)&filtered)/len(expected(q))>=0.5 for q in bank)
        # Probe target may appear in the next question's prompt; it is still tracked
        # as a routing target, while the probe's band evaluates its remaining rubric.
        raw_target_counts = Counter(canonical(c['concept']) for q in bank for c in q['concepts'])
        available_before = sum(n for c,n in counts.items() if n>=2)
        available_after = sum(n for c,n in after_counts.items() if n>=2)
        difficulty = Counter(q['difficulty'] for q in bank)
        ranks = {'easy':0,'medium':1,'hard':2}
        harder_ok = sum(any(ranks.get(other['difficulty'],1)>ranks.get(q['difficulty'],1) for other in bank) for q in bank)
        next_level_missing = sum(not any(ranks.get(other['difficulty'],1)==ranks.get(q['difficulty'],1)+1 for other in bank) for q in bank if q['difficulty']!='hard')
        # Cold-bank desired difficulty requests, one request per easy/medium/hard.
        missing_levels = [d for d in ranks if difficulty[d]==0]
        result[skill] = {'questions':len(bank), 'top_30':sorted(counts.items(), key=lambda item:(-item[1], item[0]))[:30], 'filter_min_df':cut,
            'filtered_generic_concepts':sorted(filtered), 'generic_dominated_questions':dominated,
            'generic_dominated_share':round(dominated/len(bank),4),
            'generic_occurrences':sum(counts[c] for c in filtered),
            'generic_occurrence_share':round(sum(counts[c] for c in filtered)/before_occ,4) if before_occ else None,
            'empty_before':sum(not expected(q) for q in bank),
            'empty_after':sum(not (expected(q)-filtered) for q in bank),
            'occurrences_before':before_occ,'probeable_before':available_before,
            'unique_concepts_before':len(counts), 'shared_concepts_before':sum(n>=2 for n in counts.values()),
            'unique_concepts_after':len(after_counts), 'shared_concepts_after':sum(n>=2 for n in after_counts.values()),
            'questions_with_probe_after':sum(any(counts[c]>=2 for c in expected(q)-filtered) for q in bank),
            'occurrences_after':sum(after_counts.values()),'probeable_after':available_after,
            'prompt_target_inclusive_probeable_after':sum(n for c,n in after_counts.items() if raw_target_counts[c]>=2),
            'concept_probes_enabled_in_proposal':skill!='HR',
            'difficulty_counts':dict(difficulty),'harder_available_questions':harder_ok,
            'harder_fallback_questions':len(bank)-harder_ok, 'next_level_missing_nonhard':next_level_missing,
            'cold_missing_difficulty_levels':missing_levels}
    return result


def main():
    p=argparse.ArgumentParser(); p.add_argument('--output', required=True); args=p.parse_args()
    questions = list(load_index()['questions'].values())
    primary = [q for q in questions if q['bank_source']=='v6']
    combined = {}
    for q in questions:
        if q['bank_source']=='bundle': continue  # DB review status unavailable
        q = dict(q)
        q['skill'] = {'FastAPI':'Python', 'Node.js':'JavaScript', 'React':'JavaScript'}.get(q['skill'],q['skill'])
        combined.setdefault((q['skill'],q['question']),q)
    golden=json.loads((ROOT/'tests/fixtures/step1_golden_prechange.json').read_text())
    cases=[]; wrong=Counter(); bands=Counter(); by_tier=defaultdict(Counter)
    tier3=[]; potential_misses=[]
    for case in golden['cases']:
        r=run_scoring_pipeline(**case['input']); b=band(r,case['input']['answer_text'])
        ctx=case['input']['question_context']
        cases.append({'id':case['id'],'band':b,'result':r})
        if case['group']=='validation':
            bands[b]+=1; by_tier[case['label']][b]+=1
            if b=='wrong':
                wrong['guard_based' if r['guard_applied'] else 'content_signal_only']+=1
                if r['guard_applied']:wrong['guard:'+r['guard_applied']]+=1
        for t in r['concepts']['concept_match_trace']:
            item={'case_id':case['id'],'skill':ctx['skill'],'question':ctx['question'],
                  'answer':case['input']['answer_text'],'ideal_answer':ctx['ideal_answer'],
                  'label':case.get('label',case['id']),**t}
            if t['source']=='ideal_answer_kg': tier3.append(item)
            if not t['matched']: potential_misses.append(item)
        print(case['id'],flush=True)
    tier3_cosines=[x['similarity'] for x in tier3 if x['similarity'] is not None]
    result={'generic_filter':{'candidates':sorted(GENERIC_CANDIDATES),'min_df':MIN_DOCUMENT_FREQUENCY,'share':FREQUENCY_SHARE,
              'dominated_definition':'at least 50% of nonempty post-prompt concepts are in the skill frequency-qualified generic set; denominator all questions'},
            'primary':bank_stats(primary),'combined_csv':bank_stats(list(combined.values())),
            'bands':dict(bands),'bands_by_label':dict(by_tier),'wrong_basis':dict(wrong),
            'tier3':{'total':len(tier3),'exact_or_alias':sum(x['method'] in {'exact','alias'} for x in tier3),
                     'cosine_computed':len(tier3_cosines),'semantic_hits':sum(x['method']=='semantic' for x in tier3),
                     'below_062':sum(x<.62 for x in tier3_cosines),'between_060_064':sum(.60<=x<=.64 for x in tier3_cosines),
                     'between_062_072':sum(.62<=x<.72 for x in tier3_cosines)},
            'concept_statuses_by_tier':{
                source:dict(Counter(t['status'] for c in cases for t in c['result']['concepts']['concept_match_trace'] if t['source']==source))
                for source in ('bundle_v2','ideal_keywords','ideal_answer_kg')
            },
            'tier3_cosine_distribution':sorted(tier3_cosines),
            'tier3_pairs':tier3,'missed_pairs':potential_misses,'cases':cases}
    Path(args.output).write_text(json.dumps(result,indent=2,ensure_ascii=False)+'\n')
    print('Wrote',args.output,flush=True)
if __name__=='__main__':main()
