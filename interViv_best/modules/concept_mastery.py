from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from enum import StrEnum
from typing import Any

from backend.config import get_settings


class MasteryLevel(StrEnum):
    MASTERED = "Mastered"
    STRONG = "Strong"
    WEAK = "Weak"
    UNTESTED = "Untested"


@dataclass
class ConceptMasteryNode:
    concept_name: str
    attempts: int
    demonstrated: int
    mastery_level: MasteryLevel
    last_seen_at: datetime | None = None

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["mastery_level"] = str(self.mastery_level)
        if self.last_seen_at is not None:
            payload["last_seen_at"] = self.last_seen_at.isoformat()
        return payload


_MEMORY_MASTERY: dict[str, dict[str, dict[str, ConceptMasteryNode]]] = {}


def reset_memory_store() -> None:
    """Test helper — clears in-memory concept mastery."""
    _MEMORY_MASTERY.clear()


def snapshot_memory_store() -> dict[str, Any]:
    import copy

    return {"mastery": copy.deepcopy(_MEMORY_MASTERY)}


def restore_memory_store(snapshot: dict[str, Any] | None) -> None:
    if not snapshot:
        return
    import copy

    _MEMORY_MASTERY.clear()
    _MEMORY_MASTERY.update(copy.deepcopy(snapshot.get("mastery") or {}))


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _using_sqlalchemy() -> bool:
    return bool(get_settings().database_url)


def _clean_skill(skill: str) -> str:
    return str(skill or "").strip() or "General"


def _clean_concept(concept: str) -> str:
    return str(concept or "").replace("_", " ").strip()


def _level(attempts: int, demonstrated: int) -> MasteryLevel:
    if attempts <= 0:
        return MasteryLevel.UNTESTED
    rate = demonstrated / attempts
    if attempts >= 3 and rate >= 0.80:
        return MasteryLevel.MASTERED
    if rate >= 0.50:
        return MasteryLevel.STRONG
    return MasteryLevel.WEAK


