"""Stage (a) invariants only: no production session wiring or concept probes."""
from dataclasses import replace
import itertools
import random
import pytest

from backend.config import SEMANTIC_MODEL_REVISION, POLICY_NEUTRAL_ELO
from modules.answer_bands import classify_answer_band, ANSWER_BANDS
from modules.adaptive_skill_graph import CANONICAL_SKILLS, bridge_coverage, prerequisites
from modules.adaptive_policy import (Question,QuestionBank,SkillProfile,PolicyState,Attempt,
    make_state,next_adaptive_move,record_outcome,expected_score,update_observed_elo,
    observed_ratings,BankExhausted)


def bank_for(skills=CANONICAL_SKILLS, difficulties=('easy','medium','hard'), per_level=3):
    questions=tuple(Question(f'{s}:{d}:{i}',s,f'{s} task {d} item {i}',d)
        for s in skills for d in difficulties for i in range(per_level))
    sims={tuple(sorted((a.id,b.id))):0.1 for a,b in itertools.combinations(questions,2) if a.skill==b.skill}
    return QuestionBank.from_similarities(questions,sims,model_revision=SEMANTIC_MODEL_REVISION)


@pytest.fixture(scope='module')
def bank():return bank_for()


def profiles(skills=CANONICAL_SKILLS):
    return tuple(SkillProfile(s,'claimed_evidenced',len(skills)-i) for i,s in enumerate(skills))


def classify(**kwargs):
    args=dict(final_score=65,rubric={'correctness':7,'depth':4.5},svm_label='Average',
              guard_type=None,word_count=15,answer_text='A meaningful candidate answer.',missed_concepts=[])
    args.update(kwargs);return classify_answer_band(**args)


@pytest.mark.parametrize('args,expected', [
    ({'answer_text':'I do not know.'},'nonanswer'),
    ({'word_count':2,'final_score':39.99},'nonanswer'),
    ({'word_count':2,'final_score':40},'wrong'),
    ({'word_count':2,'final_score':80,'rubric':{'correctness':8,'depth':5}},'strong'),
    ({'final_score':51.99},'wrong'), ({'final_score':52},'adequate'),
    ({'final_score':80,'guard_type':'truncated_fragment'},'wrong'),
    ({'final_score':80,'guard_type':'too_short'},'nonanswer'),
    ({'final_score':80,'svm_label':'Poor'},'wrong'),
    ({'final_score':72,'rubric':{'correctness':7.5,'depth':4}},'strong'),
    ({'final_score':71.99,'missed_concepts':['x']},'vague'),
    ({'final_score':80,'rubric':{'correctness':7.49,'depth':4.19},'missed_concepts':['x']},'vague'),
    ({'final_score':80,'rubric':{'correctness':7.49,'depth':4.2},'missed_concepts':['x']},'adequate'),
])
def test_band_boundaries_and_precedence(args,expected):assert classify(**args)==expected


def test_band_partition_is_total_for_finite_inputs():
    rng=random.Random(11)
    for _ in range(1000):
        assert classify(final_score=rng.uniform(-10,110),rubric={'correctness':rng.uniform(0,10),'depth':rng.uniform(0,10)},
                        missed_concepts=['x'] if rng.random()<.5 else []) in ANSWER_BANDS
    with pytest.raises(ValueError):classify(final_score=float('nan'))


def test_directional_bridge_coverage():
    c=bridge_coverage()
    assert (c['down'],c['up'],c['across'],c['up_or_across'],c['denominator'])==(3,5,8,9,11)
    assert {s for s in CANONICAL_SKILLS if prerequisites(s)}=={'ML','CN','System Design'}
    assert prerequisites('DSA')==()
    assert c['skills']['HR']=={'down':[],'up':[],'across':[]}


def test_elo_reanchoring_and_evidence_only():
    assert expected_score(1200,'medium')==.5
    assert expected_score(1200,'easy')>.5>expected_score(1200,'hard')
    assert update_observed_elo(1200,'medium',50)==1200
    assert update_observed_elo(1200,'medium',100)==1216
    assert update_observed_elo(1200,'hard',80)>update_observed_elo(1200,'easy',80)
    assert all(v==POLICY_NEUTRAL_ELO for v in observed_ratings(make_state(profiles())).values())


def test_alias_profiles_do_not_multiply_weights():
    s=make_state([{'skill':'SQL','evidence_tier':'claimed_keyword_only','role_weight':2},
                  {'skill':'DBMS','evidence_tier':'claimed_evidenced','role_weight':3}])
    assert s.profiles==(SkillProfile('DBMS','claimed_evidenced',3),)


def test_concept_flag_cannot_enable_unimplemented_feature():
    with pytest.raises(NotImplementedError):replace(make_state(profiles()),concept_probing_enabled=True)


def replay(state,bank,bands):
    moves=[]
    for band in bands:
        before=random.getstate()
        decision=next_adaptive_move(state,bank)
        assert random.getstate()==before
        moves.append(decision)
        state=record_outcome(state,decision,band=band,score=80 if band=='strong' else 20 if band in {'wrong','nonanswer'} else 65)
    return state,tuple(moves)


