"""Read-only full-bank replay and bundle audit. Writes only audit artifacts.

Use --output-dir to choose artifact destination. Never updates banks, labels,
thresholds, scored sessions, or the committed golden snapshot.
"""
from __future__ import annotations
import argparse
from collections import Counter, defaultdict
import csv
import hashlib
import json
import os
from pathlib import Path
import statistics
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
os.environ.update(HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1',DISABLE_SEMANTIC_SCORING='0',
                  LENGTH_RATIO_MULTIPLIER_ENABLED='0',LLM_LIVE_FETCH='0',JOBS_LIVE_FETCH='0')
from backend.scoring.pipeline import run_scoring_pipeline
from modules.answer_bands import classify_answer_band
from modules.question_concepts import canonical, load_index, question_concepts_summary, question_id
from scripts.audit_question_concepts import bank_stats, expected


def json_bytes(value):
    return len(json.dumps(value,ensure_ascii=False,separators=(',',':')).encode())


def describe(values):
    values=sorted(values)
    return {'n':len(values),'mean':round(statistics.mean(values),2),'median':statistics.median(values),
            'p95_nearest_rank':values[max(0,__import__('math').ceil(.95*len(values))-1)],'min':values[0],'max':values[-1]}


def main():
    p=argparse.ArgumentParser();p.add_argument('--output-dir',required=True);args=p.parse_args()
    out=Path(args.output_dir);out.mkdir(parents=True,exist_ok=True)
    index=load_index()['questions']; primary=[q for q in index.values() if q['bank_source']=='v6']
    stats=bank_stats(primary)
    target_questions=defaultdict(set)
    for q in primary:
        for concept in expected(q):target_questions[(q['skill'],concept)].add(q['question_id'])
    # Same pinned model, all primary/fallback questions, no network or mutation.
    from modules.semantic_scorer import _get_model
    import numpy as np
    model=_get_model();assert model is not None
    revision=model[0].auto_model.config._commit_hash
    questions=[q for q in index.values() if q['bank_source'] in {'v6','fallback'}]
    vectors=model.encode([q['question'] for q in questions],convert_to_numpy=True,normalize_embeddings=True,show_progress_bar=False)
    np.savez_compressed('/private/tmp/interviv_stage_a_embeddings.npz',ids=np.array([q['question_id'] for q in questions]),vectors=vectors)
    positions={q['question_id']:i for i,q in enumerate(questions)}
    def near(a,b):return float(vectors[positions[a]] @ vectors[positions[b]])>=.85
    rows=list(csv.DictReader((ROOT/'data/interview_dataset_v6.csv').open(newline='')))
    band_counts=Counter(); by_skill=defaultdict(Counter); by_label=defaultdict(Counter)
    traces=[]; trace_bytes=[]; all_bytes=[]
    with (out/'all_rows.jsonl').open('w') as f:
        for i,row in enumerate(rows,1):
            context={k:row.get(k,'') for k in ('question','skill','sub_domain','ideal_answer','ideal_keywords')}
            r=run_scoring_pipeline(answer_text=row['answer'],difficulty=row['difficulty'],question_context=context)
            b=r['scoring_breakdown'];c=r['concepts'];trace=c['concept_match_trace']
            band=classify_answer_band(final_score=r['final_score'],rubric=r['rubric'],svm_label=r['svm_label'],
                guard_type=r['guard_applied'],word_count=b['server_word_count'],answer_text=row['answer'],missed_concepts=c['missed_concepts'])
            qid=question_id(row['skill'],row['question']); eligible=[]; raw_eligible=[]
            confident=[t for t in trace if t['status']=='missed']
            surviving=[t for t in confident if t['source']!='ideal_answer_kg' or canonical(t['concept']) not in stats[row['skill']]['filtered_generic_concepts']]
            for t in surviving:
                other=target_questions[(row['skill'],canonical(t['concept']))]-{qid}
                if other:raw_eligible.append(t['concept'])
                if any(not near(qid,other_id) for other_id in other):eligible.append(t['concept'])
            counts=by_skill[row['skill']];counts['rows']+=1;counts[band]+=1;band_counts[band]+=1;by_label[row['label']][band]+=1
            if band=='vague':
                counts['vague_with_confident_miss']+=bool(confident)
                counts['vague_with_filter_survivor']+=bool(surviving)
                counts['vague_with_unseen_target_raw']+=bool(raw_eligible)
                counts['vague_with_unseen_target_deduped']+=bool(eligible)
                counts['vague_policy_eligible_hr_disabled']+=bool(eligible) and row['skill']!='HR'
            # One stored field plus its key/comma. Round snapshot stores a second copy.
            without=dict(c);without.pop('concept_match_trace')
            delta=json_bytes(c)-json_bytes(without);trace_bytes.append(delta)
            all_bytes.append(json_bytes(c)-json_bytes({k:c[k] for k in ('covered','missing')}))
            record={'row_index':i,'question_id':qid,'skill':row['skill'],'difficulty':row['difficulty'].lower(),'label':row['label'],
                    'band':band,'final_score':r['final_score'],'guard':r['guard_applied'],'rubric':r['rubric'],'svm_label':r['svm_label'],
                    'concept_trace':trace,'candidate_targets_raw':raw_eligible,'candidate_targets_after_near_dedup':eligible,
                    'trace_bytes_one_copy':delta}
            f.write(json.dumps(record,ensure_ascii=False,separators=(',',':'))+'\n')
            if i%100==0:print('REPLAY',i,'/',len(rows),flush=True)
    # Every v2 bundle: reference answer and every authored calibration answer.
    import yaml
    from modules.concept_evaluator_v2 import evaluate_answer
    bundles=[]
    for path in sorted((ROOT/'data/question_bundles').rglob('*.yaml')):
        for bundle in yaml.safe_load(path.read_text()):
            if not bundle.get('required_concepts'):continue
            examples=[{'answer':bundle['reference_answer'],'note':'reference'},*bundle.get('calibration_examples',[])]
            outcomes=[]
            for n,example in enumerate(examples):
                raw=evaluate_answer(answer_text=example['answer'],bundle_content=bundle)
                scoped=question_concepts_summary(answer_text=example['answer'],question_context=bundle,keyword_details=None)
                outcomes.append({'example_index':n,'answer':example['answer'],'author_note':example.get('note'),
                    'author_level':example.get('author_level'),'raw_evaluation':raw,'scoped_concepts':scoped})
            bundles.append({'bundle_id':bundle['bundle_id'],'question':bundle['question'],'skill':bundle['skill'],
                'required_concepts':bundle['required_concepts'],'review_status':'draft_in_source_not_human_approved','outcomes':outcomes})
    (out/'tier1_all_bundles.json').write_text(json.dumps(bundles,indent=2,ensure_ascii=False)+'\n')
    summary={'row_count':len(rows),'model_revision_loaded':revision,'bands':dict(band_counts),'bands_by_label':dict(by_label),
        'by_skill':dict(by_skill),'generic_filter_metrics':stats,
        'availability_assumption':'Only the current question is seen; another primary-bank same-skill question must retain the target after prompt exclusion. Also report exclusion of cosine >=0.85 near-duplicates. No actual session history.',
        'storage':{'trace_one_copy_compact_utf8':describe(trace_bytes),'trace_two_stored_copies_compact_utf8':describe([2*x for x in trace_bytes]),
            'all_part1_concept_fields_two_copies_compact_utf8':describe([2*x for x in all_bytes]),
            'copies':'RoundRow.scoring_breakdown_json plus attempt_snapshot_json.scoring_breakdown; JSON size only, excludes DB pages/indexes/compression.'},
        'source_sha256':{name:hashlib.sha256((ROOT/name).read_bytes()).hexdigest() for name in ['data/interview_dataset_v6.csv','data/question_concepts_v1.json','modules/answer_bands.py','backend/config.py']}}
    (out/'full_replay_summary.json').write_text(json.dumps(summary,indent=2,ensure_ascii=False)+'\n')
    print('DONE',json.dumps(summary['bands']),flush=True)
if __name__=='__main__':main()
