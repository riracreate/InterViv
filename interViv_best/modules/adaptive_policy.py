"""Stage (a) pure adaptive policy. Deliberately not imported by any session route.

No concept-probe implementation, model loading, network, persistence or global
RNG. Callers supply a complete verified similarity table (or explicitly choose
lexical offline fallback), bank features, profiles and observed round outcomes.
"""
from __future__ import annotations
from collections import Counter
from dataclasses import dataclass, replace
import hashlib
import itertools
import math
import re
from typing import Mapping

from backend.config import (
    POLICY_NEUTRAL_ELO, POLICY_DIFFICULTY_ELO, POLICY_ELO_K,
    SEMANTIC_MODEL_REVISION,
)
from modules.answer_bands import ANSWER_BANDS
from modules.adaptive_skill_graph import canonical_skill, prerequisites, dependents, symmetric_neighbors
from modules.follow_ups import non_follow_up_rounds

# Duplicate-detection thresholds stay local to this pure module (Step 0).
POLICY_SEMANTIC_DUPLICATE_THRESHOLD = 0.85
POLICY_LEXICAL_DUPLICATE_THRESHOLD = 0.65

DIFFICULTIES=('easy','medium','hard')
TIERS=('claimed_evidenced','claimed_keyword_only','role_gap')
_SOURCE_ORDER={'bundle':0,'v6':1,'fallback':2}
_STOP=frozenset('a an the is are was were be in on of to for and or how what why explain describe would you use it this that does do'.split())


def _tokens(text):return tuple(re.findall(r'[a-z0-9]+',text.casefold()))
def _identity(q):return ' '.join(_tokens(q.text))
def _pair(a,b):return tuple(sorted((a,b)))


@dataclass(frozen=True)
class Question:
    id: str
    skill: str
    text: str
    difficulty: str
    source: str='v6'
    concepts: frozenset[str]=frozenset()
    eligible: bool=True
    bundle_reviewed: bool=False

    def __post_init__(self):
        if self.skill!=canonical_skill(self.skill) or self.difficulty not in DIFFICULTIES:
            raise ValueError('Question needs a canonical skill and valid difficulty')
        if not self.id or not self.text.strip():raise ValueError('Question identity/text is required')
        if self.source not in _SOURCE_ORDER:raise ValueError('Unknown question source')


@dataclass(frozen=True)
class QuestionBank:
    questions: tuple[Question,...]
    duplicate_pairs: frozenset[tuple[str,str]]
    dedup_mode: str

    @classmethod
    def from_similarities(cls, questions, similarities: Mapping[tuple[str,str],float], *, model_revision: str):
        questions=tuple(questions)
        cls._validate(questions)
        if model_revision!=SEMANTIC_MODEL_REVISION:raise ValueError('Similarity model revision mismatch')
        duplicates=set()
        for a,b in itertools.combinations(questions,2):
            if _identity(a)==_identity(b):duplicates.add(_pair(a.id,b.id))
            if a.skill!=b.skill:continue
            key=_pair(a.id,b.id)
            if key not in similarities:raise ValueError(f'Incomplete similarity table: {key}')
            value=similarities[key]
            if not math.isfinite(value) or not -1<=value<=1:raise ValueError('Invalid cosine')
            if value>=POLICY_SEMANTIC_DUPLICATE_THRESHOLD:duplicates.add(key)
        return cls(questions,frozenset(duplicates),'semantic')

    @classmethod
    def lexical_fallback(cls, questions):
        questions=tuple(questions);cls._validate(questions);duplicates=set()
        for a,b in itertools.combinations(questions,2):
            same=_identity(a)==_identity(b)
            ta,tb=set(_tokens(a.text))-_STOP,set(_tokens(b.text))-_STOP
            similarity=len(ta&tb)/len(ta|tb) if ta|tb else 0.0
            if same or (a.skill==b.skill and similarity>=POLICY_LEXICAL_DUPLICATE_THRESHOLD):
                duplicates.add(_pair(a.id,b.id))
        return cls(questions,frozenset(duplicates),'lexical_explicit_fallback')

    @staticmethod
    def _validate(questions):
        if len({q.id for q in questions})!=len(questions):raise ValueError('Duplicate bank IDs')

    def conflicts(self, qid, asked):
        return any(qid==other or _pair(qid,other) in self.duplicate_pairs for other in asked)


