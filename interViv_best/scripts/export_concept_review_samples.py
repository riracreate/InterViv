"""Read-only blind export and deterministic stratified sampling; no labels generated."""
from collections import Counter
import csv
import hashlib
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'data/audits/concept_review'
TIER={'bundle_v2':1,'ideal_keywords':2,'ideal_answer_kg':3}


def main():
    prior=json.loads((ROOT/'data/audits/step1_concept_handcheck.json').read_text())
    blind=[{'pair_id':f'R{i:02d}','question':p['question'],'concept':p['concept'],'tier':TIER[p['source']],
            'answer_excerpt':p['answer'],'similarity':p['similarity']}
           for i,p in enumerate(prior['pairs'],1)]
    (OUT/'blind_20_pairs.json').write_text(json.dumps(blind,indent=2,ensure_ascii=False)+'\n')
    md=['# Twenty pairs for independent labeling','', 'No assistant labels are included. Answer excerpts retain the complete supplied answer to avoid removing relevant evidence. Similarity is a model diagnostic, not a correctness probability.','']
    for p in blind:
        md += [f"## {p['pair_id']}: {p['concept']} (Tier {p['tier']})",'',f"**Question:** {p['question']}",'',f"**Answer excerpt:** {p['answer_excerpt']}",'',f"**Similarity:** {p['similarity']}",'','**Your label:**','', '**Your notes:**','']
    (OUT/'blind_20_pairs.md').write_text('\n'.join(md))
    rows=list(csv.DictReader((ROOT/'data/interview_dataset_v6.csv').open(newline='')))
    pools={name:[] for name in ('tier2_exact_alias','tier2_semantic_ge072','tier3_exact_alias','tier3_semantic_062_072','tier3_semantic_ge072')}
    for line in (OUT/'all_rows.jsonl').open():
        r=json.loads(line); row=rows[r['row_index']-1]
        for t in r['concept_trace']:
            if not t['matched']:continue
            tier=TIER[t['source']];method=t['method'];sim=t['similarity']
            if method in {'exact','alias'}:stratum=f'tier{tier}_exact_alias'
            elif method=='semantic' and sim is not None:
                stratum=f'tier{tier}_semantic_'+('062_072' if sim<.72 else 'ge072')
            else:continue
            if stratum not in pools:continue
            pair_id=f"row{r['row_index']}:{t['order']}"
            pools[stratum].append({'candidate_id':pair_id,'row_index':r['row_index'],'question':row['question'],
                'skill':row['skill'],'answer':row['answer'],'ideal_answer':row['ideal_answer'],
                'concept':t['concept'],'tier':tier,'similarity':sim,'method':method,'status':t['status'],'stratum':stratum})
    allocations={'tier2_exact_alias':6,'tier2_semantic_ge072':4,'tier3_exact_alias':4,'tier3_semantic_062_072':3,'tier3_semantic_ge072':3}
    selected=[]
    for stratum,n in allocations.items():
        pool=sorted(pools[stratum],key=lambda p:hashlib.sha256(('review-seed-20261104:'+p['candidate_id']).encode()).hexdigest())
        assert len(pool)>=n,(stratum,len(pool))
        selected+=pool[:n]
    for i,p in enumerate(selected,1):p['pair_id']=f'M{i:02d}'
    payload={'selection':'Fixed seed SHA-256 order, sampled without replacement within binary-match strata before manual labeling.',
        'stratum_population':{s:len(v) for s,v in pools.items()},'allocation':allocations,
        'tier1_empty_stratum':'All 12 bundle references and all 60 authored calibration answers produce zero post-prompt Tier-1 matches; audited separately rather than fabricating Tier-1 samples.',
        'pairs':selected}
    (OUT/'matched_20_sample.json').write_text(json.dumps(payload,indent=2,ensure_ascii=False)+'\n')
    print('SAMPLE POOLS',payload['stratum_population'])
    for p in selected:
        print('\n',p['pair_id'],p['tier'],p['stratum'],p['concept'],p['similarity'],p['status'])
        print('Q:',p['question']);print('A:',p['answer'])

if __name__=='__main__':main()