class ConceptMastery:
    def update_from_round(
        self,
        user_id: str,
        skill: str,
        covered_concepts: list[str],
        missing_concepts: list[str],
    ) -> None:
        user_id = str(user_id or "").strip()
        if not user_id:
            return

        skill = _clean_skill(skill)
        covered = _unique_concepts(covered_concepts)
        covered_keys = {item.lower() for item in covered}
        missing = [
            item for item in _unique_concepts(missing_concepts)
            if item.lower() not in covered_keys
        ]

        if not covered and not missing:
            return

        if _using_sqlalchemy():
            self._update_sql(user_id, skill, covered, missing)
            return

        skill_map = _MEMORY_MASTERY.setdefault(user_id, {}).setdefault(skill, {})
        for concept in covered:
            node = skill_map.get(concept) or ConceptMasteryNode(
                concept_name=concept,
                attempts=0,
                demonstrated=0,
                mastery_level=MasteryLevel.UNTESTED,
            )
            node.attempts += 1
            node.demonstrated += 1
            node.last_seen_at = _now()
            node.mastery_level = _level(node.attempts, node.demonstrated)
            skill_map[concept] = node
        for concept in missing:
            node = skill_map.get(concept) or ConceptMasteryNode(
                concept_name=concept,
                attempts=0,
                demonstrated=0,
                mastery_level=MasteryLevel.UNTESTED,
            )
            node.attempts += 1
            node.last_seen_at = _now()
            node.mastery_level = _level(node.attempts, node.demonstrated)
            skill_map[concept] = node

    def get_mastery_map(self, user_id: str) -> dict[str, dict[str, MasteryLevel]]:
        details = self.get_mastery_details(user_id)
        return {
            skill: {
                concept: MasteryLevel(node["mastery_level"])
                for concept, node in concepts.items()
            }
            for skill, concepts in details.items()
        }

    def get_mastery_details(self, user_id: str) -> dict[str, dict[str, dict[str, Any]]]:
        user_id = str(user_id or "").strip()
        if not user_id:
            return {}
        if _using_sqlalchemy():
            return self._get_sql_details(user_id)
        return {
            skill: {
                concept: node.to_dict()
                for concept, node in sorted(concepts.items())
            }
            for skill, concepts in sorted(_MEMORY_MASTERY.get(user_id, {}).items())
        }

    def to_api_payload(self, user_id: str) -> dict[str, Any]:
        details = self.get_mastery_details(user_id)
        mastery = {
            skill: {
                concept: node["mastery_level"]
                for concept, node in concepts.items()
            }
            for skill, concepts in details.items()
        }
        return {"user_id": str(user_id), "mastery": mastery, "details": details}

    def _update_sql(
        self,
        user_id: str,
        skill: str,
        covered: list[str],
        missing: list[str],
    ) -> None:
        from backend.db.sqlalchemy_models import (
            SkillRow,
            StudentConceptMasteryRow,
        )
        from backend.db.sqlalchemy_store import session_scope
        from modules.skill_graph import _get_or_create_skill

        with session_scope() as session:
            skill_row = _get_or_create_skill(session, SkillRow, skill)
            for concept in covered:
                row = _get_or_create_concept_row(
                    session,
                    StudentConceptMasteryRow,
                    user_id=user_id,
                    skill_id=skill_row.id,
                    concept=concept,
                )
                row.attempts = int(row.attempts or 0) + 1
                row.demonstrated = int(row.demonstrated or 0) + 1
                row.last_seen_at = _now()
            for concept in missing:
                row = _get_or_create_concept_row(
                    session,
                    StudentConceptMasteryRow,
                    user_id=user_id,
                    skill_id=skill_row.id,
                    concept=concept,
                )
                row.attempts = int(row.attempts or 0) + 1
                row.last_seen_at = _now()

    def _get_sql_details(self, user_id: str) -> dict[str, dict[str, dict[str, Any]]]:
        from backend.db.sqlalchemy_models import SkillRow, StudentConceptMasteryRow
        from backend.db.sqlalchemy_store import session_scope

        details: dict[str, dict[str, dict[str, Any]]] = {}
        with session_scope() as session:
            rows = (
                session.query(StudentConceptMasteryRow, SkillRow)
                .join(SkillRow, StudentConceptMasteryRow.skill_id == SkillRow.id)
                .filter(StudentConceptMasteryRow.user_id == user_id)
                .all()
            )
            for row, skill_row in rows:
                level = _level(int(row.attempts or 0), int(row.demonstrated or 0))
                node = ConceptMasteryNode(
                    concept_name=row.concept_name,
                    attempts=int(row.attempts or 0),
                    demonstrated=int(row.demonstrated or 0),
                    mastery_level=level,
                    last_seen_at=row.last_seen_at,
                )
                details.setdefault(skill_row.canonical_name, {})[row.concept_name] = node.to_dict()
        return {
            skill: dict(sorted(concepts.items()))
            for skill, concepts in sorted(details.items())
        }


def _unique_concepts(concepts: list[str]) -> list[str]:
    seen: set[str] = set()
    cleaned: list[str] = []
    for concept in concepts or []:
        display = _clean_concept(concept)
        key = display.lower()
        if display and key not in seen:
            seen.add(key)
            cleaned.append(display)
    return cleaned


def _get_or_create_concept_row(session, concept_model, *, user_id: str, skill_id: int, concept: str):
    existing = (
        session.query(concept_model)
        .filter_by(user_id=user_id, skill_id=skill_id, concept_name=concept)
        .one_or_none()
    )
    if existing is not None:
        return existing
    row = concept_model(
        user_id=user_id,
        skill_id=skill_id,
        concept_name=concept,
        attempts=0,
        demonstrated=0,
        last_seen_at=None,
    )
    session.add(row)
    session.flush()
    return row
