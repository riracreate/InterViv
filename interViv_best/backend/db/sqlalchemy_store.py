from __future__ import annotations

import copy
from contextlib import contextmanager
from contextvars import ContextVar
from datetime import datetime, timezone
from functools import lru_cache
from typing import Any, Iterator

from backend.config import get_settings

from .sqlalchemy_models import (
    AnswerDraftRow,
    AssistanceEventRow,
    Base,
    BookmarkRow,
    BuilderDraftRow,
    CandidateRow,
    CodingSubmissionRow,
    MLPrimitivesAttemptRow,
    NarrationJobRow,
    PracticePresetRow,
    RetrySetRow,
    ReviewScheduleRow,
    RoundRow,
    SessionRow,
    SystemDesignAttemptRow,
    TargetContextRow,
    TeachingExposureRow,
    UserRow,
)


class SQLAlchemyDatabaseError(RuntimeError):
    pass


# Ambient transaction for ambient_session(): when set, session_scope() joins
# it instead of opening a committing scope. Context-local, never global.
_ambient_session: ContextVar = ContextVar("interviv_ambient_session", default=None)


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
    # Inside ambient_session() every collection op joins the shared
    # transaction instead of committing on its own. The exit flush makes
    # this op's writes visible to the next op's reads (autoflush is off):
    # without it, update-after-insert in one transaction would silently
    # match nothing. Outside ambient_session() the behavior is unchanged.
    ambient = _ambient_session.get()
    if ambient is not None:
        yield ambient
        ambient.flush()
        return
    session = _sessionmaker()()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


@contextmanager
def ambient_session():
    """Share one SQLAlchemy transaction across nested ``session_scope`` calls.

    The outermost scope still owns commit/rollback; inner scopes only flush.
    Nesting is safe (inner blocks join the outer transaction). Not
    re-entrant across threads: one block, one thread, short pure-persistence
    work only.
    """
    with session_scope() as session:
        token = _ambient_session.set(session)
        try:
            yield session
        finally:
            _ambient_session.reset(token)


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


def _as_utc(value: datetime | None) -> datetime | None:
    """Restore UTC on a SQLite read.

    Every writer stores UTC; SQLite's DateTime keeps the wall time and
    drops tzinfo. A naive deadline serializes without an offset and the
    browser reads it as local time, so a fresh round shows 00:00.
    """
    if value is not None and value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


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
        row.round_plan_json = data.get("round_plan")
        row.round_config_json = data.get("round_config")
        row.block_plan_json = data.get("block_plan")
        row.expanded_plan_json = data.get("expanded_plan")
        row.allow_unknown_topic_fallback = data.get("allow_unknown_topic_fallback")
        row.progression_blocked_reason = data.get("progression_blocked_reason")
        row.practice_mode = data.get("practice_mode")
        row.allow_optional_follow_ups = data.get("allow_optional_follow_ups")

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
                    started_at=_coerce_datetime(round_doc.get("started_at")),
                    expires_at=_coerce_datetime(round_doc.get("expires_at")),
                    status=round_doc.get("status") or ("submitted" if round_doc.get("answer_text") else "in_progress"),
                    submitted_at=_coerce_datetime(round_doc.get("submitted_at")),
                    block_id=round_doc.get("block_id"),
                    block_position=round_doc.get("block_position"),
                    block_category=round_doc.get("block_category"),
                    block_index=round_doc.get("block_index"),
                    block_total=round_doc.get("block_total"),
                    assisted=round_doc.get("assisted"),
                    assistance_kinds=round_doc.get("assistance_kinds"),
                    attempt_snapshot_json=round_doc.get("attempt_snapshot"),
                    assessment_eligibility=round_doc.get("assessment_eligibility"),
                    eligibility_policy_version=round_doc.get(
                        "eligibility_policy_version"
                    ),
                    eligibility_exclusion_reasons=round_doc.get(
                        "eligibility_exclusion_reasons"
                    ),
                    eligibility_exposure_ids=round_doc.get(
                        "eligibility_exposure_ids"
                    ),
                    is_follow_up=round_doc.get("is_follow_up"),
                    follow_up_parent_round=round_doc.get("follow_up_parent_round"),
                    follow_up_identity=round_doc.get("follow_up_identity"),
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
                    "scoring_mode": (round_row.scoring_breakdown_json or {}).get("scoring_mode"),
                    "evidence_kind": (round_row.scoring_breakdown_json or {}).get("evidence_kind"),
                    "evaluation_mode": (
                        (round_row.scoring_breakdown_json or {}).get("evaluation_mode")
                        or (round_row.artifact_json or {}).get("evaluation_mode")
                    ),
                    "guard_applied": round_row.guard_applied,
                    "question_context": round_row.question_context or {},
                    "created_at": _as_utc(round_row.created_at),
                    "started_at": _as_utc(round_row.started_at),
                    "expires_at": _as_utc(round_row.expires_at),
                    "status": round_row.status or "submitted",
                    "submitted_at": _as_utc(round_row.submitted_at),
                    "block_id": round_row.block_id,
                    "block_position": round_row.block_position,
                    "block_category": round_row.block_category,
                    "block_index": round_row.block_index,
                    "block_total": round_row.block_total,
                    "assisted": round_row.assisted,
                    "assistance_kinds": round_row.assistance_kinds or [],
                    "attempt_snapshot": round_row.attempt_snapshot_json,
                    "assessment_eligibility": round_row.assessment_eligibility,
                    "eligibility_policy_version": round_row.eligibility_policy_version,
                    "eligibility_exclusion_reasons": (
                        round_row.eligibility_exclusion_reasons or []
                    ),
                    "eligibility_exposure_ids": (
                        round_row.eligibility_exposure_ids or []
                    ),
                    "is_follow_up": round_row.is_follow_up,
                    "follow_up_parent_round": round_row.follow_up_parent_round,
                    "follow_up_identity": round_row.follow_up_identity,
                }
            )
        return {
            "session_id": row.id,
            "id": row.id,
            "user_id": row.user_id,
            "candidate_id": row.candidate_id,
            "target_company_id": row.target_company_id,
            "target_role_id": row.target_role_id,
            "started_at": _as_utc(row.started_at),
            "created_at": _as_utc(row.started_at),
            "completed_at": _as_utc(row.completed_at),
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
            "round_plan": row.round_plan_json,
            "round_config": row.round_config_json,
            "block_plan": row.block_plan_json,
            "expanded_plan": row.expanded_plan_json,
            # Legacy rows predate the flag; they were created under the old
            # always-fill selection, so missing means fallback allowed.
            "allow_unknown_topic_fallback": (
                row.allow_unknown_topic_fallback
                if row.allow_unknown_topic_fallback is not None
                else True
            ),
            "progression_blocked_reason": row.progression_blocked_reason,
            "practice_mode": row.practice_mode,
            "allow_optional_follow_ups": row.allow_optional_follow_ups,
            "rounds": rounds,
        }