def test_100_seed_profile_budget_coverage_dedup_and_replay(bank):
    for seed in range(100):
        rng=random.Random(seed);skills=rng.sample(list(CANONICAL_SKILLS),rng.randint(5,11));budget=rng.randint(8,12)
        ps=tuple(SkillProfile(s,'role_gap' if i==len(skills)-1 else 'claimed_keyword_only' if i%2 else 'claimed_evidenced',rng.random()) for i,s in enumerate(skills))
        initial=make_state(ps,total_questions=budget,seed=seed)
        bands=[rng.choice(sorted(ANSWER_BANDS)) for _ in range(budget)]
        final,moves=replay(initial,bank,bands)
        assert final.remaining==0 and not final.uncovered
        assert len(initial.must_cover)<=int(.6*budget)
        ids=[m.question.id for m in moves]
        assert len(ids)==len(set(ids))
        assert not any(tuple(sorted(pair)) in bank.duplicate_pairs for pair in itertools.combinations(ids,2))
        for i,m in enumerate(moves[1:],1):
            prev=final.history[i-1]
            if prev.band=='nonanswer' or next(p for p in initial.profiles if p.skill==prev.skill).evidence_tier=='role_gap':
                assert m.move!='PROBE_HARDER'
        for p in initial.profiles:
            count=sum(a.skill==p.skill for a in final.history)
            assert count<=(1 if p.evidence_tier=='role_gap' else 3)
        assert next_adaptive_move(final,bank).move=='END'
        assert replay(initial,bank,bands)==(final,moves)


def test_budget_invariant_forces_cover(bank):
    history=tuple(Attempt(f'{s}:easy:{i}',s,'easy','COVER','strong',80) for s,i in [('Python',0),('Python',1),('DBMS',0),('DBMS',1),('DSA',0)])
    state=PolicyState(profiles(),('CN','OOP','OS'),8,history=history)
    move=next_adaptive_move(state,bank)
    assert move.move=='COVER' and move.question.skill in state.uncovered
    assert move.reason_code=='BUDGET_INVARIANT_FORCED_COVER'


@pytest.mark.parametrize('skill',['DSA','DBMS','OS','Python'])
def test_wrong_without_prerequisite_goes_to_cover(bank,skill):
    state=replace(make_state(profiles(),seed=6),history=(Attempt(f'{skill}:medium:0',skill,'medium','COVER','wrong',20),))
    m=next_adaptive_move(state,bank)
    assert m.move=='COVER' and 'no_eligible_prerequisite' in m.fallback_reasons


def test_harder_skip_up_and_fallback_are_explicit(bank):
    # Easy→Hard is allowed when Medium is absent, and records relaxation.
    trimmed=tuple(q for q in bank.questions if q.skill!='Python' or q.difficulty!='medium')
    sims={tuple(sorted((a.id,b.id))):.1 for a,b in itertools.combinations(trimmed,2) if a.skill==b.skill}
    sparse=QuestionBank.from_similarities(trimmed,sims,model_revision=SEMANTIC_MODEL_REVISION)
    state=replace(make_state(profiles()),history=(Attempt('Python:easy:0','Python','easy','COVER','strong',80),))
    move=next_adaptive_move(state,sparse)
    assert move.move=='PROBE_HARDER' and move.question.difficulty=='hard' and move.difficulty_relaxed
    assert 'difficulty_relaxed' in move.fallback_reasons
    terminal=replace(state,history=(Attempt('Python:hard:0','Python','hard','COVER','strong',80),))
    move=next_adaptive_move(terminal,sparse)
    assert move.move in {'BRIDGE','COVER'} and 'already_at_max_difficulty' in move.fallback_reasons


def test_cover_relaxes_difficulty_without_mislabeling_harder():
    bank=bank_for(difficulties=('easy',))
    move=next_adaptive_move(make_state(profiles()),bank)
    assert move.move=='COVER' and move.requested_difficulty=='medium' and move.question.difficulty=='easy'
    assert move.difficulty_relaxed


def test_semantic_dedup_boundary_and_complete_table():
    qs=(Question('a','Python','different alpha','easy'),Question('b','Python','different beta','easy'))
    with pytest.raises(ValueError,match='Incomplete'):QuestionBank.from_similarities(qs,{},model_revision=SEMANTIC_MODEL_REVISION)
    bank=QuestionBank.from_similarities(qs,{('a','b'):.85},model_revision=SEMANTIC_MODEL_REVISION)
    assert bank.conflicts('a',['b'])
    bank=QuestionBank.from_similarities(qs,{('a','b'):.84999},model_revision=SEMANTIC_MODEL_REVISION)
    assert not bank.conflicts('a',['b'])
    with pytest.raises(ValueError,match='revision'):QuestionBank.from_similarities(qs,{('a','b'):.1},model_revision='wrong')


def test_infeasible_bank_never_relaxes_repeats():
    bank=bank_for(skills=('Python','DBMS'),difficulties=('easy',),per_level=1)
    with pytest.raises(BankExhausted):next_adaptive_move(make_state(profiles(('Python','DBMS')),total_questions=8),bank)


def test_lexical_fallback_and_cross_skill_exact_duplicate():
    qs=(Question('a','Python','Explain alpha beta gamma','easy'),Question('b','DBMS','Explain alpha beta gamma','easy'),Question('c','Python','What is alpha beta gamma','medium'))
    bank=QuestionBank.lexical_fallback(qs)
    assert bank.conflicts('a',['b']) and bank.conflicts('a',['c'])


def test_unreviewed_bundles_are_ineligible_and_history_is_unique(bank):
    from modules.adaptive_policy import _available
    draft = Question('draft','Python','draft question','medium',source='bundle')
    approved = replace(draft,id='approved',bundle_reviewed=True)
    expanded = QuestionBank(bank.questions+(draft,approved),bank.duplicate_pairs,bank.dedup_mode)
    state = make_state(profiles())
    available = _available(state,expanded)
    assert draft not in available and approved in available
    attempt = Attempt('a','Python','easy','COVER','strong',80)
    with pytest.raises(ValueError,match='Repeated history'):
        replace(state,history=(attempt,attempt))