@dataclass(frozen=True)
class SkillProfile:
    skill: str
    evidence_tier: str
    role_weight: float=1.0

    def __post_init__(self):
        if self.skill!=canonical_skill(self.skill) or self.evidence_tier not in TIERS:raise ValueError('Invalid canonical profile')
        if not math.isfinite(self.role_weight) or self.role_weight<0:raise ValueError('Invalid role weight')


@dataclass(frozen=True)
class Attempt:
    question_id: str
    skill: str
    difficulty: str
    move: str
    band: str
    score: float


@dataclass(frozen=True)
class PolicyState:
    profiles: tuple[SkillProfile,...]
    must_cover: tuple[str,...]
    total_questions: int=10
    seed: int=0
    history: tuple[Attempt,...]=()
    demonstrated: frozenset[tuple[str,str]]=frozenset()

    def __post_init__(self):
        if not 8<=self.total_questions<=12:raise ValueError('Budget must be 8–12')
        skills=[p.skill for p in self.profiles]
        if len(skills)!=len(set(skills)):raise ValueError('Profiles must be canonical and deduplicated')
        if len(self.must_cover)!=len(set(self.must_cover)) or not set(self.must_cover)<=set(skills):raise ValueError('Invalid must-cover set')
        if len(self.must_cover)>math.floor(.6*self.total_questions):raise ValueError('Must-cover exceeds 60% budget')
        if len(self.history)>self.total_questions:raise ValueError('History exceeds budget')
        if len({a.question_id for a in self.history}) != len(self.history):raise ValueError('Repeated history question')
        if any(a.skill not in skills or a.band not in ANSWER_BANDS or a.difficulty not in DIFFICULTIES or not math.isfinite(a.score) or not 0<=a.score<=100 for a in self.history):
            raise ValueError('Invalid observed history')

    @property
    def remaining(self):return self.total_questions-len(self.history)
    @property
    def uncovered(self):return tuple(s for s in self.must_cover if s not in {a.skill for a in self.history})


@dataclass(frozen=True)
class MoveDecision:
    move: str
    question: Question | None
    reason_code: str
    requested_difficulty: str | None=None
    edge_type: str | None=None
    bridge_direction: str | None=None
    fallback_reasons: tuple[str,...]=()

    @property
    def difficulty_relaxed(self):
        return bool(self.question and self.requested_difficulty!=self.question.difficulty)


class BankExhausted(ValueError):pass


def make_state(profiles, *, total_questions=10, seed=0):
    """Merge aliases once; maximum role weight, strongest resume evidence."""
    merged={}
    for raw in profiles:
        p=raw if isinstance(raw,SkillProfile) else SkillProfile(canonical_skill(raw['skill']),raw['evidence_tier'],raw.get('role_weight',1.0))
        old=merged.get(p.skill)
        if old:
            p=SkillProfile(p.skill,min((old.evidence_tier,p.evidence_tier),key=TIERS.index),max(old.role_weight,p.role_weight))
        merged[p.skill]=p
    profiles=tuple(sorted(merged.values(),key=lambda p:(-p.role_weight,p.skill)))
    strength=next((p for p in profiles if p.evidence_tier=='claimed_evidenced'),None)
    ordered=([strength] if strength else [])+[p for tier in ('claimed_keyword_only','claimed_evidenced') for p in profiles if p.evidence_tier==tier and p!=strength]
    gap=next((p for p in profiles if p.evidence_tier=='role_gap'),None)
    if gap:ordered.append(gap)
    must=tuple(p.skill for p in ordered[:min(len(profiles),math.floor(.6*total_questions))])
    return PolicyState(profiles,must,total_questions,seed)


