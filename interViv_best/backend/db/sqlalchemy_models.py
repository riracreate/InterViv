from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import (
    DateTime,
    Float,
    ForeignKey,
    Integer,
    JSON,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class UserRow(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True, nullable=False)
    name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    target_company_id: Mapped[int | None] = mapped_column(ForeignKey("companies.id"), nullable=True)
    target_role_id: Mapped[int | None] = mapped_column(ForeignKey("roles.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    last_active_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)


class CompanyRow(Base):
    __tablename__ = "companies"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    logo_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    public_info: Mapped[dict | None] = mapped_column(JSON, nullable=True)


class RoleRow(Base):
    __tablename__ = "roles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    level: Mapped[str | None] = mapped_column(String(80), nullable=True)

    __table_args__ = (UniqueConstraint("company_id", "title", "level", name="uq_roles_company_title_level"),)


class SkillRow(Base):
    __tablename__ = "skills"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    canonical_name: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    sub_domain: Mapped[str | None] = mapped_column(String(255), nullable=True)
    parent_skill_id: Mapped[int | None] = mapped_column(ForeignKey("skills.id"), nullable=True)


class CompanyRoleRequirementRow(Base):
    __tablename__ = "company_role_requirements"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    role_id: Mapped[int] = mapped_column(ForeignKey("roles.id"), nullable=False, index=True)
    skill_id: Mapped[int] = mapped_column(ForeignKey("skills.id"), nullable=False, index=True)
    required_level: Mapped[float] = mapped_column(Float, nullable=False)
    importance_weight: Mapped[float] = mapped_column(Float, nullable=False)

    __table_args__ = (UniqueConstraint("role_id", "skill_id", name="uq_company_role_requirements_role_skill"),)


class StudentSkillGraphRow(Base):
    __tablename__ = "student_skill_graph"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    skill_id: Mapped[int] = mapped_column(ForeignKey("skills.id"), nullable=False, index=True)
    current_score: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    current_elo: Mapped[float] = mapped_column(Float, default=1200.0, nullable=False)
    attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    last_practiced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (UniqueConstraint("user_id", "skill_id", name="uq_student_skill_graph_user_skill"),)


class StudentConceptMasteryRow(Base):
    __tablename__ = "student_concept_mastery"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    skill_id: Mapped[int] = mapped_column(ForeignKey("skills.id"), nullable=False, index=True)
    concept_name: Mapped[str] = mapped_column(String(255), nullable=False)
    attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    demonstrated: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (UniqueConstraint("user_id", "skill_id", "concept_name", name="uq_concept_mastery_user_skill_concept"),)


class CandidateRow(Base):
    __tablename__ = "candidates"

    candidate_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True, index=True)
    resume_skills: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    sub_domain_profile: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    elo_ratings: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    session_history: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)


class SessionRow(Base):
    __tablename__ = "sessions"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True, index=True)
    candidate_id: Mapped[str | None] = mapped_column(ForeignKey("candidates.candidate_id"), nullable=True, index=True)
    target_company_id: Mapped[int | None] = mapped_column(ForeignKey("companies.id"), nullable=True)
    target_role_id: Mapped[int | None] = mapped_column(ForeignKey("roles.id"), nullable=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    overall_readiness_score: Mapped[float | None] = mapped_column(Float, nullable=True)

    skill: Mapped[str | None] = mapped_column(String(255), nullable=True)
    sub_domain: Mapped[str | None] = mapped_column(String(255), nullable=True)
    status: Mapped[str] = mapped_column(String(50), default="active", nullable=False)
    current_difficulty: Mapped[str | None] = mapped_column(String(50), nullable=True)
    current_skill: Mapped[str | None] = mapped_column(String(255), nullable=True)
    last_round: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    skills_json: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    rounds_per_skill: Mapped[int] = mapped_column(Integer, default=3, nullable=False)
    total_rounds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    template_id: Mapped[str | None] = mapped_column(ForeignKey("interview_templates.id"), nullable=True)

    rounds: Mapped[list["RoundRow"]] = relationship(
        back_populates="session",
        cascade="all, delete-orphan",
        order_by="RoundRow.round_number",
    )


class RoundRow(Base):
    __tablename__ = "rounds"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id: Mapped[str] = mapped_column(ForeignKey("sessions.id"), nullable=False, index=True)
    round_number: Mapped[int] = mapped_column(Integer, nullable=False)
    skill_id: Mapped[int | None] = mapped_column(ForeignKey("skills.id"), nullable=True)
    question_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    answer_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    scoring_breakdown_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    confidence_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    guard_applied: Mapped[str | None] = mapped_column(String(255), nullable=True)
    feedback_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    engagement_label: Mapped[str | None] = mapped_column(String(80), nullable=True)
    engagement_delta: Mapped[int | None] = mapped_column(Integer, nullable=True)

    skill_text: Mapped[str | None] = mapped_column(String(255), nullable=True)
    round_type: Mapped[str] = mapped_column(String(50), nullable=False, default="technical_short_answer")
    artifact_json: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    config_json: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    question: Mapped[str | None] = mapped_column(Text, nullable=True)
    difficulty: Mapped[str | None] = mapped_column(String(50), nullable=True)
    difficulty_change: Mapped[str | None] = mapped_column(String(50), nullable=True)
    nlp_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    svm_label: Mapped[str | None] = mapped_column(String(80), nullable=True)
    kg_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    kg_label: Mapped[str | None] = mapped_column(String(255), nullable=True)
    covered_concepts: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    missing_concepts: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    ner_entities: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    final_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    elo_before: Mapped[float | None] = mapped_column(Float, nullable=True)
    elo_after: Mapped[float | None] = mapped_column(Float, nullable=True)
    question_context: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)

    session: Mapped[SessionRow] = relationship(back_populates="rounds")

    __table_args__ = (UniqueConstraint("session_id", "round_number", name="uq_rounds_session_round"),)


class InterviewTemplateRow(Base):
    __tablename__ = "interview_templates"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)

    rounds: Mapped[list["TemplateRoundRow"]] = relationship(
        back_populates="template",
        cascade="all, delete-orphan",
        order_by="TemplateRoundRow.position",
    )


class TemplateRoundRow(Base):
    __tablename__ = "template_rounds"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    template_id: Mapped[str] = mapped_column(ForeignKey("interview_templates.id"), nullable=False, index=True)
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    round_type: Mapped[str] = mapped_column(String(50), nullable=False, default="technical_short_answer")
    config_json: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)

    template: Mapped[InterviewTemplateRow] = relationship(back_populates="rounds")

    __table_args__ = (UniqueConstraint("template_id", "position", name="uq_template_rounds_template_position"),)


class QuestionRubricRow(Base):
    __tablename__ = "question_rubrics"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    question_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    required_concept: Mapped[str] = mapped_column(String(255), nullable=False)
    importance_weight: Mapped[float] = mapped_column(Float, nullable=False)
