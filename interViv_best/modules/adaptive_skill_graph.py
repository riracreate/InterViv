"""Pure canonical skill graph for stage (a); no student graph/persistence changes."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Literal

EdgeType = Literal['prerequisite', 'used_with', 'alternative_to']


@dataclass(frozen=True)
class SkillEdge:
    source: str
    target: str
    kind: EdgeType

CANONICAL_SKILLS = ('CN','DBMS','DSA','HR','Java','JavaScript','ML','OOP','OS','Python','System Design')
PREREQUISITES = (('Python','ML'),('DSA','System Design'),('DBMS','System Design'),
                 ('CN','System Design'),('OS','CN'),('OS','System Design'))
USED_WITH = (('OOP','Java'),('OOP','Python'),('OOP','DSA'),('Python','DBMS'),
             ('Java','DBMS'),('JavaScript','CN'),('DSA','ML'),('DBMS','ML'))
ALTERNATIVES = (('Python','Java'),('Python','JavaScript'),('Java','JavaScript'))
EDGE_TYPES = ('prerequisite','used_with','alternative_to')
EDGES = tuple(SkillEdge(a, b, kind) for kind, pairs in (
    ('prerequisite', PREREQUISITES), ('used_with', USED_WITH),
    ('alternative_to', ALTERNATIVES)) for a, b in pairs)
_ALIASES = {s.casefold():s for s in CANONICAL_SKILLS} | {
    'sql':'DBMS','databases':'DBMS','react':'JavaScript','node.js':'JavaScript',
    'nodejs':'JavaScript','fastapi':'Python','machine learning':'ML',
    'computer networks':'CN','operating systems':'OS','data structures':'DSA',
}


def canonical_skill(skill: str) -> str:
    try:return _ALIASES[skill.strip().casefold()]
    except KeyError:raise ValueError(f'Unmapped skill: {skill}') from None


def prerequisites(skill: str) -> tuple[str,...]:
    skill=canonical_skill(skill)
    return tuple(sorted(edge.source for edge in EDGES if edge.kind=='prerequisite' and edge.target==skill))


def dependents(skill: str) -> tuple[str,...]:
    skill=canonical_skill(skill)
    return tuple(sorted(edge.target for edge in EDGES if edge.kind=='prerequisite' and edge.source==skill))


def symmetric_neighbors(skill: str, edge_type: str='used_with') -> tuple[str,...]:
    skill=canonical_skill(skill)
    if edge_type not in {'used_with','alternative_to'}:raise ValueError(edge_type)
    return tuple(sorted(edge.target if edge.source==skill else edge.source for edge in EDGES
                        if edge.kind==edge_type and skill in (edge.source,edge.target)))


def bridge_coverage() -> dict:
    per_skill={s:{'down':list(prerequisites(s)),'up':list(dependents(s)),
        'across':list(symmetric_neighbors(s))} for s in CANONICAL_SKILLS}
    return {'skills':per_skill,'denominator':len(CANONICAL_SKILLS),
        'down':sum(bool(v['down']) for v in per_skill.values()),
        'up':sum(bool(v['up']) for v in per_skill.values()),
        'across':sum(bool(v['across']) for v in per_skill.values()),
        'up_or_across':sum(bool(v['up'] or v['across']) for v in per_skill.values())}