def expected_score(rating: float, difficulty: str) -> float:
    if difficulty not in POLICY_DIFFICULTY_ELO or not math.isfinite(rating):raise ValueError('Invalid Elo input')
    exponent=max(-300.0,min(300.0,(POLICY_DIFFICULTY_ELO[difficulty]-rating)/400.0))
    return 1/(1+10**exponent)


def update_observed_elo(rating: float, difficulty: str, score: float) -> float:
    if not math.isfinite(score) or not 0<=score<=100:raise ValueError('Score outside 0–100')
    return rating+POLICY_ELO_K*(score/100-expected_score(rating,difficulty))


def observed_ratings(state):
    ratings={p.skill:POLICY_NEUTRAL_ELO for p in state.profiles}
    for a in state.history:ratings[a.skill]=update_observed_elo(ratings[a.skill],a.difficulty,a.score)
    return ratings


def _priority(state,skill):
    p=next(p for p in state.profiles if p.skill==skill)
    return (skill not in state.uncovered,-p.role_weight,skill)


def _initial_difficulty(profile):
    return 'medium' if profile.evidence_tier=='claimed_evidenced' else 'easy'


def _available(state,bank,asked_extra=()):
    asked=tuple(a.question_id for a in state.history)+tuple(q.id for q in asked_extra)
    counts=Counter([a.skill for a in state.history]+[q.skill for q in asked_extra])
    profiles={p.skill:p for p in state.profiles}
    # At most one role-gap bucket per session, with one Easy observation.
    gap=next((s for s in state.must_cover if profiles[s].evidence_tier=='role_gap'),None)
    if gap is None:gap=next((p.skill for p in state.profiles if p.evidence_tier=='role_gap'),None)
    return tuple(q for q in bank.questions if q.eligible and (q.source!='bundle' or q.bundle_reviewed) and q.skill in profiles
        and counts[q.skill]<(1 if profiles[q.skill].evidence_tier=='role_gap' else 3)
        and (profiles[q.skill].evidence_tier!='role_gap' or (q.skill==gap and q.difficulty=='easy'))
        and not bank.conflicts(q.id,asked))


def _capacity(questions,bank,cap):
    """Exact per-skill independence capacity, capped at three attempts."""
    def search(items,chosen):
        if len(chosen)>=cap:return len(chosen)
        best=len(chosen)
        for i,q in enumerate(items):
            if not bank.conflicts(q.id,[c.id for c in chosen]):
                best=max(best,search(items[i+1:],chosen+(q,)))
                if best==cap:return best
        return best
    return search(questions,())


def completion_witness(state,bank,first=None):
    """Find a legal remaining cover schedule, preserving the budget invariant.

    This is feasibility lookahead, not a counterfactual scoring simulation.
    It accounts for cross-skill exact duplicates and within-skill near duplicates.
    """
    if first is not None and first not in _available(state,bank):return None
    memo=set()
    def search(chosen):
        key=tuple(sorted(q.id for q in chosen))
        if key in memo:return None
        remaining=state.remaining-len(chosen)
        seen={a.skill for a in state.history}|{q.skill for q in chosen}
        uncovered=[s for s in state.must_cover if s not in seen]
        if remaining==0:return chosen if not uncovered else None
        if remaining<len(uncovered):return None
        available=_available(state,bank,chosen)
        counts=Counter([a.skill for a in state.history]+[q.skill for q in chosen])
        groups={p.skill:tuple(q for q in available if q.skill==p.skill) for p in state.profiles}
        if any(not groups[s] for s in uncovered):return None
        capacity=sum(_capacity(groups[p.skill],bank,(1 if p.evidence_tier=='role_gap' else 3)-counts[p.skill]) for p in state.profiles)
        if capacity<remaining:return None
        skills=sorted(uncovered,key=lambda s:(len(groups[s]),_priority(state,s)))[:1] if uncovered else sorted(groups,key=lambda s:_priority(state,s))
        for skill in skills:
            for q in sorted(groups[skill],key=lambda q:(_SOURCE_ORDER[q.source],q.id)):
                found=search(chosen+(q,))
                if found is not None:return found
        memo.add(key)
        return None
    return search((first,) if first else ())