class _PresetCollection:
    """Document view over practice_presets (Phase B saved presets)."""

    @staticmethod
    def _field_columns() -> dict[str, Any]:
        return {"id": PracticePresetRow.id, "user_id": PracticePresetRow.user_id}

    def find_one(self, query: dict, projection: dict | None = None) -> dict | None:
        with session_scope() as session:
            rows = _filtered_rows(session, PracticePresetRow, self._field_columns(), query)
            for row in rows:
                doc = self._to_doc(row)
                if _matches(doc, query):
                    return _project(doc, projection)
        return None

    def find(self, query: dict | None = None) -> Iterator[dict]:
        with session_scope() as session:
            docs = [
                self._to_doc(row)
                for row in _filtered_rows(session, PracticePresetRow, self._field_columns(), query)
            ]
        return iter([doc for doc in docs if not query or _matches(doc, query)])

    def insert_one(self, doc: dict) -> _InsertResult:
        data = _json_ready(doc)
        with session_scope() as session:
            row = PracticePresetRow(
                id=data["id"],
                user_id=data["user_id"],
                name=data["name"],
                version=int(data.get("version") or 1),
                blocks_json=data.get("blocks") or [],
                created_at=_coerce_datetime(data.get("created_at")) or _now(),
                updated_at=_coerce_datetime(data.get("updated_at")) or _now(),
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
            rows = _filtered_rows(session, PracticePresetRow, self._field_columns(), query)
            for row in rows:
                if _matches(self._to_doc(row), query):
                    session.delete(row)
                    return

    def count_documents(self, query: dict) -> int:
        return sum(1 for _ in self.find(query))

    @staticmethod
    def _to_doc(row: PracticePresetRow) -> dict[str, Any]:
        return {
            "id": row.id,
            "user_id": row.user_id,
            "name": row.name,
            "version": row.version,
            "blocks": row.blocks_json or [],
            "created_at": row.created_at,
            "updated_at": row.updated_at,
        }


class _BuilderDraftCollection:
    """Document view over builder_drafts (one autosaved draft per user)."""

    @staticmethod
    def _field_columns() -> dict[str, Any]:
        return {"user_id": BuilderDraftRow.user_id}

    def find_one(self, query: dict, projection: dict | None = None) -> dict | None:
        with session_scope() as session:
            rows = _filtered_rows(session, BuilderDraftRow, self._field_columns(), query)
            for row in rows:
                doc = self._to_doc(row)
                if _matches(doc, query):
                    return _project(doc, projection)
        return None

    def find(self, query: dict | None = None) -> Iterator[dict]:
        with session_scope() as session:
            docs = [
                self._to_doc(row)
                for row in _filtered_rows(session, BuilderDraftRow, self._field_columns(), query)
            ]
        return iter([doc for doc in docs if not query or _matches(doc, query)])

    def insert_one(self, doc: dict) -> _InsertResult:
        data = _json_ready(doc)
        with session_scope() as session:
            row = BuilderDraftRow(
                user_id=data["user_id"],
                version=int(data.get("version") or 1),
                blocks_json=data.get("blocks") or [],
                updated_at=_coerce_datetime(data.get("updated_at")) or _now(),
            )
            session.merge(row)
        return _InsertResult(data["user_id"])

    def update_one(self, query: dict, update: dict, upsert: bool = False) -> _UpdateResult:
        doc = self.find_one(query)
        matched = 1 if doc else 0
        if not doc:
            if not upsert:
                return _UpdateResult(0, 0)
            doc = dict(query)
        modified = _apply_update_dict(doc, update)
        if doc.get("user_id"):
            self.insert_one(doc)
        return _UpdateResult(matched, 1 if modified else 0)

    def delete_one(self, query: dict) -> None:
        with session_scope() as session:
            rows = _filtered_rows(session, BuilderDraftRow, self._field_columns(), query)
            for row in rows:
                if _matches(self._to_doc(row), query):
                    session.delete(row)
                    return

    def count_documents(self, query: dict) -> int:
        return sum(1 for _ in self.find(query))

    @staticmethod
    def _to_doc(row: BuilderDraftRow) -> dict[str, Any]:
        return {
            "user_id": row.user_id,
            "version": row.version,
            "blocks": row.blocks_json or [],
            "updated_at": row.updated_at,
        }


class _AnswerDraftCollection:
    """Document view over answer_drafts (keyed by session + round)."""

    @staticmethod
    def _field_columns() -> dict[str, Any]:
        return {
            "session_id": AnswerDraftRow.session_id,
            "round": AnswerDraftRow.round_number,
            "round_number": AnswerDraftRow.round_number,
            "user_id": AnswerDraftRow.user_id,
        }

    def find_one(self, query: dict, projection: dict | None = None) -> dict | None:
        with session_scope() as session:
            rows = _filtered_rows(session, AnswerDraftRow, self._field_columns(), query)
            for row in rows:
                doc = self._to_doc(row)
                if _matches(doc, query):
                    return _project(doc, projection)
        return None

    def find(self, query: dict | None = None) -> Iterator[dict]:
        with session_scope() as session:
            docs = [
                self._to_doc(row)
                for row in _filtered_rows(session, AnswerDraftRow, self._field_columns(), query)
            ]
        return iter([doc for doc in docs if not query or _matches(doc, query)])

    def insert_one(self, doc: dict) -> _InsertResult:
        data = _json_ready(doc)
        with session_scope() as session:
            row = AnswerDraftRow(
                session_id=data["session_id"],
                round_number=int(data.get("round", data.get("round_number"))),
                user_id=data["user_id"],
                draft_json=data.get("draft") or {},
                updated_at=_coerce_datetime(data.get("updated_at")) or _now(),
            )
            session.merge(row)
        return _InsertResult((data["session_id"], data.get("round")))

    def update_one(self, query: dict, update: dict, upsert: bool = False) -> _UpdateResult:
        doc = self.find_one(query)
        matched = 1 if doc else 0
        if not doc:
            if not upsert:
                return _UpdateResult(0, 0)
            doc = dict(query)
        modified = _apply_update_dict(doc, update)
        if doc.get("session_id") and doc.get("round") is not None:
            self.insert_one(doc)
        return _UpdateResult(matched, 1 if modified else 0)

    def delete_one(self, query: dict) -> None:
        with session_scope() as session:
            rows = _filtered_rows(session, AnswerDraftRow, self._field_columns(), query)
            for row in rows:
                if _matches(self._to_doc(row), query):
                    session.delete(row)
                    return

    def count_documents(self, query: dict) -> int:
        return sum(1 for _ in self.find(query))

    @staticmethod
    def _to_doc(row: AnswerDraftRow) -> dict[str, Any]:
        return {
            "session_id": row.session_id,
            "round": row.round_number,
            "user_id": row.user_id,
            "draft": row.draft_json or {},
            "updated_at": row.updated_at,
        }


class _CodingSubmissionCollection:
    """Append-only view over coding_submissions (one row per attempt)."""

    @staticmethod
    def _field_columns() -> dict[str, Any]:
        return {
            "id": CodingSubmissionRow.id,
            "user_id": CodingSubmissionRow.user_id,
            "session_id": CodingSubmissionRow.session_id,
            "round": CodingSubmissionRow.round_number,
            "round_number": CodingSubmissionRow.round_number,
            "problem_id": CodingSubmissionRow.problem_id,
            "status": CodingSubmissionRow.status,
        }

    def find_one(self, query: dict, projection: dict | None = None) -> dict | None:
        with session_scope() as session:
            rows = _filtered_rows(session, CodingSubmissionRow, self._field_columns(), query)
            for row in rows:
                doc = self._to_doc(row)
                if _matches(doc, query):
                    return _project(doc, projection)
        return None

    def find(self, query: dict | None = None) -> Iterator[dict]:
        with session_scope() as session:
            docs = [
                self._to_doc(row)
                for row in _filtered_rows(session, CodingSubmissionRow, self._field_columns(), query)
            ]
        return iter([doc for doc in docs if not query or _matches(doc, query)])

    def insert_one(self, doc: dict) -> _InsertResult:
        data = _json_ready(doc)
        with session_scope() as session:
            row = CodingSubmissionRow(
                id=str(data.get("id") or ""),
                user_id=data["user_id"],
                session_id=data["session_id"],
                round_number=int(data.get("round", data.get("round_number"))),
                problem_id=str(data.get("problem_id") or ""),
                language=str(data.get("language") or "python"),
                source=str(data.get("source") or ""),
                truncated=bool(data.get("truncated")),
                status=str(data.get("status") or ""),
                score=data.get("score"),
                visible_passed=data.get("visible_passed"),
                visible_total=data.get("visible_total"),
                hidden_passed=data.get("hidden_passed"),
                hidden_total=data.get("hidden_total"),
                error=data.get("error"),
                created_at=_coerce_datetime(data.get("created_at")) or _now(),
            )
            session.merge(row)
        return _InsertResult(data.get("id"))

    def count_documents(self, query: dict) -> int:
        return sum(1 for _ in self.find(query))

    @staticmethod
    def _to_doc(row: CodingSubmissionRow) -> dict[str, Any]:
        return {
            "id": row.id,
            "user_id": row.user_id,
            "session_id": row.session_id,
            "round": row.round_number,
            "problem_id": row.problem_id,
            "language": row.language,
            "source": row.source,
            "truncated": row.truncated,
            "status": row.status,
            "score": row.score,
            "visible_passed": row.visible_passed,
            "visible_total": row.visible_total,
            "hidden_passed": row.hidden_passed,
            "hidden_total": row.hidden_total,
            "error": row.error,
            "created_at": row.created_at,
        }


class _TargetContextCollection:
    """Single shared target context per user (upsert by user_id)."""

    @staticmethod
    def _field_columns() -> dict[str, Any]:
        return {
            "user_id": TargetContextRow.user_id,
            "company_id": TargetContextRow.company_id,
            "role_id": TargetContextRow.role_id,
            "job_id": TargetContextRow.job_id,
            "resume_ref": TargetContextRow.resume_ref,
        }

    def find_one(self, query: dict, projection: dict | None = None) -> dict | None:
        with session_scope() as session:
            rows = _filtered_rows(session, TargetContextRow, self._field_columns(), query)
            for row in rows:
                doc = self._to_doc(row)
                if _matches(doc, query):
                    return _project(doc, projection)
        return None

    def find(self, query: dict | None = None) -> Iterator[dict]:
        with session_scope() as session:
            docs = [
                self._to_doc(row)
                for row in _filtered_rows(session, TargetContextRow, self._field_columns(), query)
            ]
        return iter([doc for doc in docs if not query or _matches(doc, query)])

    def insert_one(self, doc: dict) -> _InsertResult:
        data = _json_ready(doc)
        with session_scope() as session:
            row = TargetContextRow(
                user_id=data["user_id"],
                company_id=data.get("company_id"),
                role_id=data.get("role_id"),
                job_id=data.get("job_id"),
                jd_source=data.get("jd_source"),
                jd_text=data.get("jd_text"),
                resume_ref=data.get("resume_ref"),
                updated_at=_coerce_datetime(data.get("updated_at")) or _now(),
            )
            session.merge(row)
        return _InsertResult(data["user_id"])

    def update_one(self, query: dict, update: dict, upsert: bool = False) -> _UpdateResult:
        doc = self.find_one(query)
        matched = 1 if doc else 0
        if not doc:
            if not upsert:
                return _UpdateResult(0, 0)
            doc = dict(query)
        modified = _apply_update_dict(doc, update)
        if doc.get("user_id"):
            self.insert_one(doc)
        return _UpdateResult(matched, 1 if modified else 0)

    def delete_one(self, query: dict) -> None:
        with session_scope() as session:
            rows = _filtered_rows(session, TargetContextRow, self._field_columns(), query)
            for row in rows:
                if _matches(self._to_doc(row), query):
                    session.delete(row)
                    return

    def count_documents(self, query: dict) -> int:
        return sum(1 for _ in self.find(query))

    @staticmethod
    def _to_doc(row: TargetContextRow) -> dict[str, Any]:
        return {
            "user_id": row.user_id,
            "company_id": row.company_id,
            "role_id": row.role_id,
            "job_id": row.job_id,
            "jd_source": row.jd_source,
            "jd_text": row.jd_text,
            "resume_ref": row.resume_ref,
            "updated_at": row.updated_at,
        }


class _RetrySetCollection:
    """Persisted retry sets keyed by id (user-scoped reads)."""

    @staticmethod
    def _field_columns() -> dict[str, Any]:
        return {
            "id": RetrySetRow.id,
            "user_id": RetrySetRow.user_id,
            "source": RetrySetRow.source,
        }

    def find_one(self, query: dict, projection: dict | None = None) -> dict | None:
        with session_scope() as session:
            rows = _filtered_rows(session, RetrySetRow, self._field_columns(), query)
            for row in rows:
                doc = self._to_doc(row)
                if _matches(doc, query):
                    return _project(doc, projection)
        return None

    def find(self, query: dict | None = None) -> Iterator[dict]:
        with session_scope() as session:
            docs = [
                self._to_doc(row)
                for row in _filtered_rows(session, RetrySetRow, self._field_columns(), query)
            ]
        return iter([doc for doc in docs if not query or _matches(doc, query)])

    def insert_one(self, doc: dict) -> _InsertResult:
        data = _json_ready(doc)
        with session_scope() as session:
            row = RetrySetRow(
                id=str(data.get("id") or ""),
                user_id=data["user_id"],
                name=str(data.get("name") or ""),
                items_json=data.get("items") or data.get("items_json") or [],
                source=str(data.get("source") or "missed-topics"),
                created_at=_coerce_datetime(data.get("created_at")) or _now(),
            )
            session.merge(row)
        return _InsertResult(data.get("id"))

    def delete_one(self, query: dict) -> None:
        with session_scope() as session:
            rows = _filtered_rows(session, RetrySetRow, self._field_columns(), query)
            for row in rows:
                if _matches(self._to_doc(row), query):
                    session.delete(row)
                    return

    def count_documents(self, query: dict) -> int:
        return sum(1 for _ in self.find(query))

    @staticmethod
    def _to_doc(row: RetrySetRow) -> dict[str, Any]:
        return {
            "id": row.id,
            "user_id": row.user_id,
            "name": row.name,
            "items": row.items_json or [],
            "source": row.source,
            "created_at": row.created_at,
        }


class _BookmarkCollection:
    """Bookmarks keyed by user + item identity (toggle by delete/insert)."""

    @staticmethod
    def _field_columns() -> dict[str, Any]:
        return {
            "user_id": BookmarkRow.user_id,
            "item_type": BookmarkRow.item_type,
            "item_id": BookmarkRow.item_id,
        }

    def find_one(self, query: dict, projection: dict | None = None) -> dict | None:
        with session_scope() as session:
            rows = _filtered_rows(session, BookmarkRow, self._field_columns(), query)
            for row in rows:
                doc = self._to_doc(row)
                if _matches(doc, query):
                    return _project(doc, projection)
        return None

    def find(self, query: dict | None = None) -> Iterator[dict]:
        with session_scope() as session:
            docs = [
                self._to_doc(row)
                for row in _filtered_rows(session, BookmarkRow, self._field_columns(), query)
            ]
        return iter([doc for doc in docs if not query or _matches(doc, query)])

    def insert_one(self, doc: dict) -> _InsertResult:
        data = _json_ready(doc)
        with session_scope() as session:
            row = BookmarkRow(
                user_id=data["user_id"],
                item_type=str(data.get("item_type") or ""),
                item_id=str(data.get("item_id") or ""),
                created_at=_coerce_datetime(data.get("created_at")) or _now(),
            )
            session.merge(row)
        return _InsertResult((data["user_id"], data.get("item_type"), data.get("item_id")))

    def delete_one(self, query: dict) -> None:
        with session_scope() as session:
            rows = _filtered_rows(session, BookmarkRow, self._field_columns(), query)
            for row in rows:
                if _matches(self._to_doc(row), query):
                    session.delete(row)
                    return

    def count_documents(self, query: dict) -> int:
        return sum(1 for _ in self.find(query))

    @staticmethod
    def _to_doc(row: BookmarkRow) -> dict[str, Any]:
        return {
            "user_id": row.user_id,
            "item_type": row.item_type,
            "item_id": row.item_id,
            "created_at": row.created_at,
        }


class _AssistanceEventCollection:
    """Append-only hint/solution-use events (one row per view)."""

    @staticmethod
    def _field_columns() -> dict[str, Any]:
        return {
            "id": AssistanceEventRow.id,
            "user_id": AssistanceEventRow.user_id,
            "item_type": AssistanceEventRow.item_type,
            "item_id": AssistanceEventRow.item_id,
            "kind": AssistanceEventRow.kind,
            "session_id": AssistanceEventRow.session_id,
            "round": AssistanceEventRow.round,
        }

    def find_one(self, query: dict, projection: dict | None = None) -> dict | None:
        with session_scope() as session:
            rows = _filtered_rows(session, AssistanceEventRow, self._field_columns(), query)
            for row in rows:
                doc = self._to_doc(row)
                if _matches(doc, query):
                    return _project(doc, projection)
        return None

    def find(self, query: dict | None = None) -> Iterator[dict]:
        with session_scope() as session:
            docs = [
                self._to_doc(row)
                for row in _filtered_rows(session, AssistanceEventRow, self._field_columns(), query)
            ]
        return iter([doc for doc in docs if not query or _matches(doc, query)])

    def insert_one(self, doc: dict) -> _InsertResult:
        data = _json_ready(doc)
        with session_scope() as session:
            row = AssistanceEventRow(
                id=str(data.get("id") or ""),
                user_id=data["user_id"],
                item_type=str(data.get("item_type") or ""),
                item_id=str(data.get("item_id") or ""),
                kind=str(data.get("kind") or ""),
                session_id=data.get("session_id"),
                round=data.get("round"),
                created_at=_coerce_datetime(data.get("created_at")) or _now(),
            )
            session.merge(row)
        return _InsertResult(data.get("id"))

    def count_documents(self, query: dict) -> int:
        return sum(1 for _ in self.find(query))

    @staticmethod
    def _to_doc(row: AssistanceEventRow) -> dict[str, Any]:
        return {
            "id": row.id,
            "user_id": row.user_id,
            "item_type": row.item_type,
            "item_id": row.item_id,
            "kind": row.kind,
            "session_id": row.session_id,
            "round": row.round,
            "created_at": row.created_at,
        }


class _TeachingExposureCollection:
    """Phase 4A append-only teaching deliveries; idempotent on delivery_id."""

    @staticmethod
    def _field_columns() -> dict[str, Any]:
        return {
            "id": TeachingExposureRow.id,
            "delivery_id": TeachingExposureRow.delivery_id,
            "owner_key": TeachingExposureRow.owner_key,
            "user_id": TeachingExposureRow.user_id,
            "session_id": TeachingExposureRow.session_id,
            "item_id": TeachingExposureRow.item_id,
            "content_kind": TeachingExposureRow.content_kind,
        }

    def find_one(self, query: dict, projection: dict | None = None) -> dict | None:
        with session_scope() as session:
            rows = _filtered_rows(
                session, TeachingExposureRow, self._field_columns(), query
            )
            for row in rows:
                doc = self._to_doc(row)
                if _matches(doc, query):
                    return _project(doc, projection)
        return None

    def find(self, query: dict | None = None) -> Iterator[dict]:
        with session_scope() as session:
            docs = [
                self._to_doc(row)
                for row in _filtered_rows(
                    session, TeachingExposureRow, self._field_columns(), query
                )
            ]
        return iter([doc for doc in docs if not query or _matches(doc, query)])

    def insert_one(self, doc: dict) -> _InsertResult:
        data = _json_ready(doc)
        with session_scope() as session:
            delivery_id = str(data.get("delivery_id") or "")
            if delivery_id:
                existing = (
                    session.query(TeachingExposureRow)
                    .filter(TeachingExposureRow.delivery_id == delivery_id)
                    .first()
                )
                if existing is not None:
                    return _InsertResult(existing.id)
            row = TeachingExposureRow(
                id=str(data.get("id") or ""),
                delivery_id=delivery_id,
                content_id=str(data.get("content_id") or ""),
                owner_key=str(data.get("owner_key") or ""),
                user_id=data.get("user_id"),
                session_id=data.get("session_id"),
                block_id=data.get("block_id"),
                round=data.get("round"),
                item_type=data.get("item_type"),
                item_id=data.get("item_id"),
                content_kind=str(data.get("content_kind") or ""),
                policy_version=data.get("policy_version"),
                concept_topic_scope_json=data.get("concept_topic_scope"),
                delivered_at=_coerce_datetime(data.get("delivered_at")) or _now(),
                delivery_order=int(data.get("delivery_order") or 0),
                created_at=_coerce_datetime(data.get("created_at")) or _now(),
            )
            session.add(row)
        return _InsertResult(data.get("id"))

    def count_documents(self, query: dict) -> int:
        return sum(1 for _ in self.find(query))

    @staticmethod
    def _to_doc(row: TeachingExposureRow) -> dict[str, Any]:
        return {
            "id": row.id,
            "delivery_id": row.delivery_id,
            "content_id": row.content_id,
            "owner_key": row.owner_key,
            "user_id": row.user_id,
            "session_id": row.session_id,
            "block_id": row.block_id,
            "round": row.round,
            "item_type": row.item_type,
            "item_id": row.item_id,
            "content_kind": row.content_kind,
            "policy_version": row.policy_version,
            "concept_topic_scope": row.concept_topic_scope_json or {},
            "delivered_at": row.delivered_at,
            "delivery_order": row.delivery_order,
            "created_at": row.created_at,
        }


class _SystemDesignAttemptCollection:
    """Append-only view over system_design_attempts."""

    @staticmethod
    def _field_columns() -> dict[str, Any]:
        return {
            "id": SystemDesignAttemptRow.id,
            "user_id": SystemDesignAttemptRow.user_id,
            "session_id": SystemDesignAttemptRow.session_id,
            "round": SystemDesignAttemptRow.round_number,
            "round_number": SystemDesignAttemptRow.round_number,
            "prompt_id": SystemDesignAttemptRow.prompt_id,
            "status": SystemDesignAttemptRow.status,
        }

    def find_one(self, query: dict, projection: dict | None = None) -> dict | None:
        with session_scope() as session:
            rows = _filtered_rows(
                session, SystemDesignAttemptRow, self._field_columns(), query
            )
            for row in rows:
                doc = self._to_doc(row)
                if _matches(doc, query):
                    return _project(doc, projection)
        return None

    def find(self, query: dict | None = None) -> Iterator[dict]:
        with session_scope() as session:
            docs = [
                self._to_doc(row)
                for row in _filtered_rows(
                    session, SystemDesignAttemptRow, self._field_columns(), query
                )
            ]
        return iter([doc for doc in docs if not query or _matches(doc, query)])

    def insert_one(self, doc: dict) -> _InsertResult:
        data = _json_ready(doc)
        with session_scope() as session:
            row = SystemDesignAttemptRow(
                id=str(data.get("id") or ""),
                user_id=data["user_id"],
                session_id=data["session_id"],
                round_number=int(data.get("round", data.get("round_number"))),
                prompt_id=str(data.get("prompt_id") or ""),
                answer_text=str(data.get("answer_text") or ""),
                rubric_json=data.get("rubric_json") or {},
                evaluation_mode=str(
                    data.get("evaluation_mode") or "structured_self_assessment"
                ),
                status=str(data.get("status") or ""),
                score=data.get("score"),
                incomplete=bool(data.get("incomplete")),
                created_at=_coerce_datetime(data.get("created_at")) or _now(),
            )
            session.merge(row)
        return _InsertResult(data.get("id"))

    def delete_one(self, query: dict) -> None:
        with session_scope() as session:
            rows = list(
                _filtered_rows(
                    session, SystemDesignAttemptRow, self._field_columns(), query
                )
            )
            for row in rows:
                doc = self._to_doc(row)
                if _matches(doc, query):
                    session.delete(row)
                    return

    def count_documents(self, query: dict) -> int:
        return sum(1 for _ in self.find(query))

    @staticmethod
    def _to_doc(row: SystemDesignAttemptRow) -> dict[str, Any]:
        return {
            "id": row.id,
            "user_id": row.user_id,
            "session_id": row.session_id,
            "round": row.round_number,
            "prompt_id": row.prompt_id,
            "answer_text": row.answer_text,
            "rubric_json": row.rubric_json or {},
            "evaluation_mode": row.evaluation_mode,
            "status": row.status,
            "score": row.score,
            "incomplete": row.incomplete,
            "created_at": row.created_at,
        }


class _ReviewScheduleCollection:
    """Phase I spaced-review schedule rows (user + item identity)."""

    @staticmethod
    def _field_columns() -> dict[str, Any]:
        return {
            "id": ReviewScheduleRow.id,
            "user_id": ReviewScheduleRow.user_id,
            "item_type": ReviewScheduleRow.item_type,
            "item_id": ReviewScheduleRow.item_id,
        }

    def find_one(self, query: dict, projection: dict | None = None) -> dict | None:
        with session_scope() as session:
            rows = _filtered_rows(session, ReviewScheduleRow, self._field_columns(), query)
            for row in rows:
                doc = self._to_doc(row)
                if _matches(doc, query):
                    return _project(doc, projection)
        return None

    def find(self, query: dict | None = None) -> Iterator[dict]:
        with session_scope() as session:
            docs = [
                self._to_doc(row)
                for row in _filtered_rows(session, ReviewScheduleRow, self._field_columns(), query)
            ]
        return iter([doc for doc in docs if not query or _matches(doc, query)])

    def insert_one(self, doc: dict) -> _InsertResult:
        data = _json_ready(doc)
        with session_scope() as session:
            row = ReviewScheduleRow(
                id=str(data.get("id") or ""),
                user_id=str(data["user_id"]),
                item_type=str(data.get("item_type") or ""),
                item_id=str(data.get("item_id") or ""),
                skill=data.get("skill"),
                title=data.get("title"),
                source_session_id=data.get("source_session_id"),
                source_round=data.get("source_round"),
                originating_assisted=data.get("originating_assisted"),
                miss_reason=data.get("miss_reason"),
                interval_days=int(data.get("interval_days") or 1),
                interval_index=int(data.get("interval_index") or 0),
                due_at=_coerce_datetime(data.get("due_at")) or _now(),
                review_count=int(data.get("review_count") or 0),
                last_reviewed_at=_coerce_datetime(data.get("last_reviewed_at")),
                last_outcome=data.get("last_outcome"),
                last_review_assisted=data.get("last_review_assisted"),
                review_available=bool(
                    True if data.get("review_available") is None else data.get("review_available")
                ),
                unavailable_reason=data.get("unavailable_reason"),
                created_at=_coerce_datetime(data.get("created_at")) or _now(),
                updated_at=_coerce_datetime(data.get("updated_at")) or _now(),
            )
            session.merge(row)
        return _InsertResult(data.get("id"))

    def update_one(self, query: dict, update: dict, upsert: bool = False) -> _UpdateResult:
        doc = self.find_one(query)
        matched = 1 if doc else 0
        if not doc:
            if not upsert:
                return _UpdateResult(0, 0)
            doc = dict(query)
        modified = _apply_update_dict(doc, update)
        if doc.get("id") and doc.get("user_id"):
            self.insert_one(doc)
        return _UpdateResult(matched, 1 if modified else 0)

    def delete_one(self, query: dict) -> None:
        with session_scope() as session:
            rows = _filtered_rows(session, ReviewScheduleRow, self._field_columns(), query)
            for row in rows:
                if _matches(self._to_doc(row), query):
                    session.delete(row)
                    return

    def count_documents(self, query: dict) -> int:
        return sum(1 for _ in self.find(query))

    @staticmethod
    def _to_doc(row: ReviewScheduleRow) -> dict[str, Any]:
        return {
            "id": row.id,
            "user_id": row.user_id,
            "item_type": row.item_type,
            "item_id": row.item_id,
            "skill": row.skill,
            "title": row.title,
            "source_session_id": row.source_session_id,
            "source_round": row.source_round,
            "originating_assisted": row.originating_assisted,
            "miss_reason": row.miss_reason,
            "interval_days": row.interval_days,
            "interval_index": row.interval_index,
            "due_at": row.due_at,
            "review_count": row.review_count,
            "last_reviewed_at": row.last_reviewed_at,
            "last_outcome": row.last_outcome,
            "last_review_assisted": row.last_review_assisted,
            "review_available": row.review_available,
            "unavailable_reason": row.unavailable_reason,
            "created_at": row.created_at,
            "updated_at": row.updated_at,
        }


class _MLPrimitivesAttemptCollection:
    """Immutable attempts, deletable by their owner through the route."""

    @staticmethod
    def _field_columns():
        columns = {c.name: getattr(MLPrimitivesAttemptRow, c.name)
                   for c in MLPrimitivesAttemptRow.__table__.columns}
        columns["round"] = columns.pop("round_number")
        return columns

    @staticmethod
    def _to_doc(row):
        return {
            "id": row.id, "user_id": row.user_id, "session_id": row.session_id,
            "round": row.round_number, "block_id": row.block_id,
            "problem_id": row.problem_id, "problem_version": row.problem_version,
            "language": row.language, "source": row.source, "status": row.status,
            "error_code": row.error_code,
            "created_at": row.created_at.replace(tzinfo=timezone.utc)
                if row.created_at.tzinfo is None else row.created_at,
        }

    def find(self, query=None):
        with session_scope() as session:
            docs = [self._to_doc(row) for row in _filtered_rows(
                session, MLPrimitivesAttemptRow, self._field_columns(), query)]
        return iter(doc for doc in docs if _matches(doc, query))

    def find_one(self, query, projection=None):
        doc = next(self.find(query), None)
        return _project(doc, projection) if doc is not None else None

    def insert_one(self, doc):
        with session_scope() as session:
            session.add(MLPrimitivesAttemptRow(
                id=doc["id"], user_id=doc["user_id"], session_id=doc["session_id"],
                round_number=doc["round"], block_id=doc["block_id"],
                problem_id=doc["problem_id"], problem_version=doc["problem_version"],
                language=doc["language"], source=doc["source"], status=doc["status"],
                error_code=doc["error_code"], created_at=_coerce_datetime(doc["created_at"]),
            ))
        return _InsertResult(doc["id"])

    def delete_one(self, query):
        with session_scope() as session:
            for row in _filtered_rows(session, MLPrimitivesAttemptRow,
                                      self._field_columns(), query):
                if _matches(self._to_doc(row), query):
                    session.delete(row)
                    return

    def count_documents(self, query):
        return sum(1 for _ in self.find(query))


class _NarrationJobCollection:
    """Document view over narration_jobs (deterministic id per round)."""

    @staticmethod
    def _field_columns() -> dict[str, Any]:
        return {
            "id": NarrationJobRow.id,
            "user_id": NarrationJobRow.user_id,
            "session_id": NarrationJobRow.session_id,
            "round": NarrationJobRow.round_number,
            "round_number": NarrationJobRow.round_number,
            "status": NarrationJobRow.status,
        }

    def find_one(self, query: dict, projection: dict | None = None) -> dict | None:
        with session_scope() as session:
            rows = _filtered_rows(session, NarrationJobRow, self._field_columns(), query)
            for row in rows:
                doc = self._to_doc(row)
                if _matches(doc, query):
                    return _project(doc, projection)
        return None

    def find(self, query: dict | None = None) -> Iterator[dict]:
        with session_scope() as session:
            docs = [
                self._to_doc(row)
                for row in _filtered_rows(session, NarrationJobRow, self._field_columns(), query)
            ]
        return iter([doc for doc in docs if not query or _matches(doc, query)])

    def insert_one(self, doc: dict) -> _InsertResult:
        data = _json_ready(doc)
        with session_scope() as session:
            session.merge(NarrationJobRow(
                id=data["id"],
                user_id=data.get("user_id"),
                session_id=data["session_id"],
                round_number=int(data.get("round", data.get("round_number"))),
                status=data.get("status") or "queued",
                attempts=int(data.get("attempts") or 0),
                feedback_json=data.get("feedback") or {},
                snapshot_digest=data.get("snapshot_digest"),
                skill=data.get("skill"),
                final_score=data.get("final_score"),
                artifact_json=data.get("artifact"),
                last_error=data.get("last_error"),
                claim_token=data.get("claim_token"),
                lease_until=_coerce_datetime(data.get("lease_until")),
                created_at=_coerce_datetime(data.get("created_at")) or _now(),
                updated_at=_coerce_datetime(data.get("updated_at")) or _now(),
            ))
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
            rows = _filtered_rows(session, NarrationJobRow, self._field_columns(), query)
            for row in rows:
                if _matches(self._to_doc(row), query):
                    session.delete(row)
                    return

    def count_documents(self, query: dict) -> int:
        return sum(1 for _ in self.find(query))

    @staticmethod
    def _to_doc(row: NarrationJobRow) -> dict[str, Any]:
        return {
            "id": row.id,
            "user_id": row.user_id,
            "session_id": row.session_id,
            "round": row.round_number,
            "status": row.status,
            "attempts": row.attempts,
            "feedback": row.feedback_json or {},
            "snapshot_digest": row.snapshot_digest,
            "skill": row.skill,
            "final_score": row.final_score,
            "artifact": row.artifact_json,
            "last_error": row.last_error,
            "claim_token": row.claim_token,
            "lease_until": row.lease_until,
            "created_at": row.created_at,
            "updated_at": row.updated_at,
        }


class SQLAlchemyDatabase:
    def __init__(self) -> None:
        self._collections = {
            "candidates": _CandidateCollection(),
            "users": _UserCollection(),
            "sessions": _SessionCollection(),
            "practice_presets": _PresetCollection(),
            "builder_drafts": _BuilderDraftCollection(),
            "answer_drafts": _AnswerDraftCollection(),
            "coding_submissions": _CodingSubmissionCollection(),
            "system_design_attempts": _SystemDesignAttemptCollection(),
            "ml_primitives_attempts": _MLPrimitivesAttemptCollection(),
            "target_contexts": _TargetContextCollection(),
            "retry_sets": _RetrySetCollection(),
            "bookmarks": _BookmarkCollection(),
            "assistance_events": _AssistanceEventCollection(),
            "teaching_exposures": _TeachingExposureCollection(),
            "review_schedules": _ReviewScheduleCollection(),
            "narration_jobs": _NarrationJobCollection(),
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
