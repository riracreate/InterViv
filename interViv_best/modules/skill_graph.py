from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any

from backend.config import get_settings


DIFFICULTY_RATINGS = {"easy": 1000, "medium": 1500, "hard": 2000}
ROLLING_WINDOW = 5


@dataclass
class SkillNode:
    name: str
    current_score: float = 0.0
    current_elo: float = 1200.0
    attempts: int = 0
    last_practiced_at: datetime | None = None
    sub_concepts: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        if self.last_practiced_at is not None:
            payload["last_practiced_at"] = self.last_practiced_at.isoformat()
        return payload


_MEMORY_GRAPHS: dict[str, dict[str, SkillNode]] = {}
_MEMORY_RECENT_SCORES: dict[tuple[str, str], list[float]] = {}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _clean_skill(skill: str) -> str:
    return str(skill or "").strip() or "General"


def _display_concept(value: str) -> str:
    return str(value).replace("_", " ").strip()


def _skill_concepts(skill: str) -> list[str]:
    try:
        from modules.knowledge_graph import KnowledgeGraphScorer

        graph = KnowledgeGraphScorer().graphs.get(skill)
        if graph is None:
            return []
        return sorted(_display_concept(node) for node in graph.nodes())
    except Exception:
        return []


def _elo_update(current_elo: float, difficulty: str, score: float) -> float:
    question_rating = DIFFICULTY_RATINGS.get(str(difficulty).lower(), 1500)
    expected = 1.0 / (1.0 + pow(10.0, (question_rating - current_elo) / 400.0))
    actual = max(0.0, min(float(score), 100.0)) / 100.0
    updated = current_elo + 32 * (actual - expected)
    return round(max(600.0, min(2400.0, updated)), 2)


def _using_sqlalchemy() -> bool:
    return bool(get_settings().database_url)