def _select(state,bank,skill,requested,*,harder_than=None):
    candidates=[q for q in _available(state,bank) if q.skill==skill
        and (harder_than is None or DIFFICULTIES.index(q.difficulty)>DIFFICULTIES.index(harder_than))]
    learned={c for s,c in state.demonstrated if s==skill}
    fresh=[q for q in candidates if not q.concepts or len(q.concepts&learned)/len(q.concepts)<.75]
    fallback=() if fresh else (('all_candidates_previously_demonstrated',) if candidates else ())
    # Previously demonstrated concepts are a soft filter only. Safety feasibility
    # outranks it if all fresh questions would make completion impossible.
    def key(q):
        distance=abs(DIFFICULTIES.index(q.difficulty)-DIFFICULTIES.index(requested))
        tie=DIFFICULTIES.index(q.difficulty)>DIFFICULTIES.index(requested)
        seeded=hashlib.sha256(f'{state.seed}:{q.id}'.encode()).hexdigest()
        return (distance,tie,_SOURCE_ORDER[q.source],seeded,q.id)
    for group in (sorted(fresh,key=key),sorted([q for q in candidates if q not in fresh],key=key)):
        for q in group:
            if completion_witness(state,bank,q) is not None:
                reasons=fallback
                if q not in fresh and fresh:reasons+=('demonstrated_filter_relaxed_for_feasibility',)
                if q.difficulty!=requested:reasons+=('difficulty_relaxed',)
                return q,reasons
    return None,()


def next_adaptive_move(state: PolicyState, bank: QuestionBank) -> MoveDecision:
    """COVER / PROBE_HARDER / BRIDGE / END only; there is no concept-probe move."""
    if not state.remaining:
        if state.uncovered:raise BankExhausted('Completed budget with uncovered must-cover skills')
        return MoveDecision('END',None,'BUDGET_COMPLETE')
    if completion_witness(state,bank) is None:raise BankExhausted('No feasible distinct-question schedule for this budget and must-cover set')
    profiles={p.skill:p for p in state.profiles};last=state.history[-1] if state.history else None
    fallback=()
    forced=state.remaining<=len(state.uncovered)
    if not forced and last and profiles[last.skill].evidence_tier!='role_gap':
        attempts=sum(a.skill==last.skill for a in state.history)
        if last.band=='strong' and attempts<2 and last.move!='PROBE_HARDER':
            requested=DIFFICULTIES[min(2,DIFFICULTIES.index(last.difficulty)+1)]
            q,reasons=_select(state,bank,last.skill,requested,harder_than=last.difficulty)
            if q:return MoveDecision('PROBE_HARDER',q,'STRONG_ESCALATE_DIFFICULTY',requested,fallback_reasons=reasons)
            fallback=('already_at_max_difficulty' if last.difficulty=='hard' else 'no_unseen_harder_question',)
        targets=[]
        if last.band in {'wrong','nonanswer'}:
            targets=[(s,'prerequisite','down') for s in prerequisites(last.skill)]
            if not targets:fallback+=('no_eligible_prerequisite',)
        elif last.band=='strong':
            targets=[(s,'prerequisite','up') for s in dependents(last.skill)]
            targets += [(s,'used_with','across') for s in symmetric_neighbors(last.skill) if s not in dependents(last.skill)]
        for skill,edge,direction in sorted((t for t in targets if t[0] in profiles),key=lambda t:_priority(state,t[0])):
            requested=_initial_difficulty(profiles[skill])
            q,reasons=_select(state,bank,skill,requested)
            if q:return MoveDecision('BRIDGE',q,'WRONG_BRIDGE_PREREQ' if last.band in {'wrong','nonanswer'} else 'STRONG_BRIDGE',requested,edge,direction,fallback+reasons)
        if targets:fallback+=('no_eligible_bridge_question',)
    if last is None:
        strength=next((p.skill for p in state.profiles if p.evidence_tier=='claimed_evidenced'),None)
        order=([strength] if strength else [])+[s for s in state.must_cover if s!=strength]
    else:order=sorted(profiles,key=lambda s:_priority(state,s))
    for skill in order:
        if forced and skill not in state.uncovered:continue
        requested=_initial_difficulty(profiles[skill])
        q,reasons=_select(state,bank,skill,requested)
        if q:
            reason=('BUDGET_INVARIANT_FORCED_COVER' if forced else 'ROUND1_EVIDENCED_OPENER' if last is None else
                    'ROLE_GAP_SINGLE_QUESTION_CAP' if profiles[last.skill].evidence_tier=='role_gap' else 'DEFAULT_COVER_NEXT')
            return MoveDecision('COVER',q,reason,requested,fallback_reasons=fallback+reasons)
    raise BankExhausted('No legal cover question')


