from __future__ import annotations

import copy
from contextlib import contextmanager
from datetime import datetime, timezone
from functools import lru_cache
from typing import Any, Iterator

from backend.config import get_settings

from .sqlalchemy_models import (
    Base,
    CandidateRow,
    RoundRow,
    SessionRow,
    UserRow,
)


class SQLAlchemyDatabaseError(RuntimeError):
    pass


class _InsertResult:
    def __init__(self, inserted_id: Any):
        self.inserted_id = inserted_id


class _UpdateResult:
    def __init__(self, matched: int, modified: int):
        self.matched_count = matched
        self.modified_count = modified


def _normalize_database_url(url: str) -> str:
    if url.startswith("postgres://"):
        return "postgresql+psycopg://" + url.removeprefix("postgres://")
    if url.startswith("postgresql://") and "+psycopg" not in url and "+psycopg2" not in url:
        return "postgresql+psycopg://" + url.removeprefix("postgresql://")
    return url


@lru_cache(maxsize=1)
def get_engine():
    try:
        from sqlalchemy import create_engine
    except ModuleNotFoundError as exc:
        raise SQLAlchemyDatabaseError(
            "SQLAlchemy is not installed. Install requirements.txt before using DATABASE_URL."
        ) from exc

    database_url = get_settings().database_url
    if not database_url:
        raise SQLAlchemyDatabaseError("DATABASE_URL is not set.")
    return create_engine(_normalize_database_url(database_url), pool_pre_ping=True, future=True)


@lru_cache(maxsize=1)
def _sessionmaker():
    try:
        from sqlalchemy.orm import sessionmaker
    except ModuleNotFoundError as exc:
        raise SQLAlchemyDatabaseError(
            "SQLAlchemy is not installed. Install requirements.txt before using DATABASE_URL."
        ) from exc

    return sessionmaker(bind=get_engine(), autoflush=False, expire_on_commit=False, future=True)


@contextmanager
def session_scope():
    session = _sessionmaker()()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def create_all_for_smoke() -> None:
    Base.metadata.create_all(bind=get_engine())