class StudentSkillGraph:
    def __init__(self, user_id: str):
        self.user_id = str(user_id or "").strip()

    def initialize_from_resume(self, extracted_skills: list[str]) -> None:
        skills = [_clean_skill(skill) for skill in extracted_skills if _clean_skill(skill)]
        if not self.user_id or not skills:
            return

        if _using_sqlalchemy():
            self._initialize_sql(skills)
            return

        graph = _MEMORY_GRAPHS.setdefault(self.user_id, {})
        for skill in skills:
            graph.setdefault(
                skill,
                SkillNode(name=skill, sub_concepts=_skill_concepts(skill)),
            )

    def update_after_round(self, skill: str, score: float, difficulty: str) -> None:
        if not self.user_id:
            return
        skill = _clean_skill(skill)
        score = max(0.0, min(float(score), 100.0))

        if _using_sqlalchemy():
            self._update_sql(skill=skill, score=score, difficulty=difficulty)
            return

        graph = _MEMORY_GRAPHS.setdefault(self.user_id, {})
        node = graph.setdefault(
            skill,
            SkillNode(name=skill, sub_concepts=_skill_concepts(skill)),
        )
        recent_key = (self.user_id, skill)
        recent = _MEMORY_RECENT_SCORES.setdefault(recent_key, [])
        recent.append(score)
        del recent[:-ROLLING_WINDOW]

        node.current_score = round(sum(recent) / len(recent), 2)
        node.current_elo = _elo_update(node.current_elo, difficulty, score)
        node.attempts += 1
        node.last_practiced_at = _now()

    def get_current_state(self) -> dict[str, SkillNode]:
        if not self.user_id:
            return {}
        if _using_sqlalchemy():
            return self._get_sql_state()
        return dict(_MEMORY_GRAPHS.get(self.user_id, {}))

    def get_weak_skills(self, threshold: float = 50) -> list[SkillNode]:
        return [
            node
            for node in self.get_current_state().values()
            if float(node.current_score) < threshold
        ]

    def to_api_payload(self) -> dict[str, Any]:
        nodes = [
            node.to_dict()
            for node in sorted(self.get_current_state().values(), key=lambda item: item.name.lower())
        ]
        return {"user_id": self.user_id, "skills": nodes}

    def _initialize_sql(self, skills: list[str]) -> None:
        from backend.db.sqlalchemy_models import SkillRow, StudentSkillGraphRow
        from backend.db.sqlalchemy_store import session_scope

        with session_scope() as session:
            for skill in skills:
                skill_row = _get_or_create_skill(session, SkillRow, skill)
                existing = (
                    session.query(StudentSkillGraphRow)
                    .filter_by(user_id=self.user_id, skill_id=skill_row.id)
                    .one_or_none()
                )
                if existing is None:
                    session.add(
                        StudentSkillGraphRow(
                            user_id=self.user_id,
                            skill_id=skill_row.id,
                            current_score=0.0,
                            current_elo=1200.0,
                            attempts=0,
                            last_practiced_at=None,
                        )
                    )

    def _update_sql(self, *, skill: str, score: float, difficulty: str) -> None:
        from backend.db.sqlalchemy_models import (
            RoundRow,
            SessionRow,
            SkillRow,
            StudentSkillGraphRow,
        )
        from backend.db.sqlalchemy_store import session_scope

        with session_scope() as session:
            skill_row = _get_or_create_skill(session, SkillRow, skill)
            graph_row = (
                session.query(StudentSkillGraphRow)
                .filter_by(user_id=self.user_id, skill_id=skill_row.id)
                .one_or_none()
            )
            if graph_row is None:
                graph_row = StudentSkillGraphRow(
                    user_id=self.user_id,
                    skill_id=skill_row.id,
                    current_score=0.0,
                    current_elo=1200.0,
                    attempts=0,
                )
                session.add(graph_row)
                session.flush()

            from sqlalchemy import or_, and_

            recent_scores = [
                float(value)
                for (value,) in (
                    session.query(RoundRow.final_score)
                    .join(SessionRow, RoundRow.session_id == SessionRow.id)
                    .filter(SessionRow.user_id == self.user_id)
                    .filter(RoundRow.skill_text == skill)
                    .filter(RoundRow.final_score.isnot(None))
                    # Phase 4A eligible, or pre-4A legacy unassisted non-follow-up.
                    .filter(
                        or_(
                            RoundRow.assessment_eligibility == "eligible",
                            and_(
                                RoundRow.assessment_eligibility.is_(None),
                                or_(
                                    RoundRow.assisted.is_(None),
                                    RoundRow.assisted.is_(False),
                                ),
                                or_(
                                    RoundRow.is_follow_up.is_(None),
                                    RoundRow.is_follow_up.is_(False),
                                ),
                            ),
                        )
                    )
                    .order_by(RoundRow.created_at.desc(), RoundRow.id.desc())
                    .limit(ROLLING_WINDOW)
                    .all()
                )
                if value is not None
            ]
            if not recent_scores:
                recent_scores = [score]

            graph_row.current_score = round(sum(recent_scores) / len(recent_scores), 2)
            graph_row.current_elo = _elo_update(graph_row.current_elo, difficulty, score)
            graph_row.attempts = int(graph_row.attempts or 0) + 1
            graph_row.last_practiced_at = _now()

    def _get_sql_state(self) -> dict[str, SkillNode]:
        from backend.db.sqlalchemy_models import SkillRow, StudentSkillGraphRow
        from backend.db.sqlalchemy_store import session_scope

        state: dict[str, SkillNode] = {}
        with session_scope() as session:
            rows = (
                session.query(StudentSkillGraphRow, SkillRow)
                .join(SkillRow, StudentSkillGraphRow.skill_id == SkillRow.id)
                .filter(StudentSkillGraphRow.user_id == self.user_id)
                .all()
            )
            for graph_row, skill_row in rows:
                name = skill_row.canonical_name
                state[name] = SkillNode(
                    name=name,
                    current_score=round(float(graph_row.current_score or 0.0), 2),
                    current_elo=round(float(graph_row.current_elo or 1200.0), 2),
                    attempts=int(graph_row.attempts or 0),
                    last_practiced_at=graph_row.last_practiced_at,
                    sub_concepts=_skill_concepts(name),
                )
        return state


def _get_or_create_skill(session, skill_model, skill_name: str):
    skill_name = _clean_skill(skill_name)
    for row in session.query(skill_model).all():
        if row.canonical_name.lower() == skill_name.lower():
            return row
    row = skill_model(canonical_name=skill_name, sub_domain=None, parent_skill_id=None)
    session.add(row)
    session.flush()
    return row