def record_outcome(state, decision, *, band: str, score: float, demonstrated=()):
    if decision.question is None or decision.move not in {'COVER','BRIDGE','PROBE_HARDER'}:raise ValueError('Not an observable move')
    if band not in ANSWER_BANDS or not math.isfinite(score) or not 0<=score<=100:raise ValueError('Invalid observation')
    q=decision.question
    if q.id in {a.question_id for a in state.history}:raise ValueError('Repeated question')
    return replace(state,history=state.history+(Attempt(q.id,q.skill,q.difficulty,decision.move,band,score),),
        demonstrated=state.demonstrated|frozenset((q.skill,c) for c in demonstrated))


def pinned_skills(state: PolicyState) -> tuple[str, ...]:
    """Profile skills in profile order."""
    return tuple(p.skill for p in state.profiles)


def observed_ability_summary(state: PolicyState) -> dict[str, dict[str, object]]:
    """History-only per-skill attempts, mean score and last band."""
    scores: dict[str, list[float]] = {}
    last_band: dict[str, str] = {}
    for attempt in state.history:
        scores.setdefault(attempt.skill, []).append(attempt.score)
        last_band[attempt.skill] = attempt.band
    return {
        skill: {
            'attempts': len(values),
            'mean_score': sum(values) / len(values),
            'last_band': last_band[skill],
        }
        for skill, values in scores.items()
    }


def decision_log_entry(decision: MoveDecision) -> dict[str, object]:
    """JSON-ready log view of a decision."""
    return {
        'move': decision.move,
        'question_id': decision.question.id if decision.question is not None else None,
        'reason_code': decision.reason_code,
        'requested_difficulty': decision.requested_difficulty,
        'edge_type': decision.edge_type,
        'bridge_direction': decision.bridge_direction,
        'fallback_reasons': list(decision.fallback_reasons),
    }


def replay_from_round_log(state: PolicyState, bank: QuestionBank, rounds) -> PolicyState:
    """Rebuild state from a round log without mutating the inputs.

    Follow-up entries are filtered out via ``non_follow_up_rounds``. Every
    remaining entry must carry a question id, band and score; the policy's
    own next move must select that same question before its outcome folds in.
    """
    entries = non_follow_up_rounds(list(rounds))
    current = state
    for entry in entries:
        if not isinstance(entry, Mapping):
            raise ValueError('Round log entries must be mappings')
        question_id = entry.get('question_id') or entry.get('questionId') or entry.get('id')
        band = entry.get('band')
        score = entry.get('score', entry.get('final_score'))
        if not question_id or band is None or score is None:
            raise ValueError('Round log entries require question id, band and score')
        score = float(score)
        decision = next_adaptive_move(current, bank)
        if decision.question is None or decision.question.id != str(question_id):
            raise ValueError(f'Round log question mismatch: {question_id}')
        current = record_outcome(current, decision, band=str(band), score=score)
    return current