def _json_ready(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, dict):
        return {str(k): _json_ready(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_json_ready(item) for item in value]
    return value


def _coerce_datetime(value: Any) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
    return None


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _matches(doc: dict[str, Any], query: dict[str, Any]) -> bool:
    for key, value in (query or {}).items():
        current: Any = doc
        for part in key.split("."):
            if isinstance(current, dict) and part in current:
                current = current[part]
            else:
                current = None
                break
        if current != value:
            return False
    return True


def _apply_update_dict(doc: dict[str, Any], update: dict[str, Any]) -> bool:
    def target(path: str) -> tuple[dict[str, Any], str]:
        if "." not in path:
            return doc, path
        parts = path.split(".")
        current = doc
        for part in parts[:-1]:
            current = current.setdefault(part, {})
        return current, parts[-1]

    modified = False
    for op, body in (update or {}).items():
        if op == "$set":
            for key, value in body.items():
                current, leaf = target(key)
                if current.get(leaf) != value:
                    current[leaf] = value
                    modified = True
        elif op == "$addToSet":
            for key, value in body.items():
                current, leaf = target(key)
                existing = current.setdefault(leaf, [])
                if not isinstance(existing, list):
                    existing = [existing]
                    current[leaf] = existing
                    modified = True
                values = value["$each"] if isinstance(value, dict) and "$each" in value else [value]
                for item in values:
                    if item not in existing:
                        existing.append(item)
                        modified = True
        elif op == "$push":
            for key, value in body.items():
                current, leaf = target(key)
                existing = current.setdefault(leaf, [])
                values = value["$each"] if isinstance(value, dict) and "$each" in value else [value]
                existing.extend(values)
                modified = bool(values) or modified
        elif op == "$inc":
            for key, value in body.items():
                current, leaf = target(key)
                current[leaf] = current.get(leaf, 0) + value
                modified = True
    return modified


def _project(doc: dict[str, Any], projection: dict[str, Any] | None) -> dict[str, Any]:
    result = copy.deepcopy(doc)
    if not projection:
        return result
    for key, enabled in projection.items():
        if not enabled:
            result.pop(key, None)
    return result


def _filtered_rows(session, model, field_columns: dict[str, Any], query: dict[str, Any] | None):
    """Query rows with simple equality filters pushed down to SQL.

    Only query keys present in ``field_columns`` with scalar values become SQL
    filters; everything else (dotted paths, nested values) is still verified in
    Python by ``_matches`` on the resulting documents.
    """
    q = session.query(model)
    for key, value in (query or {}).items():
        column = field_columns.get(key)
        if column is not None and not isinstance(value, (dict, list)):
            q = q.filter(column == value)
    return q.all()


class _CandidateCollection:
    @staticmethod
    def _field_columns() -> dict[str, Any]:
        return {"candidate_id": CandidateRow.candidate_id, "user_id": CandidateRow.user_id}

    def find_one(self, query: dict, projection: dict | None = None) -> dict | None:
        with session_scope() as session:
            rows = _filtered_rows(session, CandidateRow, self._field_columns(), query)
            for row in rows:
                doc = self._to_doc(row)
                if _matches(doc, query):
                    return _project(doc, projection)
        return None

    def find(self, query: dict | None = None) -> Iterator[dict]:
        with session_scope() as session:
            docs = [
                self._to_doc(row)
                for row in _filtered_rows(session, CandidateRow, self._field_columns(), query)
            ]
        return iter([doc for doc in docs if not query or _matches(doc, query)])

    def insert_one(self, doc: dict) -> _InsertResult:
        data = _json_ready(doc)
        candidate_id = data["candidate_id"]
        with session_scope() as session:
            row = CandidateRow(
                candidate_id=candidate_id,
                user_id=data.get("user_id"),
                resume_skills=data.get("resume_skills") or [],
                sub_domain_profile=data.get("sub_domain_profile") or {},
                elo_ratings=data.get("elo_ratings") or {},
                session_history=data.get("session_history") or [],
                created_at=_coerce_datetime(data.get("created_at")) or _now(),
            )
            session.merge(row)
        return _InsertResult(candidate_id)

    def update_one(self, query: dict, update: dict, upsert: bool = False) -> _UpdateResult:
        doc = self.find_one(query)
        matched = 1 if doc else 0
        if not doc:
            if not upsert:
                return _UpdateResult(0, 0)
            doc = dict(query)
        modified = _apply_update_dict(doc, update)
        if doc.get("candidate_id"):
            self.insert_one(doc)
        return _UpdateResult(matched, 1 if modified else 0)

    def delete_one(self, query: dict) -> None:
        with session_scope() as session:
            row = session.get(CandidateRow, query.get("candidate_id"))
            if row:
                session.delete(row)

    def count_documents(self, query: dict) -> int:
        return sum(1 for _ in self.find(query))

    @staticmethod
    def _to_doc(row: CandidateRow) -> dict[str, Any]:
        return {
            "candidate_id": row.candidate_id,
            "user_id": row.user_id,
            "resume_skills": row.resume_skills or [],
            "sub_domain_profile": row.sub_domain_profile or {},
            "elo_ratings": row.elo_ratings or {},
            "session_history": row.session_history or [],
            "created_at": row.created_at,
        }


class _UserCollection:
    @staticmethod
    def _field_columns() -> dict[str, Any]:
        return {"id": UserRow.id, "email": UserRow.email}

    def find_one(self, query: dict, projection: dict | None = None) -> dict | None:
        with session_scope() as session:
            rows = _filtered_rows(session, UserRow, self._field_columns(), query)
            for row in rows:
                doc = self._to_doc(row)
                if _matches(doc, query):
                    return _project(doc, projection)
        return None

    def find(self, query: dict | None = None) -> Iterator[dict]:
        with session_scope() as session:
            docs = [
                self._to_doc(row)
                for row in _filtered_rows(session, UserRow, self._field_columns(), query)
            ]
        return iter([doc for doc in docs if not query or _matches(doc, query)])

    def insert_one(self, doc: dict) -> _InsertResult:
        data = _json_ready(doc)
        with session_scope() as session:
            row = UserRow(
                id=data["id"],
                email=data["email"],
                name=data.get("name"),
                password_hash=data["password_hash"],
                target_company_id=data.get("target_company_id"),
                target_role_id=data.get("target_role_id"),
                created_at=_coerce_datetime(data.get("created_at")) or _now(),
                last_active_at=_coerce_datetime(data.get("last_active_at")) or _now(),
            )
            session.merge(row)
        return _InsertResult(data["id"])

    def update_one(self, query: dict, update: dict, upsert: bool = False) -> _UpdateResult:
        doc = self.find_one(query)
        matched = 1 if doc else 0
        if not doc:
            if not upsert:
                return _UpdateResult(0, 0)
            doc = dict(query)
        modified = _apply_update_dict(doc, update)
        if doc.get("id"):
            self.insert_one(doc)
        return _UpdateResult(matched, 1 if modified else 0)

    def delete_one(self, query: dict) -> None:
        with session_scope() as session:
            row = session.get(UserRow, query.get("id"))
            if row:
                session.delete(row)

    def count_documents(self, query: dict) -> int:
        return sum(1 for _ in self.find(query))

    @staticmethod
    def _to_doc(row: UserRow) -> dict[str, Any]:
        return {
            "id": row.id,
            "email": row.email,
            "name": row.name,
            "password_hash": row.password_hash,
            "target_company_id": row.target_company_id,
            "target_role_id": row.target_role_id,
            "created_at": row.created_at,
            "last_active_at": row.last_active_at,
        }


class _SessionCollection:
    @staticmethod
    def _field_columns() -> dict[str, Any]:
        return {
            "session_id": SessionRow.id,
            "id": SessionRow.id,
            "user_id": SessionRow.user_id,
            "candidate_id": SessionRow.candidate_id,
            "status": SessionRow.status,
        }

    def find_one(self, query: dict, projection: dict | None = None) -> dict | None:
        with session_scope() as session:
            rows = _filtered_rows(session, SessionRow, self._field_columns(), query)
            for row in rows:
                doc = self._to_doc(row)
                if _matches(doc, query):
                    return _project(doc, projection)
        return None

    def find(self, query: dict | None = None) -> Iterator[dict]:
        with session_scope() as session:
            docs = [
                self._to_doc(row)
                for row in _filtered_rows(session, SessionRow, self._field_columns(), query)
            ]
        return iter([doc for doc in docs if not query or _matches(doc, query)])

    def insert_one(self, doc: dict) -> _InsertResult:
        data = _json_ready(doc)
        session_id = data.get("session_id") or data.get("id")
        if not session_id:
            raise SQLAlchemyDatabaseError("sessions.insert_one requires session_id.")
        with session_scope() as session:
            row = session.get(SessionRow, session_id)
            if row is None:
                row = SessionRow(id=session_id)
                session.add(row)
            self._apply_doc_to_row(row, data)
            session.flush()
            self._replace_rounds(session, row, data.get("rounds") or [])
        return _InsertResult(session_id)

    def update_one(self, query: dict, update: dict, upsert: bool = False) -> _UpdateResult:
        doc = self.find_one(query)
        matched = 1 if doc else 0
        if not doc:
            if not upsert:
                return _UpdateResult(0, 0)
            doc = dict(query)
        modified = _apply_update_dict(doc, update)
        if doc.get("session_id"):
            self.insert_one(doc)
        return _UpdateResult(matched, 1 if modified else 0)

    def delete_one(self, query: dict) -> None:
        session_id = query.get("session_id") or query.get("id")
        with session_scope() as session:
            row = session.get(SessionRow, session_id)
            if row:
                session.delete(row)

    def count_documents(self, query: dict) -> int:
        return sum(1 for _ in self.find(query))

    @staticmethod
    def _apply_doc_to_row(row: SessionRow, data: dict[str, Any]) -> None:
        row.user_id = data.get("user_id")
        row.candidate_id = data.get("candidate_id")
        row.target_company_id = data.get("target_company_id")
        row.target_role_id = data.get("target_role_id")
        row.started_at = _coerce_datetime(data.get("started_at") or data.get("created_at")) or row.started_at or _now()
        row.completed_at = _coerce_datetime(data.get("completed_at"))
        row.overall_readiness_score = data.get("overall_readiness_score")
        row.skill = data.get("skill")
        row.sub_domain = data.get("sub_domain")
        row.status = data.get("status") or "active"
        row.current_difficulty = data.get("current_difficulty")
        row.current_skill = data.get("current_skill")
        row.last_round = int(data.get("last_round") or 1)
        row.skills_json = data.get("skills") or ([data["skill"]] if data.get("skill") else [])
        row.rounds_per_skill = int(data.get("rounds_per_skill") or 3)
        row.total_rounds = data.get("total_rounds")
        row.template_id = data.get("template_id")

    @staticmethod
    def _replace_rounds(session, row: SessionRow, rounds: list[dict[str, Any]]) -> None:
        row.rounds.clear()
        session.flush()
        for round_doc in rounds:
            breakdown = round_doc.get("scoring_breakdown") or {}
            question_context = round_doc.get("question_context") or {}
            question_id = str(question_context.get("id") or question_context.get("question_id") or "") or None
            row.rounds.append(
                RoundRow(
                    session_id=row.id,
                    round_number=int(round_doc.get("round") or round_doc.get("round_number") or 1),
                    question_id=question_id,
                    answer_text=round_doc.get("answer_text"),
                    scoring_breakdown_json=breakdown,
                    confidence_score=round_doc.get("engagement_confidence"),
                    guard_applied=round_doc.get("guard_applied"),
                    feedback_json=round_doc.get("feedback") or {},
                    engagement_label=round_doc.get("engagement_label"),
                    engagement_delta=round_doc.get("engagement_delta"),
                    skill_text=round_doc.get("skill"),
                    # or-fallbacks: pre-Phase-1 round documents have no type
                    # keys, and every one of them is a technical short answer.
                    round_type=round_doc.get("round_type") or "technical_short_answer",
                    artifact_json=round_doc.get("artifact_json") or {},
                    config_json=round_doc.get("config_json") or {},
                    question=round_doc.get("question"),
                    difficulty=round_doc.get("difficulty"),
                    difficulty_change=round_doc.get("difficulty_change"),
                    nlp_score=round_doc.get("nlp_score"),
                    svm_label=round_doc.get("svm_label"),
                    kg_score=round_doc.get("kg_score"),
                    kg_label=round_doc.get("kg_label"),
                    covered_concepts=round_doc.get("covered_concepts") or breakdown.get("covered_concepts") or [],
                    missing_concepts=round_doc.get("missing_concepts") or breakdown.get("missing_concepts") or [],
                    ner_entities=round_doc.get("ner_entities") or [],
                    final_score=round_doc.get("final_score"),
                    elo_before=round_doc.get("elo_before"),
                    elo_after=round_doc.get("elo_after"),
                    question_context=question_context,
                    created_at=_coerce_datetime(round_doc.get("created_at")) or _now(),
                )
            )

    @staticmethod
    def _to_doc(row: SessionRow) -> dict[str, Any]:
        rounds = []
        for round_row in sorted(row.rounds, key=lambda item: item.round_number):
            rounds.append(
                {
                    "round": round_row.round_number,
                    "skill": round_row.skill_text,
                    "round_type": round_row.round_type or "technical_short_answer",
                    "artifact_json": round_row.artifact_json or {},
                    "config_json": round_row.config_json or {},
                    "question": round_row.question,
                    "answer_text": round_row.answer_text,
                    "nlp_score": round_row.nlp_score,
                    "svm_label": round_row.svm_label,
                    "kg_score": round_row.kg_score,
                    "kg_label": round_row.kg_label,
                    "covered_concepts": round_row.covered_concepts or [],
                    "missing_concepts": round_row.missing_concepts or [],
                    "ner_entities": round_row.ner_entities or [],
                    "final_score": round_row.final_score,
                    "difficulty": round_row.difficulty or "medium",
                    "difficulty_change": round_row.difficulty_change,
                    "feedback": round_row.feedback_json or {"content": [], "strengths": [], "next_step": ""},
                    "score_explanation": (round_row.scoring_breakdown_json or {}).get("score_explanation", {}),
                    "elo_before": round_row.elo_before,
                    "elo_after": round_row.elo_after,
                    "engagement_label": round_row.engagement_label,
                    "engagement_confidence": round_row.confidence_score,
                    "engagement_delta": round_row.engagement_delta,
                    "scoring_breakdown": round_row.scoring_breakdown_json or {},
                    "guard_applied": round_row.guard_applied,
                    "question_context": round_row.question_context or {},
                    "created_at": round_row.created_at,
                }
            )
        return {
            "session_id": row.id,
            "id": row.id,
            "user_id": row.user_id,
            "candidate_id": row.candidate_id,
            "target_company_id": row.target_company_id,
            "target_role_id": row.target_role_id,
            "started_at": row.started_at,
            "created_at": row.started_at,
            "completed_at": row.completed_at,
            "overall_readiness_score": row.overall_readiness_score,
            "skill": row.skill,
            "sub_domain": row.sub_domain,
            "status": row.status,
            "current_difficulty": row.current_difficulty,
            "current_skill": row.current_skill,
            "last_round": row.last_round,
            "skills": row.skills_json or [],
            "rounds_per_skill": row.rounds_per_skill,
            "total_rounds": row.total_rounds,
            "template_id": row.template_id,
            "rounds": rounds,
        }


class SQLAlchemyDatabase:
    def __init__(self) -> None:
        self._collections = {
            "candidates": _CandidateCollection(),
            "users": _UserCollection(),
            "sessions": _SessionCollection(),
        }

    def __getitem__(self, name: str):
        try:
            return self._collections[name]
        except KeyError as exc:
            raise KeyError(
                f"Unknown collection '{name}'. The document-style store exposes "
                f"{sorted(self._collections)}; the remaining Phase 2 tables "
                "(companies, roles, skills, student skill graph, concept mastery) "
                "are accessed through the ORM models in backend.db.sqlalchemy_models "
                "via session_scope()."
            ) from exc


@lru_cache(maxsize=1)
def get_sqlalchemy_database() -> SQLAlchemyDatabase:
    return SQLAlchemyDatabase()
